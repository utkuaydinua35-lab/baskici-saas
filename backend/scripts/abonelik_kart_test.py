#!/usr/bin/env python3
"""Kiracının kartla abonelik ödemesi (Faz 4) — routers/abonelik.py + services/abonelik_kart.py.

iyzico'ya GERÇEK istek gitmez: IyzicoProvider._post taklit edilir, Telegram
bildirimi yakalanır. Güven yalnız sunucudan iyzico'ya sorulan doğrulamaya
dayanmalı: tutar, conversationId, durum. Geçici kiracı kurar, sonunda SİLER.

Koşum: cd backend && .venv/bin/python scripts/abonelik_kart_test.py
"""
import sys
import uuid
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402

from app.auth.security import create_access_token, hash_password  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import AbonelikOdemesi, Plan, Tenant, User  # noqa: E402
from app.payments.iyzico import IyzicoProvider  # noqa: E402
from app.services import abonelik, telegram  # noqa: E402

GECTI = KALDI = 0
ISTEKLER: list[tuple] = []          # (api_key, yol, gövde)
DETAY: dict = {}                   # sıradaki "detail" yanıtı
TELEGRAM: list[str] = []


def kontrol(ad, kosul, bilgi=""):
    global GECTI, KALDI
    if kosul:
        GECTI += 1
        print(f"  ✓ {ad}")
    else:
        KALDI += 1
        print(f"  ✗ {ad}  → {bilgi}")


def sahte_post(self, yol, govde):
    ISTEKLER.append((self.api_key, yol, govde))
    if yol.endswith("/initialize/auth/ecom"):
        return {"status": "success", "paymentPageUrl": "https://sandbox.ornek/odeme", "token": "tok"}
    return dict(DETAY)


def onayli(kayit, tutar=None, **kw):
    return {"status": "success", "paymentStatus": "SUCCESS", "conversationId": str(kayit.id),
            "paidPrice": str(tutar if tutar is not None else kayit.toplam),
            "paymentId": "PAY-" + uuid.uuid4().hex[:6], **kw}


def main() -> int:
    IyzicoProvider._post = sahte_post
    telegram.send_message = lambda metin: TELEGRAM.append(metin) or True
    ayar = get_settings()
    eski_ayar = (ayar.iyzico_platform_api_key, ayar.iyzico_platform_secret_key)
    db = SessionLocal()
    ek = uuid.uuid4().hex[:6]
    bugun = date.today()
    plan = Plan(kod=f"kart-{ek}", ad="Kart Test", aylik_ucret=Decimal("990"),
                komisyon_orani=Decimal("0"), moduller=["magaza"])
    db.add(plan)
    db.flush()
    t = Tenant(name=f"Kart {ek}", slug=f"kart-{ek}", plan="x", plan_id=plan.id,
               active_until=bugun + timedelta(days=3))
    db.add(t)
    db.flush()
    u = User(tenant_id=t.id, email=f"sahip-{ek}@ornek.com", full_name="Ayşe Yılmaz", role="owner",
             is_active=True, password_hash=hash_password("x" * 12))
    db.add(u)
    db.commit()
    H = {"Authorization": "Bearer " + create_access_token(
        user_id=str(u.id), tenant_id=str(t.id), email=u.email)}
    c = TestClient(app)

    def kayitlar():
        db.expire_all()
        return db.scalars(select(AbonelikOdemesi).where(AbonelikOdemesi.tenant_id == t.id)
                          .order_by(AbonelikOdemesi.created_at)).all()

    try:
        print("── anahtar yokken ──")
        ayar.iyzico_platform_api_key = ayar.iyzico_platform_secret_key = ""
        d = c.get("/api/abonelik", headers=H).json()
        kontrol("'Kartla öde' kapalı", d["kart_acik"] is False, d.get("kart_acik"))
        r = c.post("/api/abonelik/kart", headers=H, json={"ay_sayisi": 1, "beklenen_toplam": "990.00"})
        kontrol("başlatma 503", r.status_code == 503, r.status_code)

        ayar.iyzico_platform_api_key, ayar.iyzico_platform_secret_key = "PLATFORM-KEY", "PLATFORM-SECRET"
        print("── başlatma ──")
        d = c.get("/api/abonelik?ay_sayisi=3", headers=H).json()
        kontrol("'Kartla öde' açık", d["kart_acik"] is True, d.get("kart_acik"))
        kontrol("3 ay peşin tahmini", d["tahmin"]["toplam"] == "2970.00", d["tahmin"]["toplam"])
        r = c.post("/api/abonelik/kart", headers=H, json={"ay_sayisi": 1, "beklenen_toplam": "1.00"})
        kontrol("ekrandakinden farklı tutar reddedilir (409)", r.status_code == 409, r.status_code)
        ISTEKLER.clear()
        r = c.post("/api/abonelik/kart", headers=H, json={"ay_sayisi": 1, "beklenen_toplam": "990.00"})
        kontrol("ödeme sayfası adresi döner", r.json().get("url") == "https://sandbox.ornek/odeme", r.json())
        k1 = kayitlar()[-1]
        anahtar, yol, govde = ISTEKLER[-1]
        kontrol("PLATFORMUN anahtarıyla gider", anahtar == "PLATFORM-KEY", anahtar)
        kontrol("tutar dondurulur", govde["price"] == govde["paidPrice"] == "990.00", govde["price"])
        kontrol("dönüş adresi kayda özel", govde["callbackUrl"].endswith(f"/api/abonelik/kart/donus/{k1.id}"),
                govde["callbackUrl"])
        kontrol("kayıt 'bekliyor', abonelik henüz uzamadı",
                (k1.durum, db.get(Tenant, t.id).active_until) == ("bekliyor", bugun + timedelta(days=3)),
                (k1.durum, db.get(Tenant, t.id).active_until))

        print("── doğrulanmayan dönüşler ──")
        DETAY.clear()
        DETAY.update(onayli(k1, tutar="1.00"))
        r = c.post(f"/api/abonelik/kart/donus/{k1.id}", data={"token": "x"}, follow_redirects=False)
        kontrol("tutarı tutmayan dönüş → hata sayfası", r.status_code == 303 and "odeme=hata" in r.headers["location"],
                r.headers.get("location"))
        kontrol("abonelik uzamadı", db.get(Tenant, t.id).active_until == bugun + timedelta(days=3))
        kontrol("kayıt başarısız", kayitlar()[-1].durum == "basarisiz", kayitlar()[-1].durum)

        c.post("/api/abonelik/kart", headers=H, json={"ay_sayisi": 1, "beklenen_toplam": "990.00"})
        k2 = kayitlar()[-1]
        DETAY.clear()
        DETAY.update(onayli(k2, conversationId=str(uuid.uuid4())))
        r = c.post(f"/api/abonelik/kart/donus/{k2.id}", data={"token": "x"}, follow_redirects=False)
        kontrol("başka ödemenin onayı kabul edilmez (conversationId)", "odeme=hata" in r.headers["location"])
        c.post("/api/abonelik/kart", headers=H, json={"ay_sayisi": 1, "beklenen_toplam": "990.00"})
        k3 = kayitlar()[-1]
        DETAY.clear()
        DETAY.update({"status": "success", "paymentStatus": "FAILURE", "errorMessage": "Kart reddedildi"})
        r = c.post(f"/api/abonelik/kart/donus/{k3.id}", data={"token": "x"}, follow_redirects=False)
        kontrol("reddedilen kart → hata", "odeme=hata" in r.headers["location"])
        r = c.post(f"/api/abonelik/kart/donus/{uuid.uuid4()}", data={"token": "x"}, follow_redirects=False)
        kontrol("olmayan kayıt → hata", "odeme=hata" in r.headers["location"])

        print("── başarılı ödeme ──")
        c.post("/api/abonelik/kart", headers=H, json={"ay_sayisi": 1, "beklenen_toplam": "990.00"})
        k4 = kayitlar()[-1]
        DETAY.clear()
        DETAY.update(onayli(k4))
        TELEGRAM.clear()
        r = c.post(f"/api/abonelik/kart/donus/{k4.id}", data={"token": "tok"}, follow_redirects=False)
        kontrol("başarı sayfasına döner", "odeme=basarili" in r.headers["location"], r.headers.get("location"))
        db.expire_all()
        kontrol("abonelik uzadı", db.get(Tenant, t.id).active_until == k4.yeni_bitis,
                db.get(Tenant, t.id).active_until)
        kontrol("kayıt ödendi + iyzico ödeme no", (db.get(AbonelikOdemesi, k4.id).durum,
                db.get(AbonelikOdemesi, k4.id).referans.startswith("PAY-")) == ("odendi", True))
        kontrol("Telegram bildirimi", len(TELEGRAM) == 1 and "İnceleme" not in TELEGRAM[0], TELEGRAM)
        bitis = db.get(Tenant, t.id).active_until
        r = c.post(f"/api/abonelik/kart/donus/{k4.id}", data={"token": "tok"}, follow_redirects=False)
        db.expire_all()
        kontrol("dönüş iki kez gelirse iki kez uzatılmaz",
                "odeme=basarili" in r.headers["location"] and db.get(Tenant, t.id).active_until == bitis)
        d = c.get("/api/abonelik", headers=H).json()
        kontrol("kiracı geçmişinde yalnız ödenen kayıt", [o["yontem"] for o in d["odemeler"]] == ["kart"],
                d["odemeler"])

        print("── salt okunur kiracı ödeyebilir ──")
        tt = db.get(Tenant, t.id)
        tt.active_until = bugun - timedelta(days=10)       # salt okunur dönem
        db.commit()
        r = c.post("/api/abonelik/kart", headers=H, json={
            "ay_sayisi": 1, "beklenen_toplam": c.get("/api/abonelik", headers=H).json()["tahmin"]["toplam"]})
        kontrol("salt okunurda da 'Kartla öde' çalışır (402 değil)", r.status_code == 200, r.status_code)
        k5 = kayitlar()[-1]

        print("── arada havale işlenirse ──")
        tt = db.get(Tenant, t.id)
        abonelik.odeme_kaydet(db, tt, yontem="havale")          # yönetici havale girdi
        db.commit()
        havale_sonrasi = db.get(Tenant, t.id).active_until
        DETAY.clear()
        DETAY.update(onayli(k5))
        TELEGRAM.clear()
        c.post(f"/api/abonelik/kart/donus/{k5.id}", data={"token": "tok"}, follow_redirects=False)
        db.expire_all()
        k5 = db.get(AbonelikOdemesi, k5.id)
        kontrol("para çekildiği için ödeme yine işlenir", k5.durum == "odendi", k5.durum)
        kontrol("dönem havale sonrasından devam eder", k5.donem_bas == havale_sonrasi + timedelta(days=1),
                (k5.donem_bas, havale_sonrasi))
        kontrol("kayıt inceleme notu alır", "İnceleme" in (k5.not_ or ""), k5.not_)
        kontrol("yönetici Telegram'da uyarılır", any("İnceleme gerekli" in m for m in TELEGRAM), TELEGRAM)
    finally:
        ayar.iyzico_platform_api_key, ayar.iyzico_platform_secret_key = eski_ayar
        db.rollback()
        db.execute(delete(AbonelikOdemesi).where(AbonelikOdemesi.tenant_id == t.id))
        db.execute(delete(User).where(User.tenant_id == t.id))
        db.execute(delete(Tenant).where(Tenant.id == t.id))
        db.execute(delete(Plan).where(Plan.id == plan.id))
        db.commit()
        db.close()

    print(f"\nGECTI: {GECTI}   KALDI: {KALDI}")
    return 1 if KALDI else 0


if __name__ == "__main__":
    sys.exit(main())
