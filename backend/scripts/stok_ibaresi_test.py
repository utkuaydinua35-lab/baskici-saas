"""Bayi ekranında "Stokta mevcut değil" — TÜRETİLEN durum.

Bayrak tek başına yetmez: ürün tekrar kalıba girdiğinde ibare KALKMALI.
Aksi halde bayi, üretimdeki siparişi "stokta yok" sanır.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import (Dealer, Design, LineItem, Mold, MoldItem,  # noqa: E402
                        Order, Store, Tenant)
from app.routers import bayii_portal as bp  # noqa: E402

GECTI = KALDI = 0
IZ = f"si{uuid.uuid4().hex[:6]}"


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


db = SessionLocal()
tenant = db.scalar(select(Tenant).order_by(Tenant.created_at).limit(1))
store = Store(tenant_id=tenant.id, slug=f"{IZ}-s", name="Stok Test",
              platform="bayii", is_active=True)
db.add(store); db.flush()
dealer = Dealer(tenant_id=tenant.id, store_id=store.id, name=f"{IZ}-D", is_active=True)
ds = Design(tenant_id=tenant.id, store_id=store.id, code=f"{IZ}-D1", name="t",
            file_path="x/a.jpg", file_format="jpg")
db.add_all([dealer, ds]); db.flush()
o = Order(tenant_id=tenant.id, store_id=store.id, order_number=f"{IZ}-1",
          external_id=f"{IZ}-1", customer_name="T", current_stage=4,
          raw={"dealer_id": str(dealer.id)})
db.add(o); db.flush()
li = LineItem(tenant_id=tenant.id, order_id=o.id, title="k", quantity=1,
              assigned_design_id=ds.id, device_model_override="iPhone 15", raw={})
db.add(li); db.commit()
db.refresh(o)


def kalem():
    db.expire_all()
    _o = db.scalar(select(Order).where(Order.id == o.id))
    return bp._ser(db, _o, detay=True)["kalemler"][0]


print("\n── 1. bayrak yokken ibare YOK ──")
es("stok_bekliyor False", False, kalem()["stok_bekliyor"])

print("\n── 2. stok yokluğuyla geri planlandı → ibare VAR ──")
li.raw = {"stok_bekliyor": {"at": "2026-08-30T10:00:00+00:00", "model": "iPhone 15"}}
db.commit()
k = kalem()
es("stok_bekliyor True", True, k["stok_bekliyor"])
es("tarih dönüyor", True, bool(k["stok_bekliyor_tarih"]))

print("\n── 3. ürün TEKRAR kalıba girdi → ibare KALKMALI ──")
mold = Mold(tenant_id=tenant.id, store_id=store.id, kod=f"{IZ}-K1",
            variation="SİYAH")   # variation NOT NULL
db.add(mold); db.flush()
mi = MoldItem(tenant_id=tenant.id, mold_id=mold.id, line_item_id=li.id,
              design_id=ds.id, store_id=store.id, slot_index=1,
              kalip_kodu=f"{IZ}-K1", design_code=ds.code,
              model="iPhone 15", order_number=o.order_number)
db.add(mi); db.commit()
es("bayrak DURUYOR ama ibare YOK", False, kalem()["stok_bekliyor"])
es("bayrak gerçekten duruyor", True,
   bool((db.get(LineItem, li.id).raw or {}).get("stok_bekliyor")))

print("\n── 4. kalıptan tekrar çıkarıldı → ibare geri gelir ──")
db.delete(mi); db.commit()
es("stok_bekliyor True", True, kalem()["stok_bekliyor"])

print("\n── 5. tarih, ibare yokken sızmamalı ──")
li.raw = {}
db.commit()
k = kalem()
es("stok_bekliyor False", False, k["stok_bekliyor"])
es("tarih None", None, k["stok_bekliyor_tarih"])

# temizlik
db.execute(text("delete from mold_items where mold_id=:m"), {"m": str(mold.id)})
db.execute(text("delete from molds where id=:m"), {"m": str(mold.id)})
db.execute(text("delete from line_items where order_id=:o"), {"o": str(o.id)})
db.execute(text("delete from orders where id=:o"), {"o": str(o.id)})
db.execute(text("delete from designs where store_id=:s"), {"s": str(store.id)})
db.execute(text("delete from dealers where store_id=:s"), {"s": str(store.id)})
db.execute(text("delete from stores where id=:s"), {"s": str(store.id)})
db.commit()

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
