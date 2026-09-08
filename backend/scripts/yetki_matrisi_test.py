"""Kısıtlı personel, izni OLMAYAN bölümlere erişebiliyor mu?

İzin sistemi var (ALL_PERMISSIONS) ve panel bölümleri buna göre gizleniyor.
Ama MENÜYÜ GİZLEMEK API'Yİ KAPATMAZ — uçların da kontrol etmesi gerekir.

Statik tarama önce 236 "korumasız" uç saydı; ampirik deneme bunun YANLIŞ
olduğunu gösterdi: izinlerin çoğu router seviyesinde tanımlı ve tarayıcı
onu görmüyordu. Gerçek sayı 38'di ve büyük kısmı meşru (kendi profili,
kendi passkey'i, kendi bildirimi). Ders: yetki matrisini koddan değil
DAVRANIŞTAN çıkar.

Gerçekten açık çıkanlar (düzeltildi): /api/dashboard/summary (ciro),
/api/dashboard/_test-daily-summary (Telegram tetikleyici),
/api/notifications/sync-all (tüm mağaza senkronu).

Bu test SADECE "paketleme" izni olan bir personel açar ve izni olmayan
bölümlerin uçlarını dener. Beklenen: 403.
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
from app.models import Store, Tenant, User  # noqa: E402

GECTI = KALDI = 0
IZ = uuid.uuid4().hex[:6]
KIRMIZI: list[str] = []


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; KIRMIZI.append(ad); print(f"  ✗ {ad}  → {gercek}")


db = SessionLocal()
_ad = next((u for u in db.scalars(select(User).where(
    User.role.in_(("yonetici", "owner"))).order_by(User.email)).all()
    if u.password_hash and verify_password("DevAdmin12345!", u.password_hash)), None)
if _ad is None:
    raise SystemExit("Dev sifresiyle girilebilen yonetici YOK — test calisamaz.")
tenant = db.get(Tenant, _ad.tenant_id)
store = db.scalar(select(Store).where(Store.tenant_id == tenant.id))

# YALNIZ paketleme izni. Rol "personel" — yonetici degil (yonetici her izni gecer).
personel = User(tenant_id=tenant.id, email=f"yet-{IZ}@bayitest.com",
                full_name="Kisitli Personel", role="personel", is_active=True,
                password_hash=hash_password("DevPersonel12345!"),
                permissions=["paketleme"])
db.add(personel); db.commit()

C = TestClient(app)
db.execute(text("delete from login_attempts where ip in ('testclient','127.0.0.1')"))
db.commit()
H = {"Authorization": "Bearer " + C.post("/api/auth/login", json={
    "email": personel.email, "password": "DevPersonel12345!"}).json()["access_token"]}

SID = str(store.id) if store else "00000000-0000-0000-0000-000000000000"

# (ad, yöntem, yol, gövde) — hepsi personelin izni OLMAYAN bölümler.
# Sadece OKUMA uçları seçildi: test veri değiştirmesin.
DENEMELER = [
    ("pazarlama: kampanya listesi",      "GET", "/api/marketing/campaigns", None),
    ("pazarlama: abone listesi",         "GET", "/api/marketing/subscribers", None),
    ("dashboard: ciro/özet",             "GET", "/api/dashboard/summary", None),
    ("stok: liste",                      "GET", "/api/stock", None),
    ("tasarım: liste",                   "GET", f"/api/designs?store_id={SID}", None),
    ("kalıp: liste",                     "GET", "/api/molds", None),
    ("sipariş: liste",                   "GET", "/api/orders", None),
    ("destek: konu listesi",             "GET", "/api/support/threads", None),
    ("telafi: liste",                    "GET", "/api/telafiler", None),
    ("askı: liste",                      "GET", "/api/aski", None),
    ("kişiye özel: liste",               "GET", "/api/kisiye-ozel", None),
    ("notlar: liste",                    "GET", "/api/notes", None),
    ("bildirim: tüm mağaza senkronu",    "POST", "/api/notifications/sync-all", {}),
    ("dashboard: telegram tetikleyici",  "POST", "/api/dashboard/_test-daily-summary", {}),
]

print("\n── kısıtlı personel (yalnız 'paketleme' izni) izinsiz bölümleri deniyor ──")
for ad, yontem, yol, govde in DENEMELER:
    r = C.request(yontem, yol, headers=H, json=govde)
    if r.status_code == 404:
        print(f"  · {ad}: uç yok (404), atlandı")
        continue
    es(f"{ad} → 403", 403, r.status_code)

print("\n── mağaza config'i: sırlar MASKELİ dönmeli ──")
# GET /api/stores izin İSTEMİYOR (kiracıdaki herkes görebiliyor). O yüzden
# maskelemenin kapsamı kritik. Eşleşme eskiden TAM ADdı; sonradan eklenen
# ig_access_token / meta_capi_token / storefront_password listeye girmediği
# için AÇIK dönüyordu. Kural artık varsayılan-maskele.
from app.routers.stores import _sir_mi  # noqa: E402

for _k in ("access_token", "ig_access_token", "meta_capi_token",
           "storefront_password", "client_secret", "paytr_merchant_salt",
           "iyzico_secret_key", "surat_sifre", "yeni_api_key"):
    es(f"config.{_k} sır sayılıyor", True, _sir_mi(_k))
for _k in ("meta_pixel_id", "paytr_merchant_id", "store_url", "custom_domain",
           "theme", "shipping_fee"):
    es(f"config.{_k} AÇIK kalıyor", False, _sir_mi(_k))

_r = C.get("/api/stores", headers=H)
if _r.status_code == 200:
    _liste = _r.json() if isinstance(_r.json(), list) else _r.json().get("items", [])
    _sizan = [f"{s.get('name')}.{k}" for s in _liste
              for k, v in (s.get("config") or {}).items()
              if _sir_mi(k) and isinstance(v, str) and v and "•" not in v]
    es("hiçbir sır maskesiz dönmüyor", [], _sizan)

print("\n── izni OLAN bölüm çalışmalı (gerileme kontrolü) ──")
r = C.get("/api/packaging/queue", headers=H)
if r.status_code == 404:
    r = C.get("/api/packaging", headers=H)
es("paketleme erişilebilir (403 değil)", False, r.status_code == 403)

db.execute(text("delete from login_attempts where ip in ('testclient','127.0.0.1')"))
db.execute(text("delete from users where id=:u"), {"u": str(personel.id)})
db.commit()

print("\n" + "=" * 50)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
if KIRMIZI:
    print("\nİZİN KONTROLÜ OLMAYAN UÇLAR:")
    for k in KIRMIZI:
        print(f"  · {k}")
sys.exit(1 if KALDI else 0)
