"""Bayi portalı — /api/bayii/*  (bayilerin kendi giriş paneli)

Bayiler kendi hesaplarıyla girer; siparişlerinin durumunu ve carilerini görür,
yeni sipariş açar. Varyasyon seçimi ve ONAY yönetimde kalır.

GÜVENLİK — buradaki HER sorgu iki şeye kilitli: user.tenant_id ve
user.dealer_id. Kilit tek yerde (_bayi + _siparis) toplandı; yeni uç eklerken
mutlaka onları kullan, elle Order sorgusu yazma.

İzin adı bilerek 'bayii_portal', 'bayii' DEĞİL: 'bayii' yönetim tarafındaki
bayi ekranlarının izni ve require_any_permission("siparisler", "bayii") gibi
yerlerde geçiyor. Aynı adı verseydik bayi kullanıcısı yönetim uçlarına da
girerdi.

DEĞİŞİKLİK KURALLARI:
  • kalıba eklenmiş kalem varsa -> hiçbir değişiklik yok
  • barkod oluşmuşsa            -> adres değişmez
  • ikisi de yoksa              -> model, tasarım ve adres değişebilir
Her değişiklik durum geçmişine yazılır + yöneticiye bildirim gider.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import (APIRouter, BackgroundTasks, Depends, File, Form,
                     HTTPException, UploadFile)
from pydantic import BaseModel, Field
from sqlalchemy import desc, func as sql_func, or_, select
from sqlalchemy.orm import Session, selectinload

from app import stages as stage_defs
from app.auth.dependencies import get_current_user, require_permission
from app.database import get_db
from app.models import (
    Dealer, DealerTransaction, Design, LineItem, MoldItem, Notification,
    Order, OrderStatusHistory, User,
)
from app.services import storage

logger = logging.getLogger("bayii-portal")

router = APIRouter(prefix="/api/bayii", tags=["bayii_portal"])
_izin = Depends(require_permission("bayii_portal"))

# Siparişin geldiği kanal. Trendyol adresi kendi tarafında tutuyor; bizden
# yalnızca alıcı adı isteniyor. Diğerlerinde kargo için tam adres şart.
KANALLAR = ("trendyol", "shopier", "instagram")
ADRES_ZORUNLU = ("shopier", "instagram")
# Bayi tasarımı JPG yükler (kullanıcıya söylenen kural); PNG/PDF de kabul.
IZINLI_UZANTI = ("jpg", "jpeg", "png", "pdf")


# ─── Kilitler ────────────────────────────────────────────────
def _bayi(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Dealer:
    if not user.dealer_id:
        raise HTTPException(403, "Bu hesap bir bayiye bağlı değil")
    d = db.scalar(select(Dealer).where(
        Dealer.id == user.dealer_id, Dealer.tenant_id == user.tenant_id))
    if not d:
        raise HTTPException(404, "Bayi bulunamadı")
    if not d.is_active:
        raise HTTPException(403, "Bayi hesabınız pasif durumda — bizimle iletişime geçin")
    return d


def _sahibi_mi(o: Order, d: Dealer) -> bool:
    """Sipariş bu bayinin mi. raw.dealer_id kesin ölçüt; yoksa mağazaya düşülür.
    (OR ile bakmak iki bayi aynı mağazayı paylaşırsa sızıntı olurdu.)"""
    rd = str((o.raw or {}).get("dealer_id") or "")
    return (rd == str(d.id)) if rd else (o.store_id == d.store_id)


def _siparis(db: Session, d: Dealer, order_id: uuid.UUID) -> Order:
    o = db.scalar(
        select(Order).where(Order.id == order_id, Order.tenant_id == d.tenant_id,
                            Order.deleted_at.is_(None))
        .options(selectinload(Order.line_items).selectinload(LineItem.assigned_design))
    )
    if not o or not _sahibi_mi(o, d):
        raise HTTPException(404, "Sipariş bulunamadı")
    return o


def _bayinin_sql_suzgeci(d: Dealer):
    """Bayinin siparislerini VERITABANINDA suz.

    Bayi siparisleri her zaman bayinin kendi magazasinda acilir ve raw'a
    dealer_id yazilir; ikisinden biri yeterli. Bu suzgec olmadan tenant'in TUM
    siparisleri cekilip Python'da eleniyordu — dev'de anlikti, canlida binlerce
    siparis + line_item + tasarim yuklenip panel hic acilmiyordu.
    """
    kosul = Order.raw["dealer_id"].astext == str(d.id)
    if d.store_id:
        kosul = or_(kosul, Order.store_id == d.store_id)
    return (Order.tenant_id == d.tenant_id) & (Order.deleted_at.is_(None)) & kosul


def _bayinin_siparisleri(db: Session, d: Dealer, limit: int = 500) -> list[Order]:
    orders = db.scalars(
        select(Order).where(_bayinin_sql_suzgeci(d))
        .options(selectinload(Order.line_items).selectinload(LineItem.assigned_design))
        .order_by(desc(Order.created_at_platform)).limit(min(limit, 500))
    ).all()
    # SQL suzgeci genis (magaza VEYA raw); son soz yine _sahibi_mi'de.
    return [o for o in orders if _sahibi_mi(o, d)]


# ─── Durum yardımcıları ──────────────────────────────────────
def _kaliba_girdi(db: Session, o: Order) -> bool:
    if any(getattr(li, "is_kaliba_eklendi", False) for li in (o.line_items or [])):
        return True
    return bool(db.scalar(select(MoldItem.id).where(
        MoldItem.tenant_id == o.tenant_id,
        MoldItem.order_number == str(o.order_number)).limit(1)))


def _barkod_var(o: Order) -> bool:
    return bool(o.barkod_kodu or (o.kargo_info or {}).get("barcode")
                or (o.current_stage or 1) >= 3)


def _yetkiler(db: Session, o: Order) -> dict:
    from app.services import bayii_iptal

    uretimde = _kaliba_girdi(db, o)
    barkod = _barkod_var(o)
    d, _ = bayii_iptal.durumu_oku(db, o)
    kapali = bool(o.is_iptal)
    return {
        "urun_degistir": not uretimde and not kapali,   # telefon modeli + tasarım
        "adres_degistir": not uretimde and not barkod and not kapali,
        # Kalıba girmemişse bayi doğrudan geri çeker
        "silinebilir": not uretimde and not kapali,
        # Kalıba girdiyse yalnız TALEP açabilir — ve basılmış kalıpta o da yok
        "iptal_talebi_acilir": (uretimde and not kapali
                                and d.talep_acilabilir
                                and not o.bayii_iptal_talebi),
        "iptal_talebi_bekliyor": bool(o.bayii_iptal_talebi),
        "iptal_edildi": kapali,
        "kalip_basildi": d.basilmis_kalip_var,
        "uretimde": uretimde,
        "barkod_var": barkod,
    }


def _kaliptaki_kalemler(db: Session, o: Order) -> set:
    """Bu siparişin ŞU AN bir kalıpta duran kalem id'leri."""
    from app.models import MoldItem as _MI
    ids = [li.id for li in (o.line_items or [])]
    if not ids:
        return set()
    return set(db.scalars(select(_MI.line_item_id).where(
        _MI.line_item_id.in_(ids))).all())


def _ser_kalem(li: LineItem, kaliptakiler: set | None = None) -> dict:
    d = li.assigned_design
    # "Stokta mevcut değil": kalem stok yokluğuyla kalıptan çıkarılmış VE şu an
    # hiçbir kalıpta değil. Bayrağa tek başına bakmıyoruz — ürün tekrar kalıba
    # girdiğinde ibare kendiliğinden kalkmalı, yoksa bayi üretimdeki siparişi
    # "stokta yok" sanır.
    _stok = (li.raw or {}).get("stok_bekliyor") if isinstance(li.raw, dict) else None
    stok_bekliyor = bool(_stok) and (
        kaliptakiler is None or li.id not in kaliptakiler)
    return {
        "id": str(li.id),
        "baslik": li.title,
        "model": li.device_model_override,
        "adet": li.quantity or 1,
        "varyasyon": li.kilif_varyasyon,
        "gorsel": storage.get_thumbnail_url(d.file_path, d.file_format) if d else None,
        "tasarim": storage.get_design_url(d.file_path) if d else None,
        # Önizleme AYRI alanda: baskı akışının yanlışlıkla almasını imkânsız
        # kılmak için hiçbir yerde "gorsel" ile karıştırılmaz.
        "onizleme": storage.onizleme_url(d.onizleme_path) if d else None,
        "tasarim_id": str(d.id) if d else None,
        "format": (d.file_format or "").lower() if d else None,
        "stok_bekliyor": stok_bekliyor,
        "stok_bekliyor_tarih": (_stok or {}).get("at") if stok_bekliyor else None,
    }


def _ser(db: Session, o: Order, detay: bool = False) -> dict:
    raw = o.raw or {}
    # Kalipta olan kalemleri YALNIZCA gerekince sor: liste ekraninda 500 siparis
    # icin sipariş basina sorgu atmak N+1 olurdu. Siparislerin buyuk cogunlugunda
    # stok bayragi hic yok.
    _onbellek: list = []

    def _kaliptaki():
        if not _onbellek:
            var = any(isinstance(li.raw, dict) and li.raw.get("stok_bekliyor")
                      for li in (o.line_items or []))
            _onbellek.append(_kaliptaki_kalemler(db, o) if var else set())
        return _onbellek[0]

    sa = raw.get("shipping_address") or {}
    out = {
        "id": str(o.id),
        "order_number": o.order_number,
        "musteri": o.customer_name,
        "kanal": raw.get("kanal"),
        "tarih": o.created_at_platform.isoformat() if o.created_at_platform else None,
        "asama": o.current_stage or 1,
        "asama_adi": stage_defs.stage_label(o.current_stage or 1),
        "onay_bekliyor": bool(o.bayii_onay_bekliyor),
        "iptal": bool(o.is_iptal),
        "iptal_talebi": bool(o.bayii_iptal_talebi),
        "adet": sum(int(li.quantity or 1) for li in (o.line_items or [])),
        "tutar": raw.get("total_price"),
        "kargo_ucreti": raw.get("shipping_fee"),
        "para_birimi": raw.get("currency", "TRY"),
        "kargo_takip": (o.kargo_info or {}).get("tracking_number"),
        "kalemler": [_ser_kalem(li, _kaliptaki()) for li in sorted(
            o.line_items or [], key=lambda x: x.position or 0)],
    }
    if detay:
        gecmis = db.scalars(
            select(OrderStatusHistory)
            .where(OrderStatusHistory.order_id == o.id)
            .order_by(desc(OrderStatusHistory.created_at)).limit(30)
        ).all()
        out |= {
            "adres": {
                "ad": sa.get("name") or o.customer_name,
                "telefon": sa.get("phone"),
                "adres": sa.get("address1"),
                "il": sa.get("city"),
                "ilce": sa.get("province"),
            },
            "not": o.note,
            "yetkiler": _yetkiler(db, o),
            "gecmis": [
                {"eylem": h.action, "not": h.note, "kim": h.created_by,
                 "tarih": h.created_at.isoformat() if h.created_at else None}
                for h in gecmis
            ],
        }
    return out


def _bildir(db: Session, d: Dealer, o: Order, baslik: str, govde: str) -> None:
    """Yöneticiye haber ver: panel bildirimi + telefona push.
    Bildirim gönderilemezse ana işlem düşmemeli — hatalar yutulur."""
    link = f"/orders/{o.id}"
    try:
        db.add(Notification(tenant_id=d.tenant_id, store_id=d.store_id,
                            kind="bayii", title=baslik, body=govde, link=link))
    except Exception:  # noqa: BLE001
        pass
    try:
        from app.services import push
        push.send_to_tenant(db, d.tenant_id, baslik, govde, url=link,
                            tag=f"bayii-{o.id}")
    except Exception:  # noqa: BLE001
        pass


def _gecmise_yaz(db: Session, o: Order, d: Dealer, eylem: str, not_: str) -> None:
    db.add(OrderStatusHistory(
        tenant_id=o.tenant_id, order_id=o.id,
        from_stage=o.current_stage, to_stage=o.current_stage,
        action=eylem, note=not_, created_by=f"Bayi: {d.name}",
    ))


# ─── Okuma uçları ────────────────────────────────────────────
@router.get("/ozet", response_model=dict, dependencies=[_izin])
def ozet(d: Dealer = Depends(_bayi), db: Session = Depends(get_db)):
    # Sayaclar SQL'de sayilir: satirlari cekip Python'da saymak canlida
    # (binlerce siparis) paneli hic actirmiyordu.
    temel = _bayinin_sql_suzgeci(d) & (Order.is_iptal == False)  # noqa: E712

    def _say(*ek) -> int:
        return int(db.scalar(select(sql_func.count(Order.id))
                             .where(temel, *ek)) or 0)

    onay = _say(Order.bayii_onay_bekliyor == True)  # noqa: E712
    kargoda = _say(Order.current_stage >= 8)
    toplam = _say()
    return {
        "bayi": {"ad": d.name, "para_birimi": (d.currency or "TRY").upper()},
        "cari": {
            "bakiye": float(d.balance or 0),
            "bakiye_usd": float(d.balance_usd or 0),
            "birim_fiyat": float(d.unit_price or 0),
            # Birim fiyat bayinin para biriminde; kargo HER ZAMAN ₺.
            # Bu alan olmadigi icin sihirbaz TRY'ye dusuyor ve USD bayide
            # "₺5,00" gosteriyordu.
            "para_birimi": (d.currency or "TRY").upper(),
            "kargo_ucreti": float(d.shipping_fee or 0),
        },
        "sayilar": {
            "toplam": toplam,
            "onay_bekleyen": onay,
            # Uretimde = onay bekleyen ve kargoya verilen disindaki her sey
            "uretimde": max(0, toplam - onay - kargoda),
            "kargoda": kargoda,
        },
        "son_siparisler": [_ser(db, o) for o in _bayinin_siparisleri(db, d, limit=6)],
    }


@router.get("/siparisler", response_model=dict, dependencies=[_izin])
def siparisler(d: Dealer = Depends(_bayi), db: Session = Depends(get_db), limit: int = 200):
    return {"items": [_ser(db, o) for o in _bayinin_siparisleri(db, d, limit=limit)]}


@router.get("/siparis/{order_id}", response_model=dict, dependencies=[_izin])
def siparis_detay(order_id: uuid.UUID, d: Dealer = Depends(_bayi),
                  db: Session = Depends(get_db)):
    return _ser(db, _siparis(db, d, order_id), detay=True)


@router.get("/cari", response_model=dict, dependencies=[_izin])
def cari(d: Dealer = Depends(_bayi), db: Session = Depends(get_db), limit: int = 100):
    hareketler = db.scalars(
        select(DealerTransaction).where(DealerTransaction.dealer_id == d.id)
        .order_by(desc(DealerTransaction.created_at)).limit(min(limit, 300))
    ).all()
    return {
        "bakiye": float(d.balance or 0),
        "bakiye_usd": float(d.balance_usd or 0),
        "para_birimi": (d.currency or "TRY").upper(),
        "items": [
            {"tarih": t.created_at.isoformat() if t.created_at else None,
             "tur": t.kind, "aciklama": t.description,
             "tutar": float(t.amount or 0), "para_birimi": t.currency or "TRY",
             "bakiye_sonra": float(t.balance_after or 0)}
            for t in hareketler
        ],
    }


@router.get("/il-ilce", response_model=dict, dependencies=[_izin])
def il_ilce():
    """TR il -> ilce listesi (statik).

    Adres serbest metin girilince yazim hatasi kargo etiketini bozuyordu;
    bayi listeden secsin. Ayni veriyi vitrin de kullaniyor.
    """
    from app.services.tr_iller import IL_ILCE
    return {"items": IL_ILCE}


@router.get("/tasarimlar", response_model=dict, dependencies=[_izin])
def tasarimlar(d: Dealer = Depends(_bayi), db: Session = Depends(get_db),
               limit: int = 200):
    """Bayinin daha önce yüklediği tasarımlar — katalog.

    Aynı tasarımı tekrar tekrar yüklemek yerine listeden seçebilsin.
    YALNIZCA bayinin kendi mağazasındaki tasarımlar; başka bayinin ya da
    bizim tasarımlarımız burada GÖRÜNMEZ.
    """
    if not d.store_id:
        return {"items": []}
    from app.services import tasarim_katalog

    rows = db.scalars(
        select(Design).where(Design.store_id == d.store_id,
                             Design.tenant_id == d.tenant_id,
                             # Dosyası temizlenmiş tasarım SEÇİLEMEZ: seçilirse
                             # kalıp basılamaz. Listede göstermek yanıltır.
                             Design.dosya_silindi_at.is_(None),
                             # Yalnız silinmiş siparişlerde kalan tasarım da
                             # görünmez (bkz. tasarim_katalog).
                             tasarim_katalog.gorunur_kosulu())
        .order_by(desc(Design.created_at)).limit(min(limit, 300))
    ).all()
    return {"items": [
        {
            "id": str(x.id),
            "kod": x.code,
            "ad": x.name or x.code,
            "format": (x.file_format or "").lower(),
            # LİSTEDE önizleme varsa O gösterilir (tasarımın kılıf üzerindeki
            # hâli). Ama seçim yine TASARIMI bağlar — "id" tasarımın id'si ve
            # kalıba giden dosya her zaman file_path'tir. Bu ayrım kritik:
            # önizleme basılırsa kılıflar çöp olur.
            "gorsel": (storage.onizleme_url(x.onizleme_path)
                       or storage.get_thumbnail_url(x.file_path, x.file_format)),
            "tasarim_gorseli": storage.get_thumbnail_url(x.file_path, x.file_format),
            "onizleme_var": bool(x.onizleme_path),
            "tarih": x.created_at.isoformat() if x.created_at else None,
        }
        for x in rows
    ]}


def _cozulen_deger(db: Session, tenant_id, *adaylar: str) -> str | None:
    """Kalıp planlayıcının TANIYACAĞI ilk aday.

    Model adı kalıp ölçüsünü buradan çözülüyor. Bayiye tanınmayan bir ad
    gösterirsek sipariş "Model tanınmadı" ile kalıp dışında kalıyor ve bu
    ancak kalıp üretilirken fark ediliyor.
    """
    from app.services import phone_models as pm

    for a in adaylar:
        a = (a or "").strip()
        if a and pm.has_spec(db, tenant_id, a):
            return a
    return None


@router.get("/modeller", response_model=dict, dependencies=[_izin])
def modeller(d: Dealer = Depends(_bayi), db: Session = Depends(get_db)):
    """Sipariş girerken seçilecek telefon modelleri.

    Dönüş {deger, etiket}: `etiket` bayinin gördüğü ad, `deger` siparişe
    yazılan ve kalıp planlayıcının çözdüğü ad. İkisi AYRIŞABİLİR — tenant'a
    "A57" diye eklenmiş bir modelin gerçek anahtarı "SAMSUNG-A57" olabilir;
    ekranda "A57" yazar ama siparişe çözülen ad gider.

    Çözülemeyen modeller listeye HİÇ girmez: bayi seçemesin.
    """
    from app.models import PhoneModel
    from app.services import phone_models as pm

    secenekler: dict[str, str] = {}   # deger -> etiket

    for m in db.scalars(select(PhoneModel).where(
            PhoneModel.tenant_id == d.tenant_id,
            PhoneModel.is_active == True)).all():  # noqa: E712
        etiket = (m.display_name or m.spec_key or "").strip()
        deger = _cozulen_deger(db, d.tenant_id, m.display_name, m.spec_key)
        if deger and etiket:
            secenekler.setdefault(deger, etiket)

    for k in pm.baseline_keys():
        if pm.is_apple_alias_key(k):
            continue
        etiket = pm.baseline_display_name(k)
        deger = _cozulen_deger(db, d.tenant_id, etiket, k)
        if deger and deger not in secenekler:
            secenekler[deger] = etiket

    return {"items": [
        {"deger": v, "etiket": e}
        for v, e in sorted(secenekler.items(), key=lambda kv: kv[1].lower())
    ]}


# ─── Sipariş oluşturma ───────────────────────────────────────
def _katalogdan_tasarim(db: Session, d: Dealer, tasarim_id: str) -> Design:
    """Bayinin KENDI katalogundan tasarim. Baska magazanin tasarimi secilemez."""
    try:
        tid = uuid.UUID(tasarim_id)
    except (ValueError, AttributeError):
        raise HTTPException(400, "Geçersiz tasarım seçimi") from None
    ds = db.scalar(select(Design).where(
        Design.id == tid, Design.tenant_id == d.tenant_id,
        Design.store_id == d.store_id))
    if not ds:
        raise HTTPException(404, "Tasarım bulunamadı")
    return ds


def _benzersiz_tasarim_kodu(db: Session, d: Dealer) -> str:
    """Bayi tasarımı için çakışmayan kod.

    Kod eskiden yalnız zaman damgasından türüyordu (santisaniye çözünürlük).
    Çoklu ürünlü siparişte tasarımlar aynı döngüde arka arkaya kaydedildiği
    için ikisi aynı santisaniyeye düşüp uq_design_store_code kısıtını bozuyor
    ve sipariş 500 ile düşüyordu. Artık veritabanına sorularak üretilir.
    """
    taban = f"B{d.id.hex[:4]}-{datetime.now(UTC).strftime('%y%m%d%H%M%S')}"
    for i in range(200):
        kod = taban if i == 0 else f"{taban}-{i}"
        var = db.scalar(select(Design.id).where(
            Design.store_id == d.store_id, Design.code == kod).limit(1))
        if not var:
            return kod
    raise HTTPException(503, "Tasarım kodu üretilemedi, birkaç saniye sonra tekrar dene")


def _ayni_tasarimi_bul(db: Session, d: Dealer, veri: bytes, icerik_hash: str) -> Design | None:
    """Bu bayide AYNI dosya zaten var mı? Yoksa/emin değilsek None.

    Kural: şüphe varsa YENİ kayıt. Yanlış eşleşme, müşteriye YANLIŞ TASARIM
    basılması demektir — yer kazancı bunun yanında önemsiz.

    Üç kapı:
      1) Aynı MAĞAZA (bayiler arası paylaşım YOK — biri silerse/değiştirirse
         diğerinin siparişi bozulur).
      2) Aynı SHA-256 ve aynı BOYUT.
      3) Dosya diskte hâlâ duruyor ve BAYT BAYT aynı. Hash eşleşip baytlar
         tutmuyorsa dosya sonradan değişmiş demektir (ör. baskı PDF'i
         yüklenmiş) — eşleşme sayılmaz, log'a yazılır.
    """
    if not d.store_id or not icerik_hash:
        return None
    adaylar = db.scalars(select(Design).where(
        Design.store_id == d.store_id,
        Design.icerik_hash == icerik_hash,
        Design.file_size_bytes == len(veri),
    ).order_by(Design.created_at.asc()).limit(5)).all()
    for aday in adaylar:
        mevcut = storage.read_design_file(aday.file_path)
        if mevcut is None:
            logger.warning("[tasarim] hash esti ama dosya YOK: %s (%s)",
                           aday.code, aday.file_path)
            continue
        if mevcut == veri:
            return aday
        logger.warning("[tasarim] hash esti ama BAYTLAR FARKLI: %s — yeni kayit "
                       "olusturuluyor", aday.code)
    return None


def _onizleme_kaydet(db: Session, d: Dealer, ds: Design, dosya: UploadFile) -> bool:
    """Tasarima ONIZLEME gorseli bagla. BASKIYA GIRMEZ.

    Ayni tasarim tekrar kullanildiginda SONUNCU onizleme gecerli olur
    (kullanicinin karari). Onizleme AYRI klasorde durur; kalip/PDF tarafi o
    klasoru hic okumaz, dolayisiyla yanlislikla basilmasi mumkun degil.
    """
    veri = dosya.file.read()
    if not veri:
        return False
    try:
        yol = storage.save_onizleme(d.tenant_id, ds.id, veri,
                                    dosya.filename or "onizleme.jpg")
    except ValueError as e:
        raise HTTPException(400, f"Önizleme: {e}") from e
    except OSError as e:
        raise HTTPException(500, f"Önizleme kaydedilemedi: {str(e)[:150]}") from e
    eski = ds.onizleme_path
    ds.onizleme_path = yol
    if eski and eski != yol:
        storage.delete_onizleme(eski)   # sonuncusu geçerli — eskisi yer kaplamasın
    return True


def _tasarim_kaydet(db: Session, d: Dealer, dosya: UploadFile, etiket: str,
                    arka: BackgroundTasks | None = None) -> Design:
    """Yüklenen dosyadan Design üret. Kod çakışmasın diye bayiye özel önek.

    Aynı dosya bu bayide zaten varsa YENİ DOSYA YAZILMAZ, mevcut tasarım
    döndürülür (bkz. _ayni_tasarimi_bul).
    """
    ext = storage.get_extension(dosya.filename or "")
    if ext not in IZINLI_UZANTI:
        raise HTTPException(400, f"İzin verilen formatlar: {', '.join(IZINLI_UZANTI).upper()}")
    veri = dosya.file.read()
    if not veri:
        raise HTTPException(400, "Dosya boş")
    if len(veri) > storage.MAX_FILE_SIZE:
        raise HTTPException(413, f"Dosya çok büyük (max {storage.MAX_FILE_SIZE // 1024 // 1024} MB)")

    icerik_hash = hashlib.sha256(veri).hexdigest()
    mevcut = _ayni_tasarimi_bul(db, d, veri, icerik_hash)
    if mevcut is not None:
        # Panelin/bayinin "yeniden kullanildi" diyebilmesi icin isaretle —
        # sessizce ayni kaydi vermek kullaniciyi yanıltır.
        mevcut._yeniden_kullanildi = True   # noqa: SLF001 (yalnizca bu istek icin)
        logger.info("[tasarim] ayni dosya zaten var, yeniden kullanildi: %s (%s)",
                    mevcut.code, d.name)
        return mevcut

    kod = _benzersiz_tasarim_kodu(db, d)
    tasarim = Design(
        tenant_id=d.tenant_id, store_id=d.store_id, code=kod,
        name=etiket[:200] or kod, is_kisiye_ozel=True,
        notes=f"Bayi portalinden yüklendi — {d.name}",
        file_path="", file_format="", file_size_bytes=0,
        icerik_hash=icerik_hash,
    )
    db.add(tasarim)
    db.flush()
    try:
        bilgi = storage.save_design_file(
            tenant_id=d.tenant_id, design_id=tasarim.id, file_data=veri,
            original_filename=dosya.filename or f"{kod}.{ext}",
            skip_thumbnail=True,  # önizleme arka planda üretilir, yükleme beklemesin
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except OSError as e:
        raise HTTPException(500, f"Dosya kaydedilemedi: {str(e)[:200]}") from e
    tasarim.file_path = bilgi["relative_path"]
    tasarim.file_format = bilgi["format"]
    tasarim.file_size_bytes = bilgi["size"]
    if arka is not None:
        # PDF'in onizlemesi (ve kalip onbellegi) YANITTAN SONRA uretilir: bayi
        # yuklemeyi beklemesin. JPG/PNG'de onizleme dosyanin kendisidir, PDF'te
        # bu gorev calismazsa panelde gorsel bos kalirdi.
        arka.add_task(storage.generate_design_thumbnail, d.tenant_id, tasarim.id)
        try:
            from app.services import mold_pdf as _mp
            arka.add_task(_mp.onbellek_hazirla, bilgi["relative_path"])
        except Exception:  # noqa: BLE001
            pass
    return tasarim


def _adres_dogrula(kanal: str, ad: str, telefon: str, adres: str, il: str, ilce: str) -> dict:
    """Kanal kuralı: Trendyol'da ad yeter, diğerlerinde tam adres şart."""
    ad = (ad or "").strip()
    if not ad:
        raise HTTPException(400, "Alıcı adı soyadı gerekli")
    if kanal not in ADRES_ZORUNLU:
        return {"name": ad}
    eksik = [etiket for etiket, deger in (
        ("telefon numarası", telefon), ("adres", adres), ("il", il), ("ilçe", ilce),
    ) if not (deger or "").strip()]
    if eksik:
        raise HTTPException(400, f"{kanal.title()} siparişinde şunlar zorunlu: {', '.join(eksik)}")
    return {
        "name": ad, "phone": telefon.strip(), "address1": adres.strip(),
        "city": il.strip(), "province": ilce.strip(), "country": "Türkiye",
    }


def _benzersiz_no(db: Session, d: Dealer, simdi: datetime) -> tuple[str, str]:
    """Benzersiz (external_id, order_number) uret.

    Numara saniye damgasindan turuyor; aynı saniyede iki siparis acilirsa
    orders(store_id, external_id) tekil kisiti INSERT'i 500 ile dusuruyordu
    (bayi ust uste tiklayinca ya da iki bayi ayni anda girince). Cakisma
    varsa saniyeye harf eki verilir.
    """
    taban = simdi.strftime("%y%m%d%H%M%S")
    for i in range(40):
        seq = taban if i == 0 else f"{taban}{chr(97 + (i - 1) % 26)}{i // 26 or ''}"
        dis = f"BAYII-{d.id.hex[:6]}-{seq}"
        # include_deleted: cope atilmis siparisin satiri DURUYOR, tekil kisit
        # onu da sayar. Global soft-delete suzgeci gizleseydi numarayi bos
        # sanip ayni cakismayi yeniden uretirdik.
        var = db.scalar(select(Order.id).where(
            Order.store_id == d.store_id, Order.external_id == dis
        ).limit(1).execution_options(include_deleted=True))
        if not var:
            return seq, f"B{seq}"
    raise HTTPException(503, "Sipariş numarası üretilemedi, birkaç saniye sonra tekrar dene")


MAX_KALEM = 20   # tek siparişte en fazla ürün


@router.post("/siparis", response_model=dict, status_code=201, dependencies=[_izin])
def siparis_olustur(
    arka: BackgroundTasks,
    # ÇOKLU ÜRÜN: üç liste konum konum eşleşir — tasarim[i] ↔ model[i] ↔ adet[i].
    # Tek ürünlü sipariş de bu yoldan geçer (tek elemanlı listeler).
    # Her urun ya YENI dosya yukler ya da KATALOGDAN secer. Ikisi de konum
    # konum eslesir; secilen urun icin tasarim_id dolu, dosya bos gelir.
    model: list[str] = Form(...),
    adet: list[int] = Form(...),
    tasarim: list[UploadFile] | None = File(None),
    tasarim_id: list[str] | None = Form(None),
    # ÖNİZLEME (opsiyonel): tasarımın kılıf üzerinde nasıl duracağını gösteren
    # görsel. BASKIYA GİRMEZ. onizleme_var[i] = "1"/"0" konum konum eşleşir;
    # dosyalar yalnız "1" olanlar için sırayla gelir (tasarım ile aynı desen).
    onizleme: list[UploadFile] | None = File(None),
    onizleme_var: list[str] | None = Form(None),
    kanal: str = Form(...),
    ad_soyad: str = Form(...),
    telefon: str = Form(""),
    adres: str = Form(""),
    il: str = Form(""),
    ilce: str = Form(""),
    aciklama: str = Form(""),
    d: Dealer = Depends(_bayi),
    db: Session = Depends(get_db),
):
    """Bayi siparişi açar. Sipariş ONAY BEKLER: yönetici varyasyonu seçip
    onaylayana kadar kalıba girmez ve cari borç İŞLENMEZ."""
    kanal = (kanal or "").strip().lower()
    if kanal not in KANALLAR:
        raise HTTPException(400, f"Geçersiz kanal. Seçenekler: {', '.join(KANALLAR)}")
    if not d.store_id:
        raise HTTPException(400, "Bayi mağazası tanımlı değil — bizimle iletişime geçin")

    # Listeler aynı boyda olmalı: eşleşme konuma dayanıyor, kayarsa tasarım
    # yanlış modele bağlanır ve bu ancak baskıda fark edilir.
    if len(model) != len(adet):
        raise HTTPException(400, "Ürün bilgileri eksik gönderildi (model/adet eşleşmiyor)")
    if not 1 <= len(model) <= MAX_KALEM:
        raise HTTPException(400, f"Bir siparişte 1 ile {MAX_KALEM} arası ürün olabilir")

    # Katalogdan seçim: boş dize "bu üründe dosya yüklenmedi" demek.
    kimlikler = list(tasarim_id or [])
    if kimlikler and len(kimlikler) != len(model):
        raise HTTPException(400, "Ürün bilgileri eksik gönderildi (tasarım/model eşleşmiyor)")
    kimlikler += [""] * (len(model) - len(kimlikler))

    dosyalar = [f for f in (tasarim or []) if (f.filename or "").strip()]
    gereken_dosya = sum(1 for k in kimlikler if not k.strip())
    if len(dosyalar) != gereken_dosya:
        raise HTTPException(400, "Ürün bilgileri eksik gönderildi (tasarım/model eşleşmiyor)")

    # Önizleme hizalaması — tasarımdakiyle aynı katılıkta. Kayarsa bir ürünün
    # önizlemesi BAŞKA ürüne bağlanır; baskıyı bozmaz ama bayiyi yanıltır.
    onz_bayrak = [str(x).strip() == "1" for x in (onizleme_var or [])]
    if onz_bayrak and len(onz_bayrak) != len(model):
        raise HTTPException(400, "Ürün bilgileri eksik gönderildi (önizleme/model eşleşmiyor)")
    onz_bayrak += [False] * (len(model) - len(onz_bayrak))
    onz_dosyalar = [f for f in (onizleme or []) if (f.filename or "").strip()]
    if len(onz_dosyalar) != sum(onz_bayrak):
        raise HTTPException(400, "Ürün bilgileri eksik gönderildi (önizleme/model eşleşmiyor)")

    modeller = [(m or "").strip() for m in model]
    for i, m in enumerate(modeller, 1):
        if not m:
            raise HTTPException(400, f"{i}. üründe telefon modeli seçilmeli")
        # Kalıp ölçüsü model adından çözülüyor. Tanınmayan ad kabul edilirse
        # sipariş sessizce kalıp dışında kalıyor ("Model tanınmadı") ve bu
        # ancak kalıp üretilirken fark ediliyor. Kapıda durduruyoruz.
        if not _cozulen_deger(db, d.tenant_id, m):
            raise HTTPException(
                400, f"{i}. üründeki telefon modeli tanınmadı: {m}. "
                     "Lütfen listeden seç.")
    for i, a in enumerate(adet, 1):
        if not 1 <= a <= 99:
            raise HTTPException(400, f"{i}. üründe adet 1 ile 99 arasında olmalı")

    sa = _adres_dogrula(kanal, ad_soyad, telefon, adres, il, ilce)
    toplam_adet = sum(adet)

    simdi = datetime.now(UTC)
    seq, order_number = _benzersiz_no(db, d, simdi)
    raw = {
        "source": "bayii", "kanal": kanal, "dealer_id": str(d.id),
        "currency": (d.currency or "TRY").upper(),
        # Tutarlar ONAYDA kesinleşir; burada bayinin gördüğü tahmini bedel.
        "total_price": str(Decimal(str(d.unit_price or 0)) * Decimal(toplam_adet)),
        "shipping_fee": str(Decimal(str(d.shipping_fee or 0))) if kanal in ADRES_ZORUNLU else "0",
        "shipping_address": sa,
        "customer_phone": sa.get("phone", ""),
    }
    o = Order(
        tenant_id=d.tenant_id, store_id=d.store_id,
        external_id=f"BAYII-{d.id.hex[:6]}-{seq}",
        order_number=order_number, name=f"#{order_number}",
        customer_name=sa["name"], created_at_platform=simdi,
        note=(aciklama or "").strip() or None,
        current_stage=1, bayii_onay_bekliyor=True, raw=raw,
    )
    db.add(o)
    db.flush()

    ozet = []
    sirali_dosya = iter(dosyalar)
    sirali_onz = iter(onz_dosyalar)
    yeniden_kullanilan: list[str] = []   # aynısı zaten yüklüydü — kullanıcıya söylenir
    onizlemeli = 0
    for i, (m, a) in enumerate(zip(modeller, adet)):
        kimlik = kimlikler[i].strip()
        if kimlik:
            ds = _katalogdan_tasarim(db, d, kimlik)
        else:
            ds = _tasarim_kaydet(db, d, next(sirali_dosya), f"{m} — {sa['name']}", arka)
            if getattr(ds, "_yeniden_kullanildi", False):
                yeniden_kullanilan.append(ds.code)
        if onz_bayrak[i]:
            if _onizleme_kaydet(db, d, ds, next(sirali_onz)):
                onizlemeli += 1
        db.add(LineItem(
            tenant_id=d.tenant_id, order_id=o.id,
            title=f"{m} — {ds.code}", quantity=a, position=i,
            assigned_design_id=ds.id, device_model_override=m,
            properties=[], raw={"source": "bayii", "kanal": kanal},
        ))
        ozet.append(f"{m} × {a}")

    metin = " · ".join(ozet)
    _gecmise_yaz(db, o, d, "bayii_siparis",
                 f"Bayi portalinden açıldı · {metin} · kanal: {kanal}"
                 + (f" · aynı tasarım yeniden kullanıldı: {', '.join(yeniden_kullanilan)}"
                    if yeniden_kullanilan else ""))
    _bildir(db, d, o, "Yeni bayi siparişi",
            f"{d.name} — #{order_number} · {metin} ({kanal}) · onay bekliyor")
    db.commit()
    db.refresh(o)
    return {"ok": True, "id": str(o.id), "order_number": order_number,
            "kalem_sayisi": len(ozet), "toplam_adet": toplam_adet,
            # Sessizce yeniden kullanmak kullanıcıyı yanıltır — açıkça bildirilir.
            "yeniden_kullanilan_tasarimlar": yeniden_kullanilan,
            "onizlemeli_urun": onizlemeli,
            "mesaj": "Siparişin alındı, onay bekliyor."
                     + (f" (Aynı görsel zaten kayıtlıydı, tekrar yüklenmedi: "
                        f"{', '.join(yeniden_kullanilan)})" if yeniden_kullanilan else "")}


# ─── Düzenleme ───────────────────────────────────────────────
class UrunIn(BaseModel):
    model: str | None = Field(None, max_length=200)
    adet: int | None = Field(None, ge=1, le=99)


def _kalem(o: Order, kalem_id: uuid.UUID) -> LineItem:
    """Siparişin BU kalemi. Çoklu üründe 'ilk kalem' varsaymak, bayinin
    2. ürünü düzenlemesini 1.'ye uygulardı."""
    for li in (o.line_items or []):
        if li.id == kalem_id:
            return li
    raise HTTPException(404, "Ürün bulunamadı")


@router.patch("/siparis/{order_id}/kalem/{kalem_id}", response_model=dict,
              dependencies=[_izin])
def urun_guncelle(order_id: uuid.UUID, kalem_id: uuid.UUID, req: UrunIn,
                  d: Dealer = Depends(_bayi), db: Session = Depends(get_db)):
    """Bir ürünün telefon modelini/adedini değiştir. Kalıba girdiyse reddedilir."""
    o = _siparis(db, d, order_id)
    if not _yetkiler(db, o)["urun_degistir"]:
        raise HTTPException(409, "Bu sipariş üretime girdi, artık değiştirilemez")
    li = _kalem(o, kalem_id)

    degisiklikler = []
    if req.model is not None:
        yeni_m = req.model.strip()
        if not yeni_m:
            raise HTTPException(400, "Telefon modeli boş olamaz")
        if not _cozulen_deger(db, d.tenant_id, yeni_m):
            raise HTTPException(400, f"Telefon modeli tanınmadı: {yeni_m}. Listeden seç.")
        if yeni_m != (li.device_model_override or ""):
            degisiklikler.append(f"model: {li.device_model_override or '—'} → {yeni_m}")
            li.device_model_override = yeni_m
    if req.adet is not None and req.adet != (li.quantity or 1):
        degisiklikler.append(f"adet: {li.quantity or 1} → {req.adet}")
        li.quantity = req.adet

    if not degisiklikler:
        return {"ok": True, "degisiklik": False}
    not_ = " · ".join(degisiklikler)
    _gecmise_yaz(db, o, d, "bayii_guncelleme", not_)
    _bildir(db, d, o, "Bayi siparişi güncellendi", f"{d.name} — #{o.order_number} · {not_}")
    db.commit()
    return {"ok": True, "degisiklik": True}


@router.post("/siparis/{order_id}/kalem/{kalem_id}/tasarim", response_model=dict,
             dependencies=[_izin])
def tasarim_degistir(order_id: uuid.UUID, kalem_id: uuid.UUID, arka: BackgroundTasks,
                     tasarim: UploadFile = File(...),
                     d: Dealer = Depends(_bayi), db: Session = Depends(get_db)):
    """Bir ürünün tasarımını değiştir. Kalıba girdiyse reddedilir."""
    o = _siparis(db, d, order_id)
    if not _yetkiler(db, o)["urun_degistir"]:
        raise HTTPException(409, "Bu sipariş üretime girdi, tasarım değiştirilemez")
    li = _kalem(o, kalem_id)
    eski = li.assigned_design.code if li.assigned_design else "—"
    ds = _tasarim_kaydet(db, d, tasarim,
                         f"{li.device_model_override or ''} — {o.customer_name}", arka)
    li.assigned_design_id = ds.id
    li.is_hazir = False          # yeni tasarım geldi, hazır işareti düşer
    li.title = f"{li.device_model_override or ''} — {ds.code}".strip(" —")
    _gecmise_yaz(db, o, d, "bayii_guncelleme",
                 f"{li.device_model_override or 'Ürün'} tasarımı değişti: {eski} → {ds.code}")
    _bildir(db, d, o, "Bayi tasarımı değişti",
            f"{d.name} — #{o.order_number} · yeni tasarım {ds.code}")
    db.commit()
    return {"ok": True, "tasarim_kodu": ds.code,
            "gorsel": storage.get_thumbnail_url(ds.file_path, ds.file_format)}


class AdresIn(BaseModel):
    ad_soyad: str = Field(..., max_length=200)
    telefon: str = ""
    adres: str = ""
    il: str = ""
    ilce: str = ""


@router.patch("/siparis/{order_id}/adres", response_model=dict, dependencies=[_izin])
def adres_guncelle(order_id: uuid.UUID, req: AdresIn, d: Dealer = Depends(_bayi),
                   db: Session = Depends(get_db)):
    """Adresi güncelle. Barkod oluştuysa reddedilir (kargo etiketi basılmış olur)."""
    o = _siparis(db, d, order_id)
    y = _yetkiler(db, o)
    if y["uretimde"]:
        raise HTTPException(409, "Bu sipariş üretime girdi, adres değiştirilemez")
    if not y["adres_degistir"]:
        raise HTTPException(409, "Barkod oluşturuldu, adres artık değiştirilemez")

    raw = dict(o.raw or {})
    kanal = raw.get("kanal") or "trendyol"
    yeni = _adres_dogrula(kanal, req.ad_soyad, req.telefon, req.adres, req.il, req.ilce)
    eski = raw.get("shipping_address") or {}
    if eski == yeni:
        return {"ok": True, "degisiklik": False}

    raw["shipping_address"] = yeni
    raw["customer_phone"] = yeni.get("phone", "")
    o.raw = raw            # JSONB: yeni sözlük atanmalı, yerinde değişiklik yazılmaz
    o.customer_name = yeni["name"]
    _gecmise_yaz(db, o, d, "bayii_guncelleme",
                 "Adres güncellendi: " + " · ".join(filter(None, [
                     yeni.get("name"), yeni.get("phone"), yeni.get("city"),
                     yeni.get("province")])))
    _bildir(db, d, o, "Bayi adresi güncelledi",
            f"{d.name} — #{o.order_number} · alıcı: {yeni['name']}")
    db.commit()
    return {"ok": True, "degisiklik": True}


class IptalIn(BaseModel):
    sebep: str | None = Field(None, max_length=500)


@router.delete("/siparis/{order_id}", response_model=dict, dependencies=[_izin])
def siparis_iptal(order_id: uuid.UUID, d: Dealer = Depends(_bayi),
                  db: Session = Depends(get_db)):
    """Bayi siparişini geri çeker — YALNIZCA kalıba girmemişse.

    Sipariş SİLİNMEZ, "iptal edildi" olarak kalır: bayi kendi listesinde
    görebilsin. is_iptal=True olduğu için kalıp planına ve paketleme
    kuyruğuna girmez (order_scope.acik_siparis_filtresi).
    """
    from app.services import bayii_iptal

    o = _siparis(db, d, order_id)
    y = _yetkiler(db, o)
    if y["iptal_edildi"]:
        raise HTTPException(409, "Bu sipariş zaten iptal edilmiş")
    if not y["silinebilir"]:
        raise HTTPException(409, "Sipariş üretime girdi — iptal talebi açmalısın")

    ozet = bayii_iptal.uygula(db, o, kim=f"Bayi: {d.name}", sebep=None)
    _bildir(db, d, o, "Bayi siparişi geri çekti",
            f"{d.name} — #{o.order_number} iptal edildi")
    db.commit()
    return {"ok": True, **ozet}


@router.post("/siparis/{order_id}/iptal-talebi", response_model=dict,
             dependencies=[_izin])
def iptal_talebi(order_id: uuid.UUID, req: IptalIn, d: Dealer = Depends(_bayi),
                 db: Session = Depends(get_db)):
    """Üretime girmiş sipariş için iptal TALEBİ aç.

    Bayi tek başına iptal edemez: kalıp silinip yeniden planlanacak ve borç
    iade edilecek. Basılmış kalıpta talep hiç açılamaz.
    """
    o = _siparis(db, d, order_id)
    y = _yetkiler(db, o)
    if y["iptal_edildi"]:
        raise HTTPException(409, "Bu sipariş zaten iptal edilmiş")
    if y["iptal_talebi_bekliyor"]:
        raise HTTPException(409, "Bu sipariş için zaten bir iptal talebin var")
    if not y["uretimde"]:
        raise HTTPException(409, "Bu sipariş henüz üretime girmedi — doğrudan geri çekebilirsin")
    if y["kalip_basildi"]:
        raise HTTPException(
            409, "Kılıf basıldı, iptal edilemez — bizimle iletişime geç")

    sebep = (req.sebep or "").strip() or None
    o.bayii_iptal_talebi = True
    o.bayii_iptal_sebep = sebep
    _gecmise_yaz(db, o, d, "bayii_iptal_talebi",
                 "İptal talebi açıldı" + (f" · sebep: {sebep}" if sebep else ""))
    _bildir(db, d, o, "Bayi iptal talebi",
            f"{d.name} — #{o.order_number} için iptal talebi"
            + (f": {sebep}" if sebep else ""))
    db.commit()
    return {"ok": True, "mesaj": "İptal talebin iletildi, onay bekliyor."}


@router.delete("/siparis/{order_id}/iptal-talebi", response_model=dict,
               dependencies=[_izin])
def iptal_talebi_geri_al(order_id: uuid.UUID, d: Dealer = Depends(_bayi),
                         db: Session = Depends(get_db)):
    """Açılmış iptal talebini geri çek (henüz işlenmediyse)."""
    o = _siparis(db, d, order_id)
    if not o.bayii_iptal_talebi:
        raise HTTPException(409, "Açık bir iptal talebin yok")
    o.bayii_iptal_talebi = False
    o.bayii_iptal_sebep = None
    _gecmise_yaz(db, o, d, "bayii_guncelleme", "İptal talebi geri alındı")
    _bildir(db, d, o, "Bayi iptal talebini geri aldı",
            f"{d.name} — #{o.order_number}")
    db.commit()
    return {"ok": True}
