"""Presence ping'i: eşzamanlı ilk ping'ler 500 vermemeli ve kayıt YAZILMALI.

BULGU (canlı günlük, 2026-10-11): sayfa açılışında iki ping aynı anda gelince
ikisi de "satır yok" görüp ekliyor, biri uq_presence_store_key'e takılıp 500
veriyordu. İlk düzeltme denemesi satırı last_seen'siz flush edip NOT NULL'a
takıldı ve hatayı yutarak HİÇBİR ŞEY yazmadı — bu test onu da yakalar.
"""
from __future__ import annotations

import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Store, StorefrontPresence, VitrinOturum  # noqa: E402
from app.routers import public_shop as ps  # noqa: E402

GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


db = SessionLocal()
store = db.scalar(select(Store).where(Store.platform == "storefront", Store.is_active.is_(True)))
if not store:
    print("  · vitrin mağazası yok — atlandı\n\n0 GECTI, 0 KALDI"); sys.exit(0)
slug = store.slug
db.close()
k = "test-" + uuid.uuid4().hex


def ping(yol="/urun/x", sepet=0):
    s = SessionLocal()
    try:
        istek = SimpleNamespace(headers={"x-vitrin-host": "ornek.com"})
        ps.presence_ping(slug, ps.PresenceIn(key=k, path=yol, cart_items=sepet, tik="fbclid", mobil=True),
                         istek, None, s)
        return "ok"
    except Exception as e:  # noqa: BLE001
        return type(e).__name__
    finally:
        s.close()


def say():
    s = SessionLocal()
    try:
        return (s.scalar(select(func.count(StorefrontPresence.id)).where(StorefrontPresence.session_key == k)),
                s.scalar(select(func.count(VitrinOturum.id)).where(VitrinOturum.ziyaretci == k)))
    finally:
        s.close()


try:
    with ThreadPoolExecutor(8) as ex:
        sonuc = set(ex.map(lambda _: ping(), range(8)))
    es("8 eşzamanlı ilk ping: hata yok", {"ok"}, sonuc)
    p, o = say()
    es("presence: tek satır YAZILDI", 1, p)
    es("oturum: TEK kayıt (eşzamanlı ping'ler çift oturum açmaz)", 1, o)
    es("sonraki ping", "ok", ping("/odeme", 2))
    s = SessionLocal()
    o1 = s.scalar(select(VitrinOturum).where(VitrinOturum.ziyaretci == k).order_by(VitrinOturum.son.desc()))
    es("kaynak: Meta reklamı", "meta_reklam", o1.kaynak)
    es("huni: ürün gördü + sepete ekledi + ödemeye geçti", (True, True, True),
       (o1.urun_gordu, o1.sepete_ekledi, o1.odemeye_gecti))
    s.close()
finally:
    s = SessionLocal()
    s.query(VitrinOturum).filter(VitrinOturum.ziyaretci == k).delete()
    s.query(StorefrontPresence).filter(StorefrontPresence.session_key == k).delete()
    s.commit(); s.close()

print(f"\n{GECTI} GECTI, {KALDI} KALDI")
sys.exit(1 if KALDI else 0)
