"""Destek botu model araması — "İphone 15 pro max" bulunmalı.

BULGU (canlı, 2026-10-13): müşteri "İphone 15 pro max" yazdı, bot "listede
yok" dedi; model 236 üründe vardı. Türkçe İ küçültülünce "i̇" (i + birleşen
nokta) oluyor ve kelime bölünüyordu. Telefon klavyesi cümle başını büyük
yazdığı için müşterilerin çoğu tam böyle yazar.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import model_bul as mb  # noqa: E402

GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


MODELLER = [mb.Model(ad, marka, 10, "Örnek", "ornek") for ad, marka in [
    ("iPhone 15", "Apple"), ("iPhone 15 Plus", "Apple"), ("iPhone 15 Pro", "Apple"),
    ("iPhone 15 Pro Max", "Apple"), ("iPhone 14 Pro Max", "Apple"), ("iPhone 13", "Apple"),
    ("Galaxy S24", "Samsung"), ("Galaxy S24 Plus", "Samsung"), ("Galaxy S24 Ultra", "Samsung"),
    ("Galaxy A54", "Samsung"), ("Oppo A54", "Oppo"), ("Redmi Note 13 Pro 5G", "Xiaomi"),
    ("Redmi Note 13 4G", "Xiaomi"), ("Xiaomi 13T", "Xiaomi"),
]]


def ara(q):
    r = mb.bul(q, MODELLER)
    return [m["model"] for m in r["models"]], r["tahmini"]


print("— birebir (yazılış farkı önemsiz)")
for q in ["İphone 15 pro max", "iphone 15 pro max", "IPHONE 15 PRO MAX", "ıphone 15 pro max",
          "iphone15promax", "İPHONE 15 PRO MAX var mı", "telefonum iphone 15 pro max için kılıf"]:
    es(q, (["iPhone 15 Pro Max"], False), ara(q))
es("samsung s24 ultra → marka eş anlamlısı", (["Galaxy S24 Ultra"], False), ara("samsung s24 ultra"))
es("S24+ → Plus", (["Galaxy S24 Plus"], False), ara("Samsung S24+"))
es("iphone 15 → en yalın model önce", "iPhone 15", ara("iphone 15")[0][0])
es("iphone 15 → 14'ü getirmez", False, "iPhone 14 Pro Max" in ara("iphone 15")[0])
es("a54 → iki markada da", (["Galaxy A54", "Oppo A54"], False), ara("a54"))

print("— yakın (yazım hatası / yarım / okunduğu gibi)")
es("ipone 15 pro", "iPhone 15 Pro", ara("ipone 15 pro")[0][0])
es("ayfon 15 pro maks", ["iPhone 15 Pro Max"], ara("ayfon 15 pro maks")[0])
es("galaksi s24 ultr", (["Galaxy S24 Ultra"], True), ara("galaksi s24 ultr"))
es("galxy a54", (["Galaxy A54"], True), ara("galxy a54"))
es("redmi not 13 pro", ["Redmi Note 13 Pro 5G"], ara("redmi not 13 pro")[0])

print("— sayı HER ZAMAN birebir (yanlış nesil önerilmez)")
es("iphone 99 → yok", ([], True), ara("iphone 99"))
es("iphone 5 → 15'i getirmez", [], ara("iphone 5")[0])
es("olmayan marka", [], ara("nokia 3310")[0])
es("boş / yalnız dolgu kelime", ([], False), ara("kılıf var mı"))

print(f"\n{GECTI} GECTI, {KALDI} KALDI")
sys.exit(1 if KALDI else 0)
