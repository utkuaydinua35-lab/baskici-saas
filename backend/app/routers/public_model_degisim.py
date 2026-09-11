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
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    CatalogImage, CatalogProduct, LineItem, ModelDegisimTalebi, Mold, MoldItem, MoldStatusHistory,
    Notification, Order, OrderStatusHistory, PhoneModel, Store,
)
from app.routers.public_tracker import rate_limit
from app.services import model_degisim as md
from app.services import urun_katalog

router = APIRouter(tags=["public-model-degisim"])

_HTML_PATH = Path(__file__).parent.parent / "public" / "model-degisim.html"
try:
    _SAYFA = _HTML_PATH.read_text(encoding="utf-8")
except OSError:
    _SAYFA = "<h1>Sayfa yüklenemedi</h1>"

UYARI_METNI = "Telefon modeli değişikliği nedeniyle kalıptan ürün çıkarıldı."


def _talep(db: Session, token: str, *, kilitle: bool = False) -> ModelDegisimTalebi:
    """Token'dan talep. `kilitle=True` satırı kilitler (bkz. uygula()).

    ⚠ KİLİT NEDEN GEREKLİ: müşteri bağlantıyı iki sekmede açıp aynı anda
    onaylarsa iki istek de "bekliyor" görüp İKİSİ de uygulanıyordu — kalem iki
    kez işlenip çift bildirim ve çift geçmiş kaydı düşüyordu. Testte
    doğrulandı: iki eşzamanlı istek de 200 dönüyordu. Satır kilidiyle ikinci
    istek birincinin commit'ini bekler, sonra "uygulandi" görüp 409 alır.
    """
    q = select(ModelDegisimTalebi).where(ModelDegisimTalebi.token == token)
    if kilitle:
        q = q.with_for_update()
    t = db.scalar(q.execution_options(include_deleted=True))
    if not t:
        raise HTTPException(status_code=404, detail="Bağlantı bulunamadı")
    return t


def _sureli_mi(t: ModelDegisimTalebi) -> bool:
    return bool(t.expires_at and t.expires_at > datetime.now(UTC))


# Anahtar önekinden marka etiketi. Bilinmeyen önek başlık biçimine çevrilir.
_MARKA_ETIKET = {
    "IPHONE": "iPhone", "SAMSUNG": "Samsung", "REDMI": "Redmi", "XIAOMI": "Xiaomi",
    "OPPO": "Oppo", "REALME": "Realme", "TECNO": "Tecno", "POCO": "Poco",
    "HUAWEI": "Huawei", "VIVO": "Vivo", "OMIX": "Omix",
}
# Marka sırası: müşterinin en çok aradığı önde olsun, gerisi alfabetik eklenir.
_MARKA_SIRA = ["iPhone", "Samsung", "Xiaomi", "Redmi", "Poco", "Oppo", "Realme",
               "Huawei", "Vivo", "Tecno", "Omix"]


def _marka_of(key: str, etiket: str) -> str:
    onek = (key or "").split("-")[0].upper()
    if onek in _MARKA_ETIKET:
        return _MARKA_ETIKET[onek]
    # Çıplak Samsung anahtarları (S23, S10E…) marka öneki taşımıyor.
    if onek[:1] == "S" and onek[1:2].isdigit():
        return "Samsung"
    ilk = (etiket or "").split(" ")[0]
    return ilk if ilk else "Diğer"


def _markalara_ayir(secenekler: list[dict]) -> list[dict]:
    """[{deger, etiket, stokta, _key}] → [{marka, modeller:[…]}].

    Müşteri önce markayı, sonra modeli seçiyor: 300 satırlık tek liste
    telefonda kullanılamıyordu.
    """
    gruplar: dict[str, list[dict]] = {}
    for m in secenekler:
        marka = m.pop("_marka", None) or "Diğer"
        gruplar.setdefault(marka, []).append(m)

    def _sira(ad: str) -> tuple:
        return (_MARKA_SIRA.index(ad), "") if ad in _MARKA_SIRA else (len(_MARKA_SIRA), ad.lower())

    return [{"marka": ad, "modeller": gruplar[ad]} for ad in sorted(gruplar, key=_sira)]


def _tum_modeller(db: Session, tenant_id) -> list[dict]:
    """Kalıp motorunun tanıdığı TÜM modeller, markasıyla birlikte."""
    from app.services import phone_models as pm

    _baseline = set(pm.baseline_keys())

    def _coz(*adaylar: str) -> str | None:
        for a in adaylar:
            a = (a or "").strip()
            if a and pm.has_spec(db, tenant_id, a):
                return a
        return None

    secenekler: dict[str, dict] = {}
    for m in db.scalars(select(PhoneModel).where(
            PhoneModel.tenant_id == tenant_id,
            PhoneModel.is_active.is_(True))).all():
        etiket = (m.display_name or m.spec_key or "").strip()
        deger = _coz(m.display_name, m.spec_key)
        if deger and etiket:
            secenekler.setdefault(deger, {
                "deger": deger, "etiket": etiket, "stokta": True,
                "_marka": (m.brand or "").strip() or _marka_of(m.spec_key or "", etiket)})

    for k in pm.baseline_keys():
        if pm.is_apple_alias_key(k):
            continue
        # Çıplak Samsung ikizi (S23 ↔ SAMSUNG-S23): kanonik olanı bırak.
        if f"SAMSUNG-{k}" in _baseline:
            continue
        etiket = pm.baseline_display_name(k)
        deger = _coz(etiket, k)
        if deger and deger not in secenekler:
            secenekler[deger] = {"deger": deger, "etiket": etiket, "stokta": True,
                                 "_marka": _marka_of(k, etiket)}

    return sorted(secenekler.values(), key=lambda m: m["etiket"].lower())


def _model_secenekleri(db: Session, t: ModelDegisimTalebi) -> tuple[list[dict], bool]:
    """(marka grupları, ozel_seri_mi).

    ⚠ PARLAK (BERNZ Special) yalnız birkaç modelde stok tutuyor. Orada TÜM
    kataloğu sunmak, karşılanamayacak bir siparişe dönüşür — bu yüzden liste
    ozel_seri_stok tablosuyla sınırlanır. `stokta=False` modeller GÖRÜNÜR ama
    seçilemez: müşteri "bu model var ama şu an yok" ile "hiç yok" arasındaki
    farkı görsün.
    """
    if t.kalip_turu == md.PARLAK:
        from app.services import ozel_seri

        secenekler = []
        for r in ozel_seri.secenekler(db, t.tenant_id):
            r = dict(r)
            r["_marka"] = _marka_of("", r["etiket"])
            secenekler.append(r)
        return _markalara_ayir(secenekler), True
    return _markalara_ayir(_tum_modeller(db, t.tenant_id)), False


def _siparis_magazasi(db: Session, t: ModelDegisimTalebi):
    """Talebin siparişinin mağazası — katalog kaynağını (Shopify/vitrin) belirler."""
    order = db.scalar(select(Order).where(Order.id == t.order_id)
                      .execution_options(include_deleted=True))
    if order is None or order.store_id is None:
        return None
    return db.scalar(select(Store).where(Store.id == order.store_id))


def _kalem_durumu(li: LineItem) -> str:
    """Müşteriye gösterilecek kalem durumu — panel terimleri değil."""
    if li.is_hazir:
        return "Hazır"
    if (li.raw or {}).get("stok_bekliyor"):
        return "Stok bekleniyor"
    if li.is_kaliba_eklendi:
        return "Üretimde"
    return "Hazırlanıyor"


def _siparis_ozeti(db: Session, t: ModelDegisimTalebi) -> dict:
    """Sayfada gösterilecek sipariş bilgisi + diğer kalemlerin durumu.

    ⚠ Bu sayfa müşterinin KENDİ adres/telefon bilgisini gösteriyor. Onay
    sayfasında (public_approval) bilinçli olarak gösterilmiyordu; burada
    işletme açıkça istedi: müşteri "siparişim doğru bilgilerle duruyor mu"
    sorusunu sayfadan cevaplayabilsin. Bağlantı tahmin edilemez ve 12 saat
    sonra kapanıyor.
    """
    order = db.scalar(select(Order).where(Order.id == t.order_id)
                      .execution_options(include_deleted=True))
    if order is None:
        return {}

    ham = order.raw or {}
    adres = ham.get("shipping_address") or {}
    _ad = " ".join(x for x in [adres.get("first_name"), adres.get("last_name")] if x).strip()
    _satir = " ".join(x for x in [adres.get("address1"), adres.get("address2")] if x).strip()

    from app.services import mold_planner as _mp

    _kalem_listesi = list(db.scalars(
        select(LineItem).where(LineItem.order_id == order.id)).all())

    # Görsel kaynağı: kalemin kendi `product_image_url`'i çoğu kalemde BOŞ
    # (üretimde 609/8575). Aynı başlıklı katalog ürününün görseli çok daha
    # kapsayıcı (5558/8575), o yüzden ikisi birlikte kullanılıyor.
    _basliklar = {(li.title or "").strip() for li in _kalem_listesi if li.title}
    _katalog_gorsel: dict[str, str] = {}
    if _basliklar:
        for _p, _yol in db.execute(
            select(CatalogProduct.title, CatalogImage.file_path)
            .join(CatalogImage, CatalogImage.product_id == CatalogProduct.id)
            .where(CatalogProduct.tenant_id == t.tenant_id,
                   CatalogProduct.title.in_(_basliklar))
            .order_by(CatalogImage.position)
        ).all():
            _katalog_gorsel.setdefault((_p or "").strip(), f"/storage/{_yol}")

    kalemler = []
    for li in _kalem_listesi:
        # Model TEK KAYNAKTAN: elle düzeltilmişse o, yoksa siparişten çözülen.
        # Yalnız device_model_override'a bakmak, düzeltilmemiş kalemlerde
        # modeli boş gösteriyordu.
        _model = (li.device_model_override or "").strip() or _mp.extract_phone_model(li) or None
        kalemler.append({
            "urun": (li.title or "")[:160],
            "model": _model,
            "gorsel": (li.product_image_url
                       or _katalog_gorsel.get((li.title or "").strip()) or None),
            "durum": _kalem_durumu(li),
            "bu_kalem": str(li.id) == str(t.line_item_id),
        })

    # Sayfanın alt kısmındaki "adresimi güncelle" bağlantısı yalnız gerçekten
    # değiştirilebiliyorsa gösterilir; aksi halde müşteri tıklayıp duvara
    # çarpar. Sebep de gönderiliyor ki ne yapması gerektiğini bilsin.
    from app.services import adres_degisim as _adsvc

    _izin, _sebep = _adsvc.degistirilebilir_mi(order)
    if _izin and _adsvc.zaten_degistirildi(db, order.id):
        _izin, _sebep = False, _adsvc.BIR_KEZ_MESAJI

    return {
        "no": order.name or (f"#{order.order_number}" if order.order_number else None),
        "adres_degisim": {"acik": _izin, "sebep": _sebep},
        "ad": _ad or (order.customer_name or None),
        "telefon": adres.get("phone") or ham.get("phone") or None,
        "adres": _satir or None,
        "ilce": adres.get("district") or adres.get("city") or None,
        "il": adres.get("province") or None,
        "kalemler": kalemler,
    }


_FAVICON = Path(__file__).parent.parent / "public" / "bernz-favicon.png"


@router.get("/api/public/model-degisim-favicon")
def favicon():
    """Sekme ikonu. `app/public` statik olarak sunulmuyor (HTML'ler dosyadan
    okunup string olarak dönüyor), o yüzden küçük bir uç."""
    if not _FAVICON.exists():
        raise HTTPException(status_code=404, detail="yok")
    return FileResponse(_FAVICON, media_type="image/png",
                        headers={"Cache-Control": "public, max-age=86400"})


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

    _magaza = _siparis_magazasi(db, t)
    markalar, ozel = _model_secenekleri(db, t)
    # BERNZ Special'da müşterinin telefonu listede olmayabilir. O durumda
    # Special'da kalmak mümkün değil ama BAŞKA bir ürüne geçerek modelini
    # koruyabilir — bu yüzden tam liste de gönderilir ve sayfada "modelim
    # listede yok" seçeneğiyle açılır.
    tum = _markalara_ayir(_tum_modeller(db, t.tenant_id)) if ozel else None
    return {
        "durum": "bekliyor",
        "urun": t.urun_adi,
        "mevcut_model": t.mevcut_model,
        "ozel_seri": ozel,
        "kalip_turu": t.kalip_turu,
        "markalar": markalar,
        "markalar_tum": tum,
        "siparis": _siparis_ozeti(db, t),
        "katalog": urun_katalog.katalog(db, t.tenant_id, _magaza),
        "son_gecerlilik": t.expires_at.isoformat() if t.expires_at else None,
    }


@router.post("/api/public/model-degisim/{token}/adres-degisim", response_model=dict)
def adres_baglantisi(token: str, db: Session = Depends(get_db),
                     _rl: None = Depends(rate_limit)):
    """Bu siparişin adres değişikliği bağlantısını üretir.

    Neden güvenli: bu token müşteriye siparişteki telefona WhatsApp'tan
    gönderildi; yani elinde tutan kişi zaten numaranın sahibi. Operatörden
    ikinci bir mesaj istemek müşteriyi bekletmekten başka bir güvenlik
    kazandırmıyor. Üretilen adres bağlantısı yine 60 dakikalık ve tek
    kullanımlık; kargo kapısı hem burada hem uygulama anında yeniden bakılır.
    """
    t = _talep(db, token)
    if not _sureli_mi(t):
        raise HTTPException(status_code=410, detail="Bağlantının süresi doldu.")

    order = db.scalar(select(Order).where(Order.id == t.order_id)
                      .execution_options(include_deleted=True))
    from app.services import adres_degisim as ad_svc

    izin, sebep = ad_svc.degistirilebilir_mi(order)
    if not izin:
        raise HTTPException(status_code=409, detail=sebep)
    try:
        talep = ad_svc.talep_olustur(db, order)
    except ad_svc.ZatenDegistirildi as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    db.commit()
    return {"link": ad_svc.link(talep.token)}


class SecimIstegi(BaseModel):
    model: str | None = None
    urun_id: str | None = None


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
    # Satır kilidi: aynı bağlantıya iki sekmeden aynı anda basılırsa yalnız
    # biri uygulansın (bkz. _talep).
    t = _talep(db, token, kilitle=True)
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
    urun_adi = None
    if istek.urun_id:
        # ⚠ Seçilen ürün GERÇEKTEN koleksiyonda mı — istek elle de atılabilir.
        urun_adi = urun_katalog.urun_dogrula(
            db, t.tenant_id, istek.urun_id, _siparis_magazasi(db, t))
        if urun_adi is None:
            raise HTTPException(status_code=400, detail="Seçilen ürün listede yok.")

    if not model and urun_adi is None:
        raise HTTPException(status_code=400,
                            detail="Telefon modeli ya da ürün seçmelisiniz.")

    if model:
        markalar, ozel = _model_secenekleri(db, t)
        # BERNZ Special stok kısıtı YALNIZ Special'da kalınırken geçerli.
        # Müşteri başka bir ürüne geçiyorsa (urun seçtiyse) o ürünün model
        # yelpazesi geçerlidir — aksi halde "modelim Special'da yok" diyen
        # müşteriye çıkış yolu bırakmamış olurduk.
        # NOT: ürün değiştiren müşteri için model DEĞİŞTİRMEK ZORUNDA DEĞİL;
        # telefonu aynı kalır. Model yalnız açıkça istendiğinde gönderilir
        # (sayfada "telefon modelimi de değiştirmek istiyorum" kutusu).
        if ozel and urun_adi is not None:
            markalar, ozel = _markalara_ayir(_tum_modeller(db, t.tenant_id)), False
        # ⚠ Yalnız STOKTA olan seçilebilir. Listede görünen ama stokta olmayan
        # bir modelin sunucuda da reddedilmesi şart: sayfadaki `disabled`
        # yalnız görsel bir engel.
        _secilebilir = {m["deger"] for g in markalar for m in g["modeller"] if m.get("stokta")}
        if model not in _secilebilir:
            raise HTTPException(status_code=400,
                                detail="Bu model şu an seçilemiyor. Lütfen listeden birini seçin.")
        if ozel:
            from app.services import ozel_seri
            if not ozel_seri.stokta_mi(db, t.tenant_id, model):
                raise HTTPException(
                    status_code=400,
                    detail="Bu model BERNZ Special'da stokta değil. Farklı bir ürün "
                           "seçerek bu modelde devam edebilirsiniz.")


    # ⚠ ÖNCE kalıptan çek: aşağıdaki alan değişiklikleri sırasında hata çıksa
    # bile yanlış modelli kılıfın basılması ihtimali kalmasın.
    cekilen = _kaliptan_cek(db, li)

    if model:
        from app.services.phone_models import gorunen_ad as _ad
        li.device_model_override = (_ad(db, t.tenant_id, model) or model)[:100]

    # "Stok bekliyor" bayrağı kalkmalı: müşteri beklemeyi seçmedi, değiştirdi.
    # Kalırsa bayi portalinde ve panelde hâlâ "Stokta mevcut değil" görünürdü.
    ham = dict(li.raw or {})
    if ham.pop("stok_bekliyor", None) is not None:
        li.raw = ham

    t.durum = "uygulandi"
    t.secilen_model = model[:100] if model else None
    t.secilen_varyasyon = (urun_adi[:20] if urun_adi is not None else None)
    t.uygulandi_at = datetime.now(UTC)

    order = db.scalar(select(Order).where(Order.id == t.order_id)
                      .execution_options(include_deleted=True))
    _no = (order.name or f"#{order.order_number or ''}") if order else ""
    _parcalar = []
    if model:
        _parcalar.append(f"model: {t.mevcut_model or '—'} → {model}")
    if urun_adi is not None:
        # ⚠ TASARIM OTOMATİK DEĞİŞTİRİLMİYOR — bilinçli. Vitrin katalog ürünleri
        # ile üretimdeki tasarımlar AYRI kimlik uzayında (Design.product_id
        # katalog ürün id'siyle eşleşmiyor); tahminle tasarım atamak YANLIŞ
        # kılıf bastırır. Müşterinin seçimi kayda geçer, kalem kalıptan çekilir
        # ve panele bildirim düşer; tasarımı operatör bağlar.
        # ÖNCEKİ → SONRAKİ: operatör geçmişe bakınca neyin neye dönüştüğünü
        # görmeli. Yalnız yeni adı yazmak "ne değişti?" sorusunu bıraktı.
        _onceki = (li.title or "").strip() or "—"
        _parcalar.append(f"ürün: {_onceki} → {urun_adi}")
    _not = ("Müşteri değişiklik yaptı — " + " · ".join(_parcalar)
            + (f" · {cekilen} kalıp slotundan çıkarıldı" if cekilen else "")
            + (" · ÜRÜN DEĞİŞİKLİĞİ: tasarımı elle bağlayın" if urun_adi is not None else ""))

    db.add(OrderStatusHistory(
        tenant_id=t.tenant_id, order_id=t.order_id,
        action="musteri_model_degisikligi", note=_not, created_by="Müşteri",
    ))
    db.add(Notification(
        tenant_id=t.tenant_id, store_id=(order.store_id if order else None),
        kind="warn" if cekilen else "info",
        title=(f"{_no} · müşteri ÜRÜN değiştirdi" if urun_adi is not None
               else f"{_no} · müşteri model değiştirdi"),
        body=_not,
        link=f"/orders/{t.order_id}",
    ))
    db.commit()

    # Panel/uygulama bildirimi — kalıptan çekildiyse acil, baskıcı görmeli.
    try:
        from app.services import push
        push.send_to_tenant(
            db, t.tenant_id,
            (f"{_no} · müşteri ÜRÜN değiştirdi" if urun_adi is not None
             else f"{_no} · müşteri model değiştirdi"), _not,
            url=f"/orders/{t.order_id}", tag=f"model-degisim-{t.order_id}",
        )
    except Exception:  # noqa: BLE001 — bildirim akışı bozmasın
        pass

    return {"ok": True, "model": model or None,
            "urun": urun_adi}
