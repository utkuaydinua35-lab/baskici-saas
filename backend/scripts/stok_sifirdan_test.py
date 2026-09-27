"""Stoğu sıfırdan kurma — sil, ihtiyaç duyulan modelleri aç, sayımı gir.

Sınananlar:
  • /api/stock/sifirla yazılı onay ister; yanlış onay hiçbir şey silmez
  • sıfırlama stok kalemlerini + TÜM hareket geçmişini siler; siparişe,
    kalıba ve tasarıma DOKUNMAZ
  • ana kalemler (gruplar) istenmedikçe korunur — bağlı ürün eşleşmeleri kalsın
  • kurulum: basılmamış kalıplardaki ve açık siparişlerdeki modeller için
    (model × varyasyon) 0 adetli kayıt açar
  • kurulum TEKRAR çalıştırılabilir: var olan kayıt ve sayılmış adet bozulmaz
  • sayım sonrası kalıp analizi ve toplam eksik doğru çalışır (eksik = ihtiyaç − raf)
  • Toplam Eksik yanıtı ihtiyaç/mevcut de döner (ekranda "-12" tek başına
    stok eksi sanılıyordu)
"""
from __future__ import annotations

import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import func, select, text  # noqa: E402

from app.auth.security import create_access_token  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (LineItem, Mold, MoldItem, Order, Plan, StockGroup, StockItem,  # noqa: E402
                        StockMovement, Store, Tenant, User)
from app.services import stock as stock_svc, stok_kurulum as sk  # noqa: E402

GECTI = KALDI = 0
IZ = f"sstest{uuid.uuid4().hex[:6]}"


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen: {beklenen!r}\n      gercek  : {gercek!r}")


db = SessionLocal()
# ⚠ Bu test GERÇEKTEN stok siliyor: kendi tenant'ında çalışır, canlı tenant'a dokunmaz.
# Üretim modülü açık bir plan gerekiyor: "stok" yetkisi o modülden geliyor
# (plansız kiracı en kısıtlı hâle düşer — bkz. services/abonelik.py).
plan = Plan(kod=f"{IZ}-plan", ad="Test", moduller=["magaza", "uretim"], aktif=True)
db.add(plan); db.flush()
tenant = Tenant(name=f"{IZ}-atolye", slug=f"{IZ}-atolye", plan="trial", plan_id=plan.id)
db.add(tenant); db.flush()
yon = User(tenant_id=tenant.id, email=f"{IZ}@ornek.test", full_name="Test",
           password_hash="x", role="owner", permissions=["stok", "kalip"], is_active=True)
db.add(yon); db.flush()
st = Store(tenant_id=tenant.id, slug=f"{IZ}-m", name="SS", platform="storefront", is_active=True)
db.add(st); db.flush()
db.commit()

H = {"Authorization": "Bearer " + create_access_token(user_id=str(yon.id), tenant_id=str(tenant.id),
                                                       email=yon.email, expires_minutes=30)}
c = TestClient(app)


def say(model, **kw):
    return int(db.scalar(select(func.count()).select_from(model)
                         .where(model.tenant_id == tenant.id)) or 0)


try:
    # ── Eski (güvenilmez) stok + hareket geçmişi ──
    g = StockGroup(tenant_id=tenant.id, name="Boş Kılıf", linked_products=[{"product_id": "p1"}])
    db.add(g); db.flush()
    eski = StockItem(tenant_id=tenant.id, group_id=g.id, sku=f"{IZ}-ESKI", name="iPhone 11",
                     category="bos_kilif", variation="siyah", model="iPhone 11",
                     models=["iPhone 11"], quantity=7)
    db.add(eski); db.flush()
    stock_svc.apply_adjustment(db, eski, 7, "manuel", note="eski kayıt")
    # Açık sipariş + basılmamış kalıp: kurulum bu modelleri açacak
    o = Order(tenant_id=tenant.id, store_id=st.id, external_id=f"{IZ}-1",
              order_number=f"{IZ}1", customer_name="Ayşe", current_stage=2,
              created_at_platform=datetime.now(UTC), raw={})
    db.add(o); db.flush()
    li = LineItem(tenant_id=tenant.id, order_id=o.id, title="Kılıf", quantity=1,
                  product_id=f"{IZ}-p", properties=[], device_model_override="iPhone 15")
    db.add(li); db.flush()
    mo = Mold(tenant_id=tenant.id, kod=f"{IZ}K1", variation="SİYAH", kalip_kodlari=[],
              kilif_sayisi=2, current_stage=3, print_status="bekliyor")
    db.add(mo); db.flush()
    for i, model in enumerate(("iPhone 15", "Galaxy S24")):
        db.add(MoldItem(tenant_id=tenant.id, mold_id=mo.id, store_id=st.id, slot_index=i,
                        kalip_kodu="A1", model=model, order_number=str(o.order_number)))
    db.commit()

    print("\n── Onay olmadan silinmez ──")
    r = c.post("/api/stock/sifirla", headers=H, json={"onay": "sil"})
    es("yanlış onay → 400", 400, r.status_code)
    es("hiçbir şey silinmedi", 1, say(StockItem))

    print("\n── Sıfırlama ──")
    r = c.post("/api/stock/sifirla", headers=H, json={"onay": "stok sifirla"})
    es("onay büyük/küçük harf duyarsız → 200", 200, r.status_code)
    es("kalem silindi", 0, say(StockItem))
    es("hareket geçmişi silindi", 0, say(StockMovement))
    es("ana kalem KORUNDU", 1, say(StockGroup))
    es("bağlı ürün eşleşmesi korundu", [{"product_id": "p1"}],
       db.scalar(select(StockGroup.linked_products).where(StockGroup.tenant_id == tenant.id)))
    es("sipariş silinmedi", 1, say(Order))
    es("kalıp silinmedi", 1, say(Mold))
    es("sayılar yanıtta", (1, 1), (r.json()["silinen_kalem"], r.json()["silinen_hareket"]))

    print("\n── Kurulum önizlemesi ──")
    r = c.get("/api/stock/kur/_onizleme?kaynak=kaliplar", headers=H)
    es("kalıp modelleri", ["Galaxy S24", "iPhone 15"], sorted(r.json()["modeller"]))
    r = c.get("/api/stock/kur/_onizleme?kaynak=siparisler", headers=H)
    es("sipariş modelleri", ["iPhone 15"], r.json()["modeller"])
    r = c.get("/api/stock/kur/_onizleme?kaynak=ikisi", headers=H)
    es("ikisi birleşik ve tekil", ["Galaxy S24", "iPhone 15"], sorted(r.json()["modeller"]))
    es("geçersiz kaynak → 400", 400, c.get("/api/stock/kur/_onizleme?kaynak=xx", headers=H).status_code)

    print("\n── Kurulum ──")
    r = c.post("/api/stock/kur", headers=H, json={"kaynak": "ikisi", "varyasyonlar": ["siyah", "şeffaf"]})
    es("2 model × 2 varyasyon = 4 kayıt", (200, 4), (r.status_code, r.json()["olusturulan"]))
    es("hepsi 0 adet", [0, 0, 0, 0],
       [q for (q,) in db.execute(select(StockItem.quantity).where(StockItem.tenant_id == tenant.id)).all()])
    es("hepsi boş kılıf kategorisinde", {"bos_kilif"},
       {k for (k,) in db.execute(select(StockItem.category).where(StockItem.tenant_id == tenant.id)).all()})
    es("var olan ana kaleme bağlandı", 1, say(StockGroup))
    es("geçersiz varyasyon → 400", 400,
       c.post("/api/stock/kur", headers=H, json={"kaynak": "ikisi", "varyasyonlar": ["altın"]}).status_code)

    print("\n── Sayım ve tekrar kurulum ──")
    kalem = db.scalar(select(StockItem).where(StockItem.tenant_id == tenant.id,
                                             StockItem.model == "iPhone 15",
                                             StockItem.variation == "siyah"))
    r = c.post(f"/api/stock/{kalem.id}/adjust", headers=H, json={"delta": 5, "reason": "manuel"})
    es("sayım girildi", (200, 5), (r.status_code, r.json()["quantity"]))
    r = c.post("/api/stock/kur", headers=H, json={"kaynak": "ikisi", "varyasyonlar": ["siyah", "şeffaf"]})
    es("tekrar kurulumda yeni kayıt yok", (0, 4), (r.json()["olusturulan"], r.json()["atlanan"]))
    db.expire_all()
    es("sayılan adet BOZULMADI", 5,
       db.scalar(select(StockItem.quantity).where(StockItem.id == kalem.id)))
    r = c.post("/api/stock/kur", headers=H, json={"kaynak": "ikisi", "varyasyonlar": ["beyaz"]})
    es("yeni varyasyon eklenebilir", 2, r.json()["olusturulan"])

    print("\n── Eksik hesabı ──")
    mo = db.scalar(select(Mold).where(Mold.tenant_id == tenant.id))
    res = stock_svc.analyze_mold_stock(db, tenant.id, mo)
    eksikler = {(x["model"]): x for x in res["missing_stock"]}
    es("iPhone 15: ihtiyaç 1, raf 5 → eksik yok", True, "iPhone 15" not in eksikler)
    es("Galaxy S24 eksik 1", 1, eksikler["Galaxy S24"]["missing"])
    es("Galaxy S24 sistemde VAR (0 adet)", False, eksikler["Galaxy S24"]["not_in_system"])
    tm = c.get("/api/molds/print/total-missing", headers=H).json()
    satir = next((i for i in tm["items"] if i.get("model") == "Galaxy S24"), None)
    es("toplam eksik satırı var", True, satir is not None)
    es("ihtiyaç ve raf adedi de dönüyor", (1, 0), (satir["ihtiyac"], satir["mevcut"]))
    es("eksik adedi pozitif sayı", 1, satir["total_missing"])
finally:
    db.rollback()
    for q in ("delete from stock_movements where tenant_id = :t",
              "delete from stock_items where tenant_id = :t",
              "delete from stock_groups where tenant_id = :t",
              "delete from mold_items where tenant_id = :t",
              "delete from molds where tenant_id = :t",
              "delete from activity_log where tenant_id = :t",
              "delete from order_status_history where tenant_id = :t",
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
