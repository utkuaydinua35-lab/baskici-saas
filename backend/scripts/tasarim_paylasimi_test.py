"""Mağazalar arası tasarım paylaşımı — aynı atölyenin iki kanalı tek havuz.

Aynı işletmenin eski Shopify mağazası ile kendi vitrini ayrı "store" kayıtları.
Tasarımlar mağazaya bağlı olduğu için vitrin tarafında "bu mağazada o kodlu
tasarım yok" çıkıyordu.

Sınananlar:
  • paylaşım KAPALIYKEN eski davranış: mağaza yalnız kendi tasarımlarını görür
  • paylaşım açıkken liste, istatistik ve kod ile atama diğer mağazayı da görür
  • BAYİ mağazaları paylaşıma dahil DEĞİL (kendi kodlu katalogları karışmasın)
  • farklı gruptaki mağaza paylaşmaz; başka ATÖLYE asla paylaşmaz
  • listede tasarımın hangi mağazadan geldiği yazılı
  • paylaşım açılıp kapatılabiliyor (geri alınabilir)
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
from app.models import Design, LineItem, Order, Store, Tenant, User  # noqa: E402
from app.services import tasarim_kapsam as tk  # noqa: E402

GECTI = KALDI = 0
IZ = f"tptest{uuid.uuid4().hex[:6]}"


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


def magaza(ad, platform="shopify", grup=None, tid=None):
    st = Store(tenant_id=(tid or tenant.id), slug=f"{IZ}-{ad}", name=f"{IZ} {ad}",
               platform=platform, is_active=True, tasarim_grubu=grup)
    db.add(st); db.flush()
    return st


def tasarim(st, kod):
    d = Design(tenant_id=st.tenant_id, store_id=st.id, code=kod,
               file_path=f"x/{kod}.png", file_format="png")
    db.add(d); db.flush()
    return d


try:
    shopify = magaza("shopify", "shopify")
    vitrin = magaza("vitrin", "storefront")
    bayi_st = magaza("bayi", "bayii")
    yabanci = magaza("yabanci", "shopify", grup="ortak")   # aynı atölye, farklı grup değil → sonra
    d_shop = tasarim(shopify, f"{IZ}-S1")
    d_vit = tasarim(vitrin, f"{IZ}-V1")
    d_bayi = tasarim(bayi_st, f"{IZ}-B1")
    db.commit()

    print("\n── Paylaşım KAPALIYKEN (eski davranış) ──")
    es("kapsam yalnız kendisi", [shopify.id], tk.paylasilan_idler(db, shopify.id))
    liste = c.get(f"/api/designs?store_id={vitrin.id}&per_page=100", headers=H).json()
    kodlar = {x["code"] for x in liste["items"]}
    es("vitrin yalnız kendi tasarımını görür", ({f"{IZ}-V1"}, False),
       (kodlar & {f"{IZ}-S1", f"{IZ}-V1"}, liste["paylasimli"]))

    print("\n── Paylaşım açılıyor ──")
    r1 = c.patch(f"/api/stores/{shopify.id}", headers=H, json={"tasarim_grubu": "ortak"})
    r2 = c.patch(f"/api/stores/{vitrin.id}", headers=H, json={"tasarim_grubu": "ortak"})
    es("mağaza ayarı kaydedildi", (200, "ortak"), (r2.status_code, r2.json()["tasarim_grubu"]))
    db.expire_all()
    es("kapsam iki mağaza", {shopify.id, vitrin.id},
       set(tk.paylasilan_idler(db, vitrin.id)) - {yabanci.id})

    liste = c.get(f"/api/designs?store_id={vitrin.id}&per_page=100", headers=H).json()
    kodlar = {x["code"] for x in liste["items"]}
    es("vitrin artık Shopify tasarımını da görüyor", {f"{IZ}-S1", f"{IZ}-V1"},
       kodlar & {f"{IZ}-S1", f"{IZ}-V1"})
    es("paylaşım işareti yanıtta", True, liste["paylasimli"])
    gelen = next(x for x in liste["items"] if x["code"] == f"{IZ}-S1")
    es("hangi mağazadan geldiği yazılı", (True, f"{IZ} shopify"),
       (gelen["baska_magazadan"], gelen["magaza_adi"]))
    kendi = next(x for x in liste["items"] if x["code"] == f"{IZ}-V1")
    es("kendi tasarımı işaretsiz", False, kendi["baska_magazadan"])

    print("\n── Bayi mağazası karışmaz ──")
    es("bayi tasarımı listede YOK", False, f"{IZ}-B1" in kodlar)
    db.refresh(bayi_st)
    es("bayi mağazası gruba alınmadı", None, bayi_st.tasarim_grubu)

    print("\n── Sipariş detayında kod ile atama ──")
    o = Order(tenant_id=tenant.id, store_id=vitrin.id, external_id=f"{IZ}-1",
              order_number=f"{IZ}1", customer_name="Ayşe", current_stage=2, raw={})
    db.add(o); db.flush()
    li = LineItem(tenant_id=tenant.id, order_id=o.id, title="Kılıf", quantity=1,
                  product_id=f"{IZ}-p", properties=[])
    db.add(li); db.commit()
    # 1) Panelin tasarım seçicisi (manuel sipariş, askı, telafi aynı ucu kullanır)
    secici = c.get(f"/api/orders/_meta/store-designs?store_id={vitrin.id}", headers=H).json()
    es("seçicide diğer mağazanın tasarımı var", True,
       any(x["code"] == f"{IZ}-S1" for x in secici["items"]))
    es("seçicide bayi tasarımı YOK", False,
       any(x["code"] == f"{IZ}-B1" for x in secici["items"]))

    # 2) Müşteri ürün değişikliğinde "kod ile bağla" — eskiden "bu mağazada yok" diyordu
    li.urun_degisikligi = {"durum": "bekliyor", "baslik": "Yeni Ürün", "urun_id": "9999"}
    db.commit()
    r = c.post(f"/api/orders/{o.id}/line-items/{li.id}/urun-degisikligi", headers=H,
               json={"islem": "kod", "tasarim_kodu": f"{IZ}-S1"})
    es("diğer mağazanın kodu bağlanabiliyor", 200, r.status_code)
    db.expire_all()
    es("kalem o tasarıma bağlandı", d_shop.id, db.get(LineItem, li.id).assigned_design_id)

    print("\n── Ayrışma ──")
    baska_t = db.scalar(select(Tenant).where(Tenant.id != tenant.id).limit(1))
    if baska_t is not None:
        yab = magaza("baskaatolye", "shopify", grup="ortak", tid=baska_t.id)
        db.commit()
        es("BAŞKA ATÖLYE asla paylaşmaz", False,
           yab.id in tk.paylasilan_idler(db, vitrin.id))
    else:
        print("  · tek atölye, atlandı")
    c.patch(f"/api/stores/{shopify.id}", headers=H, json={"tasarim_grubu": "digergrup"})
    db.expire_all()
    es("farklı grup paylaşmaz", False, shopify.id in tk.paylasilan_idler(db, vitrin.id))

    print("\n── Geri alınabilirlik ──")
    r = c.patch(f"/api/stores/{vitrin.id}", headers=H, json={"tasarim_grubu": ""})
    es("paylaşım kapatılabiliyor", None, r.json()["tasarim_grubu"])
    db.expire_all()
    es("kapanınca eski davranışa döner", [vitrin.id], tk.paylasilan_idler(db, vitrin.id))
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
        db.execute(text("delete from designs where store_id = any(:s)").bindparams(s=ids))
        db.execute(text("delete from stores where id = any(:s)").bindparams(s=ids))
    db.commit()

print(f"\n{'='*46}\nGECTI: {GECTI}   KALDI: {KALDI}\n{'='*46}")
sys.exit(1 if KALDI else 0)
