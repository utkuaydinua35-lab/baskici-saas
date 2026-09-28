#!/usr/bin/env python3
"""Gün sınırı — services/gun.py (Europe/Istanbul, tek kaynak).

Gece 00:00–03:00 (İstanbul) arası gelen sipariş İSTANBUL gününe yazılmalı;
eskiden dashboard/analitik UTC gece yarısı kullanıyordu ve bu siparişler düne
düşüyordu (canlıda "bugün" 03:00'te başlıyordu). Saat ELLE verilir — test
günün hangi saatinde koşulursa koşulsun aynı sonucu verir. Veritabanı oturumu
bilerek UTC'ye alınır (CI gibi): gruplama oturum ayarına güvenmemeli.

Koşum: cd backend && .venv/bin/python scripts/gun_siniri_test.py
"""
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import literal, select, text  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.services import gun  # noqa: E402

GECTI = KALDI = 0


def kontrol(ad, gercek, beklenen):
    global GECTI, KALDI
    if gercek == beklenen:
        GECTI += 1
        print(f"  ✓ {ad}")
    else:
        KALDI += 1
        print(f"  ✗ {ad}\n      beklenen: {beklenen!r}\n      gercek  : {gercek!r}")


def main() -> int:
    gece = datetime(2026, 9, 27, 22, 30, tzinfo=timezone.utc)     # İstanbul 28 Eylül 01:30
    ogle = datetime(2026, 9, 28, 10, 0, tzinfo=timezone.utc)      # İstanbul 28 Eylül 13:00

    print("── bugün ──")
    kontrol("UTC 22:30 → İstanbul'da ertesi gün", gun.bugun(gece), date(2026, 9, 28))
    kontrol("öğlen aynı gün", gun.bugun(ogle), date(2026, 9, 28))

    print("── sınırlar ──")
    kontrol("İstanbul 00:00 = UTC 21:00 (önceki gün)", gun.gun_basi(date(2026, 9, 28)),
            datetime(2026, 9, 27, 21, 0, tzinfo=timezone.utc))
    bas, bit = gun.aralik(date(2026, 9, 28), date(2026, 9, 28))
    kontrol("gece 01:30 siparişi 28 Eylül aralığında", bas <= gece < bit, True)
    kontrol("aralık tam 24 saat", (bit - bas).total_seconds(), 86400.0)

    print("── SQL gruplama (oturum UTC'de) ──")
    db = SessionLocal()
    try:
        db.execute(text("SET LOCAL TIME ZONE 'UTC'"))
        g = db.scalar(select(gun.gun_sql(literal(gece))))
        kontrol("gece siparişi İstanbul gününe gruplanır", g.date(), date(2026, 9, 28))
        g = db.scalar(select(gun.gun_sql(literal(datetime(2026, 9, 27, 20, 59, tzinfo=timezone.utc)))))
        kontrol("İstanbul 23:59 hâlâ 27 Eylül", g.date(), date(2026, 9, 27))
    finally:
        db.rollback()
        db.close()

    print(f"\nGECTI: {GECTI}   KALDI: {KALDI}")
    return 1 if KALDI else 0


if __name__ == "__main__":
    sys.exit(main())
