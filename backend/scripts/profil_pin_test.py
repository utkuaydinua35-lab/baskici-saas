"""Profil seçiminde PIN — kendi profilinde de sorulmalı.

Belirti: PIN atanan profil kendi e-postasıyla giriş yapınca PIN sorulmuyordu
(`target.id != user.id` muafiyeti). Panel PIN atamaya izin verip 🔒 gösterdiği
için bu sessiz bir yanlış güven duygusuydu.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.auth.security import hash_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Tenant, User  # noqa: E402

C = TestClient(app)
GECTI = KALDI = 0
IZ = f"pin{uuid.uuid4().hex[:6]}"
SIFRE = "Profil12345!"


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


db = SessionLocal()
t = db.scalar(select(Tenant).limit(1))


def kullanici(ad, rol, pin=None):
    u = User(tenant_id=t.id, email=f"{IZ}.{ad}@ornek.com",
             password_hash=hash_password(SIFRE), full_name=f"{IZ}-{ad}",
             role=rol, permissions=["paketleme"] if rol != "yonetici" else [],
             pin_hash=hash_password(pin) if pin else None, is_active=True)
    db.add(u); db.flush()
    return u


pinli = kullanici("pinli", "paketlemeci", pin="1234")
pinsiz = kullanici("pinsiz", "paketlemeci")
yonetici = kullanici("admin", "yonetici")
db.commit()


def giris(u):
    r = C.post("/api/auth/login", json={"email": u.email, "password": SIFRE})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def sec(H, hedef, **ek):
    return C.post("/api/auth/select-profile", headers=H,
                  json={"user_id": str(hedef.id), **ek})


print("\n── KENDİ profilini seçerken de PIN sorulur ──")
H = giris(pinli)
es("PIN'siz 401", 401, sec(H, pinli).status_code)
es("yanlis PIN 401", 401, sec(H, pinli, pin="9999").status_code)
es("dogru PIN 200", 200, sec(H, pinli, pin="1234").status_code)

print("\n── BAŞKASININ PIN'li profili (eskiden de korunuyordu) ──")
H2 = giris(pinsiz)
es("PIN'siz 401", 401, sec(H2, pinli).status_code)
es("dogru PIN 200", 200, sec(H2, pinli, pin="1234").status_code)

print("\n── PIN'siz profil serbest ──")
es("kendi profili 200", 200, sec(H2, pinsiz).status_code)
es("baska pinsiz profil 200", 200, sec(H, pinsiz).status_code)

print("\n── Yönetici kendi profilinde parola sorulmaz (değişmedi) ──")
H3 = giris(yonetici)
es("yonetici kendi profili 200", 200, sec(H3, yonetici).status_code)
es("baskasi yoneticiyi parolasiz secemez", 401, sec(H2, yonetici).status_code)

print("\n── /profiles: has_pin doğru ──")
pr = C.get("/api/auth/profiles", headers=H).json()
bul = {p["full_name"]: p for p in pr}
es("pinli profil has_pin=True", True, bul[f"{IZ}-pinli"]["has_pin"])
es("pinsiz profil has_pin=False", False, bul[f"{IZ}-pinsiz"]["has_pin"])
es("yonetici has_pin=False", False, bul[f"{IZ}-admin"]["has_pin"])

print("\n── PIN kaldırılınca tekrar serbest (kilitlenme kurtarma) ──")
adminH = giris(yonetici)
# Yonetici izniyle PIN kaldir
_y = db.scalar(select(User).where(User.id == yonetici.id))
_y.permissions = ["kullanici_yonetimi"]; _y.role = "operator"; db.commit()
adminH = giris(_y)
es("PIN kaldirma 200", 200,
   C.post(f"/api/users/{pinli.id}/pin", headers=adminH, json={"pin": None}).status_code)
es("artik PIN'siz girilebiliyor", 200, sec(H, pinli).status_code)

db.execute(text("delete from login_attempts where email like :p"), {"p": f"{IZ}%"})
db.execute(text("delete from users where email like :p"), {"p": f"{IZ}%"})
db.commit()

print(f"\n{'='*46}\nGECTI: {GECTI}   KALDI: {KALDI}\n{'='*46}")
sys.exit(1 if KALDI else 0)
