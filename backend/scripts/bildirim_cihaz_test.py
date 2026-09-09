"""Uygulama bildirimi: cihaz jetonu kaydi ve gonderim yolu.

Web Push tarayici icindir ve uygulamada calismaz (service worker yok, origin
capacitor://localhost). Uygulamaya bildirim APNs uzerinden gidiyor; jetonlar
device_tokens tablosunda duruyor ve services/push.py ayni cagrilarda ikisini
birden besliyor.

Sinananlar:
  · jeton kaydi (upsert) ve ayni jetonun ikinci kez yazilmamasi,
  · jeton BASKA kullaniciya gecince sahiplendirilmesi (eski sahibe gitmemeli),
  · gecersiz jeton / bilinmeyen platform reddi,
  · kimliksiz istek 401,
  · APNs yapilandirilmamisken gonderimin SESSIZCE no-op olmasi
    (bildirim hicbir is akisini durdurmamali),
  · olu jetonun gonderim sirasinda silinmesi,
  · bayi hesaplarinin send_to_tenant'tan HARIC tutulmasi.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.auth.security import verify_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import DeviceToken, User  # noqa: E402
from app.services import apns as apns_svc  # noqa: E402
from app.services import push as push_svc  # noqa: E402

GECTI = KALDI = 0
IZ = uuid.uuid4().hex[:8]


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


C = TestClient(app)
db = SessionLocal()

_ad = next((u for u in db.scalars(select(User)).all()
            if u.password_hash and verify_password("DevAdmin12345!", u.password_hash)), None)
if not _ad:
    raise SystemExit("Dev admin YOK — test calisamaz.")

_tok = C.post("/api/auth/login",
              json={"email": _ad.email, "password": "DevAdmin12345!"}).json()["access_token"]
BASLIK = {"Authorization": f"Bearer {_tok}"}
JETON = f"JETON{IZ}"
temizlenecek = [JETON]


def cihaz_sayisi(jeton: str) -> int:
    db.expire_all()
    return len(db.scalars(select(DeviceToken).where(DeviceToken.token == jeton)).all())


print("\n── jeton kaydi ──")
r = C.post("/api/push/device", headers=BASLIK,
           json={"token": JETON, "platform": "ios", "device_name": "iPhone"})
es("kayit kabul edildi", True, r.json().get("ok"))
es("tabloda 1 kayit", 1, cihaz_sayisi(JETON))

r = C.post("/api/push/device", headers=BASLIK, json={"token": JETON, "platform": "ios"})
es("ayni jeton IKINCI kez eklenmedi", 1, cihaz_sayisi(JETON))

print("\n── gecersiz girdiler reddediliyor ──")
es("bos jeton", False,
   C.post("/api/push/device", headers=BASLIK,
          json={"token": "   ", "platform": "ios"}).json().get("ok"))
es("bilinmeyen platform", False,
   C.post("/api/push/device", headers=BASLIK,
          json={"token": f"X{IZ}", "platform": "windows"}).json().get("ok"))
es("cok uzun jeton", False,
   C.post("/api/push/device", headers=BASLIK,
          json={"token": "A" * 401, "platform": "ios"}).json().get("ok"))

print("\n── kimlik zorunlu ──")
es("jetonsuz istek 401", 401,
   C.post("/api/push/device", json={"token": "ZZZ", "platform": "ios"}).status_code)

print("\n── jeton baska kullaniciya gecerse SAHIPLENDIRILIR ──")
# Ayni telefonu devralan biri, eski sahibin bildirimlerini gormemeli.
_kayit = db.scalar(select(DeviceToken).where(DeviceToken.token == JETON))
_baska = db.scalar(select(User).where(User.id != _ad.id, User.is_active.is_(True)))
if _baska is None:
    print("  · ikinci kullanici yok — atlandi")
else:
    _kayit.user_id = _baska.id
    db.commit()
    C.post("/api/push/device", headers=BASLIK, json={"token": JETON, "platform": "ios"})
    db.expire_all()
    es("jeton yeniden dev admin'e baglandi", _ad.id,
       db.scalar(select(DeviceToken).where(DeviceToken.token == JETON)).user_id)
    es("hala tek kayit", 1, cihaz_sayisi(JETON))

print("\n── APNs yapilandirilmamisken gonderim SESSIZ no-op ──")
es("apns_enabled false", False, apns_svc.apns_enabled())
es("gonder() bos donuyor", (0, []), apns_svc.gonder([JETON], "x", "y"))
# Asil onemli olan: gonderim patlamamali, cagiran is akisi devam etmeli.
try:
    _n = push_svc.send_to_user(db, _ad.id, "deneme", "govde", url="/", tag="test")
    es("send_to_user patlamadi", True, isinstance(_n, int))
except Exception as e:  # noqa: BLE001
    es("send_to_user patlamadi", True, f"PATLADI: {e}")

print("\n── olu jeton gonderimde siliniyor ──")
_gercek_gonder = apns_svc.gonder
apns_svc.apns_enabled = lambda: True                      # noqa: E731
apns_svc.gonder = lambda tokens, *a, **k: (0, list(tokens))   # hepsi olu  # noqa: E731
try:
    push_svc.send_to_user(db, _ad.id, "deneme", "govde")
    es("olu jetonun kaydi silindi", 0, cihaz_sayisi(JETON))
finally:
    apns_svc.gonder = _gercek_gonder
    apns_svc.apns_enabled = lambda: bool(  # noqa: E731
        __import__("app.config", fromlist=["get_settings"]).get_settings().apns_key_path)

print("\n── bayi hesaplari send_to_tenant'tan HARIC ──")
# Bayi portali hesaplari ayni tenant icinde ama yonetim bildirimlerini
# gormemeli; bu kural Web Push'ta vardi, cihaz jetonlarinda da olmali.
_bayi = db.scalar(select(User).where(User.dealer_id.isnot(None),
                                     User.tenant_id == _ad.tenant_id))
if _bayi is None:
    print("  · bayi hesabi yok — atlandi")
else:
    _bj = f"BAYI{IZ}"
    temizlenecek.append(_bj)
    db.add(DeviceToken(tenant_id=_bayi.tenant_id, user_id=_bayi.id,
                       token=_bj, platform="ios"))
    db.commit()
    gonderilenler: list[list[str]] = []
    apns_svc.apns_enabled = lambda: True                                  # noqa: E731
    apns_svc.gonder = lambda tokens, *a, **k: (gonderilenler.append(list(tokens)),  # noqa: E731
                                               (len(tokens), []))[1]
    try:
        push_svc.send_to_tenant(db, _ad.tenant_id, "yonetim", "bildirimi")
        _hepsi = [t for grup in gonderilenler for t in grup]
        es("bayi jetonuna GONDERILMEDI", False, _bj in _hepsi)
    finally:
        apns_svc.gonder = _gercek_gonder
        apns_svc.apns_enabled = lambda: bool(  # noqa: E731
            __import__("app.config", fromlist=["get_settings"]).get_settings().apns_key_path)

for j in temizlenecek:
    for k in db.scalars(select(DeviceToken).where(DeviceToken.token == j)).all():
        db.delete(k)
db.commit()

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
