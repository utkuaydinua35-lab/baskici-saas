"""Ürün kimliği mağaza doğrulaması — yanlış mağazaya yazılan işaret kaydı.

2026-10-13'te yandı: Aksesuarlar ekranında mağaza değiştirilince geciken
Shopify ürün listesi yeni listenin üstüne biniyordu; ekranda Shopify ürünleri,
seçili mağaza ise VİTRİN oluyordu. Tıklanan satırlar Shopify kimliğini vitrin
mağazasına yazdı → kayıt "✓ Aksesuar" görünüyor ama hiçbir vitrin ürünüyle
eşleşmiyor, kalıp planlayıcı o boş kılıf için "tasarım eksik" demeye devam etti.

Sınananlar:
  • vitrin mağazasına Shopify sayısal kimliği aksesuar/couple/kişiye özel
    olarak YAZILAMAZ (400)
  • başka mağazanın katalog ürününün UUID'si de yazılamaz
  • doğru UUID yazılabiliyor ve kalıp planlayıcı o kalemi artık eksik SAYMAZ
  • Shopify mağazasında eski davranış korunur (sayısal kimlik kabul)
"""
from __future__ import annotations

import sys
import uuid
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.auth.security import create_access_token  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    CatalogProduct, LineItem, Order, Store, Tenant, User,
)
from app.services import mold_planner  # noqa: E402

GECTI = KALDI = 0
IZ = f"uktest{uuid.uuid4().hex[:6]}"


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen: {beklenen!r}\n      gercek  : {gercek!r}")


db = SessionLocal()
tenant = db.scalar(select(Tenant).limit(1))
yon = db.scalar(select(User).where(User.tenant_id == tenant.id,
                                  User.role.in_(["owner", "yonetici"]),
                                  User.dealer_id.is_(None)).limit(1))
c = TestClient(app)
H = {"Authorization": "Bearer " + create_access_token(
    user_id=str(yon.id), tenant_id=str(tenant.id), email=yon.email, expires_minutes=30)}

SAYISAL = "8922951909605"   # gerçek olayda vitrine yazılan Shopify kimliği
try:
    shopify = Store(tenant_id=tenant.id, slug=f"{IZ}-shop", name=f"{IZ} shop",
                    platform="shopify", is_active=True)
    vitrin = Store(tenant_id=tenant.id, slug=f"{IZ}-vitrin", name=f"{IZ} vitrin",
                   platform="storefront", is_active=True)
    vitrin2 = Store(tenant_id=tenant.id, slug=f"{IZ}-vitrin2", name=f"{IZ} vitrin2",
                    platform="storefront", is_active=True)
    db.add_all([shopify, vitrin, vitrin2]); db.flush()
    u = CatalogProduct(tenant_id=tenant.id, store_id=vitrin.id, status="active",
                       title=f"{IZ} Magsafe Şeffaf Airbag", slug=f"{IZ}-magsafe",
                       base_price=Decimal("249.00"))
    u2 = CatalogProduct(tenant_id=tenant.id, store_id=vitrin2.id, status="active",
                        title=f"{IZ} Başka mağazanın ürünü", slug=f"{IZ}-baska",
                        base_price=Decimal("249.00"))
    db.add_all([u, u2]); db.commit()

    print("\n── Vitrin mağazasına YANLIŞ kimlik yazılamaz ──")
    for yol, govde in (
        ("/api/accessories", {"store_id": str(vitrin.id), "product_id": SAYISAL,
                              "product_title": "Magsafe"}),
        ("/api/couple", {"store_id": str(vitrin.id), "product_id": SAYISAL,
                         "product_title": "Magsafe"}),
        ("/api/kisiye-ozel/products", {"store_id": str(vitrin.id), "product_id": SAYISAL,
                                       "product_title": "Magsafe"}),
    ):
        r = c.post(yol, headers=H, json=govde)
        es(f"{yol} Shopify kimliğini reddetti", 400, r.status_code)
    r = c.post("/api/accessories", headers=H, json={
        "store_id": str(vitrin.id), "product_id": str(u2.id), "product_title": "yabancı"})
    es("başka mağazanın ürün UUID'si reddedildi", 400, r.status_code)
    r = c.post("/api/accessories", headers=H, json={
        "store_id": str(vitrin.id), "product_id": "bu-bir-uuid-degil"})
    es("bozuk kimlik reddedildi", 400, r.status_code)

    print("\n── Shopify mağazasında eski davranış korunur ──")
    r = c.post("/api/accessories", headers=H, json={
        "store_id": str(shopify.id), "product_id": SAYISAL, "product_title": "Magsafe"})
    es("sayısal kimlik kabul edildi", True, r.status_code < 400 and r.json().get("ok"))

    print("\n── Doğru kimlik: aksesuar işareti kalıp planını susturuyor ──")
    o = Order(tenant_id=tenant.id, store_id=vitrin.id, external_id=f"{IZ}-1",
              order_number=f"{IZ}1", customer_name="Ayşe", current_stage=2, raw={})
    db.add(o); db.flush()
    db.add(LineItem(tenant_id=tenant.id, order_id=o.id, product_id=str(u.id),
                    title=u.title, variant_title="iPhone 15", quantity=1,
                    device_model_override="iPhone 15", properties=[], raw={}))
    db.commit()
    p = mold_planner.plan_molds(db, tenant_id=tenant.id, store_id=vitrin.id)
    es("işaretlenmeden önce eksik listesinde", True,
       any(e["product_id"] == str(u.id) for e in p["eksikler"]))
    r = c.post("/api/accessories", headers=H, json={
        "store_id": str(vitrin.id), "product_id": str(u.id), "product_title": u.title})
    es("doğru UUID kabul edildi", True, r.status_code < 400 and r.json().get("ok"))
    db.expire_all()
    p = mold_planner.plan_molds(db, tenant_id=tenant.id, store_id=vitrin.id)
    es("aksesuar artık eksik SAYILMIYOR", False,
       any(e["product_id"] == str(u.id) for e in p["eksikler"]))
finally:
    db.rollback()
    ids = [x for (x,) in db.execute(select(Store.id).where(Store.slug.like(f"{IZ}-%"))).all()]
    oids = [x for (x,) in db.execute(select(Order.id).where(Order.external_id.like(f"{IZ}%"))).all()]
    if oids:
        for q in ("delete from order_status_history where order_id = any(:o)",
                  "delete from line_items where order_id = any(:o)",
                  "delete from orders where id = any(:o)"):
            db.execute(text(q).bindparams(o=oids))
    if ids:
        for tbl in ("accessory_products", "couple_products", "kisiye_ozel_products",
                    "catalog_products"):
            db.execute(text(f"delete from {tbl} where store_id = any(:s)").bindparams(s=ids))
        db.execute(text("delete from stores where id = any(:s)").bindparams(s=ids))
    db.commit()

print(f"\n{'='*46}\nGECTI: {GECTI}   KALDI: {KALDI}\n{'='*46}")
sys.exit(1 if KALDI else 0)
