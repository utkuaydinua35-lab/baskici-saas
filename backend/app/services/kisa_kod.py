"""
Kisa kalip kodu: grup+renk -> kullanicinin 3 harfiyle G1..J3 formatinda kod.

Eslesme (blok, numara) — 1-tabanli:
  blok 0 (1. harf):  G1..G9
  blok 1 (2. harf):  H1..H9
  blok 2 (3. harf):  J1..J9
Kullanici "GHJ" girerse -> blok0=G, blok1=H, blok2=J.

Sabit eslesme tablosu (Utku'nun verdigi):
  G1/G2 = iPhone 11 s/b
  G3/G4 = iPhone 13 s/b
  G5/G6 = iPhone 15 s/b
  G7/G8 = 13 pro max (+14plus +16plus) s/b
  G9/H1 = 15/16/17 pro s/b
  H2/H3 = 15/16/17 pro max s/b
  H4 = seffaf
  H5 = parlak
  H6 = redmi
  H7 = xiaomi
  H8 = samsung A+M
  H9 = samsung S
  J1 = samsung ultra
  J2 = diger android
  J3 = magsafe
"""

# grup_kodu (GRUP|RENK ya da ozel) -> (blok_index, numara)
# blok_index: 0=1.harf, 1=2.harf, 2=3.harf
_KOD_TO_SLOT = {
    # iPhone 11
    "IPHONE-11-GROUP|SIYAH": (0, 1), "IPHONE-11-GROUP|BEYAZ": (0, 2),
    # iPhone 13
    "IPHONE-13-GROUP|SIYAH": (0, 3), "IPHONE-13-GROUP|BEYAZ": (0, 4),
    # iPhone 15
    "IPHONE-15-GROUP|SIYAH": (0, 5), "IPHONE-15-GROUP|BEYAZ": (0, 6),
    # 13 pro max + 14 plus + 16 plus (ayni kalip)
    "IPHONE-13-PROMAX-GROUP|SIYAH": (0, 7), "IPHONE-13-PROMAX-GROUP|BEYAZ": (0, 8),
    "IPHONE-14-PLUS-GROUP|SIYAH": (0, 7), "IPHONE-14-PLUS-GROUP|BEYAZ": (0, 8),
    "IPHONE-16-PLUS-GROUP|SIYAH": (0, 7), "IPHONE-16-PLUS-GROUP|BEYAZ": (0, 8),
    # 15/16/17 pro (ayni kalip)  G9 / H1
    "IPHONE-15-PRO-GROUP|SIYAH": (0, 9), "IPHONE-15-PRO-GROUP|BEYAZ": (1, 1),
    "IPHONE-16-PRO-GROUP|SIYAH": (0, 9), "IPHONE-16-PRO-GROUP|BEYAZ": (1, 1),
    "IPHONE-17-PRO-GROUP|SIYAH": (0, 9), "IPHONE-17-PRO-GROUP|BEYAZ": (1, 1),
    # 15/16/17 pro max (ayni kalip)  H2 / H3
    "IPHONE-15-PROMAX-GROUP|SIYAH": (1, 2), "IPHONE-15-PROMAX-GROUP|BEYAZ": (1, 3),
    "IPHONE-16-PROMAX-GROUP|SIYAH": (1, 2), "IPHONE-16-PROMAX-GROUP|BEYAZ": (1, 3),
    "IPHONE-17-PROMAX-GROUP|SIYAH": (1, 2), "IPHONE-17-PROMAX-GROUP|BEYAZ": (1, 3),
    # ozel varyasyonlar
    "SEFFAF": (1, 4),
    "PARLAK": (1, 5),
    "MAGSAFE": (2, 3),
    # android
    "REDMI-GROUP|SIYAH": (1, 6),
    "XIAOMI-GROUP|SIYAH": (1, 7),
    "SAMSUNG-A-GROUP|SIYAH": (1, 8), "SAMSUNG-M-GROUP|SIYAH": (1, 8),
    "SAMSUNG-S-GROUP|SIYAH": (1, 9),
    "SAMSUNG-ULTRA-GROUP|SIYAH": (2, 1),
    # diger android -> J2
    "POCO-GROUP|SIYAH": (2, 2), "OPPO-GROUP|SIYAH": (2, 2), "VIVO-GROUP|SIYAH": (2, 2),
    "REALME-GROUP|SIYAH": (2, 2), "TECNO-GROUP|SIYAH": (2, 2), "HUAWEI-GROUP|SIYAH": (2, 2),
    "OMIX-GROUP|SIYAH": (2, 2), "SAMSUNG-OTHER-GROUP|SIYAH": (2, 2),
}


def kisa_kod(grup_kodu: str, harfler: str = "GHJ") -> str:
    """Grup kodu (GRUP|RENK) -> kisa kod (orn 'G1'). harfler: 3 harf, blok sirasi.
    Eslesme yoksa grup kodunu kisaltarak don (fallback)."""
    if not grup_kodu:
        return "?"
    h = (harfler or "GHJ").strip().upper()
    # 3 harfe tamamla/kirp
    if len(h) < 3:
        h = (h + "GHJ")[:3]
    h = h[:3]
    slot = _KOD_TO_SLOT.get(grup_kodu)
    if slot is None:
        # android beyaz vb. normalize denemesi: |BEYAZ -> |SIYAH
        if "|BEYAZ" in grup_kodu:
            slot = _KOD_TO_SLOT.get(grup_kodu.replace("|BEYAZ", "|SIYAH"))
    if slot is None:
        return grup_kodu.split("|")[0].replace("-GROUP", "")[:4]  # fallback
    blok, numara = slot
    return f"{h[blok]}{numara}"


def kisa_kodlar(grup_kodlari: list, harfler: str = "GHJ") -> list:
    """Birden cok grup kodu -> benzersiz kisa kodlar (sirali)."""
    seen = []
    for gk in grup_kodlari:
        kk = kisa_kod(gk, harfler)
        if kk not in seen:
            seen.append(kk)
    return seen
