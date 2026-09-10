"""Model değişikliği sayfasındaki alternatif ürün kataloğu.

Müşteri, eksik stok nedeniyle bekleyen kalemini başka bir tasarım ürünüyle
değiştirmek isteyebilir. Ürünler işletmenin panelden oluşturduğu BİR
KOLEKSİYONDAN gelir (bkz. KOLEKSIYON_ADI) — böylece müşteriye yalnız bu iş
için uygun görülen ürünler sunulur.

KATEGORİLER ELLE GİRİLMEZ. Ürün adları düzenli:
    BERNZ "Berserk Hero" Tasarım Telefon Kılıfı - Berserk Serisi
Seri adı başlığın sonundaki "… Serisi" parçasından okunur. Elle liste tutmak,
yeni bir seri eklendiğinde sessizce "Diğer"e düşürürdü.

⚠ TÜRKÇE BÜYÜK-KÜÇÜK HARF TUZAĞI: Python'da "SERİSİ".lower() → "seri̇si̇"
(noktalı i + birleşik nokta), yani düz "serisi" ile EŞLEŞMEZ. Sahadaki
başlıklarda üç yazım birden var (Serisi / SERISI / SERİSİ); bu yüzden
karşılaştırmalar `_katla()` üzerinden yapılır. Aynı sebeple "ÖZEL TASARIM" ile
"OZEL TASARIM" tek grupta toplanır.
"""
from __future__ import annotations

import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import CatalogCollection, CatalogProduct, catalog_product_collections

# İşletmenin panelden oluşturduğu koleksiyon. Ada göre bulunur: koleksiyon
# silinip yeniden oluşturulsa da (id değişir) bağlantı kopmaz.
KOLEKSIYON_ADI = "BERNZ Special alternatif ürün listesi"

_AYIRAC = re.compile(r"\s[-–—]\s")
_SERI_SON = "serisi"

_TR_ESLEME = str.maketrans({
    "İ": "i", "I": "i", "ı": "i", "Ş": "s", "ş": "s", "Ğ": "g", "ğ": "g",
    "Ü": "u", "ü": "u", "Ö": "o", "ö": "o", "Ç": "c", "ç": "c",
})


def _katla(s: str) -> str:
    """Karşılaştırma anahtarı: Türkçe harfler sadeleşir, küçük harfe iner.

    Arama ve gruplama bunun üzerinden yapılır; "Türk" yazan da "turk" yazan da
    aynı ürünü bulur.
    """
    if not s:
        return ""
    d = unicodedata.normalize("NFKC", s).translate(_TR_ESLEME).lower()
    return unicodedata.normalize("NFKD", d).encode("ascii", "ignore").decode()


def seri_adi(baslik: str) -> str | None:
    """Ürün adından seri (kategori) adını çıkarır; yoksa None."""
    parcalar = _AYIRAC.split(baslik or "")
    if len(parcalar) < 2:
        return None
    kuyruk = parcalar[-1].strip()
    if not _katla(kuyruk).endswith(_SERI_SON):
        return None
    # "… Serisi" ekini at — yazımı ne olursa olsun uzunluğu aynı.
    # Yalnız boşluk ve tire kırpılır: parantez KIRPILMAZ — "Vitray (Stained
    # Glass) Serisi" başlığında kapanış parantezi de gidiyordu.
    ad = kuyruk[: len(kuyruk) - len(_SERI_SON)].strip(" -–—")
    return ad or None


_TIRNAK = re.compile(r"[\"“”'‘’]([^\"“”'‘’]{2,})[\"“”'‘’]")


def kisa_ad(baslik: str) -> str:
    """Izgarada gösterilecek kısa ad.

    Başlıklar uzun ve tekrarlı: `BERNZ "Berserk Hero" Tasarım Telefon Kılıfı -
    Berserk Serisi`. Küçük kartlarda bunun tamamı okunmuyor, üstelik her karta
    aynı "Tasarım Telefon Kılıfı" tekrarı giriyor. Tırnak içindeki tasarım adı
    varsa o kullanılır; yoksa seri eki atılmış başlık.
    """
    m = _TIRNAK.search(baslik or "")
    if m:
        return m.group(1).strip()
    parcalar = _AYIRAC.split(baslik or "")
    if len(parcalar) > 1 and _katla(parcalar[-1]).endswith(_SERI_SON):
        return _AYIRAC.split(baslik)[0].strip() or (baslik or "").strip()
    return (baslik or "").strip()


def _urun_gorseli(p: CatalogProduct) -> str | None:
    gorseller = sorted(p.images or [], key=lambda i: (getattr(i, "position", 0) or 0))
    return f"/storage/{gorseller[0].file_path}" if gorseller else None


def koleksiyon(db: Session, tenant_id) -> CatalogCollection | None:
    """Adı KOLEKSIYON_ADI olan aktif koleksiyon (tenant içinde)."""
    hedef = _katla(KOLEKSIYON_ADI)
    for c in db.scalars(select(CatalogCollection).where(
            CatalogCollection.tenant_id == tenant_id,
            CatalogCollection.is_active.is_(True))).all():
        if _katla(c.title) == hedef:
            return c
    return None


def katalog(db: Session, tenant_id) -> list[dict]:
    """[{kategori, urunler:[{id, ad, gorsel, ara}]}] — koleksiyon yoksa boş liste.

    `ara`: arama için katlanmış metin; istemci bunun üzerinden filtreler,
    böylece "türk" yazan da "TÜRK" yazan da bulur.
    """
    koll = koleksiyon(db, tenant_id)
    if koll is None:
        return []

    urunler = db.scalars(
        select(CatalogProduct)
        .join(catalog_product_collections,
              catalog_product_collections.c.product_id == CatalogProduct.id)
        .where(catalog_product_collections.c.collection_id == koll.id,
               CatalogProduct.status == "active")
        .options(selectinload(CatalogProduct.images))
        .order_by(CatalogProduct.title)
    ).all()

    # Gruplama anahtarı katlanmış ad; gösterilen etiket ise o grupta EN SIK
    # geçen özgün yazım (ÖZEL TASARIM ile OZEL TASARIM tek grup, etiket düzgün).
    gruplar: dict[str, dict] = {}
    for p in urunler:
        ad = seri_adi(p.title) or "Diğer"
        k = _katla(ad)
        g = gruplar.setdefault(k, {"etiketler": {}, "urunler": []})
        g["etiketler"][ad] = g["etiketler"].get(ad, 0) + 1
        g["urunler"].append({
            "id": str(p.id),
            "ad": kisa_ad(p.title),
            "tam_ad": p.title,
            "gorsel": _urun_gorseli(p),
            "ara": _katla(p.title),
        })

    cikti = []
    for k, g in gruplar.items():
        etiket = max(g["etiketler"].items(), key=lambda kv: kv[1])[0]
        cikti.append({"kategori": etiket, "urunler": g["urunler"]})

    # Çok ürünlü kategoriler önde; "Diğer" her zaman en sonda.
    cikti.sort(key=lambda g: (g["kategori"] == "Diğer", -len(g["urunler"]),
                              _katla(g["kategori"])))
    return cikti


def urun_dogrula(db: Session, tenant_id, urun_id: str) -> CatalogProduct | None:
    """Seçilen ürün GERÇEKTEN bu koleksiyonda mı? (istek elle atılabilir)"""
    koll = koleksiyon(db, tenant_id)
    if koll is None:
        return None
    return db.scalar(
        select(CatalogProduct)
        .join(catalog_product_collections,
              catalog_product_collections.c.product_id == CatalogProduct.id)
        .where(catalog_product_collections.c.collection_id == koll.id,
               CatalogProduct.id == urun_id,
               CatalogProduct.status == "active")
    )
