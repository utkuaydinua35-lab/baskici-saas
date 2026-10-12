"""Vitrin ürünü -> baskı tasarımı bağı (kalıp planlayıcı eşleşmesi).

NEDEN: Vitrin siparişlerinde line_items.product_id = catalog_products.id
(UUID), Design.product_id ise Shopify sayısal kimliğidir. İkisi eşleşemez;
planlayıcı bu yüzden "ürün tasarıma bağlanmamış" diyordu. Bağ artık
catalog_products.design_id'de açıkça tutulur.

Sınananlar:
  • bağ YOKKEN planlayıcı eksik der (eski davranış korunur)
  • bağ varken planlayıcı tasarımı çözer, kalem kalıba girer
  • ORTAK HAVUZdaki başka mağazanın tasarımı da bağlanabilir
  • bağ kaldırılabilir (geri alınabilir) — tekrar eksik der
  • API: başka ATÖLYEnin tasarımı bağlanamaz (404)
  • toplu eşleştirme: kuru çalışma yazmaz, uygula bağlar,
    birden fazla adayla eşleşene DOKUNMAZ, zaten bağlıyı korur
  • Shopify sayısal kimliğinde bu bağ devreye girmez
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
    CatalogProduct, Design, LineItem, Order, Store, Tenant, User,
)
from app.services import katalog_tasarim as kt, mold_planner  # noqa: E402

GECTI = KALDI = 0
IZ = f"kttest{uuid.uuid4().hex[:6]}"


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


def tasarim(st, kod, baslik=None, ad=None):
    d = Design(tenant_id=st.tenant_id, store_id=st.id, code=kod, name=ad,
               product_title=baslik, file_path=f"x/{kod}.png", file_format="png",
               kalip_tipi="SİYAH")
    db.add(d); db.flush()
    return d


def urun(st, baslik, slug=None):
    p = CatalogProduct(tenant_id=st.tenant_id, store_id=st.id, title=baslik,
                       slug=slug or f"{IZ}-{uuid.uuid4().hex[:6]}",
                       status="active", base_price=Decimal("399.00"))
    db.add(p); db.flush()
    return p


def plan_eksikleri(store_id):
    p = mold_planner.plan_molds(db, tenant_id=tenant.id, store_id=store_id)
    return p, {(e["product_id"], e["reason"]) for e in p["eksikler"]}


yabanci_tenant = None
try:
    shopify = magaza("shopify", "shopify", grup="ortak")
    vitrin = magaza("vitrin", "storefront", grup="ortak")
    d_shop = tasarim(shopify, f"{IZ}-S1", ad="ortak havuz tasarimi")
    db.commit()

    u = urun(vitrin, f"{IZ} Kılıf Tek Eşleşme")
    o = Order(tenant_id=tenant.id, store_id=vitrin.id, external_id=f"{IZ}-1",
              order_number=f"{IZ}1", customer_name="Ayşe", current_stage=2, raw={})
    db.add(o); db.flush()
    li = LineItem(tenant_id=tenant.id, order_id=o.id, product_id=str(u.id),
                  title=u.title, variant_title="iPhone 15", quantity=1,
                  device_model_override="iPhone 15", properties=[], raw={})
    db.add(li); db.commit()

    print("\n── Bağ YOKKEN (hatanın kendisi) ──")
    p, eksik = plan_eksikleri(vitrin.id)
    es("planlayıcı 'ürün tasarıma bağlanmamış' der", True,
       (str(u.id), "urun_tasarima_baglanmamis") in eksik)
    es("kalıp oluşturulamıyor", False, p["can_create"])

    print("\n── Ortak havuzdaki tasarım bağlanıyor ──")
    r = c.patch(f"/api/catalog/products/{u.id}", headers=H,
                json={"design_id": str(d_shop.id)})
    es("API bağı kaydetti", (200, str(d_shop.id)),
       (r.status_code, r.json().get("design_id")))
    es("yanıtta tasarım kodu var", f"{IZ}-S1", r.json().get("design_kodu"))
    db.expire_all()
    p, eksik = plan_eksikleri(vitrin.id)
    es("artık eksik DEĞİL", False, (str(u.id), "urun_tasarima_baglanmamis") in eksik)
    es("kalem kalıba girdi", True, p["total_units"] >= 1)
    es("tek ürün araması da bağı bulur", d_shop.id,
       getattr(kt.tasarim_bul(db, vitrin.id, u.id), "id", None))

    print("\n── Shopify kimliğinde bu bağ devreye girmez ──")
    es("sayısal product_id -> None", None, kt.tasarim_bul(db, vitrin.id, "7391234567"))
    es("başka mağazanın ürünü -> None", None, kt.tasarim_bul(db, shopify.id, u.id))

    print("\n── Başka ATÖLYEnin tasarımı bağlanamaz ──")
    yabanci_tenant = Tenant(name=f"{IZ} yabanci", slug=f"{IZ}-yabanci")
    db.add(yabanci_tenant); db.flush()
    y_st = magaza("ystore", "shopify", grup="ortak", tid=yabanci_tenant.id)
    d_yabanci = tasarim(y_st, f"{IZ}-Y1")
    db.commit()
    r = c.patch(f"/api/catalog/products/{u.id}", headers=H,
                json={"design_id": str(d_yabanci.id)})
    es("yabancı tasarım reddedildi", 404, r.status_code)
    db.expire_all()
    es("bağ bozulmadı", d_shop.id, db.get(CatalogProduct, u.id).design_id)

    print("\n── Bağ kaldırılabiliyor (geri alınabilir) ──")
    r = c.patch(f"/api/catalog/products/{u.id}", headers=H, json={"design_id": None})
    es("bağ kaldırıldı", (200, None), (r.status_code, r.json().get("design_id")))
    db.expire_all()
    _, eksik = plan_eksikleri(vitrin.id)
    es("tekrar eksik diyor", True, (str(u.id), "urun_tasarima_baglanmamis") in eksik)

    print("\n── Toplu eşleştirme (başlık birebir) ──")
    # tam = başlığı tasarımın product_title'ı ile birebir aynı
    d_tam = tasarim(shopify, f"{IZ}-T1", baslik=f'BERNZ "{IZ} Tam" Tasarım Kılıf')
    u_tam = urun(vitrin, f'BERNZ “{IZ} Tam” Tasarım   Kılıf')   # tırnak/boşluk farklı
    # ad alanında tam başlık tutan tasarım (göç etmiş kayıtlar böyle)
    d_ad = tasarim(shopify, f"{IZ}-A1", ad=f'BERNZ "{IZ} Addan" Tasarım Kılıf')
    u_ad = urun(vitrin, f'BERNZ "{IZ} Addan" Tasarım Kılıf')
    # iki tasarım aynı başlığı taşıyor -> belirsiz, elle bağlanmalı
    tasarim(shopify, f"{IZ}-C1", baslik=f'BERNZ "{IZ} Cift" Tasarım Kılıf')
    tasarim(vitrin, f"{IZ}-C2", baslik=f'BERNZ "{IZ} Cift" Tasarım Kılıf')
    u_cift = urun(vitrin, f'BERNZ "{IZ} Cift" Tasarım Kılıf')
    u_yok = urun(vitrin, f"{IZ} Hiç eşleşmeyen baskısız kılıf")
    u_elle = urun(vitrin, f'BERNZ "{IZ} Tam" Tasarım Kılıf')    # elle başka tasarıma bağlı
    u_elle.design_id = d_shop.id
    db.commit()

    kuru = kt.toplu_eslestir(db, vitrin.id, uygula=False)
    db.expire_all()
    es("kuru çalışma hiçbir şey yazmadı", (None, None),
       (db.get(CatalogProduct, u_tam.id).design_id,
        db.get(CatalogProduct, u_ad.id).design_id))
    es("kuru raporda bağlanacaklar sayılı", True, kuru["baglandi"] >= 2)
    es("belirsiz ayrı sayıldı", True, kuru["belirsiz"] >= 1)
    es("eşleşmeyen ayrı sayıldı", True, kuru["eslesmeyen"] >= 1)

    rapor = kt.toplu_eslestir(db, vitrin.id, uygula=True)
    db.expire_all()
    es("product_title ile eşleşen bağlandı", d_tam.id, db.get(CatalogProduct, u_tam.id).design_id)
    es("name alanıyla eşleşen bağlandı", d_ad.id, db.get(CatalogProduct, u_ad.id).design_id)
    es("belirsiz olan BAĞLANMADI", None, db.get(CatalogProduct, u_cift.id).design_id)
    es("eşleşmeyen BAĞLANMADI", None, db.get(CatalogProduct, u_yok.id).design_id)
    es("elle verilen karar korundu", d_shop.id, db.get(CatalogProduct, u_elle.id).design_id)
    es("rapor sayıları tutuyor", (rapor["baglandi"], rapor["zaten_bagli"] >= 1), (2, True))

    print("\n── Panel seçicisi ──")
    r = c.get(f"/api/catalog/products/{u_tam.id}/tasarim-ara", headers=H).json()
    es("başlık önerisi veriliyor", f"{IZ}-T1", (r.get("oneri") or {}).get("code"))
    es("öneri ortak havuzdan geldiği işaretli", True, (r.get("oneri") or {}).get("baska_magazadan"))
    r2 = c.get(f"/api/catalog/products/{u_cift.id}/tasarim-ara?q={IZ}-C1", headers=H).json()
    es("kod aramasıyla bulunuyor", True, any(x["code"] == f"{IZ}-C1" for x in r2["items"]))
    r3 = c.get(f"/api/catalog/products/{u_cift.id}/tasarim-onerisi", headers=H).json()
    es("belirsizde öneri verilmiyor", None, r3["oneri"])

    print("\n── Aksesuar/kişiye özel işaretleme ekranı vitrini görüyor ──")
    # Bu uç Shopify'da platform API'sine gider; vitrinde ürünler bizim
    # veritabanımızda — dönmezse o ekranlar vitrin mağazasında boş kalır
    # (baskısız kılıfı aksesuar işaretlemek imkânsız hale geliyordu).
    r4 = c.get(f"/api/designs/_meta/products?store_id={vitrin.id}", headers=H)
    kimlikler = {x["id"] for x in r4.json().get("items", [])}
    es("vitrin ürünleri listelenebiliyor", (200, True),
       (r4.status_code, str(u_yok.id) in kimlikler))
    r5 = c.get(f"/api/designs/_meta/products?store_id={vitrin.id}"
               f"&search=baskısız", headers=H).json()
    es("başlık aramasıyla süzülüyor", [str(u_yok.id)], [x["id"] for x in r5["items"]])
finally:
    db.rollback()
    ids = [x for (x,) in db.execute(select(Store.id).where(Store.slug.like(f"{IZ}-%"))).all()]
    oids = [x for (x,) in db.execute(select(Order.id).where(Order.external_id.like(f"{IZ}%"))).all()]
    if oids:
        for q in ("delete from mold_items where line_item_id in"
                  " (select id from line_items where order_id = any(:o))",
                  "delete from order_status_history where order_id = any(:o)",
                  "delete from line_items where order_id = any(:o)",
                  "delete from orders where id = any(:o)"):
            db.execute(text(q).bindparams(o=oids))
    if ids:
        db.execute(text("delete from catalog_products where store_id = any(:s)").bindparams(s=ids))
        db.execute(text("delete from designs where store_id = any(:s)").bindparams(s=ids))
        db.execute(text("delete from stores where id = any(:s)").bindparams(s=ids))
    if yabanci_tenant is not None:
        db.execute(text("delete from tenants where id = :t").bindparams(t=yabanci_tenant.id))
    db.commit()

print(f"\n{'='*46}\nGECTI: {GECTI}   KALDI: {KALDI}\n{'='*46}")
sys.exit(1 if KALDI else 0)
