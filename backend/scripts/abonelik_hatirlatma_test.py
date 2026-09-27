#!/usr/bin/env python3
"""Abonelik hatırlatma e-postaları — services/abonelik_hatirlatma.py.

Gerçek e-posta GÖNDERİLMEZ: gönderim fonksiyonu yakalanır. Kendi verisini
kurar; servis commit etse de işlem sonunda geri alınır (commit → flush).

Koşum: cd backend && .venv/bin/python scripts/abonelik_hatirlatma_test.py
"""
import sys
import uuid
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import Plan, PlatformAyari, Tenant, User  # noqa: E402
from app.services import abonelik_hatirlatma as ah  # noqa: E402
from app.services import email_service  # noqa: E402

GECTI = KALDI = 0
GIDEN: list[dict] = []
BASARISIZ_KALAN = 0   # >0 iken gönderimler başarısız döner


def kontrol(ad, gercek, beklenen):
    global GECTI, KALDI
    if gercek == beklenen:
        GECTI += 1
        print(f"  ✓ {ad}")
    else:
        KALDI += 1
        print(f"  ✗ {ad}\n      beklenen: {beklenen!r}\n      gercek  : {gercek!r}")


def sahte_gonder(to, subject, html, text=None, headers=None):
    global BASARISIZ_KALAN
    if BASARISIZ_KALAN > 0:
        BASARISIZ_KALAN -= 1
        return email_service.Sonuc(False, "resend", None, "test: sağlayıcı hatası")
    GIDEN.append({"to": to, "subject": subject, "html": html})
    return email_service.Sonuc(True, "resend", f"msg-{uuid.uuid4().hex[:8]}")


def kos(db, bugun):
    GIDEN.clear()
    return ah.hatirlatmalari_gonder(db, bugun=bugun)


def main() -> int:
    global BASARISIZ_KALAN
    email_service.send_email_ex = sahte_gonder
    db = SessionLocal()
    db.commit = db.flush          # servis commit etse de sonunda geri alınsın
    ek = uuid.uuid4().hex[:6]
    bugun = date(2026, 9, 27)
    try:
        ucretli = Plan(kod=f"ucr-{ek}", ad="Standart Test", aylik_ucret=Decimal("1000"),
                       komisyon_orani=Decimal("0"), moduller=["magaza"])
        ucretsiz = Plan(kod=f"ucz-{ek}", ad="Ücretsiz Test", moduller=["magaza"])
        db.add_all([ucretli, ucretsiz])
        # Havale bilgisi işlem içinde yazılır (varsa üzerine) — sonunda geri alınır
        havale = {"alici": "Test Ltd", "banka": "Test Bank", "iban": "TR330006100519786457841326"}
        kayit = db.get(PlatformAyari, "havale")
        if kayit is None:
            db.add(PlatformAyari(anahtar="havale", deger=havale))
        else:
            kayit.deger = havale
        db.flush()

        def kiraci(ad, plan, bitis, aktif=True):
            t = Tenant(name=ad, slug=f"{ad.lower()}-{ek}", plan="x", plan_id=plan.id,
                       active_until=bitis, is_active=aktif)
            db.add(t)
            db.flush()
            for rol, n in (("owner", 1), ("owner", 2), ("yonetici", 3)):
                db.add(User(tenant_id=t.id, email=f"{rol}{n}-{t.slug}@ornek.com", full_name=rol,
                            role=rol, is_active=True, password_hash="x"))
            db.flush()
            db.refresh(t)
            return t

        a = kiraci("Yaklasan", ucretli, bugun + timedelta(days=5))
        b = kiraci("Erken", ucretli, bugun + timedelta(days=6))
        kiraci("Ucretsiz", ucretsiz, bugun - timedelta(days=3))
        kiraci("Elleaskida", ucretli, bugun - timedelta(days=3), aktif=False)

        print("── 5 gün kala ──")
        kos(db, bugun)
        alicilar = sorted(g["to"] for g in GIDEN)
        kontrol("yalnız 5 gün kalan kiracının SAHİPLERİNE gider",
                alicilar, sorted([f"owner1-{a.slug}@ornek.com", f"owner2-{a.slug}@ornek.com"]))
        html = GIDEN[0]["html"] if GIDEN else ""
        kontrol("tutar Türkçe biçimde", "1.000,00 TL" in html, True)
        kontrol("IBAN 4'lü gruplu", "TR33 0006 1005" in html, True)
        kontrol("havale açıklama kodu = mağaza kodu", a.slug in html, True)
        kontrol("düğme abonelik sayfasına", "/abonelik" in html, True)
        kos(db, bugun)
        kontrol("aynı gün ikinci kez gitmez", len(GIDEN), 0)
        kos(db, bugun + timedelta(days=2))
        kontrol("aynı dönemde aşama değişmeden tekrar gitmez",
                len([g for g in GIDEN if a.slug in g["to"]]), 0)
        kontrol("o gün 4 günü kalan diğer kiracıya gider",
                len([g for g in GIDEN if b.slug in g["to"]]), 2)

        print("── gecikme aşamaları ──")
        kos(db, a.active_until + timedelta(days=2))
        kontrol("ek süre e-postası", {g["subject"] for g in GIDEN if a.slug in g["to"]},
                {"Aboneliğinizin süresi doldu"})
        kos(db, a.active_until + timedelta(days=9))
        kontrol("salt okunur e-postası", {g["subject"] for g in GIDEN if a.slug in g["to"]},
                {"Paneliniz salt okunur duruma geçti"})
        kos(db, a.active_until + timedelta(days=20))
        konu = {g["subject"] for g in GIDEN if a.slug in g["to"]}
        kontrol("vitrin kapandı e-postası", konu, {"Vitrininiz kapatıldı"})

        print("── ödeme sonrası yeni dönem ──")
        a.active_until = bugun + timedelta(days=35)
        db.flush()
        kos(db, bugun + timedelta(days=31))
        kontrol("yeni dönemin 5-gün hatırlatması yeniden gider",
                len([g for g in GIDEN if a.slug in g["to"]]), 2)

        print("── gönderilmeyenler ──")
        kos(db, bugun)
        kontrol("ücretsiz plana ve elle askıya alınmışa gitmez",
                [g["to"] for g in GIDEN if "ucretsiz" in g["to"] or "elleaskida" in g["to"]], [])

        print("── başarısız gönderim ──")
        c = kiraci("Hatali", ucretli, bugun + timedelta(days=60))
        BASARISIZ_KALAN = 2
        s = kos(db, c.active_until - timedelta(days=5))
        kontrol("sağlayıcı hatası sayılır", (s["basarisiz"], len([g for g in GIDEN if c.slug in g["to"]])), (2, 0))
        kos(db, c.active_until - timedelta(days=4))
        kontrol("ertesi gün yeniden denenir", len([g for g in GIDEN if c.slug in g["to"]]), 2)
    finally:
        db.rollback()
        db.close()

    print(f"\nGECTI: {GECTI}   KALDI: {KALDI}")
    return 1 if KALDI else 0


if __name__ == "__main__":
    sys.exit(main())
