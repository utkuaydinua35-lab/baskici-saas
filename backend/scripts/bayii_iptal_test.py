"""Bayi iptal KURALI — saf fonksiyon testi (veritabanı yok).

İade edilip edilmeyeceğine ve kalıbın silinip silinmeyeceğine burası karar
veriyor; parası olan tek yer bu, o yüzden ayrı ve hızlı sınanıyor.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.bayii_iptal import durum_belirle  # noqa: E402

GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}, gercek {gercek!r}")


print("\n── A) Kaliba girmemis ──")
d = durum_belirle([])
es("talep gerekmez", False, d.talep_gerekir)
es("talep acilabilir", True, d.talep_acilabilir)
es("iade edilir", True, d.iade_edilir)
es("silinecek kalip yok", False, d.kaliplar_silinir)

print("\n── B) Kalipta, TAMAMLANMAMIS ──")
for asama, ad in [(1, "taslak"), (2, "hazir"), (3, "baskiya gonderildi"), (4, "baskida")]:
    d = durum_belirle([asama])
    es(f"{ad}: talep gerekir", True, d.talep_gerekir)
    es(f"{ad}: talep acilabilir", True, d.talep_acilabilir)
    es(f"{ad}: IADE edilir", True, d.iade_edilir)
    es(f"{ad}: kalip SILINIR", True, d.kaliplar_silinir)

print("\n── C) Kalipta, TAMAMLANMIS ──")
d = durum_belirle([5])
es("talep gerekir", True, d.talep_gerekir)
es("talep ACILAMAZ", False, d.talep_acilabilir)
es("iade EDILMEZ", False, d.iade_edilir)
es("kalip SILINMEZ", False, d.kaliplar_silinir)

print("\n── Karisik: bir kalibi basilmis, digeri degil ──")
# Coklu urunde kalemler farkli kaliplara dagilabilir. TEK kalem bile
# basildiysa malzeme harcanmistir -> iade yok, silme yok.
d = durum_belirle([2, 5])
es("iade EDILMEZ", False, d.iade_edilir)
es("kalip SILINMEZ", False, d.kaliplar_silinir)
es("talep acilamaz", False, d.talep_acilabilir)

d = durum_belirle([2, 3, 4])
es("hicbiri basilmadi -> iade", True, d.iade_edilir)
es("hicbiri basilmadi -> silinir", True, d.kaliplar_silinir)

print("\n── Bozuk veri ──")
es("None asama basilmis sayilmaz", True, durum_belirle([None]).iade_edilir)
es("0 asama basilmis sayilmaz", True, durum_belirle([0]).iade_edilir)
es("6 (ileri asama) basilmis sayilir", False, durum_belirle([6]).iade_edilir)

print(f"\n{'='*44}\nGECTI: {GECTI}   KALDI: {KALDI}\n{'='*44}")
sys.exit(1 if KALDI else 0)
