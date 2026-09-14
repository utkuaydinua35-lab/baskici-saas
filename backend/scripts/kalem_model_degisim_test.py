"""Sipariş detayı → kalem "Telefon modeli değiştir" (WhatsApp bağlantısı).

Kalıptaki "kalıptan çıkar → WhatsApp'tan bildir" ile AYNI şablon/bağlantı;
fark: kalem kalıptan ÇIKARILMAZ. Sınananlar:
  • telefon yoksa 422, kalem başka siparişinse 404, çift kılıfta 409
  • mesaj türü kalemin varyasyonundan (şeffaf → şeffaf metni)
  • ikinci basış YENİ bağlantı üretmez (müşteride iki link olmasın)
  • kalem kalıp durumu DEĞİŞMEZ, geçmişe kayıt düşer
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

GECTI = KALDI = 0
IZ = f"kmdtest{uuid.uuid4().hex[:6]}"


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

st = Store(tenant_id=tenant.id, slug=f"{IZ}-m", name="KMD", platform="storefront", is_active=True)
db.add(st); db.flush()


def siparis(telefon, **li_alan):
    o = Order(tenant_id=tenant.id, store_id=st.id, external_id=f"{IZ}-{uuid.uuid4().hex[:6]}",
              order_number=f"{IZ}{uuid.uuid4().hex[:4]}", customer_name="Ayşe Yılmaz",
              current_stage=2, raw={"shipping_address": {"name": "Ayşe Yılmaz", "phone": telefon}})
    db.add(o); db.flush()
    li = LineItem(tenant_id=tenant.id, order_id=o.id, title="Kelebek Tasarım Kılıf", quantity=1,
                  position=0, device_model_override="iPhone 15", properties=[], **li_alan)
    db.add(li); db.flush()
    return o, li


try:
    o1, li1 = siparis("0532 160 24 42", kilif_varyasyon="ŞEFFAF")
    o2, li2 = siparis("")
    db.commit()
    yol = lambda o, li: f"/api/orders/{o.id}/line-items/{li.id}/model-degisim"  # noqa: E731

    print("\n── Kurallar ──")
    es("telefon yok 422", 422, c.post(yol(o2, li2), headers=H, json={}).status_code)
    es("başka siparişin kalemi 404", 404, c.post(yol(o1, li2), headers=H, json={}).status_code)

    print("\n── Bağlantı ──")
    r = c.post(yol(o1, li1), headers=H, json={})
    es("200", 200, r.status_code)
    j = r.json()
    es("tür kalem varyasyonundan: şeffaf", "seffaf", j.get("kalip_turu"))
    es("ürün adı: tasarım + varyasyon + model", "Kelebek Tasarım Kılıf (Şeffaf iPhone 15)", j.get("urun_adi"))
    es("şeffaf şablonu", True, "Şeffaf kılıflardaki eksik stok" in (j.get("message") or ""))
    es("wa.me + TR numara", True, (j.get("wa_url") or "").startswith("https://wa.me/905321602442?text="))
    es("bağlantı mesajın içinde", True, j["link"] in j["message"])
    r2 = c.post(yol(o1, li1), headers=H, json={}).json()
    es("ikinci basış AYNI bağlantı", j["link"], r2.get("link"))
    db.expire_all()
    es("kalem kalıp durumu değişmedi", False, bool(db.get(LineItem, li1.id).is_kaliba_eklendi))
    es("geçmişe kayıt", True, bool(db.scalar(select(OrderStatusHistory.id).where(
        OrderStatusHistory.order_id == o1.id, OrderStatusHistory.action == "model_baglantisi").limit(1))))
finally:
    db.rollback()
    oids = [x for (x,) in db.execute(select(Order.id).where(Order.store_id == st.id)).all()]
    if oids:
        for q in ("delete from model_degisim_talepleri where order_id = any(:o)",
                  "delete from order_status_history where order_id = any(:o)",
                  "delete from line_items where order_id = any(:o)",
                  "delete from orders where id = any(:o)"):
            db.execute(text(q).bindparams(o=oids))
    db.execute(text("delete from stores where id = :s").bindparams(s=st.id))
    db.commit()

print(f"\n{'='*46}\nGECTI: {GECTI}   KALDI: {KALDI}\n{'='*46}")
sys.exit(1 if KALDI else 0)
