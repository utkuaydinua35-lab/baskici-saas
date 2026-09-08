"""Marka süzgeci önbelleği: doğru mu, gerçekten tasarruf ediyor mu?

BULGU (2026-09-08, CANLI ölçüm): vitrin ürün listesi ucu, marka filtresi
kutusunu doldurmak için HER İSTEKTE mağazanın tüm varyantlarını ürünlerle
birleştiriyordu. EXPLAIN ANALYZE (canlı):

    Parallel Seq Scan on catalog_variants  (rows=63786, loops=3)
    Execution Time: ~103 ms   ·   Buffers: shared hit=3873

pg_stat_user_tables'ta catalog_variants 383 MİLYON satır okumasıyla
veritabanının en büyük I/O tüketicisiydi ve seq_scan sayısı (6003) ürün
listesi istek sayısıyla örtüşüyordu.

Sınananlar:
  · aynı mağaza için sorgu YALNIZ BİR KEZ çalışır (önbellek isabeti),
  · farklı mağazalar birbirinin listesini GÖRMEZ,
  · katalog değişince önbellek düşer,
  · TTL dolunca yeniden hesaplanır.
"""
from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import vitrin_cache  # noqa: E402

GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


A, B = uuid.uuid4(), uuid.uuid4()
sayac = {"a": 0, "b": 0}


def oku_a():
    sayac["a"] += 1
    return ["Apple", "Samsung"]


def oku_b():
    sayac["b"] += 1
    return ["Xiaomi"]


vitrin_cache.markalari_dusur()

print("\n── aynı mağaza: sorgu bir kez çalışmalı ──")
ilk = vitrin_cache.markalar(None, A, oku_a)
for _ in range(20):
    vitrin_cache.markalar(None, A, oku_a)
es("sonuç doğru", ["Apple", "Samsung"], ilk)
es("21 istekte sorgu 1 kez çalıştı", 1, sayac["a"])

print("\n── mağazalar birbirine karışmıyor ──")
es("B kendi listesini aldı", ["Xiaomi"], vitrin_cache.markalar(None, B, oku_b))
es("A hâlâ kendi listesi", ["Apple", "Samsung"], vitrin_cache.markalar(None, A, oku_a))
es("A'nın sorgusu tekrar çalışmadı", 1, sayac["a"])

print("\n── katalog değişince önbellek düşer ──")
vitrin_cache.markalari_dusur()
vitrin_cache.markalar(None, A, oku_a)
es("düşürme sonrası yeniden hesaplandı", 2, sayac["a"])

print("\n── TTL güvenlik ağı ──")
es("TTL 5 dakika", 300, vitrin_cache._MARKA_TTL_SN)
_eski = vitrin_cache._MARKA_TTL_SN
vitrin_cache._MARKA_TTL_SN = 0.05
vitrin_cache.markalar(None, A, oku_a)   # taze, önbellekten
_once = sayac["a"]
time.sleep(0.1)
vitrin_cache.markalar(None, A, oku_a)
es("TTL dolunca yeniden hesaplandı", _once + 1, sayac["a"])
vitrin_cache._MARKA_TTL_SN = _eski
vitrin_cache.markalari_dusur()

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
