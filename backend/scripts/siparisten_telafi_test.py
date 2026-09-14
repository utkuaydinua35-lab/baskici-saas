"""Sipariş detayından telafi — /api/telafiler/from-order ile uçtan uca.

Sınananlar:
  • seçili kalemler klonlanır, adet kalem başına düşürülebilir (fazlası 400)
  • çift kılıfın 2. tasarımı/modeli ve elle seçilmiş varyasyon KOPYALANIR
  • telafi Telafiler listesinde, açık sipariş ölçütünde (kalıp/paketleme) görünür
  • kaynak sipariş detayında telafi + hangi kaleme ait olduğu görünür, geçmişe iz
  • telafi kodu çöpe atılan telafiden SONRA tekrar verilmez (canlıda T-1 ×2, T-8 ×3)
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.auth.security import create_access_token  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import LineItem, Order, OrderStatusHistory, Store, Tenant, User  # noqa: E402
from app.services.order_scope import acik_siparis_filtresi  # noqa: E402

GECTI = KALDI = 0
IZ = f"stftest{uuid.uuid4().hex[:6]}"


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen: {beklenen!r}\n      gercek  : {gercek!r}")


db = SessionLocal()
tenant = db.scalar(select(Tenant).limit(1))
yon = db.scalar(select(User).where(User.tenant_id == tenant.id, User.role.in_(["owner", "yonetici"])).limit(1))
if yon is None:
    print("yönetici yok — atlandı\nGECTI: 0   KALDI: 0"); sys.exit(0)
H = {"Authorization": "Bearer " + create_access_token(
    user_id=str(yon.id), tenant_id=str(tenant.id), email=yon.email, expires_minutes=30)}
c = TestClient(app)

st = Store(tenant_id=tenant.id, slug=f"{IZ}-m", name="STF", platform="storefront", is_active=True)
db.add(st); db.flush()
src = Order(tenant_id=tenant.id, store_id=st.id, external_id=f"{IZ}-src", order_number=f"{IZ}9",
            customer_name="Ayşe Yılmaz", current_stage=8, fulfillment_status="fulfilled",
            raw={"shipping_address": {"name": "Ayşe Yılmaz", "phone": "05321602442"}})
db.add(src); db.flush()
li_tek = LineItem(tenant_id=tenant.id, order_id=src.id, title="Kelebek Kılıf", quantity=2, position=0,
                  device_model_override="iPhone 15", kilif_varyasyon="ŞEFFAF", properties=[])
li_cift = LineItem(tenant_id=tenant.id, order_id=src.id, title="Couple Kılıf", quantity=1, position=1,
                   device_model_override="iPhone 14", device_model_override_2="Galaxy S24",
                   kilif_varyasyon="SİYAH", kilif_varyasyon_2="BEYAZ", properties=[])
li_disari = LineItem(tenant_id=tenant.id, order_id=src.id, title="Seçilmeyen", quantity=1, position=2,
                     device_model_override="iPhone 13", properties=[])
db.add_all([li_tek, li_cift, li_disari]); db.commit()
URL = f"/api/telafiler/from-order/{src.id}"

try:
    print("\n── Doğrulama ──")
    es("fazla adet 400", 400, c.post(URL, headers=H, json={
        "line_item_ids": [str(li_tek.id)], "adetler": {str(li_tek.id): 3}}).status_code)
    es("boş seçim 400", 400, c.post(URL, headers=H, json={"line_item_ids": []}).status_code)

    print("\n── Oluşturma ──")
    r = c.post(URL, headers=H, json={"line_item_ids": [str(li_tek.id), str(li_cift.id)],
                                    "telafi_sebep": "Hatalı model", "adetler": {str(li_tek.id): 1}})
    es("200", 200, r.status_code)
    t1 = r.json()
    db.expire_all()
    tel = db.get(Order, uuid.UUID(t1["id"]))
    kal = sorted(tel.line_items, key=lambda x: x.position)
    es("yalnız seçili 2 kalem", ["Kelebek Kılıf", "Couple Kılıf"], [k.title for k in kal])
    es("adet düşürüldü (2→1)", 1, kal[0].quantity)
    es("varyasyon kopyalandı", "ŞEFFAF", kal[0].kilif_varyasyon)
    es("çift kılıf 2. model + varyasyon", ("Galaxy S24", "BEYAZ"),
       (kal[1].device_model_override_2, kal[1].kilif_varyasyon_2))
    es("kaynak kalem izi", str(li_tek.id), (kal[0].raw or {}).get("kaynak_line_item_id"))
    es("telafi işaretli + sebep", (True, "Hatalı model"), (tel.is_telafi, tel.telafi_sebep))
    es("aşama 1 (yeniden üretime girer)", 1, tel.current_stage or 1)

    print("\n── İşleyişe dahil ──")
    liste = c.get("/api/telafiler", headers=H).json()["items"]
    es("Telafiler listesinde", True, any(x["id"] == t1["id"] for x in liste))
    es("açık sipariş ölçütünde (kalıp + paketleme)", True, bool(db.scalar(
        select(Order.id).where(acik_siparis_filtresi(tenant.id), Order.id == tel.id))))
    det = c.get(f"/api/orders/{src.id}/detail", headers=H).json()
    t_det = next((x for x in det["telafiler"] if x["id"] == t1["id"]), None)
    es("kaynak detayda telafi görünür", True, t_det is not None)
    es("hangi kalemin telafisi", sorted([str(li_tek.id), str(li_cift.id)]), (t_det or {}).get("kaynak_kalemler"))
    es("kaynak geçmişine iz", True, bool(db.scalar(select(OrderStatusHistory.id).where(
        OrderStatusHistory.order_id == src.id, OrderStatusHistory.action == "telafi_olusturuldu").limit(1))))

    print("\n── Kod tekrarı ──")
    kod1 = t1["order_number"].rsplit("T-", 1)[1]
    es("çöpe at 204", 204, c.delete(f"/api/telafiler/{t1['id']}", headers=H).status_code)
    t2 = c.post(URL, headers=H, json={"line_item_ids": [str(li_tek.id)]}).json()
    kod2 = t2["order_number"].rsplit("T-", 1)[1]
    es("silinen telafinin kodu tekrar VERİLMEDİ", True, int(kod2) > int(kod1))
    det = c.get(f"/api/orders/{src.id}/detail", headers=H).json()
    es("silinen telafi detayda görünmez", [t2["id"]], [x["id"] for x in det["telafiler"]])
finally:
    db.rollback()
    oids = [x for (x,) in db.execute(select(Order.id).where(Order.store_id == st.id)
                                     .execution_options(include_deleted=True)).all()]
    if oids:
        for q in ("delete from order_status_history where order_id = any(:o)",
                  "delete from line_items where order_id = any(:o)",
                  "update orders set telafi_kaynak_order_id = null where id = any(:o)",
                  "delete from orders where id = any(:o)"):
            db.execute(text(q).bindparams(o=oids))
    db.execute(text("delete from stores where id = :s").bindparams(s=st.id))
    db.commit()

print(f"\n{'='*46}\nGECTI: {GECTI}   KALDI: {KALDI}\n{'='*46}")
sys.exit(1 if KALDI else 0)
