"""Alan adı doğrulama ucu SSRF'e açık mı?

BULGU (2026-09-08): POST /api/stores/{id}/vitrin/domain-check kiracının
yazdığı `domain`'i doğrudan f-string'e koyup GERÇEK istek atıyor:
`requests.get(f"https://{domain}/api/dogrulama")`.

Vitrin yetkisi olan bir kiracı yöneticisi bununla:
  · iç adreslere istek attırabiliyor (127.0.0.1, 169.254.169.254, RFC1918),
  · gövdeyi göremese de ULAŞILABİLİRLİK, HTTP DURUMU ve yönlendirmedeki
    Location başlığını okuyabiliyor → iç ağ port tarayıcısı,
  · `@` ya da `/` içeren bir "alan adı" ile URL'i yeniden yazabiliyor.

Beklenen davranış: ad gerçek bir alan adı olacak ve ÖZEL/İÇ adrese
çözümlenen hiçbir ada istek ATILMAYACAK.
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
from app.models import Store, Tenant, User  # noqa: E402

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
store = Store(tenant_id=tenant.id, slug=f"{IZ}-ssrf", name="SSRF Test",
              platform="storefront", is_active=True)
db.add(store); db.commit()

C = TestClient(app)
db.execute(text("delete from login_attempts where ip in ('testclient','127.0.0.1')"))
db.commit()
H = {"Authorization": "Bearer " + C.post("/api/auth/login", json={
    "email": _ad.email, "password": "DevAdmin12345!"}).json()["access_token"]}
YOL = f"/api/store-settings/{store.id}/verify-domain"


def dene(domain: str) -> dict:
    r = C.post(YOL, headers=H, json={"domain": domain})
    return {"durum": r.status_code, "govde": r.json() if r.status_code < 500 else {}}

# Bu adresler DIŞARIYA çıkmaz — hepsi yerel/iç ağ. Test dış trafik üretmez.
print("\n── iç adreslere istek atılabiliyor mu ──")
for ad in ("127.0.0.1", "localhost", "169.254.169.254", "10.0.0.1"):
    s = dene(ad)
    mesaj = str(s["govde"].get("message", ""))
    # Reddedilmesi gereken: 422 ya da "geçerli bir alan adı değil" benzeri.
    # Kabul edilirse cevapta bağlantı denemesinin izi olur.
    reddedildi = s["durum"] == 422 or "geçerli" in mesaj.lower() or "iç adres" in mesaj.lower()
    es(f"{ad}: istek ATILMADI (reddedildi)", True, reddedildi)
    if not reddedildi:
        print(f"      → uç yanıtı: {mesaj[:110]}")

print("\n── URL yeniden yazma (f-string enjeksiyonu) ──")
for ad in ("evil.example/@127.0.0.1", "example.com/#", "example.com:8000",
           "user@127.0.0.1", "example.com/path"):
    s = dene(ad)
    mesaj = str(s["govde"].get("message", ""))
    reddedildi = s["durum"] == 422 or "geçerli" in mesaj.lower()
    es(f"{ad!r}: reddedildi", True, reddedildi)

print("\n── meşru alan adı hâlâ çalışıyor (gerileme yok) ──")
s = dene("magaza.bernzcompany.com")
es("gerçek alan adı 422 DEĞİL", True, s["durum"] != 422)

db.execute(text("delete from stores where id=:s"), {"s": str(store.id)})
db.commit()

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
