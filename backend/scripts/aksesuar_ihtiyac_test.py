"""'Gerekli Modeller' ihtiyaç listesi — stok grubuna bağlı OLMAYAN ürünler.

Liste stoğa BAKMADAN "ne hazırlayacağım" der. Ama `aksesuar_talebi` ürünün bir
StockGroup'a bağlı olmasını şart koşuyordu; henüz stok takibine bağlanmamış
ürünler (magsafe kılıflar gibi) listeden tamamen düşüyordu.

Kural: İHTİYAÇ listesi bağlantı aramaz, EKSİK listesi arar.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import (AccessoryProduct, LineItem, Order, StockGroup,  # noqa: E402
                        Store, Tenant)
from app.services import stock as stock_svc  # noqa: E402

GECTI = KALDI = 0
IZ = f"akstest{uuid.uuid4().hex[:6]}"


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


db = SessionLocal()
tenant = db.scalar(select(Tenant).limit(1))
store = Store(tenant_id=tenant.id, slug=f"{IZ}-s", name="Aks Test",
              platform="bayii", is_active=True)
db.add(store); db.flush()

PID_BAGLI = f"{IZ}-bagli"
PID_BAGSIZ = f"{IZ}-bagsiz"

# İki aksesuar ürünü: biri stok grubuna BAĞLI, biri değil
db.add_all([
    AccessoryProduct(tenant_id=tenant.id, store_id=store.id, product_id=PID_BAGLI,
                     product_title="Ekran Koruyucu"),
    AccessoryProduct(tenant_id=tenant.id, store_id=store.id, product_id=PID_BAGSIZ,
                     product_title="Magsafe Şeffaf Kılıf"),
])
grup = StockGroup(tenant_id=tenant.id, name=f"{IZ} Ekran Koruyucu", is_active=True,
                  linked_products=[{"product_id": PID_BAGLI}])
db.add(grup); db.flush()

# Her ikisini de içeren açık bir sipariş
o = Order(tenant_id=tenant.id, store_id=store.id, external_id=f"{IZ}-1",
          order_number=f"{IZ}5", name=f"#{IZ}5", customer_name="Test",
          current_stage=2)
db.add(o); db.flush()
db.add_all([
    LineItem(tenant_id=tenant.id, order_id=o.id, product_id=PID_BAGLI,
             title="Ekran Koruyucu", variant_title="iPhone 15", quantity=2,
             device_model_override="iPhone 15", properties=[], raw={}),
    LineItem(tenant_id=tenant.id, order_id=o.id, product_id=PID_BAGSIZ,
             title="Magsafe Şeffaf Kılıf", variant_title="iPhone 15", quantity=3,
             device_model_override="iPhone 15", properties=[], raw={}),
])
db.commit()

print("\n── İHTİYAÇ listesi (stoğa bakmaz) ──")
ihtiyac = stock_svc.aksesuar_ihtiyaci(db, tenant.id)
bizim = [x for x in ihtiyac if IZ in (x["grup"] or "") or "Magsafe" in (x["grup"] or "")]
adlar = {x["grup"]: x for x in bizim}
es("BAGLI urun listede", True, any(IZ in k for k in adlar))
es("BAGSIZ urun da listede", True, any("Magsafe" in k for k in adlar))
ms = next((v for k, v in adlar.items() if "Magsafe" in k), None)
es("bagsiz urunun adedi dogru", 3, ms["count"] if ms else None)
es("bagsiz urun 'stok takibi yok' isaretli", False, ms["stok_takibi"] if ms else None)
bg = next((v for k, v in adlar.items() if IZ in k), None)
es("bagli urun 'stok takibi var' isaretli", True, bg["stok_takibi"] if bg else None)

print("\n── EKSİK listesi (stoğa bakar) — bağsız ürün GİRMEMELİ ──")
eksik = stock_svc.siparis_stok_eksigi(db, tenant.id)
es("bagsiz urun EKSIK listesinde YOK", False,
   any("Magsafe" in (x.get("grup") or "") for x in eksik))

print("\n── Hiç aksesuar kayıtlı değilse çökmemeli ──")
bos = stock_svc.aksesuar_ihtiyaci(db, uuid.uuid4())
es("bilinmeyen tenant bos liste", [], bos)

# Temizlik
db.execute(text("delete from line_items where order_id = :o"), {"o": o.id})
db.execute(text("delete from orders where id = :o"), {"o": o.id})
db.execute(text("delete from stock_groups where name like :p"), {"p": f"{IZ}%"})
db.execute(text("delete from accessory_products where product_id like :p"), {"p": f"{IZ}%"})
db.execute(text("delete from stores where slug like :p"), {"p": f"{IZ}%"})
db.commit()

print(f"\n{'='*46}\nGECTI: {GECTI}   KALDI: {KALDI}\n{'='*46}")
sys.exit(1 if KALDI else 0)
