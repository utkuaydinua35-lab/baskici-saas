"""Onay kuyrugunda tasarim degistirme — kayitli tasarimi yeniden kullan.

Bayi ayni gorseli her sipariste yeniden yukluyor; yonetici onaylarken
katalogdaki tasarimi secebilirse yeni dosya hic olusmaz.
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
from app.models import (Design, LineItem, Order, OrderStatusHistory,  # noqa: E402
                        Store, Tenant, User)

C = TestClient(app)
GECTI = KALDI = 0
IZ = f"otd{uuid.uuid4().hex[:6]}"
DEV_SIFRE = "DevAdmin12345!"


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


db = SessionLocal()
_adaylar = db.scalars(
    select(User).where(User.role.in_(("yonetici", "owner"))).order_by(User.email)).all()
admin = next((u for u in _adaylar
              if u.password_hash and verify_password(DEV_SIFRE, u.password_hash)), None)
if admin is None:
    raise SystemExit("Dev sifresiyle girilebilen yonetici YOK — test calisamaz.")
tenant = db.get(Tenant, admin.tenant_id)

db.execute(text("delete from login_attempts where ip in ('testclient','127.0.0.1')"))
db.commit()
r = C.post("/api/auth/login", json={"email": admin.email, "password": DEV_SIFRE})
if r.status_code != 200:
    raise SystemExit(f"Giris basarisiz ({r.status_code}) — test calisamaz.")
H = {"Authorization": f"Bearer {r.json()['access_token']}"}

store = Store(tenant_id=tenant.id, slug=f"{IZ}-s", name="Onay Test",
              platform="bayii", is_active=True)
db.add(store); db.flush()
eski_d = Design(tenant_id=tenant.id, store_id=store.id, code=f"{IZ}-ESKI",
                name="bayi yuklemesi", file_path="x/eski.jpg", file_format="jpg")
yeni_d = Design(tenant_id=tenant.id, store_id=store.id, code=f"{IZ}-KAYITLI",
                name="katalog", file_path="x/yeni.pdf", file_format="pdf")
db.add_all([eski_d, yeni_d]); db.flush()

o = Order(tenant_id=tenant.id, store_id=store.id, order_number=f"{IZ}-1",
          external_id=f"{IZ}-1", customer_name="Test", current_stage=1,
          bayii_onay_bekliyor=True, raw={})
db.add(o); db.flush()
li = LineItem(tenant_id=tenant.id, order_id=o.id, title="k", quantity=1,
              assigned_design_id=eski_d.id, device_model_override="iPhone 15")
db.add(li); db.commit()

U = f"/api/dealers/portal/onay-bekleyen/{o.id}/kalem/{li.id}/tasarim"

print("\n── 1. kuyruk store_id veriyor (secici icin gerekli) ──")
kuyruk = C.get("/api/dealers/portal/onay-bekleyen", headers=H).json()
kayit = next((x for x in kuyruk if x["id"] == str(o.id)), None)
es("siparis kuyrukta", True, kayit is not None)
es("store_id var", str(store.id), kayit and kayit.get("store_id"))

print("\n── 2. tasarim degistirme ──")
r = C.patch(U, json={"design_id": str(yeni_d.id)}, headers=H)
es("200", 200, r.status_code)
j = r.json()
es("yeni kod dondu", f"{IZ}-KAYITLI", j.get("tasarim_kodu"))
es("eski tasarim BOSTA kaldi", True, j.get("eski_bosta"))
es("eski kod bildirildi", f"{IZ}-ESKI", j.get("eski_tasarim_kodu"))
db.expire_all()
es("kalem gercekten guncellendi", yeni_d.id, db.get(LineItem, li.id).assigned_design_id)
es("YENI dosya olusmadi (ayni Design)", 2, db.scalar(
    select(__import__("sqlalchemy").func.count()).select_from(Design)
    .where(Design.store_id == store.id)))

print("\n── 3. gecmise yazildi ──")
gecmis = db.scalars(select(OrderStatusHistory).where(
    OrderStatusHistory.order_id == o.id,
    OrderStatusHistory.action == "bayii_tasarim_degisti")).all()
es("kayit var", 1, len(gecmis))
es("eski->yeni yazili", True,
   bool(gecmis) and f"{IZ}-ESKI" in gecmis[0].note and f"{IZ}-KAYITLI" in gecmis[0].note)

print("\n── 4. korumalar ──")
es("ayni tasarim -> degismedi", True,
   C.patch(U, json={"design_id": str(yeni_d.id)}, headers=H).json().get("degismedi"))
es("olmayan tasarim 404", 404,
   C.patch(U, json={"design_id": str(uuid.uuid4())}, headers=H).status_code)
es("olmayan kalem 404", 404, C.patch(
    f"/api/dealers/portal/onay-bekleyen/{o.id}/kalem/{uuid.uuid4()}/tasarim",
    json={"design_id": str(yeni_d.id)}, headers=H).status_code)
es("kimliksiz istek reddedilir", 401,
   C.patch(U, json={"design_id": str(yeni_d.id)}).status_code)

o.bayii_onay_bekliyor = False; db.commit()
es("ONAYLANMIS sipariste 409", 409,
   C.patch(U, json={"design_id": str(eski_d.id)}, headers=H).status_code)

# temizlik
db.execute(text("delete from order_status_history where order_id=:o"), {"o": str(o.id)})
db.execute(text("delete from line_items where order_id=:o"), {"o": str(o.id)})
db.execute(text("delete from orders where id=:o"), {"o": str(o.id)})
db.execute(text("delete from designs where store_id=:s"), {"s": str(store.id)})
db.execute(text("delete from stores where id=:s"), {"s": str(store.id)})
db.commit()

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
