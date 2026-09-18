"""Oturumun sessizce düşmesi — /api/auth/refresh ve istemcideki 401 davranışı.

NEDEN: token 7 gün geçerli, panel günlerce açık duruyor. Süre dolunca panel
AÇIK kalıyor, istekler 401 dönüyor ve kullanıcı "Bearer token gerekli" diye
anlamsız bir hata görüyordu (paketlemede "P" kısayolunda yaşandı).

Sınananlar:
  • geçerli token → yeni token; yenisi çalışır ve süresi ileri alınır
  • token yok / bozuk / süresi dolmuş → 401 (tazeleme kapıyı açmaz)
  • bayi hesabı da tazeleyebilir (kapı listesinde)
  • istemci tarafı: hiçbir ekranda elle "Bearer ..." kurulmaz ve 401'de
    oturum KAPANIR (eski hata tam buydu: koşul "token varsa" idi)
"""
from __future__ import annotations

import re
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.auth.security import create_access_token, safe_decode  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Tenant, User  # noqa: E402

GECTI = KALDI = 0
KOK = Path(__file__).resolve().parent.parent.parent   # depo kökü


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen: {beklenen!r}\n      gercek  : {gercek!r}")


c = TestClient(app)
db = SessionLocal()
tenant = db.scalar(select(Tenant).limit(1))
yon = db.scalar(select(User).where(User.tenant_id == tenant.id,
                                   User.role.in_(["owner", "yonetici"])).limit(1))
bayi = db.scalar(select(User).where(User.tenant_id == tenant.id,
                                    User.role == "bayii_portal", User.is_active.is_(True)).limit(1))


def basl(u, dk=30):
    return {"Authorization": "Bearer " + create_access_token(
        user_id=str(u.id), tenant_id=str(u.tenant_id), email=u.email, expires_minutes=dk)}


print("\n── Tazeleme ──")
H = basl(yon, dk=5)
r = c.post("/api/auth/refresh", headers=H)
es("geçerli token → 200", 200, r.status_code)
yeni = (r.json() or {}).get("access_token")
es("yeni token döner", True, bool(yeni))
es("token_type bearer", "bearer", (r.json() or {}).get("token_type"))

if yeni:
    eski_exp = safe_decode(H["Authorization"].split(" ", 1)[1]).get("exp")
    yeni_exp = safe_decode(yeni).get("exp")
    es("süre İLERİ alınır", True, yeni_exp > eski_exp)
    es("yeni token çalışır", 200, c.get("/api/auth/me", headers={"Authorization": f"Bearer {yeni}"}).status_code)
    es("kullanıcı DEĞİŞMEZ", str(yon.id), safe_decode(yeni).get("sub"))

print("\n── Tazeleme kapı açmaz ──")
es("başlık yok → 401", 401, c.post("/api/auth/refresh").status_code)
es("mesaj: Bearer token gerekli", "Bearer token gerekli",
   c.post("/api/auth/refresh").json().get("detail"))
es("bozuk token → 401", 401,
   c.post("/api/auth/refresh", headers={"Authorization": "Bearer abc.def.ghi"}).status_code)
suresi_dolmus = create_access_token(user_id=str(yon.id), tenant_id=str(tenant.id),
                                    email=yon.email, expires_minutes=-1)
es("süresi dolmuş token → 401", 401,
   c.post("/api/auth/refresh", headers={"Authorization": f"Bearer {suresi_dolmus}"}).status_code)
es("'Bearer null' (istemci hatası) → 401", 401,
   c.post("/api/auth/refresh", headers={"Authorization": "Bearer null"}).status_code)

if bayi is not None:
    es("bayi de tazeleyebilir", 200, c.post("/api/auth/refresh", headers=basl(bayi)).status_code)
else:
    print("  · bayi hesabı yok, o sınama atlandı")

print("\n── İstemci tarafı (kaynak kodu) ──")
# Elle kurulan "Bearer ${...}" başlığı: token yokken "Bearer null" gönderir ve
# 401'de kimse oturumu kapatmaz. Tek kapı lib/api.js olmalı.
kacak = []
for kok, muaf in ((KOK / "frontend/src", "lib/api.js"), (KOK / "panel/src", "lib/api.js")):
    for f in list(kok.rglob("*.js")) + list(kok.rglob("*.jsx")):
        if f.as_posix().endswith(muaf):
            continue
        if re.search(r"Bearer \$\{", f.read_text(encoding="utf-8")):
            kacak.append(f.relative_to(KOK).as_posix())
es("elle kurulan Bearer başlığı kalmadı", [], sorted(kacak))

for ad, yol in (("studio", KOK / "frontend/src/lib/api.js"), ("panel", KOK / "panel/src/lib/api.js")):
    kaynak = yol.read_text(encoding="utf-8")
    es(f"{ad}: 401 'token varsa' koşuluna BAĞLI DEĞİL", False,
       bool(re.search(r"status === 401 && token", kaynak)))
    es(f"{ad}: 401'de oturum kapanır", True, "oturumBitti()" in kaynak)
    es(f"{ad}: token yoksa başlık eklenmez", True, "auth/refresh" in kaynak)

db.close()
print(f"\n{'='*46}\nGECTI: {GECTI}   KALDI: {KALDI}\n{'='*46}")
sys.exit(1 if KALDI else 0)
