"""select-profile: yönetici profiline kaba kuvvet mümkün mü?

BULGU (2026-09-08): /api/auth/select-profile, aynı tenant'taki bir personel
token'ıyla YÖNETİCİ profiline geçmeyi dener. Geçiş yöneticinin 2FA kodu —
2FA yoksa yöneticinin PAROLASI — ile korunuyor. Ama bu yolda ne
_login_rate_limit ne de _login_record_fail vardı:

  · 2FA'lı yönetici: 6 haneli TOTP sınırsız denenebiliyordu.
  · 2FA'sız yönetici: yöneticinin PAROLASI sınırsız denenebiliyordu —
    /login'deki brute-force korumasının etrafından dolanan bir yol.

Yükselme personelden yöneticiye (aynı kiracı içinde). Profil geçişi zaten
paylaşılan cihaz senaryosu için var; düşük yetkili token ele geçirmek kolay
olan taraf.

Test, sınırlayıcının GERÇEKTEN devreye girdiğini sınar: art arda yanlış
parolayla denenir, bir noktada 429 gelmelidir.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.auth.security import hash_password, verify_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Tenant, User  # noqa: E402

GECTI = KALDI = 0
IZ = uuid.uuid4().hex[:6]


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


db = SessionLocal()
_ad = next((u for u in db.scalars(select(User).where(
    User.role.in_(("yonetici", "owner"))).order_by(User.email)).all()
    if u.password_hash and verify_password("DevAdmin12345!", u.password_hash)), None)
if _ad is None:
    raise SystemExit("Dev sifresiyle girilebilen yonetici YOK — test calisamaz.")
tenant = db.get(Tenant, _ad.tenant_id)

# Ayni tenant'ta DUSUK YETKILI personel — saldirganin elindeki token bu.
personel = User(tenant_id=tenant.id, email=f"prs-{IZ}@bayitest.com",
                full_name="Personel", role="personel", is_active=True,
                password_hash=hash_password("DevPersonel12345!"),
                permissions=["siparisler"])
db.add(personel); db.commit()

C = TestClient(app)


def temizle():
    db.execute(text("delete from login_attempts where ip in ('testclient','127.0.0.1')"))
    db.commit()


temizle()
_t = C.post("/api/auth/login", json={"email": personel.email,
                                     "password": "DevPersonel12345!"})
es("personel giriş yapabildi", 200, _t.status_code)
H = {"Authorization": f"Bearer {_t.json()['access_token']}"}

print("\n── yönetici profiline yanlış parolayla ardışık deneme ──")
temizle()
durumlar = []
for i in range(25):
    r = C.post("/api/auth/select-profile", headers=H,
               json={"user_id": str(_ad.id), "password": f"yanlis-{i}"})
    durumlar.append(r.status_code)
    if r.status_code == 429:
        break

es("hiçbir deneme BAŞARILI olmadı", False, 200 in durumlar)
es("bir noktada 429 (hız sınırı) geldi", True, 429 in durumlar)
print(f"     {len(durumlar)} denemede durdu · durumlar: {durumlar[:12]}…")

print("\n── başarısız deneme KAYDA geçiyor mu (sınırlayıcı bunu sayıyor) ──")
sayi = db.scalar(text("select count(*) from login_attempts "
                      "where reason like '%profil%'")) or 0
es("profil geçişi başarısızlığı kaydedildi", True, sayi > 0)

print("\n── meşru kullanım bozulmadı: kendi profilini seçmek ──")
temizle()
r = C.post("/api/auth/select-profile", headers=H, json={"user_id": str(personel.id)})
es("kendi profilini seçebiliyor", 200, r.status_code)

db.execute(text("delete from login_attempts where ip in ('testclient','127.0.0.1')"))
db.execute(text("delete from users where id=:u"), {"u": str(personel.id)})
db.commit()

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
