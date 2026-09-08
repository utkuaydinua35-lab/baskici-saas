"""Kupon kullanım sayacı limiti aşabiliyor mu?

BULGU (2026-09-08): limit checkout AÇILIRKEN kontrol ediliyor, sayaç ise
ödeme DOĞRULANINCA artıyor. Arada 2 saatlik oturum ömrü var. Aynı kuponla
N oturum açıp hepsini ödeyen biri tek kullanımlık kuponu N kez kullanabilir
(eşzamanlı checkout yarışı).

Sömürü saldırgana N GERÇEK ödeme yaptırdığı için kazancı (N-1)×indirimle
sınırlı — klasik bir güvenlik açığından çok iş mantığı sızıntısı. Ödeme
alındıktan sonra reddedilemeyeceği için burada iki şey yapılıyor:
  1) sayaç limiti AŞMASIN (koşullu artırım),
  2) aşım olursa işletme Telegram'dan haberdar edilsin.

Bu test 1. maddeyi sınar: sayaç hiçbir koşulda usage_limit'i geçmemeli.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import or_, select, text, update  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import DiscountCode, Store  # noqa: E402

GECTI = KALDI = 0
IZ = uuid.uuid4().hex[:6]


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


db = SessionLocal()
store = db.scalar(select(Store).where(Store.platform == "storefront"))
if not store:
    raise SystemExit("Vitrin magazasi YOK — test calisamaz.")

kupon = DiscountCode(tenant_id=store.tenant_id, store_id=store.id,
                     code=f"TEST{IZ}".upper(), kind="amount", value=50,
                     usage_limit=1, usage_count=0, is_active=True)
db.add(kupon); db.commit()
KID = kupon.id


def artir() -> int:
    """storefront_order'daki KOŞULLU artırımın aynısı."""
    r = db.execute(
        update(DiscountCode)
        .where(DiscountCode.id == KID,
               or_(DiscountCode.usage_limit.is_(None),
                   DiscountCode.usage_count < DiscountCode.usage_limit))
        .values(usage_count=DiscountCode.usage_count + 1))
    db.commit()
    return r.rowcount


def sayac() -> int:
    db.expire_all()
    return db.get(DiscountCode, KID).usage_count


print("\n── tek kullanımlık kupon, EŞZAMANLI beş ödeme ──")
sonuclar = [artir() for _ in range(5)]
es("yalnız BİRİ sayacı artırdı", 1, sum(sonuclar))
es("sayaç limiti aşmadı", 1, sayac())
es("kalan dördü tespit edildi (uyarı tetiklenir)", 4, sonuclar.count(0))

print("\n── limitsiz kupon her zaman artmalı ──")
db.execute(update(DiscountCode).where(DiscountCode.id == KID)
           .values(usage_limit=None, usage_count=0))
db.commit()
es("limitsizde beş artış da geçti", 5, sum(artir() for _ in range(5)))
es("sayaç 5", 5, sayac())

print("\n── limit 3: tam üç kez ──")
db.execute(update(DiscountCode).where(DiscountCode.id == KID)
           .values(usage_limit=3, usage_count=0))
db.commit()
es("üç artış geçti", 3, sum(artir() for _ in range(6)))
es("sayaç tam 3", 3, sayac())

db.execute(text("delete from discount_codes where id=:i"), {"i": str(KID)})
db.commit()

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
