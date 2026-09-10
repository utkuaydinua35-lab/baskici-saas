"""Model değişikliği sayfasındaki alternatif ürün kataloğu.

Müşteri, eksik stok nedeniyle bekleyen kalemini başka bir tasarım ürünüyle
değiştirmek isteyebilir. Ürünler işletmenin oluşturduğu BİR KOLEKSİYONDAN
gelir (bkz. KOLEKSIYON_ADI) — böylece müşteriye yalnız bu iş için uygun
görülen ürünler sunulur.

KAYNAK İKİ YERDE OLABİLİR:
  · Mağaza SHOPIFY'daysa koleksiyon Shopify'da tutulur ve oradan okunur.
    Vitrin (catalog_collections) o mağazada kullanılmıyor.
  · Vitrin mağazasıysa kendi koleksiyon tablosundan okunur.
Önce Shopify denenir, bulunamazsa vitrine düşülür — böylece iki kurulum da
tek kod yoluyla çalışır.

⚠ Shopify çağrısı AĞ üzerinden ve yavaş. Müşteri sayfası her açılışta
Shopify'a gitmemeli; sonuç kısa süreli önbellekte tutulur.

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


# Tırnak çiftleri — SIRA ÖNEMLİ, açan/kapayan AYNI türden olmalı.
# ⚠ Eskiden tek bir "herhangi tırnak" kalıbı vardı ve içindeki kesme
# işaretinde duruyordu: `BERNZ "Don't Panic It's Organic" …` başlığından
# yalnızca "Don" çıkıyordu. Artık her tür kendi eşiyle kapanıyor.
_TIRNAK_CIFTLERI = [
    re.compile(r'"([^"]{2,})"'),      # düz çift tırnak
    re.compile(r"“([^”]{2,})”"),      # eğik çift tırnak
    re.compile(r"‘([^’]{2,})’"),      # eğik tek tırnak (içindeki ' sorun değil)
]
# Düz tek tırnak ancak metinde TAM İKİ tane varsa çift sayılır; aksi halde
# kesme işaretidir ("Editor's Choice" gibi).
_DUZ_TEK = re.compile(r"'([^']{2,})'")
_KARISIK = re.compile(r"[‘'“\"]([^’'”\"]{2,})[’'”\"]")


def kisa_ad(baslik: str) -> str:
    """Izgarada gösterilecek kısa ad.

    Başlıklar uzun ve tekrarlı: `BERNZ "Berserk Hero" Tasarım Telefon Kılıfı -
    Berserk Serisi`. Küçük kartlarda bunun tamamı okunmuyor, üstelik her karta
    aynı "Tasarım Telefon Kılıfı" tekrarı giriyor. Tırnak içindeki tasarım adı
    varsa o kullanılır; yoksa seri eki atılmış başlık.
    """
    b = baslik or ""
    for kalip in _TIRNAK_CIFTLERI:
        m = kalip.search(b)
        if m:
            return m.group(1).strip()
    if b.count("'") == 2:
        m = _DUZ_TEK.search(b)
        if m:
            return m.group(1).strip()
    # Son çare: karışık tırnak (‘911' gibi açan eğik, kapayan düz). Sıkı
    # eşleşmeler tutmadığı için burada kesme işareti riski YOK — kesme işareti
    # olsaydı yukarıdaki kalıplardan biri zaten yakalardı.
    m = _KARISIK.search(b)
    if m:
        return m.group(1).strip()
    m = None
    parcalar = _AYIRAC.split(baslik or "")
    if len(parcalar) > 1 and _katla(parcalar[-1]).endswith(_SERI_SON):
        return _AYIRAC.split(baslik)[0].strip() or (baslik or "").strip()
    return (baslik or "").strip()


# Aile adının başındaki anlamsız kelimeler ("The Serenity Collection" → serenity)
_ATLA = {"the", "bernz", "a", "an"}

# Farklı ailelerin TEK başlık altında toplanması. Aile adı otomatik çıkarılıyor
# ama bazı seriler müşteri gözünde aynı şey; ayrı ayrı durunca çip şeridi
# gereksiz uzuyor. İşletmenin kararı — değiştirmek bu sözlükte bir satır.
# (anahtar: _aile() çıktısı, değer: gösterilecek başlık)
_BIRLESTIR = {
    "pembe": "Estetik",       # Pembe Dünya
    "girly": "Estetik",
    "glow": "Estetik",        # Glow Up
    "melek": "Estetik",
    "sevimli": "Estetik",
    "aura": "Estetik",
    "celestial": "Estetik",
    "meyve": "Estetik",
}


def _aile(seri: str) -> str:
    """Serinin ait olduğu AİLE anahtarı — ilk anlamlı kelime.

    "Vintage Pembe", "Vintage Kolaj", "Vintage Aşk" hepsi tek başlık altında
    toplansın diye. Yüzlerce ürün için 143 ayrı kategori, müşteriye seçmek
    değil aramak gibi geliyordu.
    """
    kelimeler = [k for k in (seri or "").replace("&", " ").split()
                 if _katla(k) and _katla(k) not in _ATLA]
    return _katla(kelimeler[0]) if kelimeler else _katla(seri)


def _tr_baslik(s: str) -> str:
    """TÜMÜ BÜYÜK yazılmış adı okunur hale getirir; karışık yazımı bozmaz.

    "SCARFACE" → "Scarface", "BREAKING BAD" → "Breaking Bad", ama zaten düzgün
    yazılmış "Red Dead Redemption" aynen kalır. Türkçe'de I/İ ayrımı olduğu
    için `.title()` doğrudan kullanılamaz.
    """
    if not s or s != s.upper():
        return s
    # NOT: I → ı (Türkçe kuralı) DEĞİL, I → i uygulanıyor. Sahadaki tümü-büyük
    # seri adlarında I geçen örnekler İngilizce ("BREAKING BAD"); Türkçe kuralı
    # uygulayınca "Breakıng Bad" çıkıyordu. Türkçe adlar zaten noktalı İ ile
    # yazılmış (ANİME, FİLM / DİZİ) ve o doğru dönüşüyor.
    cikti = []
    for kelime in s.split(" "):
        if not kelime:
            continue
        kucuk = kelime.replace("İ", "i").lower()
        ilk = "İ" if kucuk[0] == "i" else kucuk[0].upper()
        cikti.append(ilk + kucuk[1:])
    return " ".join(cikti)


def _aile_etiketi(uyeler: dict[str, int]) -> str:
    """Aileye ortak etiket: üyelerin PAYLAŞTIĞI kelime öneki.

    {"Vintage", "Vintage Pembe", "Vintage Kolaj"} → "Vintage"
    {"Doğa & Botanik", "Doğa & Manzara"}          → "Doğa"
    {"Ozel Tasarim", "Özel Tasarım"}              → "Özel Tasarım"
    Yazım, ürünü en çok olan üyeden alınır (Türkçe karakterli hâli kazansın).
    """
    en_cok = max(uyeler.items(), key=lambda kv: kv[1])[0]
    listeler = [[_katla(k) for k in ad.replace("&", " ").split() if _katla(k)]
                for ad in uyeler]
    ortak = 0
    if listeler:
        for i in range(min(len(x) for x in listeler)):
            if len({x[i] for x in listeler}) == 1:
                ortak += 1
            else:
                break
    if ortak:
        kelimeler = [k for k in en_cok.replace("&", " ").split() if k.strip()]
        return _tr_baslik(" ".join(kelimeler[:ortak]))
    return _tr_baslik(en_cok)


def _urun_gorseli(p: CatalogProduct) -> str | None:
    gorseller = sorted(p.images or [], key=lambda i: (getattr(i, "position", 0) or 0))
    return f"/storage/{gorseller[0].file_path}" if gorseller else None


# ─── Shopify kaynağı ─────────────────────────────────────────────────────
# Koleksiyon içeriği sık değişmiyor; müşteri sayfasını yavaşlatmamak için
# kısa süreli önbellek. (store_id) -> (zaman, urunler)
_ONBELLEK_SN = 600
_onbellek: dict[str, tuple[float, list[dict]]] = {}


def _shopify_urunleri(store) -> list[dict]:
    """Shopify'daki KOLEKSIYON_ADI koleksiyonunun ürünleri; yoksa boş liste."""
    import time

    anahtar = str(store.id)
    simdi = time.time()
    vurus = _onbellek.get(anahtar)
    if vurus and simdi - vurus[0] < _ONBELLEK_SN:
        return vurus[1]

    urunler: list[dict] = []
    try:
        from app.adapters.shopify import ShopifyAdapter

        ad = ShopifyAdapter(store)
        hedef = _katla(KOLEKSIYON_ADI)
        koll = next((c for c in ad.get_collections() if _katla(c["title"]) == hedef), None)
        if koll:
            urunler = ad.get_collection_products(koll["id"])
    except Exception:  # noqa: BLE001 — katalog gelmezse sayfanın gerisi çalışsın
        urunler = []

    _onbellek[anahtar] = (simdi, urunler)
    return urunler


def onbellegi_dusur(store_id=None) -> None:
    """Koleksiyon değiştiğinde elle tazeleme için."""
    if store_id is None:
        _onbellek.clear()
    else:
        _onbellek.pop(str(store_id), None)


def koleksiyon(db: Session, tenant_id) -> CatalogCollection | None:
    """Adı KOLEKSIYON_ADI olan aktif koleksiyon (tenant içinde)."""
    hedef = _katla(KOLEKSIYON_ADI)
    for c in db.scalars(select(CatalogCollection).where(
            CatalogCollection.tenant_id == tenant_id,
            CatalogCollection.is_active.is_(True))).all():
        if _katla(c.title) == hedef:
            return c
    return None


def ham_urunler(db: Session, tenant_id, store=None) -> list[dict]:
    """Koleksiyondaki ürünler: [{id, baslik, gorsel}] — kaynak neresi olursa olsun."""
    if store is not None and (store.platform or "").lower() == "shopify":
        return [{"id": p["id"], "baslik": p["title"], "gorsel": p["image_url"] or None}
                for p in _shopify_urunleri(store) if (p.get("title") or "").strip()]

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
    return [{"id": str(p.id), "baslik": p.title, "gorsel": _urun_gorseli(p)} for p in urunler]


def katalog(db: Session, tenant_id, store=None) -> list[dict]:
    """[{kategori, urunler:[{id, ad, gorsel, ara}]}] — koleksiyon yoksa boş liste.

    `ara`: arama için katlanmış metin; istemci bunun üzerinden filtreler,
    böylece "türk" yazan da "TÜRK" yazan da bulur.
    """
    urunler = ham_urunler(db, tenant_id, store)
    if not urunler:
        return []

    # AİLE bazlı gruplama: "Vintage Pembe" / "Vintage Kolaj" tek "Vintage"
    # başlığı altında. Seri adları çok parçalı; ham hâliyle 143 kategori
    # çıkıyor ve çip şeridi kullanılamaz hâle geliyor.
    gruplar: dict[str, dict] = {}
    for p in urunler:
        baslik = p["baslik"]
        seri = seri_adi(baslik) or "Diğer"
        k = "" if seri == "Diğer" else _BIRLESTIR.get(_aile(seri), _aile(seri))
        g = gruplar.setdefault(k, {"uyeler": {}, "urunler": []})
        g["uyeler"][seri] = g["uyeler"].get(seri, 0) + 1
        g["urunler"].append({
            "id": p["id"],
            "ad": kisa_ad(baslik),
            "tam_ad": baslik,
            "gorsel": p["gorsel"],
            "ara": _katla(baslik),
        })

    cikti, artan = [], []
    for k, g in gruplar.items():
        # Elle birleştirilen ailelerde etiket sözlükten gelir; otomatik
        # çıkarım "Pembe" gibi tek üyenin adını seçerdi.
        etiket = "Diğer" if k == "" else (k if k in _BIRLESTIR.values()
                                          else _aile_etiketi(g["uyeler"]))
        # Tek ürünlü kategoriler çip şeridini şişiriyor ve seçim kolaylığı
        # sağlamıyor — "Diğer"e katılır, aramadan yine bulunur.
        if etiket != "Diğer" and len(g["urunler"]) < 2:
            artan.extend(g["urunler"])
            continue
        cikti.append({"kategori": etiket, "urunler": g["urunler"]})

    if artan:
        diger = next((g for g in cikti if g["kategori"] == "Diğer"), None)
        if diger:
            diger["urunler"].extend(artan)
        else:
            cikti.append({"kategori": "Diğer", "urunler": artan})

    # Çok ürünlü kategoriler önde; "Diğer" her zaman en sonda.
    cikti.sort(key=lambda g: (g["kategori"] == "Diğer", -len(g["urunler"]),
                              _katla(g["kategori"])))
    return cikti


def urun_dogrula(db: Session, tenant_id, urun_id: str, store=None) -> str | None:
    """Seçilen ürün GERÇEKTEN bu koleksiyonda mı? Başlığını döner, yoksa None.

    İstek elle de atılabildiği için sunucu tarafında doğrulanır.
    """
    for p in ham_urunler(db, tenant_id, store):
        if str(p["id"]) == str(urun_id):
            return p["baslik"]
    return None
