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

from app.models import Dealer  # noqa: E402
dealer = Dealer(tenant_id=tenant.id, store_id=store.id, name=f"{IZ}-BAYI",
                is_active=True, unit_price=10, currency="TRY", shipping_fee=0)
db.add(dealer); db.flush()
o = Order(tenant_id=tenant.id, store_id=store.id, order_number=f"{IZ}-1",
          external_id=f"{IZ}-1", customer_name="Test", current_stage=1,
          bayii_onay_bekliyor=True, raw={"dealer_id": str(dealer.id)})
db.add(o); db.flush()
li = LineItem(tenant_id=tenant.id, order_id=o.id, title="k", quantity=1,
              assigned_design_id=eski_d.id, device_model_override="iPhone 15")
db.add(li); db.commit()

U = f"/api/dealers/portal/siparis/{o.id}/kalem/{li.id}"
U_ESKI = f"/api/dealers/portal/onay-bekleyen/{o.id}/kalem/{li.id}/tasarim"

print("\n── 1. kuyruk store_id veriyor (secici icin gerekli) ──")
kuyruk = C.get("/api/dealers/portal/onay-bekleyen", headers=H).json()
kayit = next((x for x in kuyruk if x["id"] == str(o.id)), None)
es("siparis kuyrukta", True, kayit is not None)
es("store_id var", str(store.id), kayit and kayit.get("store_id"))
# ÖNİZLEME onay ekranında görünmeli: bayi "kılıf üzerinde böyle duracak" diye
# yüklüyor, onaylayanın görmesi gerek. Ayrı alanda — baskı hep "dosya"dan.
eski_d.onizleme_path = "x/onz.jpg"
db.commit()
_k = next(x for x in C.get("/api/dealers/portal/onay-bekleyen", headers=H).json()
          if x["id"] == str(o.id))["kalemler"][0]
es("önizleme alanı var", "/storage/x/onz.jpg", _k.get("onizleme"))
es("tasarım alanı AYRI durur", True, _k.get("dosya") != _k.get("onizleme"))
eski_d.onizleme_path = None
db.commit()

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
    OrderStatusHistory.action == "bayii_kalem_duzeltildi")).all()
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

es("eski yol da calisiyor (acik sekmeler icin)", 200,
   C.patch(U_ESKI, json={"design_id": str(eski_d.id)}, headers=H).status_code)

print("\n── 5. VARYASYON duzeltme ──")
r = C.patch(U, json={"varyasyon": "seffaf"}, headers=H)
es("200", 200, r.status_code)
es("normalize edildi", "ŞEFFAF", r.json().get("varyasyon"))
db.expire_all()
es("kaleme yazildi", "ŞEFFAF", db.get(LineItem, li.id).kilif_varyasyon)
es("tasarim+varyasyon birlikte", 200, C.patch(
    U, json={"design_id": str(yeni_d.id), "varyasyon": "SİYAH"}, headers=H).status_code)
db.expire_all()
_li = db.get(LineItem, li.id)
es("ikisi de uygulandi", (yeni_d.id, "SİYAH"), (_li.assigned_design_id, _li.kilif_varyasyon))
es("bos istek degismedi", True,
   C.patch(U, json={}, headers=H).json().get("degismedi"))

print("\n── 6. SINIR: onay DEGIL, kalip ──")
o.bayii_onay_bekliyor = False; db.commit()
es("ONAYLANMIS sipariste artik CALISIR", 200,
   C.patch(U, json={"varyasyon": "BEYAZ"}, headers=H).status_code)
_gec = db.scalars(select(OrderStatusHistory).where(
    OrderStatusHistory.order_id == o.id,
    OrderStatusHistory.action == "bayii_kalem_duzeltildi")).all()
es("gecmiste ONAY SONRASI yazili", True,
   any("ONAY SONRASI" in (g.note or "") for g in _gec))

# kaliba sok -> artik degistirilemez
from app.models import Mold, MoldItem  # noqa: E402
_m = Mold(tenant_id=tenant.id, store_id=store.id, kod=f"{IZ}-K", variation="SİYAH")
db.add(_m); db.flush()
db.add(MoldItem(tenant_id=tenant.id, mold_id=_m.id, line_item_id=li.id,
                design_id=yeni_d.id, store_id=store.id, slot_index=1,
                kalip_kodu=f"{IZ}-K", design_code=yeni_d.code,
                model="iPhone 15", order_number=o.order_number))
db.commit()
es("KALIPTAKI kalem 409", 409,
   C.patch(U, json={"varyasyon": "SİYAH"}, headers=H).status_code)
db.execute(text("delete from mold_items where mold_id=:m"), {"m": str(_m.id)})
db.execute(text("delete from molds where id=:m"), {"m": str(_m.id)})
db.commit()

print("\n── 7. YONETICI IPTALI ──")
IU = f"/api/dealers/portal/siparis/{o.id}/iptal"
r = C.post(IU, json={"sebep": "test"}, headers=H)
es("onaysiz istek ONIZLEME doner", True, r.json().get("onay_gerekli"))
es("henuz iptal DEGIL", False, bool(db.get(Order, o.id).is_iptal))
es("ne olacagi soyleniyor", True, "iade" in (r.json().get("mesaj") or "").lower())
_ip = C.post(IU, json={"sebep": "test", "onayla": True}, headers=H)
es("onayla=true ile iptal", 200, _ip.status_code)
# iade POLITIKASI ile GERCEKTEN iade edilen para ayri seyler: borc hic
# yazilmamissa "iade edildi" demek bayiyi yaniltir.
es("iade politikasi acik", True, _ip.json().get("iade_edildi"))
es("ama gercek iade YOK (borc yazilmamisti)", False, _ip.json().get("iade_tutari_var"))
db.expire_all()
es("siparis iptal edildi", True, bool(db.get(Order, o.id).is_iptal))
es("ikinci iptal 409", 409,
   C.post(IU, json={"onayla": True}, headers=H).status_code)
es("iptal edilmis sipariste duzeltme 409", 409,
   C.patch(U, json={"varyasyon": "SİYAH"}, headers=H).status_code)

# temizlik
db.execute(text("delete from order_status_history where order_id=:o"), {"o": str(o.id)})
db.execute(text("delete from line_items where order_id=:o"), {"o": str(o.id)})
db.execute(text("delete from orders where id=:o"), {"o": str(o.id)})
db.execute(text("delete from designs where store_id=:s"), {"s": str(store.id)})
db.execute(text("delete from dealer_transactions where dealer_id=:d"),
           {"d": str(dealer.id)})
db.execute(text("delete from dealers where id=:d"), {"d": str(dealer.id)})
db.execute(text("delete from stores where id=:s"), {"s": str(store.id)})
db.commit()

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
