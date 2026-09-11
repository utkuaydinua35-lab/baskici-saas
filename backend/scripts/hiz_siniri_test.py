"""Hız sınırı süreçler (worker'lar) arasında ORTAK mı?

⚠ NEDEN: sayaç her sürecin kendi belleğindeydi. İkinci uvicorn worker'ı açıldığı
gün IP başına hak worker sayısı kadar KATLANACAKTI (giriş kodu 5/5 dk → 10/5 dk).
Sayaç veritabanına taşındı.

İki worker'ı taklit etmek için AYNI kimlikle iki ayrı sınırlayıcı açılır: her
birinin kendi bellek sözlüğü var, ama kararı ortak tablo verir.
"""
from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import HTTPException  # noqa: E402
from sqlalchemy import text  # noqa: E402
from starlette.requests import Request  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.services import rate_limit as rl  # noqa: E402

GECTI = KALDI = 0
AD = "test-ortak-" + uuid.uuid4().hex[:8]


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


def istek(ip: str) -> Request:
    return Request({"type": "http", "headers": [(b"cf-connecting-ip", ip.encode())],
                    "client": ("127.0.0.1", 1)})


def dene(sinirlayici, ip: str) -> int:
    try:
        sinirlayici(istek(ip))
        return 200
    except HTTPException as e:
        return e.status_code


db = SessionLocal()
try:
    print("\n── tablo var ──")
    es("hiz_siniri_vuruslari tablosu", True,
       db.execute(text("select to_regclass('public.hiz_siniri_vuruslari') is not null")).scalar())

    print("\n── iki 'worker' AYNI sayacı paylaşıyor ──")
    worker_a = rl.make_rate_limiter(max_hits=3, window=60.0, ad=AD)
    worker_b = rl.make_rate_limiter(max_hits=3, window=60.0, ad=AD)
    sirali = [dene(w, "10.250.0.1") for w in (worker_a, worker_b, worker_a, worker_b, worker_a)]
    es("ilk 3 istek geçti (hangi worker olursa olsun)", [200, 200, 200], sirali[:3])
    es("4. ve 5. istek 429 — hak KATLANMADI", [429, 429], sirali[3:])

    print("\n── başka IP etkilenmiyor ──")
    es("farklı IP geçer", 200, dene(worker_b, "10.250.0.2"))

    print("\n── pencere dolunca yeniden açılıyor ──")
    kisa = rl.make_rate_limiter(max_hits=1, window=1.0, ad=AD + "-kisa")
    es("ilk istek", 200, dene(kisa, "10.250.0.3"))
    es("hemen ikinci 429", 429, dene(kisa, "10.250.0.3"))
    time.sleep(1.3)
    es("pencere sonrası yine geçer", 200, dene(kisa, "10.250.0.3"))

    print("\n── kimlik koddan türetiliyor (worker'larda aynı) ──")
    k1 = rl.make_rate_limiter(max_hits=5, window=60.0)
    k2 = rl.make_rate_limiter(max_hits=5, window=60.0)
    es("kimlik modül adını taşıyor", True, k1.kimlik.startswith("__main__:"))
    es("farklı satırdaki sınırlayıcılar ayrı kota", True, k1.kimlik != k2.kimlik)

    print("\n── veritabanı yoksa bellek sayacına düşüyor (istek düşmez) ──")
    _gercek = rl._ortak_sayac
    rl._ortak_sayac = lambda *a, **k: None
    try:
        yedek = rl.make_rate_limiter(max_hits=2, window=60.0, ad=AD + "-yedek")
        es("DB yokken de sınır işliyor", [200, 200, 429],
           [dene(yedek, "10.250.0.4") for _ in range(3)])
    finally:
        rl._ortak_sayac = _gercek
finally:
    db.rollback()
    db.execute(text("delete from hiz_siniri_vuruslari where anahtar like :p"), {"p": f"{AD}%"})
    db.commit()
    print("\n  · test vuruşları silindi")

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
