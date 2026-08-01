"""Kargo firması listesindeki gönderileri siparişlerle eşleştir (isim + adres).

Kargo export'unda sipariş numarası YOK ve telefon maskeli ('552*****42'), bu
yüzden eşleşme alıcı adı + adres + il/ilçe benzerliği üzerinden yapılır.

Tasarım kararı: BELİRSİZLİKTE TAHMİN YOK. Skor eşiğin altındaysa "eşleşmedi"
denir, ortadaysa "şüpheli" olarak işaretlenip kullanıcı onayına bırakılır.
Yanlış siparişe takip no yazmak müşteriye yanlış bilgi gitmesi demektir.
"""
from __future__ import annotations

from difflib import SequenceMatcher

# Adres gürültüsü — eşleşmeye katkısı yok, çıkarılır.
_ADRES_GURULTU = {
    "mah", "mahalle", "mahallesi", "mh", "cad", "cadde", "caddesi", "cd",
    "sok", "sokak", "sk", "no", "nu", "numara", "daire", "dair", "d", "kat",
    "blok", "blk", "apt", "apartmani", "apartman", "site", "sitesi", "bina",
    "kapi", "giris", "turkiye", "turkey",
}

KESIN_ESIK = 0.80      # bu ve üzeri: otomatik eşleşir
SUPHELI_ESIK = 0.60    # arada: kullanıcı onayına sunulur


def _tr_kucult(s: str) -> str:
    s = (s or "").replace("İ", "i").replace("I", "ı")
    return s.lower().translate(str.maketrans("ığüşöçâîé", "igusocaie"))


def normalize_ad(s: str) -> str:
    """'Meltem Sare KURTTEKİN' -> 'kurttekin meltem sare' (sıra bağımsız)."""
    t = _tr_kucult(s)
    kelimeler = sorted(k for k in "".join(
        ch if ch.isalnum() else " " for ch in t).split() if len(k) > 1)
    return " ".join(kelimeler)


def normalize_adres(s: str) -> str:
    """Adresi karşılaştırılabilir hale getir: gürültü kelimeleri ve noktalama at."""
    t = _tr_kucult(s)
    kelimeler = ["".join(ch for ch in k if ch.isalnum())
                 for k in "".join(ch if ch.isalnum() else " " for ch in t).split()]
    return " ".join(sorted(
        k for k in kelimeler if k and k not in _ADRES_GURULTU and len(k) > 1))


def _benzerlik(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def skorla(siparis: dict, kargo: dict) -> tuple[float, dict]:
    """0..1 arası benzerlik + hangi bileşenden geldiği (şeffaflık için).

    siparis/kargo: {"ad": ..., "adres": ..., "il": ..., "ilce": ...}
    """
    ad = _benzerlik(normalize_ad(siparis.get("ad")), normalize_ad(kargo.get("ad")))
    adres = _benzerlik(normalize_adres(siparis.get("adres")),
                       normalize_adres(kargo.get("adres")))
    _si, _ki = _tr_kucult(siparis.get("il") or ""), _tr_kucult(kargo.get("il") or "")
    _sc, _kc = _tr_kucult(siparis.get("ilce") or ""), _tr_kucult(kargo.get("ilce") or "")
    if _si and _ki and _si == _ki:
        yer = 1.0 if (_sc and _kc and _sc == _kc) else 0.6
    elif not _si or not _ki:
        yer = 0.3      # bilgi yok — ne ödül ne ceza
    else:
        yer = 0.0      # farklı il: güçlü olumsuz sinyal
    toplam = 0.55 * ad + 0.30 * adres + 0.15 * yer
    return toplam, {"ad": round(ad, 3), "adres": round(adres, 3), "yer": round(yer, 3)}


def eslestir(siparisler: list[dict], kargolar: list[dict]) -> list[dict]:
    """Her kargo satırına EN İYİ siparişi ata — bire bir, en yüksek skordan başlayarak.

    siparisler: [{"id", "ad", "adres", "il", "ilce", "etiket"}]
    kargolar:   [{"takip_no", "ad", "adres", "il", "ilce", "tarih"}]
    Dönüş: her kargo satırı için {"kargo", "siparis"|None, "skor", "detay", "durum"}
    """
    ciftler = []
    for ki, k in enumerate(kargolar):
        for si, s in enumerate(siparisler):
            sk, detay = skorla(s, k)
            if sk >= SUPHELI_ESIK:
                ciftler.append((sk, ki, si, detay))
    ciftler.sort(key=lambda x: x[0], reverse=True)

    kullanilan_kargo: set[int] = set()
    kullanilan_siparis: set[int] = set()
    sonuc: dict[int, dict] = {}
    for sk, ki, si, detay in ciftler:
        if ki in kullanilan_kargo or si in kullanilan_siparis:
            continue
        kullanilan_kargo.add(ki)
        kullanilan_siparis.add(si)
        sonuc[ki] = {
            "kargo": kargolar[ki],
            "siparis": siparisler[si],
            "skor": round(sk, 3),
            "detay": detay,
            "durum": "kesin" if sk >= KESIN_ESIK else "supheli",
        }
    return [
        sonuc.get(ki, {"kargo": k, "siparis": None, "skor": 0.0,
                       "detay": {}, "durum": "eslesmedi"})
        for ki, k in enumerate(kargolar)
    ]
