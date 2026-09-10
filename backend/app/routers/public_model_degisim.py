"""Public telefon modeli değişikliği — AUTH YOK (token ile erişim).

- GET  /model-degisim/{token}              → sayfa (HTML)
- GET  /api/public/model-degisim/{token}   → seçenekler (JSON, hassas veri yok)
- POST /api/public/model-degisim/{token}   → değişikliği uygula

Bu bağlantı, stok yokluğu nedeniyle kalıptan çıkarılan bir kalem için müşteriye
WhatsApp'tan gönderilir (bkz. services/model_degisim.py).

⚠ EN KRİTİK KISIM — KALIPTAN ÇEKME
Müşteri değişikliği yaptığında kalem O AN başka bir kalıba planlanmış olabilir:
mesaj gönderildikten sonra 12 saat geçiyor, bu sürede planlayıcı kalemi yeni bir
kalıba koymuş olabilir. Kalem çekilmezse ESKİ modelin kılıfı basılır ve doğrudan
çöpe gider. Bu yüzden değişiklik uygulanırken kalem bulunduğu HER kalıptan
çıkarılır, kalıba uyarı düşülür ve hazırlanmış PDF geçersiz kılınır.

Güvenlik: token tahmin edilemez (secrets.token_urlsafe), 12 saat geçerli, tek
kullanımlık. Sayfada e-posta/telefon/adres YOK.
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    LineItem, ModelDegisimTalebi, Mold, MoldItem, MoldStatusHistory,
    Notification, Order, OrderStatusHistory, PhoneModel,
)
from app.routers.public_tracker import rate_limit
from app.services import model_degisim as md

router = APIRouter(tags=["public-model-degisim"])

_HTML_PATH = Path(__file__).parent.parent / "public" / "model-degisim.html"
try:
    _SAYFA = _HTML_PATH.read_text(encoding="utf-8")
except OSError:
    _SAYFA = "<h1>Sayfa yüklenemedi</h1>"

UYARI_METNI = "Telefon modeli değişikliği nedeniyle kalıptan ürün çıkarıldı."


def _talep(db: Session, token: str) -> ModelDegisimTalebi:
    t = db.scalar(
        select(ModelDegisimTalebi).where(ModelDegisimTalebi.token == token)
        .execution_options(include_deleted=True)
    )
    if not t:
        raise HTTPException(status_code=404, detail="Bağlantı bulunamadı")
    return t


def _sureli_mi(t: ModelDegisimTalebi) -> bool:
    return bool(t.expires_at and t.expires_at > datetime.now(UTC))


def _modeller(db: Session, tenant_id) -> list[dict]:
    """Müşteriye sunulacak telefon modelleri: [{deger, etiket}].

    ⚠ Yalnız ölçüsü ÇÖZÜLEBİLEN modeller listelenir. Ölçüsü olmayan bir adı
    sunarsak müşteri onu seçer, sipariş "Model tanınmadı" diye kalıp dışında
    kalır ve bu ancak kalıp üretilirken fark edilir — yani sorunu çözmek yerine
    daha kötü bir yere taşımış oluruz.

    Aynı liste bayi portalinde de kuruluyor (routers/bayii_portal.py:modeller);
    kaynak ve kurallar bilerek aynı: PhoneModel (tenant ölçü ezmesi) + baseline
    katalog, Apple takma adları elenmiş.
    """
    from app.services import phone_models as pm

    def _coz(*adaylar: str) -> str | None:
        for a in adaylar:
            a = (a or "").strip()
            if a and pm.has_spec(db, tenant_id, a):
                return a
        return None

    secenekler: dict[str, str] = {}
    for m in db.scalars(select(PhoneModel).where(
            PhoneModel.tenant_id == tenant_id,
            PhoneModel.is_active.is_(True))).all():
        etiket = (m.display_name or m.spec_key or "").strip()
        deger = _coz(m.display_name, m.spec_key)
        if deger and etiket:
            secenekler.setdefault(deger, etiket)

    for k in pm.baseline_keys():
        if pm.is_apple_alias_key(k):
            continue
        etiket = pm.baseline_display_name(k)
        deger = _coz(etiket, k)
        if deger and deger not in secenekler:
            secenekler[deger] = etiket

    return [{"deger": v, "etiket": e}
            for v, e in sorted(secenekler.items(), key=lambda kv: kv[1].lower())]


@router.get("/model-degisim/{token}", response_class=HTMLResponse)
def sayfa(token: str):
    return HTMLResponse(_SAYFA)


@router.get("/api/public/model-degisim/{token}", response_model=dict)
def veri(token: str, db: Session = Depends(get_db), _rl: None = Depends(rate_limit)):
    t = _talep(db, token)
    if t.durum == "uygulandi":
        return {"durum": "uygulandi", "secilen_model": t.secilen_model,
                "secilen_varyasyon": t.secilen_varyasyon}
    if not _sureli_mi(t):
        return {"durum": "suresi_doldu"}

    return {
        "durum": "bekliyor",
        "urun": t.urun_adi,
        "mevcut_model": t.mevcut_model,
        "modeller": _modeller(db, t.tenant_id),
        "varyasyonlar": md.secilebilir_varyasyonlar(t.kalip_turu),
        "son_gecerlilik": t.expires_at.isoformat() if t.expires_at else None,
    }


class SecimIstegi(BaseModel):
    model: str
    varyasyon: str | None = None


def _kaliptan_cek(db: Session, li: LineItem) -> int:
    """Kalemi bulunduğu HER kalıptan çıkarır; çıkarılan slot sayısını döner.

    Panelin kendi çıkarma ucuyla AYNI yardımcıları kullanır (tek uygulama):
    slot plana geri döner, MoldItem silinir, kalıbın hazır PDF'i geçersiz olur.
    Ek olarak kalıba baskıcının göreceği bir uyarı düşülür.
    """
    from app.routers.molds import _pdf_gecersiz, _replan_mold_item

    slotlar = db.scalars(select(MoldItem).where(MoldItem.line_item_id == li.id)).all()
    cekilen = 0
    for it in slotlar:
        mo = db.get(Mold, it.mold_id)
        if mo is None or mo.status == "iptal":
            continue
        _replan_mold_item(db, li.tenant_id if hasattr(li, "tenant_id") else mo.tenant_id, it)

        uyarilar = list(mo.uyarilar or [])
        uyarilar.append({
            "at": datetime.now(UTC).isoformat(),
            "mesaj": UYARI_METNI,
            "slot": it.slot_index,
            "model": it.model,
            "siparis": it.order_number,
        })
        mo.uyarilar = uyarilar
        mo.kilif_sayisi = max(0, (mo.kilif_sayisi or 0) - 1)

        db.add(MoldStatusHistory(
            tenant_id=mo.tenant_id, mold_id=mo.id,
            action="musteri_model_degisikligi",
            note=f"{UYARI_METNI} (slot #{it.slot_index} · {it.model or ''})",
            created_by="Müşteri",
        ))
        db.delete(it)
        _pdf_gecersiz(mo.id)
        cekilen += 1
    if cekilen:
        li.is_kaliba_eklendi = False
    return cekilen


@router.post("/api/public/model-degisim/{token}", response_model=dict)
def uygula(token: str, istek: SecimIstegi,
           db: Session = Depends(get_db), _rl: None = Depends(rate_limit)):
    t = _talep(db, token)
    if t.durum == "uygulandi":
        raise HTTPException(status_code=409, detail="Bu bağlantı zaten kullanıldı.")
    if not _sureli_mi(t):
        raise HTTPException(status_code=410, detail="Bağlantının süresi doldu.")

    if t.line_item_id is None:
        raise HTTPException(status_code=409,
                            detail="Sipariş kalemi bulunamadı. Lütfen bizimle iletişime geçin.")
    li = db.scalar(select(LineItem).where(LineItem.id == t.line_item_id))
    if li is None:
        raise HTTPException(status_code=409,
                            detail="Sipariş kalemi bulunamadı. Lütfen bizimle iletişime geçin.")

    model = (istek.model or "").strip()
    if model not in {m["deger"] for m in _modeller(db, t.tenant_id)}:
        raise HTTPException(status_code=400, detail="Geçersiz telefon modeli.")

    varyasyon = (istek.varyasyon or "").strip() or None
    izinli = md.secilebilir_varyasyonlar(t.kalip_turu)
    if varyasyon and varyasyon not in izinli:
        raise HTTPException(status_code=400, detail="Bu ürün için geçersiz seçenek.")

    # ⚠ ÖNCE kalıptan çek: aşağıdaki alan değişiklikleri sırasında hata çıksa
    # bile yanlış modelli kılıfın basılması ihtimali kalmasın.
    cekilen = _kaliptan_cek(db, li)

    li.device_model_override = model[:100]
    if varyasyon:
        li.kilif_varyasyon = varyasyon[:20]

    # "Stok bekliyor" bayrağı kalkmalı: müşteri beklemeyi seçmedi, değiştirdi.
    # Kalırsa bayi portalinde ve panelde hâlâ "Stokta mevcut değil" görünürdü.
    ham = dict(li.raw or {})
    if ham.pop("stok_bekliyor", None) is not None:
        li.raw = ham

    t.durum = "uygulandi"
    t.secilen_model = model[:100]
    t.secilen_varyasyon = varyasyon
    t.uygulandi_at = datetime.now(UTC)

    order = db.scalar(select(Order).where(Order.id == t.order_id)
                      .execution_options(include_deleted=True))
    _no = (order.name or f"#{order.order_number or ''}") if order else ""
    _ek = f" · {varyasyon}" if varyasyon else ""
    _not = (f"Müşteri telefon modelini değiştirdi: "
            f"{t.mevcut_model or '—'} → {model}{_ek}"
            + (f" · {cekilen} kalıp slotundan çıkarıldı" if cekilen else ""))

    db.add(OrderStatusHistory(
        tenant_id=t.tenant_id, order_id=t.order_id,
        action="musteri_model_degisikligi", note=_not, created_by="Müşteri",
    ))
    db.add(Notification(
        tenant_id=t.tenant_id, store_id=(order.store_id if order else None),
        kind="warn" if cekilen else "info",
        title=f"{_no} · müşteri model değiştirdi",
        body=_not,
        link=f"/orders/{t.order_id}",
    ))
    db.commit()

    # Panel/uygulama bildirimi — kalıptan çekildiyse acil, baskıcı görmeli.
    try:
        from app.services import push
        push.send_to_tenant(
            db, t.tenant_id,
            f"{_no} · müşteri model değiştirdi", _not,
            url=f"/orders/{t.order_id}", tag=f"model-degisim-{t.order_id}",
        )
    except Exception:  # noqa: BLE001 — bildirim akışı bozmasın
        pass

    return {"ok": True, "model": model, "varyasyon": varyasyon}
