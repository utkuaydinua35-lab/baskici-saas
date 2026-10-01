"""Vitrin ürün araması — Türkçe harf toleranslı, yazım hatası toleranslı, sıralı.

ESKİ HÂL (canlıda ölçüldü, 2026-10-02): başlık ILIKE '%q%' VEYA herhangi bir
varyant modeli ILIKE '%q%'. Sonuçları:
  • "kilif" 18 sonuç, "kılıf" 595 — Türkçe harfsiz yazan müşteri ürünleri GÖRMÜYORDU
    (telefonda çoğu müşteri böyle yazar); "cicek" 0, "çiçek" 5
  • "ihpone" 0, "anatomik" 0 ("Anatomic Heart" var) — yazım hatası yok
  • "iphone 15" → 624 ürünün hepsi, sırasız (her ürün o modele uyuyor)
  • her arama 191 bin varyant satırını taradı: 1-3.3 sn
YENİ: mağazanın aranabilir metni (ad, etiketler, koleksiyonlar, uyumlu
modeller) bellekte tutulur; arama milisaniyeler sürer. Katalog değişince
düşürülür (vitrin_cache.katalog_degisti), ayrıca TTL güvenlik ağı vardır.

Eşleşme KELİME BAŞINDAN (kelime içinden değil): "sari" → "Sarı" evet,
"Tasarım" HAYIR — ilk denemede kelime içi eşleşme "sari"yi 610 ürüne
yaydı. Yarım kelime (öneki) yalnız SON kelimede (yazarken öneriler) ve 4+
harfli kelimelerde geçerli; "pro" gibi kısa ara kelime tam eşleşmeli —
yoksa "15 pro max" araması "Project Rock"u en üste çıkarıyordu.

Sıra (kelime kelime, HER kelime eşleşmeli):
  ürün adı 3  >  etiket/koleksiyon 2  >  uyumlu model 1
  yazım hatası (bir harf eksik/fazla/yanlış ya da yer değiştirmiş) — yalnız
  tam eşleşme yoksa: adda 1.5, etikette 1.2, modelde 0.8
Hiç sonuç yoksa en az bir kelimesi tutan ürünler gösterilir (boş sayfa yerine).
"""
from __future__ import annotations

import re
import threading
import time
import unicodedata

_TR = str.maketrans({"ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u",
                     "â": "a", "î": "i", "û": "u", "é": "e"})
_TTL_SN = 600


def normalize(metin: str | None) -> str:
    """'İPHONE 15 Kılıf' → 'iphone 15 kilif'. Büyük I/İ ikisi de 'i' olur:
    müşteri "IPHONE" yazınca Türkçe kurala göre "ıphone" olmasın."""
    s = (metin or "").replace("İ", "i").replace("I", "i").lower().translate(_TR)
    s = "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _ucluler(kelime: str) -> set[str]:
    k = f"  {kelime} "
    return {k[i:i + 3] for i in range(len(k) - 2)}


def benzerlik(a: str, b: str) -> float:
    """Kelime benzerliği (trigram Jaccard)."""
    ua, ub = _ucluler(a), _ucluler(b)
    return len(ua & ub) / len(ua | ub) if ua and ub else 0.0


def yakin(a: str, b: str) -> bool:
    """Yazım hatası mı? Damerau-Levenshtein ≤ 1 (4-6 harf) / ≤ 2 (7+ harf):
    'ihpone'→'iphone' (yer değiştirme), 'ferari'→'ferrari', 'anatomik'→'anatomic'."""
    if abs(len(a) - len(b)) > 2 or len(a) < 4:
        return False
    sinir = 1 if len(a) < 7 else 2
    onceki2, onceki = None, list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        simdiki = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            m = 0 if a[i - 1] == b[j - 1] else 1
            simdiki[j] = min(onceki[j] + 1, simdiki[j - 1] + 1, onceki[j - 1] + m)
            if onceki2 is not None and i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                simdiki[j] = min(simdiki[j], onceki2[j - 2] + 1)
        if min(simdiki) > sinir:
            return False
        onceki2, onceki = onceki, simdiki
    return onceki[-1] <= sinir


class _Urun:
    __slots__ = ("id", "ad_kelimeleri", "ek_kelimeleri", "model_kelimeleri")

    def __init__(self, id_, ad, ek, model):
        self.id = id_
        self.ad_kelimeleri = set(ad.split())
        self.ek_kelimeleri = set(ek.split())
        self.model_kelimeleri = set(model.split())


_onbellek: dict[str, tuple[float, list[_Urun]]] = {}
_kilit = threading.Lock()


def dusur() -> None:
    with _kilit:
        _onbellek.clear()


def _dizin(db, store) -> list[_Urun]:
    anahtar = str(store.id)
    simdi = time.monotonic()
    with _kilit:
        kayit = _onbellek.get(anahtar)
        if kayit and simdi - kayit[0] < _TTL_SN:
            return kayit[1]
    from sqlalchemy import text
    satirlar = db.execute(text("""
        SELECT p.id, p.title, coalesce(p.tags, ''),
               coalesce((SELECT string_agg(c.title, ' ')
                         FROM catalog_product_collections pc
                         JOIN catalog_collections c ON c.id = pc.collection_id AND c.is_active
                         WHERE pc.product_id = p.id), ''),
               coalesce((SELECT string_agg(DISTINCT v.model_display, ' | ')
                         FROM catalog_variants v
                         WHERE v.product_id = p.id AND v.is_active), '')
        FROM catalog_products p
        WHERE p.store_id = :sid AND p.status = 'active'
        ORDER BY p.position, p.created_at DESC
    """), {"sid": store.id}).all()
    dizin = [_Urun(r[0], normalize(r[1]), normalize(f"{r[2]} {r[3]}"), normalize(r[4])) for r in satirlar]
    with _kilit:
        _onbellek[anahtar] = (simdi, dizin)
    return dizin


def _tutar(t: str, kelimeler: set[str], onek: bool) -> bool:
    return t in kelimeler or (onek and any(w.startswith(t) for w in kelimeler))


def _kelime_puani(t: str, u: _Urun, bulanik: bool, onek: bool) -> float:
    if _tutar(t, u.ad_kelimeleri, onek):
        return 3.0
    if _tutar(t, u.ek_kelimeleri, onek):
        return 2.0
    if _tutar(t, u.model_kelimeleri, onek):
        return 1.0
    if bulanik:
        for kume, puan in ((u.ad_kelimeleri, 1.5), (u.ek_kelimeleri, 1.2), (u.model_kelimeleri, 0.8)):
            if any(yakin(t, w) for w in kume):
                return puan
    return 0.0


def ara(db, store, sorgu: str) -> list:
    """Sorguya uyan ürün kimlikleri, en alakalıdan başlayarak (eşitlikte panel sırası)."""
    kelimeler = [k for k in normalize(sorgu).split() if k][:8]
    if not kelimeler:
        return []
    dizin = _dizin(db, store)

    son = len(kelimeler) - 1
    # Yarım kelime: son kelime (yazılmakta olan) ya da 4+ harfli kelime
    onekler = [i == son or len(t) >= 4 for i, t in enumerate(kelimeler)]

    def tur(bulanik: bool, hepsi: bool) -> list:
        sonuc = []
        for sira, u in enumerate(dizin):
            puanlar = [_kelime_puani(t, u, bulanik, onekler[i]) for i, t in enumerate(kelimeler)]
            if (all(puanlar) if hepsi else any(puanlar)):
                sonuc.append((-sum(puanlar), sira, u.id))
        sonuc.sort()
        return [x[2] for x in sonuc]

    return tur(False, True) or tur(True, True) or tur(True, False)
