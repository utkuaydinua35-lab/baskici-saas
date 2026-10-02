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


class _Dizin:
    __slots__ = ("zaman", "urunler", "sozluk", "bayat")

    def __init__(self, urunler: list[_Urun]):
        self.zaman = time.monotonic()
        self.urunler = urunler
        # Mağazadaki tüm kelimeler — yazım hatası/önek bir kez burada aranır,
        # ürün ürün değil (canlıda ürün başına karşılaştırma ~1 sn sürüyordu)
        self.sozluk: set[str] = set()
        for u in urunler:
            self.sozluk |= u.ad_kelimeleri | u.ek_kelimeleri | u.model_kelimeleri
        self.bayat = False


_onbellek: dict[str, _Dizin] = {}
_yenileniyor: set[str] = set()
_kilit = threading.Lock()


def dusur() -> None:
    """Katalog değişti: dizin BAYAT işaretlenir, silinmez. Bir sonraki arama
    eskisiyle hemen yanıtlanır, yenisi arkada kurulur — canlıda stok/eşitleme
    sık güncellendiği için silmek her seferinde bir müşteriyi 3-4 sn bekletirdi."""
    with _kilit:
        for d in _onbellek.values():
            d.bayat = True


def _kur(db, store_id) -> _Dizin:
    from sqlalchemy import text
    satirlar = db.execute(text("""
        WITH p AS (
            SELECT id, title, coalesce(tags, '') AS tags, position, created_at
            FROM catalog_products WHERE store_id = :sid AND status = 'active'),
        k AS (
            SELECT pc.product_id, string_agg(c.title, ' ') AS t
            FROM catalog_product_collections pc
            JOIN p ON p.id = pc.product_id
            JOIN catalog_collections c ON c.id = pc.collection_id AND c.is_active
            GROUP BY pc.product_id),
        m AS (
            SELECT v.product_id, string_agg(DISTINCT v.model_display, ' | ') AS t
            FROM catalog_variants v JOIN p ON p.id = v.product_id
            WHERE v.is_active GROUP BY v.product_id)
        SELECT p.id, p.title, p.tags, coalesce(k.t, ''), coalesce(m.t, '')
        FROM p LEFT JOIN k ON k.product_id = p.id LEFT JOIN m ON m.product_id = p.id
        ORDER BY p.position, p.created_at DESC
    """), {"sid": store_id}).all()
    # Ürünlerin çoğu aynı model listesini taşır — bir kez normalleştir
    norm_onbellek: dict[str, str] = {}

    def n(x: str) -> str:
        if x not in norm_onbellek:
            norm_onbellek[x] = normalize(x)
        return norm_onbellek[x]
    return _Dizin([_Urun(r[0], normalize(r[1]), normalize(f"{r[2]} {r[3]}"), n(r[4])) for r in satirlar])


def _arkada_yenile(store_id) -> None:
    anahtar = str(store_id)
    with _kilit:
        if anahtar in _yenileniyor:
            return
        _yenileniyor.add(anahtar)

    def is_() -> None:
        try:
            from app.database import SessionLocal
            with SessionLocal() as db:
                yeni = _kur(db, store_id)
            with _kilit:
                _onbellek[anahtar] = yeni
        except Exception:  # noqa: BLE001 — eski dizinle devam
            pass
        finally:
            with _kilit:
                _yenileniyor.discard(anahtar)
    threading.Thread(target=is_, daemon=True).start()


def _dizin(db, store) -> _Dizin:
    anahtar = str(store.id)
    with _kilit:
        d = _onbellek.get(anahtar)
    if d is None:
        d = _kur(db, store.id)        # ilk kez: mecburen beklenir
        with _kilit:
            _onbellek[anahtar] = d
        return d
    if d.bayat or time.monotonic() - d.zaman > _TTL_SN:
        _arkada_yenile(store.id)
    return d


def ara(db, store, sorgu: str) -> list:
    """Sorguya uyan ürün kimlikleri, en alakalıdan başlayarak (eşitlikte panel sırası)."""
    kelimeler = [k for k in normalize(sorgu).split() if k][:8]
    if not kelimeler:
        return []
    dizin = _dizin(db, store)
    sozluk = dizin.sozluk

    son = len(kelimeler) - 1
    # Yarım kelime: son kelime (yazılmakta olan) ya da 4+ harfli kelime
    tam: list[set[str]] = []
    for i, t in enumerate(kelimeler):
        onek = i == son or len(t) >= 4
        tam.append({w for w in sozluk if w.startswith(t)} if onek else ({t} & sozluk))
    bulanik_onbellek: dict[int, set[str]] = {}

    def bulanik(i: int) -> set[str]:
        if i not in bulanik_onbellek:
            bulanik_onbellek[i] = {w for w in sozluk if yakin(kelimeler[i], w)}
        return bulanik_onbellek[i]

    def puan(u: _Urun, i: int, bulanik_mi: bool) -> float:
        e = tam[i]
        if e:
            if not u.ad_kelimeleri.isdisjoint(e):
                return 3.0
            if not u.ek_kelimeleri.isdisjoint(e):
                return 2.0
            if not u.model_kelimeleri.isdisjoint(e):
                return 1.0
        if bulanik_mi:
            f = bulanik(i)
            if f:
                if not u.ad_kelimeleri.isdisjoint(f):
                    return 1.5
                if not u.ek_kelimeleri.isdisjoint(f):
                    return 1.2
                if not u.model_kelimeleri.isdisjoint(f):
                    return 0.8
        return 0.0

    def tur(bulanik_mi: bool, hepsi: bool) -> list:
        sonuc = []
        for sira, u in enumerate(dizin.urunler):
            puanlar = [puan(u, i, bulanik_mi) for i in range(len(kelimeler))]
            if (all(puanlar) if hepsi else any(puanlar)):
                sonuc.append((-sum(puanlar), sira, u.id))
        sonuc.sort()
        return [x[2] for x in sonuc]

    return tur(False, True) or tur(True, True) or tur(True, False)
