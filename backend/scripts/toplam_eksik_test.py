"""Toplam Eksik — hangi kalıplar sayılıyor?

İstenen: EKRANDA duran (panelde görünen) ve HENÜZ BASILMAMIŞ kalıplarda gereken
ama rafta olmayan boş kılıflar. Eskiden yalnız print_status'e bakılıyordu:
taslak kalıplar ve aylar önce TAMAMLANMIŞ kalıplar da listeyi şişiriyordu.

Sınananlar:
  • basılmamış panel kalıbı sayılır; eksik = ihtiyaç − raftaki
  • "basıldı" işaretli kalıp sayılmaz
  • TAMAMLANDI (aşama 5) kalıp sayılmaz — print_status boş olsa bile
  • TASLAK (aşama 1) kalıp sayılmaz
  • içi boş kalıp (kilif_sayisi 0) sayılmaz
  • rafta yeterli stok varsa satır çıkmaz; stok kaydı hiç yoksa "stokta yok"
  • aksesuar/işlemsiz ürün eksikleri VARSAYILAN OLARAK yok, ?siparisler=true ile gelir
  • "Gerekli Modeller" ile "Toplam Eksik" AYNI kalıp kümesini kullanır
"""
from __future__ import annotations

import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.auth.security import create_access_token  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (AccessoryProduct, LineItem, Mold, MoldItem, Order, Plan,  # noqa: E402
                        StockGroup, StockItem, Store, Tenant, User)
from app.services import kalip_kapsam  # noqa: E402

GECTI = KALDI = 0
IZ = f"tetest{uuid.uuid4().hex[:6]}"


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen: {beklenen!r}\n      gercek  : {gercek!r}")


db = SessionLocal()
# Kendi kiracısında çalışır — canlı stok/kalıp verisine dokunmaz
plan = Plan(kod=f"{IZ}-plan", ad="Test", moduller=["magaza", "uretim"], aktif=True)
db.add(plan); db.flush()
tenant = Tenant(name=f"{IZ}-atolye", slug=f"{IZ}-atolye", plan="trial", plan_id=plan.id)
db.add(tenant); db.flush()
yon = User(tenant_id=tenant.id, email=f"{IZ}@ornek.test", full_name="Test", password_hash="x",
           role="owner", permissions=["stok", "kalip"], is_active=True)
db.add(yon); db.flush()
st = Store(tenant_id=tenant.id, slug=f"{IZ}-m", name="TE", platform="storefront", is_active=True)
db.add(st); db.flush()
db.commit()

H = {"Authorization": "Bearer " + create_access_token(user_id=str(yon.id), tenant_id=str(tenant.id),
                                                      email=yon.email, expires_minutes=30)}
c = TestClient(app)


def kalip(kod, model, *, stage=3, durum="bekliyor", adet=1, varyasyon="SİYAH"):
    mo = Mold(tenant_id=tenant.id, store_id=st.id, kod=f"{IZ}{kod}", variation=varyasyon,
              kalip_kodlari=[], kilif_sayisi=adet, current_stage=stage, print_status=durum)
    db.add(mo); db.flush()
    for i in range(adet):
        db.add(MoldItem(tenant_id=tenant.id, mold_id=mo.id, store_id=st.id, slot_index=i,
                        kalip_kodu="A1", model=model))
    db.flush()
    return mo


def eksikler(siparisler=False):
    r = c.get(f"/api/molds/print/total-missing{'?siparisler=true' if siparisler else ''}", headers=H)
    assert r.status_code == 200, r.text
    d = r.json()
    return d, {i["model"]: i for i in d["items"] if i.get("model")}


try:
    print("\n── Kapsam kuralı ──")
    es("panel kalıbı (aşama 3, basılmamış) sayılır", True,
       kalip_kapsam.panelde_basilmamis(kalip("A", "iPhone 15")))
    es("'basıldı' işaretli sayılmaz", False,
       kalip_kapsam.panelde_basilmamis(kalip("B", "iPhone 14", durum="basildi")))
    es("TAMAMLANDI (aşama 5) sayılmaz", False,
       kalip_kapsam.panelde_basilmamis(kalip("C", "iPhone 13", stage=5)))
    es("TASLAK (aşama 1) sayılmaz", False,
       kalip_kapsam.panelde_basilmamis(kalip("D", "iPhone 12", stage=1)))
    es("içi boş kalıp sayılmaz", False,
       kalip_kapsam.panelde_basilmamis(kalip("E", "iPhone 11", adet=0)))
    db.commit()

    print("\n── Liste ──")
    d, m = eksikler()
    es("yalnız panel kalıbının modeli listede", ["iPhone 15"], sorted(m.keys()))
    es("kaç kalıptan hesaplandığı dönüyor", 1, d["kalip_sayisi"])
    es("eksik = ihtiyaç (raf boş)", (1, 1, 0), (m["iPhone 15"]["total_missing"],
                                               m["iPhone 15"]["ihtiyac"], m["iPhone 15"]["mevcut"]))
    es("stok kaydı yok işareti", True, m["iPhone 15"]["not_in_system"])

    print("\n── Raftaki stok düşülür ──")
    g = StockGroup(tenant_id=tenant.id, name="Boş Kılıf", linked_products=[])
    db.add(g); db.flush()
    kalem = StockItem(tenant_id=tenant.id, group_id=g.id, sku=f"{IZ}-S1", name="iPhone 15",
                      category="bos_kilif", variation="siyah", model="iPhone 15",
                      models=["iPhone 15"], quantity=1)
    db.add(kalem); db.commit()
    d, m = eksikler()
    es("stok yeterliyse satır YOK", [], sorted(m.keys()))
    kalip("F", "iPhone 15", adet=3)
    db.commit()
    d, m = eksikler()
    es("4 ihtiyaç − 1 raf = 3 eksik", (3, 4, 1), (m["iPhone 15"]["total_missing"],
                                                 m["iPhone 15"]["ihtiyac"], m["iPhone 15"]["mevcut"]))
    es("iki kalıptan geldiği yazılı", 2, m["iPhone 15"]["mold_count"])

    print("\n── Aksesuar (kalıba girmeyen) satırları ──")
    g2 = StockGroup(tenant_id=tenant.id, name="Ekran Koruyucu", linked_products=[
        {"store_id": str(st.id), "product_id": f"{IZ}-ek", "title": "Ekran"}])
    db.add(g2); db.flush()
    db.add(AccessoryProduct(tenant_id=tenant.id, store_id=st.id, product_id=f"{IZ}-ek",
                            product_title="Ekran Koruyucu"))
    o = Order(tenant_id=tenant.id, store_id=st.id, external_id=f"{IZ}-1", order_number=f"{IZ}1",
              customer_name="Ayşe", current_stage=2, created_at_platform=datetime.now(UTC), raw={})
    db.add(o); db.flush()
    db.add(LineItem(tenant_id=tenant.id, order_id=o.id, title="Ekran Koruyucu", quantity=2,
                    product_id=f"{IZ}-ek", properties=[], device_model_override="iPhone 15"))
    db.commit()
    d, _ = eksikler()
    es("varsayılanda aksesuar satırı YOK", 0, d["siparis_kalem_sayisi"])
    es("varsayılan: siparişler dahil değil", False, d["siparisler_dahil"])
    d2, _ = eksikler(siparisler=True)
    es("istenirse aksesuar satırı gelir", 1, d2["siparis_kalem_sayisi"])
    es("her satır kaynağını söylüyor (kalip / siparis)", {"kalip", "siparis"},
       {i.get("kaynak") for i in d2["items"]})
    es("aksesuar satırı sipariş kaynaklı", "Ekran Koruyucu",
       next(i["grup"] for i in d2["items"] if i.get("kaynak") == "siparis"))

    print("\n── Gerekli Modeller ile aynı kalıp kümesi ──")
    rm = c.get("/api/molds/print/required-models", headers=H).json()
    es("yalnız panel kalıplarının modelleri", {"iPhone 15"},
       {i["model"] for i in rm["items"]})
finally:
    db.rollback()
    for q in ("delete from mold_items where tenant_id = :t",
              "delete from molds where tenant_id = :t",
              "delete from stock_movements where tenant_id = :t",
              "delete from stock_items where tenant_id = :t",
              "delete from stock_groups where tenant_id = :t",
              "delete from accessory_products where tenant_id = :t",
              "delete from line_items where tenant_id = :t",
              "delete from orders where tenant_id = :t",
              "delete from stores where tenant_id = :t",
              "delete from users where tenant_id = :t",
              "delete from tenants where id = :t",
              "delete from plans where kod = :k"):
        db.execute(text(q).bindparams(**({"k": f"{IZ}-plan"} if ":k" in q else {"t": tenant.id})))
    db.commit()

print(f"\n{'='*46}\nGECTI: {GECTI}   KALDI: {KALDI}\n{'='*46}")
sys.exit(1 if KALDI else 0)
