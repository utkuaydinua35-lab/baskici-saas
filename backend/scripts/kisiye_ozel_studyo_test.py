"""Kişiye Özel: vitrin stüdyosundan gelen müşteri tasarımı panelde görünür,
indirilir ve tek tıkla baskı tasarımı olarak atanır.

ESKİ HÂL (2026-10-14, #1011): satırda yalnız "Tasarım No" + "/storage/…"
yazısı vardı; görsel 📷, indirme yok, baskıya atamak için dosyayı elle bulup
yüklemek gerekiyordu.
"""
from __future__ import annotations

import io
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.auth.security import create_access_token  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (CaseTemplate, Customer, CustomerDesign, Design, DesignAsset,  # noqa: E402
                        LineItem, Order, Store, Tenant, User)
from app.routers import kisiye_ozel  # noqa: E402
from app.services import storage as storage_svc  # noqa: E402

GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


db = SessionLocal()
IZ = f"kost{uuid.uuid4().hex[:6]}"
tenant = db.scalar(select(Tenant).limit(1))
admin = db.scalar(select(User).where(User.tenant_id == tenant.id,
                                     User.role.in_(["owner", "yonetici"])).limit(1))
H = {"Authorization": "Bearer " + create_access_token(
    user_id=str(admin.id), tenant_id=str(admin.tenant_id), email=admin.email, expires_minutes=30)}
c = TestClient(app)

st = Store(tenant_id=tenant.id, slug=f"{IZ}-v", name="Stüdyo test", platform="storefront", config={})
db.add(st); db.flush()
tpl = CaseTemplate(tenant_id=tenant.id, store_id=st.id, key=f"{IZ}-seffaf", label="Şeffaf Kılıf",
                   area_x=0, area_y=0, area_w=1, area_h=1, cutouts=[],
                   print_width_mm=40, print_height_mm=80, print_dpi=100, is_active=True)
cu = Customer(tenant_id=tenant.id, email=f"{IZ}@ornek.test", name="Murat")
db.add_all([tpl, cu]); db.flush()

# Müşterinin yüklediği fotoğraf (rötuş için orijinali indirilebilmeli)
arel = f"tenants/_test/{IZ}-foto.png"
(storage_svc.STORAGE_ROOT / arel).parent.mkdir(parents=True, exist_ok=True)
Image.new("RGB", (300, 300), (10, 120, 200)).save(storage_svc.STORAGE_ROOT / arel)
asset = DesignAsset(tenant_id=tenant.id, store_id=st.id, customer_id=cu.id, original_path=arel,
                    width=300, height=300, filename="tatil.png")
db.add(asset); db.flush()
cd = CustomerDesign(tenant_id=tenant.id, store_id=st.id, customer_id=cu.id, name="Tasarımım",
                    template_key=tpl.key, status="ordered", layers=[
                        {"id": "a", "type": "image", "asset_id": str(asset.id), "url": "/x",
                         "x": 0, "y": 0, "w": 1, "h": 1, "rot": 0, "src_w": 300, "src_h": 300},
                        {"id": "b", "type": "text", "text": "MURAT", "font": "anton", "size": 0.1,
                         "color": "#ffffff", "x": 0.1, "y": 0.4, "w": 0.8, "rot": 0, "align": "center"}])
db.add(cd); db.flush()
o = Order(tenant_id=tenant.id, store_id=st.id, external_id=f"{IZ}", order_number="1011", name="#1011")
db.add(o); db.flush()
li = LineItem(tenant_id=tenant.id, order_id=o.id, title="Kişiye Özel Tasarım Kılıf", quantity=1,
              product_id=str(uuid.uuid4()), properties=[
                  {"name": "Telefon Modeli", "value": "iPhone 17 Pro"},
                  {"name": "Tasarım", "value": "Tasarımım"},
                  {"name": "Tasarım No", "value": str(cd.id)},
                  {"name": "Önizleme", "value": "/storage/yok/onizleme.png"}])
db.add(li); db.commit()
olusan: list[uuid.UUID] = []
try:
    print("\n── Panelde görünüm ──")
    s = kisiye_ozel._serialize_line_item(db.get(LineItem, li.id), set(), set())
    es("stüdyo tasarımı tanındı", (str(cd.id), "Şeffaf Kılıf"),
       ((s["studyo"] or {}).get("id"), (s["studyo"] or {}).get("kilif")))
    es("ham 'Tasarım No'/'Önizleme' metni listede yok", [], [p["name"] for p in s["customer_props"]
                                                            if p["name"] in ("Tasarım No", "Önizleme")])
    es("müşterinin orijinal görseli indirilebilir", [(f"/storage/{arel}", "tatil.png")],
       [(x["url"], x["ad"]) for x in s["studyo"]["orijinaller"]])
    es("baskı dosyası henüz yok", (None, None), (s["studyo"]["baski_pdf_url"], s["studyo"]["baski_png_url"]))

    print("\n── Tek tıkla baskıya ata ──")
    r = c.post(f"/api/kisiye-ozel/line-items/{li.id}/studyo-ata", headers=H)
    es("atandı", 200, r.status_code)
    j = r.json()
    es("kalem HAZIR, tasarım kodu sipariş numarasıyla", (True, True),
       (j["status"] == "hazir", (j["assigned_design"] or {}).get("code", "").startswith("STD-1011-1-")))
    db.expire_all()
    li2 = db.get(LineItem, li.id)
    d = db.get(Design, li2.assigned_design_id)
    olusan.append(d.id)
    es("baskı dosyası PDF (vektörel) olarak tasarıma kopyalandı", ("pdf", True),
       (d.file_format, (storage_svc.STORAGE_ROOT / d.file_path).is_file()))
    es("kılıf varyasyonu şablondan (Şeffaf)", "ŞEFFAF", j["efektif_varyasyon"])
    es("baskı dosyaları artık indirilebilir", (True, True),
       (bool(j["studyo"]["baski_pdf_url"]), bool(j["studyo"]["baski_png_url"])))
    es("satır görseli (varsa) depodaki tasarım önizlemesi", True,
       j["customer_image_url"] is None or j["customer_image_url"].startswith("/storage/"))

    print("\n── Kenar durumlar ──")
    li3 = LineItem(tenant_id=tenant.id, order_id=o.id, title="Düz kılıf", quantity=1,
                   properties=[{"name": "Telefon Modeli", "value": "iPhone 15"}])
    db.add(li3); db.commit()
    es("stüdyo tasarımı olmayan satır → anlaşılır hata", 422,
       c.post(f"/api/kisiye-ozel/line-items/{li3.id}/studyo-ata", headers=H).status_code)
    es("kılıf şablonu yoksa varyasyon boş kalır", None, kisiye_ozel._kilif_tipi(None))
    es("adında renk geçmeyen kılıf → varyasyon TAHMİN EDİLMEZ", None,
       kisiye_ozel._kilif_tipi(CaseTemplate(key="ozel", label="Premium")))
finally:
    db.rollback()
    for x in db.scalars(select(LineItem).where(LineItem.order_id == o.id)).all():
        db.delete(x)
    db.flush()
    for did in olusan:
        dd = db.get(Design, did)
        if dd:
            storage_svc.delete_design_file(dd.file_path)
            db.delete(dd)
    db.delete(db.get(Order, o.id))
    db.delete(db.get(CustomerDesign, cd.id))
    db.delete(db.get(DesignAsset, asset.id))
    db.delete(db.get(Customer, cu.id))
    db.flush()
    db.delete(db.get(Store, st.id))
    db.commit()
    (storage_svc.STORAGE_ROOT / arel).unlink(missing_ok=True)
    db.close()

print(f"\n{GECTI} GECTI, {KALDI} KALDI")
sys.exit(1 if KALDI else 0)
