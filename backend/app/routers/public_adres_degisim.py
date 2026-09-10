"""Public teslimat adresi değişikliği — AUTH YOK (token ile erişim).

- GET  /adres-degisim/{token}              → sayfa (HTML)
- GET  /api/public/adres-degisim/{token}   → mevcut adres + durum (JSON)
- POST /api/public/adres-degisim/{token}   → yeni adresi uygula

Erişim modeli ve neden böyle olduğu: services/adres_degisim.py başlığı.

⚠ SIRA ÖNEMLİ: adres ÖNCE Shopify'da güncellenir, sonra yerelde. Tersi olursa
bir sonraki senkron yereli Shopify'daki ESKİ adresle ezer ve kargo yanlış
adrese çıkar — bu akışın en tehlikeli hatası budur.
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
from app.models import AdresDegisimTalebi, Notification, Order, OrderStatusHistory, Store
from app.routers.public_tracker import rate_limit
from app.services import adres_degisim as ad

router = APIRouter(tags=["public-adres-degisim"])

_HTML_PATH = Path(__file__).parent.parent / "public" / "adres-degisim.html"
try:
    _SAYFA = _HTML_PATH.read_text(encoding="utf-8")
except OSError:
    _SAYFA = "<h1>Sayfa yüklenemedi</h1>"


def _talep(db: Session, token: str, *, kilitle: bool = False) -> AdresDegisimTalebi:
    q = select(AdresDegisimTalebi).where(AdresDegisimTalebi.token == token)
    if kilitle:
        # Aynı bağlantıya iki sekmeden aynı anda basılırsa yalnız biri uygulansın.
        q = q.with_for_update()
    t = db.scalar(q.execution_options(include_deleted=True))
    if not t:
        raise HTTPException(status_code=404, detail="Bağlantı bulunamadı")
    return t


def _gecerli_mi(t: AdresDegisimTalebi) -> bool:
    return bool(t.expires_at and t.expires_at > datetime.now(UTC))


def _siparis(db: Session, t: AdresDegisimTalebi, *, kilitle: bool = False) -> Order | None:
    """Siparişi getirir. `kilitle=True` SİPARİŞ satırını kilitler.

    ⚠ Talep satırını kilitlemek yetmez: aynı siparişe ait İKİ FARKLI bağlantı
    (operatör mesajı yeniledi, müşteride iki bağlantı var) ayrı satırlardır ve
    birbirini beklemez — ikisi de "daha önce değiştirilmemiş" görüp ikisi de
    uygulanabilirdi. Siparişte buluşuyorlar, kilit oraya konur.
    """
    q = select(Order).where(Order.id == t.order_id)
    if kilitle:
        q = q.with_for_update()
    return db.scalar(q.execution_options(include_deleted=True))


@router.get("/adres-degisim/{token}", response_class=HTMLResponse)
def sayfa(token: str):
    return HTMLResponse(_SAYFA)


@router.get("/api/public/adres-degisim/{token}", response_model=dict)
def veri(token: str, db: Session = Depends(get_db), _rl: None = Depends(rate_limit)):
    t = _talep(db, token)
    if t.durum == "uygulandi":
        return {"durum": "uygulandi"}
    if not _gecerli_mi(t):
        return {"durum": "suresi_doldu"}
    # Aynı sipariş için BAŞKA bir bağlantı zaten uygulanmışsa bu bekleyen
    # bağlantı da ölüdür — adres yalnız bir kez değiştirilebilir.
    if ad.zaten_degistirildi(db, t.order_id):
        return {"durum": "kapali", "sebep": ad.BIR_KEZ_MESAJI}

    order = _siparis(db, t)
    izin, sebep = ad.degistirilebilir_mi(order)
    if not izin:
        return {"durum": "kapali", "sebep": sebep}

    a = (order.raw or {}).get("shipping_address") or {}
    return {
        "durum": "bekliyor",
        "siparis_no": order.name or (f"#{order.order_number}" if order.order_number else None),
        "son_gecerlilik": t.expires_at.isoformat() if t.expires_at else None,
        # Form ÖN DOLU gelir: müşteri çoğu zaman tek bir alanı düzeltiyor
        # (apartman no, ilçe). Sıfırdan yazdırmak hata kaynağı olurdu.
        "adres": {
            "eposta": order.customer_email or "",
            "ad": a.get("first_name") or "",
            "soyad": a.get("last_name") or "",
            "adres": a.get("address1") or "",
            "adres2": a.get("address2") or "",
            "il": a.get("province") or "",
            "ilce": a.get("city") or "",
            "telefon": a.get("phone") or "",
        },
    }


class AdresIstegi(BaseModel):
    eposta: str | None = None
    pazarlama: bool = False
    ad: str
    soyad: str
    adres: str
    adres2: str | None = None
    il: str
    ilce: str
    telefon: str


def _kirp(s: str | None, n: int) -> str:
    return (s or "").strip()[:n]


@router.post("/api/public/adres-degisim/{token}", response_model=dict)
def uygula(token: str, istek: AdresIstegi,
           db: Session = Depends(get_db), _rl: None = Depends(rate_limit)):
    t = _talep(db, token, kilitle=True)
    if t.durum == "uygulandi":
        raise HTTPException(status_code=409, detail="Bu bağlantı zaten kullanıldı.")
    if not _gecerli_mi(t):
        raise HTTPException(status_code=410, detail="Bağlantının süresi doldu.")

    order = _siparis(db, t, kilitle=True)
    # ⚠ Sipariş satırı KİLİTLENDİKTEN sonra bakılır (bkz. _siparis).
    if ad.zaten_degistirildi(db, t.order_id):
        raise HTTPException(status_code=409, detail=ad.BIR_KEZ_MESAJI)
    # ⚠ Bağlantı üretildikten sonra kargo başlamış olabilir — burada TEKRAR bak.
    izin, sebep = ad.degistirilebilir_mi(order)
    if not izin:
        raise HTTPException(status_code=409, detail=sebep)

    form = {
        "ad": _kirp(istek.ad, 60),
        "soyad": _kirp(istek.soyad, 60),
        "adres": _kirp(istek.adres, 300),
        "adres2": _kirp(istek.adres2, 120),
        "il": _kirp(istek.il, 60),
        "ilce": _kirp(istek.ilce, 60),
    }
    for alan, etiket in (("ad", "İsim"), ("soyad", "Soyisim"),
                         ("adres", "Adres"), ("il", "İl"), ("ilce", "İlçe")):
        if not form[alan]:
            raise HTTPException(status_code=400, detail=f"{etiket} zorunlu.")

    tel = ad.telefon_gecerli(istek.telefon)
    if not tel:
        raise HTTPException(status_code=400,
                            detail="Telefon numarası geçersiz. 5XX XXX XX XX biçiminde girin.")
    form["telefon"] = tel

    eposta = _kirp(istek.eposta, 200)
    if eposta and not ad.eposta_gecerli(eposta):
        raise HTTPException(status_code=400, detail="E-posta adresi geçersiz.")

    eski = dict((order.raw or {}).get("shipping_address") or {})
    yeni = ad.adres_kur(form, eski)

    # ── ÖNCE Shopify ──
    store = db.scalar(select(Store).where(Store.id == order.store_id)) if order.store_id else None
    if store is not None and (store.platform or "").lower() == "shopify":
        harici = (order.raw or {}).get("id")
        if not harici:
            raise HTTPException(status_code=409,
                                detail="Sipariş kaydı eksik. Lütfen bizimle iletişime geçin.")
        from app.adapters.shopify import ShopifyAdapter

        adapter = ShopifyAdapter(store)
        ok, mesaj_ = adapter.update_shipping_address(str(harici), yeni)
        if not ok:
            # Yerelde DEĞİŞTİRMİYORUZ: yerel ile Shopify ayrışırsa senkron
            # yereli ezer ve kargo eski adrese çıkar — sessiz ve tehlikeli.
            raise HTTPException(
                status_code=502,
                detail="Adres şu an güncellenemedi. Lütfen birkaç dakika sonra tekrar "
                       "deneyin ya da bizimle iletişime geçin.")
        # Shopify'ın döndürdüğü güncel hâli al (normalize edilmiş alanlar).
        taze = adapter.get_order_raw(str(harici))
        if taze:
            order.raw = taze
        else:
            _r = dict(order.raw or {})
            _r["shipping_address"] = yeni
            order.raw = _r
    else:
        _r = dict(order.raw or {})
        _r["shipping_address"] = yeni
        order.raw = _r

    # ── Yerel yan etkiler ──
    if eposta:
        order.customer_email = eposta
    order.customer_name = f"{form['ad']} {form['soyad']}".strip() or order.customer_name

    # Elle girilmiş il/ilçe düzeltmeleri artık ESKİ adrese ait — temizlenmezse
    # kargo etiketi yeni adresle eski ilçeyi birleştirir.
    _r2 = dict(order.raw or {})
    for k in ("il_override", "ilce_override"):
        _r2.pop(k, None)
    order.raw = _r2

    t.durum = "uygulandi"
    t.yeni_adres = yeni
    t.pazarlama_izni = bool(istek.pazarlama)
    t.uygulandi_at = datetime.now(UTC)

    _no = order.name or (f"#{order.order_number}" if order.order_number else "")
    # Başlık ("🏠 Müşteri teslimat adresini değiştirdi") panelde zaten
    # yazıyor; not yalnız ESKİ/YENİ karşılaştırmasını taşır.
    _not = f"ESKİ: {ad.ozet(eski)}\nYENİ: {ad.ozet(yeni)}"
    db.add(OrderStatusHistory(
        tenant_id=t.tenant_id, order_id=t.order_id,
        action="musteri_adres_degisikligi", note=_not, created_by="Müşteri",
    ))
    db.add(Notification(
        tenant_id=t.tenant_id, store_id=order.store_id,
        kind="warn",
        title=f"{_no} · müşteri ADRES değiştirdi",
        body=ad.ozet(yeni),
        link=f"/orders/{t.order_id}",
    ))
    db.commit()

    try:
        from app.services import push
        push.send_to_tenant(
            db, t.tenant_id, f"{_no} · müşteri ADRES değiştirdi", ad.ozet(yeni),
            url=f"/orders/{t.order_id}", tag=f"adres-{t.order_id}",
        )
    except Exception:  # noqa: BLE001 — bildirim akışı bozmasın
        pass

    return {"ok": True}
