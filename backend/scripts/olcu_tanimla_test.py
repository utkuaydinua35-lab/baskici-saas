"""Hata mesajından ölçü tanımlama — kaydedilen ölçüyü PDF motoru BULMALI.

En can sıkıcı hata türü: kullanıcı ölçüyü girer, "kaydedildi" der, ama kalıp
PDF'i hâlâ "ölçüsü tanımlı değil" der. Anahtar üretimi iki tarafta AYNI
fonksiyondan gelmeli — testlerin ağırlığı burada.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.auth.security import verify_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import PhoneModel, Tenant, User  # noqa: E402
from app.services import phone_models as pm  # noqa: E402

C = TestClient(app)
GECTI = KALDI = 0
IZ = uuid.uuid4().hex[:5].upper()
DEV_SIFRE = "DevAdmin12345!"


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


db = SessionLocal()
_adaylar = db.scalars(select(User).where(
    User.role.in_(("yonetici", "owner"))).order_by(User.email)).all()
admin = next((u for u in _adaylar
              if u.password_hash and verify_password(DEV_SIFRE, u.password_hash)), None)
if admin is None:
    raise SystemExit("Dev sifresiyle girilebilen yonetici YOK — test calisamaz.")
tenant = db.get(Tenant, admin.tenant_id)
db.execute(text("delete from login_attempts where ip in ('testclient','127.0.0.1')"))
db.commit()
r = C.post("/api/auth/login", json={"email": admin.email, "password": DEV_SIFRE})
if r.status_code != 200:
    raise SystemExit(f"Giris basarisiz ({r.status_code})")
H = {"Authorization": f"Bearer {r.json()['access_token']}"}

MODEL = f"Samsung Galaxy S{IZ}FE"
U = "/api/phone-models/olcu-tanimla"

print("\n── 1. baştan tanımlama ──")
es("once olcu YOK", None, pm.get_spec(db, tenant.id, MODEL))
r = C.post(U, json={"model": MODEL, "width_cm": 7.6, "height_cm": 16.0,
                    "radius_cm": 1.0}, headers=H)
es("200", 200, r.status_code)
j = r.json()
es("olusturuldu", True, j["olusturuldu"])
es("SUNUCU dogruladi", True, j["dogrulandi"])

print("\n── 2. PDF MOTORU ayni olcuyu buluyor mu? (asıl sınama) ──")
db.expire_all()
es("get_spec buluyor", (7.6, 16.0, 1.0), pm.get_spec(db, tenant.id, MODEL))
from app.services import mold_pdf  # noqa: E402
kutu = {"x0": 0, "y0": 0, "x": 0, "y": 0, "w": 400, "h": 700}
es("yerlesim hesaplaniyor (artik atlanmaz)", True,
   mold_pdf._placement_rect(kutu, MODEL, pm.get_spec(db, tenant.id, MODEL)) is not None)
es("olcusuz model HALA atlanir", None,
   mold_pdf._placement_rect(kutu, "Olmayan Model XYZ", None))

print("\n── 3. mevcut kaydı GÜNCELLER (mükerrer açmaz) ──")
r2 = C.post(U, json={"model": MODEL, "width_cm": 7.8, "height_cm": 16.2,
                     "radius_cm": 1.2}, headers=H)
es("200", 200, r2.status_code)
es("olusturmadi, guncelledi", False, r2.json()["olusturuldu"])
es("ayni kayit", j["id"], r2.json()["id"])
db.expire_all()
es("yeni olcu okunuyor", (7.8, 16.2, 1.2), pm.get_spec(db, tenant.id, MODEL))
es("tek kayit var", 1, len(db.scalars(select(PhoneModel).where(
    PhoneModel.tenant_id == tenant.id,
    PhoneModel.spec_key == pm.normalize_key(MODEL))).all()))

print("\n── 4. korumalar ──")
es("olcusuz istek 422", 422, C.post(U, json={"model": MODEL}, headers=H).status_code)
es("sifir en 422", 422, C.post(U, json={"model": MODEL, "width_cm": 0,
                                        "height_cm": 16.0}, headers=H).status_code)
es("sacma buyuk olcu 422", 422, C.post(U, json={"model": MODEL, "width_cm": 99,
                                                "height_cm": 16.0}, headers=H).status_code)
es("bos model adi 422", 422, C.post(U, json={"model": "", "width_cm": 7,
                                             "height_cm": 16}, headers=H).status_code)
es("kimliksiz istek reddedilir", 401, C.post(U, json={
    "model": MODEL, "width_cm": 7, "height_cm": 16}).status_code)

db.execute(text("delete from phone_models where spec_key = :k"),
           {"k": pm.normalize_key(MODEL)})
db.commit()

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
