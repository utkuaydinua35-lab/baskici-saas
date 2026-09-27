#!/usr/bin/env python3
"""Kiralama tahakkuku ve ödeme kaydı — services/abonelik.py (Faz 3).

Para hesabı: yanlış bir satır kiracıya fazla/eksik fatura demek. Kendi
verisini kurar (plan, kiracı, vitrin + Shopify mağazası, siparişler), her şey
TEK işlemde koşar ve sonunda ROLLBACK edilir — veritabanında iz kalmaz.

Koşum: cd backend && .venv/bin/python scripts/abonelik_test.py
"""
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import Order, Plan, Store, Tenant  # noqa: E402
from app.services import abonelik as ab  # noqa: E402

GECTI = KALDI = 0


def kontrol(ad, gercek, beklenen):
    global GECTI, KALDI
    if gercek == beklenen:
        GECTI += 1
        print(f"  ✓ {ad}")
    else:
        KALDI += 1
        print(f"  ✗ {ad}\n      beklenen: {beklenen!r}\n      gercek  : {gercek!r}")


def reddedilir(ad, fn):
    try:
        fn()
        kontrol(ad, "kabul edildi", "reddedildi")
    except ValueError:
        kontrol(ad, "reddedildi", "reddedildi")


def main() -> int:
    db = SessionLocal()
    ek = uuid.uuid4().hex[:6]
    bugun = date(2026, 9, 27)
    try:
        print("── takvim ──")
        kontrol("31 Ocak + 1 ay = 28 Şubat", ab.ay_ekle(date(2026, 1, 31), 1), date(2026, 2, 28))
        kontrol("15 Mart - 1 ay", ab.ay_ekle(date(2026, 3, 15), -1), date(2026, 2, 15))

        plan = Plan(kod=f"test-{ek}", ad="Test Planı", aylik_ucret=Decimal("1000"),
                    komisyon_orani=Decimal("5"), moduller=["magaza"])
        db.add(plan)
        db.flush()
        t = Tenant(name=f"Abonelik {ek}", slug=f"abn-{ek}", plan="x", plan_id=plan.id,
                   active_until=bugun - timedelta(days=3))
        db.add(t)
        db.flush()
        db.refresh(t)
        vitrin = Store(tenant_id=t.id, slug=f"v-{ek}", name="Vitrin", platform="storefront", config={})
        shop = Store(tenant_id=t.id, slug=f"s-{ek}", name="Shopify", platform="shopify", config={})
        db.add_all([vitrin, shop])
        db.flush()

        def siparis(store, gun, tutar, **kw):
            db.add(Order(
                tenant_id=t.id, store_id=store.id, external_id=uuid.uuid4().hex[:12],
                order_number=uuid.uuid4().hex[:8],
                created_at_platform=datetime.combine(gun, datetime.min.time(), tzinfo=timezone.utc)
                + timedelta(hours=12),
                raw={"total_price": str(tutar), "currency": "TRY"}, **kw))

        d = t.active_until
        siparis(vitrin, d - timedelta(days=5), 1000)
        siparis(vitrin, d - timedelta(days=1), 500)
        siparis(vitrin, d - timedelta(days=2), 9999, cancelled_at=datetime.now(timezone.utc))
        siparis(vitrin, d - timedelta(days=2), 8888, financial_status="refunded")
        siparis(vitrin, d - timedelta(days=2), 7777, is_telafi=True)
        siparis(shop, d - timedelta(days=2), 6666)       # Shopify: komisyona girmez
        siparis(vitrin, d - timedelta(days=60), 5555)    # dönem dışı
        db.flush()

        print("── ek süredeki kiracı ──")
        th = ab.tahakkuk_hesapla(db, t, bugun=bugun)
        kontrol("yeni dönem bitişin ertesi günü başlar", th.donem_bas, d + timedelta(days=1))
        kontrol("komisyon dönemi = biten ay", (th.ciro_bas, th.ciro_bit),
                (ab.ay_ekle(d, -1) + timedelta(days=1), d))
        kontrol("ciro yalnız geçerli vitrin satışı (iptal/iade/telafi/Shopify/dönem dışı hariç)",
                th.ciro, Decimal("1500.00"))
        kontrol("sipariş adedi", th.siparis_sayisi, 2)
        kontrol("komisyon %5", th.komisyon, Decimal("75.00"))
        kontrol("toplam", th.toplam, Decimal("1075.00"))

        o1 = ab.odeme_kaydet(db, t, yontem="havale", bugun=bugun)
        db.flush()
        kontrol("ödeme aboneliği uzattı", t.active_until, th.yeni_bitis)

        print("── zincirleme ikinci ödeme, 3 ay peşin ──")
        siparis(vitrin, d + timedelta(days=10), 2000)
        db.flush()
        th2 = ab.tahakkuk_hesapla(db, t, ay_sayisi=3, bugun=bugun)
        kontrol("komisyon dönemi öncekinin ertesinden (boşluk/çift sayım yok)",
                th2.ciro_bas, o1.ciro_bit + timedelta(days=1))
        kontrol("yeni dönem cirosu", th2.ciro, Decimal("2000.00"))
        kontrol("sabit ücret 3 ay", th2.sabit_ucret, Decimal("3000.00"))
        o2 = ab.odeme_kaydet(db, t, yontem="havale", ay_sayisi=3, bugun=bugun)
        db.flush()

        print("── geri alma ──")
        reddedilir("en son olmayan ödeme geri alınamaz", lambda: ab.odeme_iptal(db, o1))
        ab.odeme_iptal(db, o2)
        db.flush()
        kontrol("bitiş eski tarihe döndü", t.active_until, o1.yeni_bitis)
        kontrol("kayıt iptal", o2.durum, "iptal")
        reddedilir("iptal edilmiş kayıt tekrar iptal edilemez", lambda: ab.odeme_iptal(db, o2))

        print("── özel durumlar ──")
        askida = Tenant(name="Askıda", slug=f"ask-{ek}", plan="x", plan_id=plan.id,
                        active_until=bugun - timedelta(days=30))
        suresiz = Tenant(name="Süresiz", slug=f"srz-{ek}", plan="x", plan_id=plan.id)
        plansiz = Tenant(name="Plansız", slug=f"pls-{ek}", plan="x")
        db.add_all([askida, suresiz, plansiz])
        db.flush()
        for x in (askida, suresiz, plansiz):
            db.refresh(x)
        kontrol("vitrini kapanmış kiracının dönemi bugünden başlar",
                ab.tahakkuk_hesapla(db, askida, bugun=bugun).donem_bas, bugun)
        th5 = ab.tahakkuk_hesapla(db, suresiz, bugun=bugun)
        kontrol("süresizden ücretliye geçişte geçmiş ciroya komisyon yok",
                (th5.ciro_bas, th5.komisyon, th5.toplam), (None, Decimal("0.00"), Decimal("1000.00")))
        reddedilir("plansız kiracıya tahakkuk yapılmaz",
                   lambda: ab.tahakkuk_hesapla(db, plansiz, bugun=bugun))
        reddedilir("ay sayısı sınırı", lambda: ab.tahakkuk_hesapla(db, t, ay_sayisi=25, bugun=bugun))
        reddedilir("geçersiz ödeme yöntemi", lambda: ab.odeme_kaydet(db, t, yontem="nakit", bugun=bugun))
    finally:
        db.rollback()
        db.close()

    print(f"\nGECTI: {GECTI}   KALDI: {KALDI}")
    return 1 if KALDI else 0


if __name__ == "__main__":
    sys.exit(main())
