"""Forma tasarlayıcıda kulüp/marka adı engeli.

NEDEN: lisanssız üründe kulüp adı basmak marka ihlalidir; forma şablonu tam
da bunun yazılacağı yer. Müşterinin yazdığı isim/numara alanları bu listeden
geçer; eşleşirse tasarım KAYDEDİLMEZ ve müşteriye nedenini söyleriz.

Eşleşme kaçamaklara dayanıklı: büyük/küçük harf, Türkçe harf, boşluk, nokta,
tire ve rakamla harf taklidi (G4L4T4S4R4Y) yok sayılır.
  "Galata Saray", "G.A.L.A.T.A.S.A.R.A.Y", "FENERBAHÇELİ" → engellenir
Kısaltmalar (GS, FB, BJK, TS) yalnız metnin TAMAMI o ise engellenir —
"Gökhan S." gibi baş harfler ve "FB" geçen sıradan kelimeler etkilenmez.

İstemcideki eşi (anında uyarı için): storefront/components/studio/yasak.ts.
Asıl karar BURADA verilir; istemci atlanabilir.
"""
from __future__ import annotations

import re

_TR = str.maketrans({"ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u",
                     "â": "a", "î": "i", "û": "u"})
_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b"})

# Metnin içinde GEÇMESİ yeterli (harfler birleştirildikten sonra)
ICEREN = [
    # Türkiye
    "galatasaray", "fenerbahce", "besiktas", "trabzonspor", "basaksehir",
    "cimbom", "ultraslan", "carsi", "genclerbirligi", "bursaspor", "goztepe",
    "samsunspor", "konyaspor", "sivasspor", "kayserispor", "antalyaspor",
    "alanyaspor", "rizespor", "kasimpasa", "gaziantepfk", "hatayspor",
    "adanademirspor", "eyupspor", "kocaelispor", "sakaryaspor",
    "karsiyaka", "eskisehirspor", "ankaragucu",
    # BİLEREK YOK: "altay", "kartal", "aslan", "kanarya" — yaygın ad/soyad ve
    # sıradan kelime; engellemek gerçek müşteriyi ("Altay", "Aslan") geri çevirir.
    # Avrupa
    "realmadrid", "barcelona", "atleticomadrid", "manchesterunited", "manchestercity",
    "liverpool", "chelsea", "arsenal", "tottenham", "juventus", "acmilan", "intermilan",
    "internazionale", "bayernmunchen", "bayernmunich", "borussiadortmund",
    "parissaintgermain", "ajax", "benfica", "napoli",
    # Kuruluş / lig
    "fifa", "uefa", "superlig", "tff",
]
# Yalnız metnin TAMAMI buysa (kısa kısaltmalar — sıradan metinde yanlış alarm verir)
TAM = ["gs", "fb", "bjk", "ts", "gfk", "psg", "fcb", "rma", "mufc", "mcfc", "lfc"]

MESAJ = ("Bu alana kulüp ya da marka adı yazılamaz — lisanssız üründe basamıyoruz. "
         "Kendi adını, lakabını ya da numaranı yazabilirsin.")


def normalize(metin: str | None) -> str:
    """'G.A.L.A.T.A Saray' → 'galatasaray' (yalnız harf/rakam, Türkçe harfsiz)."""
    s = (metin or "").replace("İ", "i").replace("I", "i").lower().translate(_TR)
    return re.sub(r"[^a-z0-9]+", "", s)


def _ek_normalize(ekler) -> list[str]:
    return [n for n in (normalize(e) for e in (ekler or [])) if len(n) >= 2]


def yasak_mi(metin: str | None, ekler=None) -> bool:
    """Metin yasak bir ad içeriyor mu. ekler: mağazanın eklediği kelimeler."""
    n = normalize(metin)
    if not n:
        return False
    if n in TAM:
        return True
    adaylar = {n, n.translate(_LEET)}       # "g4l4t4s4r4y" → "galatasaray"
    kelimeler = ICEREN + _ek_normalize(ekler)
    return any(k in a for a in adaylar for k in kelimeler)


def ilk_yasak(degerler: dict | None, ekler=None) -> str | None:
    """Alan değerlerinde yasak ada takılan İLK metni döndür (yoksa None).
    `_` ile başlayan anahtarlar (desen/renk seçimleri) metin değildir, atlanır."""
    for k, v in (degerler or {}).items():
        if str(k).startswith("_") or not isinstance(v, str):
            continue
        if yasak_mi(v, ekler):
            return v
    return None
