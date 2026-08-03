"""Code 128-B barkod kodlayıcı — bağımlılıksız, çizim motorundan bağımsız.

Kargo etiketindeki barkodun TARANABİLİR olması gerekiyor (eski etiket kodu
'*ABC*' diye düz metin yazıyordu, okutulamıyordu).

pattern_widths() modül genişliklerini döner: [bar, boşluk, bar, ...] sırasıyla,
ilk eleman HER ZAMAN bar. Çizen taraf 1 modül = kaç pt olduğuna kendi karar verir.
"""
from __future__ import annotations

# Code 128 desen tablosu: her değer 6 modül genişliği (stop 7).
# Her desen (stop hariç) toplam 11 modüldür — _dogrula() bunu sınar.
_PATTERNS = [
    "212222", "222122", "222221", "121223", "121322", "131222", "122213", "122312",
    "132212", "221213", "221312", "231212", "112232", "122132", "122231", "113222",
    "123122", "123221", "223211", "221132", "221231", "213212", "223112", "312131",
    "311222", "321122", "321221", "312212", "322112", "322211", "212123", "212321",
    "232121", "111323", "131123", "131321", "112313", "132113", "132311", "211313",
    "231113", "231311", "112133", "112331", "132131", "113123", "113321", "133121",
    "313121", "211331", "231131", "213113", "213311", "213131", "311123", "311321",
    "331121", "312113", "312311", "332111", "314111", "221411", "431111", "111224",
    "111422", "121124", "121421", "141122", "141221", "112214", "112412", "122114",
    "122411", "142112", "142211", "241211", "221114", "413111", "241112", "134111",
    "111242", "121142", "121241", "114212", "124112", "124211", "411212", "421112",
    "421211", "212141", "214121", "412121", "111143", "111341", "131141", "114113",
    "114311", "411113", "411311", "113141", "114131", "311141", "411131",
    "211412",   # 103 Start A
    "211214",   # 104 Start B
    "211232",   # 105 Start C
    "2331112",  # 106 Stop
]

START_B = 104
STOP = 106


class BarcodeError(Exception):
    pass


def _dogrula() -> None:
    """Tablo bütünlüğü — elle yazılmış sabit, dizgi hatası sessizce okunamayan
    barkod üretir. İçe aktarmada bir kez sınanır."""
    if len(_PATTERNS) != 107:
        raise BarcodeError("Code128 tablosu eksik")
    for i, p in enumerate(_PATTERNS[:-1]):
        if len(p) != 6 or sum(int(c) for c in p) != 11:
            raise BarcodeError(f"Code128 deseni bozuk: index {i} = {p}")
    if sum(int(c) for c in _PATTERNS[STOP]) != 13:
        raise BarcodeError("Code128 stop deseni bozuk")


_dogrula()


def temizle(text: str) -> str:
    """Code128-B yalnızca ASCII 32..126 taşır; diğerlerini at."""
    return "".join(ch for ch in (text or "") if 32 <= ord(ch) <= 126)


def pattern_widths(text: str) -> list[int]:
    """Metni Code128-B olarak kodla; modül genişlikleri listesi döner.

    Sıra: bar, boşluk, bar, ... (ilk eleman bar). Sessiz alan (quiet zone)
    ÇAĞIRANIN sorumluluğu — en az 10 modül boşluk bırakılmalı.
    """
    veri = temizle(text)
    if not veri:
        raise BarcodeError("Barkod metni boş")
    kodlar = [START_B] + [ord(ch) - 32 for ch in veri]
    # Kontrol basamağı: start + sum(pozisyon * deger), mod 103
    toplam = START_B + sum(i * (ord(ch) - 32) for i, ch in enumerate(veri, start=1))
    kodlar.append(toplam % 103)
    kodlar.append(STOP)
    return [int(c) for k in kodlar for c in _PATTERNS[k]]


def toplam_modul(text: str) -> int:
    return sum(pattern_widths(text))
