"""Destek botu: "Telefonuma uygun kılıf var mı?" — toleranslı model eşleştirme.

ESKİ HÂL (canlı, 2026-10-13): müşteri "İphone 15 pro max" yazdı, bot "listede
kılıf görünmüyor" dedi — oysa o model 236 üründe var. Sebep Türkçe İ:
"İphone".lower() → "i̇phone" (i + birleşen nokta); nokta harf sayılmadığından
kelime "i" + "phone" diye bölünüyor, "iphone" ile eşleşmiyordu. Telefon
klavyesi cümle başını büyük yazdığı için müşterilerin çoğu tam böyle yazar.
"Yok" cevabı alan müşteri çıkıp gider — bu doğrudan satış kaybı.

YENİ: üç kademe, ilk sonuç veren kullanılır.
  1) TAM     — sorgudaki her kelime modelde var (Türkçe harf/büyük-küçük,
               boşluk ve bitişik yazım fark etmez: "iphone15promax", "S24+")
  2) YAKIN   — yazım hatası ve yarım kelime: "ipone 15", "samsng s24 ultr"
  3) ÖNERİ   — tam tutmuyorsa en çok kelimesi tutan modeller ("şunlardan biri mi?")
Sayılar HER kademede birebir tutmalı: "iphone 15" için 14'ü önermek yanlış
kılıf sattırır.
"""
from __future__ import annotations

import re
import time

from app.services.arama import normalize, yakin

# "s24 plus var mı" gibi cümlelerde modele ait olmayan dolgu kelimeleri
DOLGU = {
    "var", "mi", "mu", "midir", "kilif", "kilifi", "kiliflar", "kiliflari", "case",
    "uyumlu", "icin", "telefon", "telefonum", "telefonuma", "telefonumun", "model",
    "modeli", "acaba", "merhaba", "selam", "ve", "ile", "bir", "bende", "benim",
    "ya", "da", "de", "olan", "lazim", "istiyorum", "ariyorum", "cep", "serisi",
}

# Müşterinin kullandığı marka adı ile katalogdaki ad çoğu zaman tutmuyor
# ("samsung s24" ↔ "Galaxy S24"). Marka başına eş anlamlı kelimeler.
MARKA_ESANLAM: dict[str, list[str]] = {
    "samsung": ["galaxy", "samsung"],
    "apple": ["iphone", "apple"],
    "xiaomi": ["xiaomi", "mi", "redmi", "poco"],
    "huawei": ["huawei", "nova", "mate"],
    "honor": ["honor"],
    "oppo": ["oppo", "reno"],
    "vivo": ["vivo"],
    "realme": ["realme"],
    "tecno": ["tecno"],
    "infinix": ["infinix"],
    "reeder": ["reeder"],
    "general mobile": ["general", "mobile", "gm"],
    "google": ["google", "pixel"],
    "oneplus": ["oneplus"],
}

# Okunduğu gibi yazılan marka adları → doğrusu (yazım hatası toleransı bunları
# yakalamaz: "ayfon" ile "iphone" arasında 3 harf fark var)
SESTEN = {
    "ayfon": "iphone", "ayfone": "iphone", "ayfın": "iphone", "ifon": "iphone", "aypon": "iphone",
    "iphon": "iphone", "ipone": "iphone", "iphne": "iphone",
    "galaksi": "galaxy", "galaksy": "galaxy", "samsun": "samsung", "sansung": "samsung",
    "saomi": "xiaomi", "siyomi": "xiaomi", "xiomi": "xiaomi", "xaomi": "xiaomi", "şaomi": "xiaomi",
    "huavei": "huawei", "huvawei": "huawei", "redmı": "redmi", "not": "note", "maks": "max",
    "pilus": "plus", "artı": "plus", "arti": "plus",
}

_PARCA = re.compile(r"[a-z]+|\d+")
_SESTEN = {normalize(a): b for a, b in SESTEN.items()}


def kelimeler(metin: str | None, sozluk: set[str] | None = None) -> list[str]:
    """Metni karşılaştırma kelimelerine indirger.

    'İPHONE15ProMax' → ['iphone', '15', 'pro', 'max'] ; 'S24+' → ['s', '24', 'plus'].
    Harf ve rakam AYRILIR (iki tarafta aynı kural → 's24' ile 's 24' aynı).
    Bitişik yazılmış iki kelime ("promax"), ikisi de katalog sözlüğünde varsa ayrılır.
    """
    s = normalize((metin or "").replace("+", " plus "))
    cikti: list[str] = []
    for k in _PARCA.findall(s):
        if k in DOLGU:
            continue
        k = _SESTEN.get(k, k)
        if sozluk and k.isalpha() and k not in sozluk and len(k) >= 5:
            bolundu = next(((k[:i], k[i:]) for i in range(2, len(k) - 1)
                            if k[:i] in sozluk and k[i:] in sozluk), None)
            if bolundu:
                cikti.extend(bolundu)
                continue
        cikti.append(k)
    return cikti


class Model:
    __slots__ = ("ad", "urun_sayisi", "ornek_baslik", "ornek_slug", "oz", "genis")

    def __init__(self, ad, marka, urun_sayisi, ornek_baslik, ornek_slug):
        self.ad = ad
        self.urun_sayisi = urun_sayisi
        self.ornek_baslik = ornek_baslik
        self.ornek_slug = ornek_slug
        self.oz = kelimeler(ad)                       # modelin kendi kelimeleri
        genis = set(self.oz) | set(kelimeler(marka))
        for anahtar, esler in MARKA_ESANLAM.items():
            if any(e in genis for e in esler) or all(p in genis for p in anahtar.split()):
                genis |= set(esler)
        self.genis = genis                            # + marka ve eş anlamlıları


def _kelime_tutuyor(q: str, m: Model, gevsek: bool) -> bool:
    if q in m.genis:
        return True
    if not gevsek or q.isdigit():
        return False                   # sayı HER ZAMAN birebir: 15 ≠ 14, 5 ≠ 15
    for w in m.genis:
        if w.isdigit():
            continue
        # yarım kelime ("ultr" → ultra) ya da yazım hatası ("ipone" → iphone)
        if (len(q) >= 3 and w.startswith(q)) or yakin(q, w):
            return True
    return False


def bul(sorgu: str, modeller: list[Model], sinir: int = 10) -> dict:
    """Dönüş: {"models": [...], "tahmini": bool}
    tahmini=True → birebir bulunamadı, bunlar yakın eşleşme/öneri (bot
    "şunlardan biri mi?" diye sorar)."""
    sozluk: set[str] = set()
    for m in modeller:
        sozluk |= m.genis
    q = kelimeler(sorgu, sozluk)
    if not q:
        return {"models": [], "tahmini": False}

    def sirala(liste: list[tuple[Model, int]]) -> list[dict]:
        # Az fazlalık = daha isabetli ("iphone 15" → önce "iPhone 15", sonra Pro/Max)
        liste.sort(key=lambda x: (x[1], len(x[0].oz), x[0].ad))
        return [{"model": m.ad, "product_count": m.urun_sayisi,
                 "sample_title": m.ornek_baslik, "sample_slug": m.ornek_slug}
                for m, _ in liste[:sinir]]

    for gevsek in (False, True):
        tutan = [(m, len([w for w in m.oz if w not in q]))
                 for m in modeller if all(_kelime_tutuyor(k, m, gevsek) for k in q)]
        if tutan:
            return {"models": sirala(tutan), "tahmini": gevsek}

    # ÖNERİ: hepsi tutmuyor — en çok kelimesi tutanlar. Sorgudaki sayılar yine
    # birebir tutmalı (yanlış nesil önerme); en az bir harfli kelime de tutmalı.
    sayilar = [k for k in q if k.isdigit()]
    harfliler = [k for k in q if not k.isdigit()]
    oneri = []
    for m in modeller:
        if any(s not in m.genis for s in sayilar):
            continue
        tutan_h = sum(1 for k in harfliler if _kelime_tutuyor(k, m, True))
        if harfliler and tutan_h == 0:
            continue
        if not harfliler and not sayilar:
            continue
        oneri.append((m, (len(harfliler) - tutan_h) * 10 + len([w for w in m.oz if w not in q])))
    return {"models": sirala(oneri)[:6], "tahmini": True}


# ─── Mağaza başına model listesi (bellekte, kısa ömürlü) ─────────────────
# Liste 190 bin varyant satırından GROUP BY ile çıkar (~yüzlerce model);
# her soruda yeniden hesaplamak botu saniyelerce bekletirdi.
_TTL_SN = 600
_onbellek: dict[str, tuple[float, list[Model]]] = {}


def magaza_modelleri(db, store) -> list[Model]:
    from sqlalchemy import func, select

    from app.models import CatalogProduct, CatalogVariant

    anahtar = str(store.id)
    kayit = _onbellek.get(anahtar)
    if kayit and time.monotonic() - kayit[0] < _TTL_SN:
        return kayit[1]
    satirlar = db.execute(
        select(
            CatalogVariant.model_display,
            func.min(CatalogVariant.brand),
            func.count(func.distinct(CatalogProduct.id)),      # VARYANT değil, benzersiz ürün
            func.min(CatalogProduct.title),
            func.min(CatalogProduct.slug),
        )
        .join(CatalogProduct, CatalogVariant.product_id == CatalogProduct.id)
        .where(CatalogProduct.store_id == store.id, CatalogProduct.status == "active",
               CatalogVariant.is_active.is_(True))
        .group_by(CatalogVariant.model_display)
    ).all()
    modeller = [Model(*s) for s in satirlar if s[0]]
    _onbellek[anahtar] = (time.monotonic(), modeller)
    return modeller
