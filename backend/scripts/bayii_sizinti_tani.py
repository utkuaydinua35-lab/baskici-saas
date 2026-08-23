"""Bayi hesabi HANGI uclara erisebiliyor?

Bayi kullanicisi yonetimle AYNI tenant icinde. Yalnizca izin adini ayirmak
yetmez: izin ISTEMEYEN (sadece get_current_user ile korunan) her uc bayiye de
acik demektir. Bu betik parametresiz GET uclarini bayi token'iyla dener ve
200 donenleri listeler — her biri elden gecirilmelidir.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402

db = SessionLocal()
bayi = db.scalar(select(User).where(User.role == "bayii_portal").limit(1))
if not bayi:
    raise SystemExit("Bayi kullanicisi yok — once bir portal hesabi ac.")

c = TestClient(app)
r = c.post("/api/auth/login", json={"email": bayi.email, "password": "Demo12345!"})
if r.status_code != 200:
    raise SystemExit(f"Demo bayi girisi basarisiz ({r.status_code}). "
                     "Bu betik demo@bayi.example.com / Demo12345! bekler.")
H = {"Authorization": f"Bearer {r.json()['access_token']}"}

acik, kapali = [], 0
for rota in app.routes:
    yol = getattr(rota, "path", "")
    if "{" in yol or not yol.startswith("/api"):
        continue
    if "GET" not in (getattr(rota, "methods", None) or set()):
        continue
    if yol.startswith("/api/bayii") or yol.startswith("/api/auth"):
        continue  # portalin kendi uclari + oturum uclari
    try:
        s = c.get(yol, headers=H).status_code
    except Exception as e:  # noqa: BLE001
        s = f"HATA {type(e).__name__}"
    if s == 200:
        acik.append(yol)
    else:
        kapali += 1

print(f"\nBayi token'i ile 200 donen yonetim ucu: {len(acik)}   (kapali: {kapali})\n")
for y in sorted(acik):
    print(f"  ⚠ {y}")
if not acik:
    print("  ✓ Hicbiri acik degil.")
