"""Ürün sayfası önerileri: "Yanında Al" ve "Bu ürüne benzer ürünler".

  • Yanında Al = cross-sell ayarı (elle ürünler, sonra koleksiyonların ürünleri)
  • tek seçenekli ürün "hızlı ekle" bilgisini taşır; çok seçenekli / özel alanlı /
    stoksuz ürün taşımaz (müşteri ürün sayfasına gider)
  • benzer: elle seçim varsa o, yoksa aynı koleksiyondan otomatik
  • taslak, 'ozel' (linkle) ürün ve ürünün kendisi listeye girmez
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import CatalogCollection, CatalogProduct, CatalogVariant, Store, Tenant  # noqa: E402

GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


db = SessionLocal()
IZ = f"on{uuid.uuid4().hex[:6]}"
tenant = db.scalar(select(Tenant).limit(1))
st = Store(tenant_id=tenant.id, slug=f"{IZ}-v", name="Öneri", platform="storefront", config={})
db.add(st); db.flush()


def urun(ad, modeller=("tek",), status="active", stok=True, ozel_alan=False, pos=0):
    p = CatalogProduct(tenant_id=tenant.id, store_id=st.id, slug=f"{IZ}-{ad}", title=ad, status=status,
                       base_price=100, position=pos,
                       custom_fields=[{"key": "isim", "label": "İsim", "type": "text", "required": False}]
                       if ozel_alan else None)
    db.add(p); db.flush()
    for m in modeller:
        db.add(CatalogVariant(tenant_id=tenant.id, product_id=p.id, model_key=m, model_display=m.title(),
                              track_stock=not stok, quantity=0))
    return p


ana = urun("kilif", modeller=("iphone-15", "iphone-16"))
tutucu = urun("tutucu", pos=1)                                   # tek seçenek → hızlı
airpods = urun("airpods", modeller=("beyaz", "siyah"), pos=2)     # çok seçenek
isimli = urun("isimli", ozel_alan=True, pos=3)                    # özel alan
stoksuz = urun("stoksuz", stok=False, pos=4)
taslak = urun("taslak", status="draft", pos=5)
ozel = urun("ozel", status="ozel", pos=6)
kardes = urun("kardes", modeller=("iphone-15",), pos=7)
kol = CatalogCollection(tenant_id=tenant.id, store_id=st.id, slug=f"{IZ}-aks", title="Aksesuar")
kol2 = CatalogCollection(tenant_id=tenant.id, store_id=st.id, slug=f"{IZ}-kilif", title="Kılıf")
db.add_all([kol, kol2]); db.flush()
kol.products = [airpods, isimli, stoksuz, taslak, ozel, ana]
kol2.products = [ana, kardes]
ana.cross_sell_slugs = [tutucu.slug, ana.slug]
ana.cross_sell_koleksiyonlar = [kol.slug]
db.commit()
c = TestClient(app)
try:
    d = c.get(f"/api/shop/{st.slug}/products/{ana.slug}").json()
    ya = d["yaninda_al"]
    es("Yanında Al: önce elle seçilen, sonra koleksiyon (taslak/özel/kendisi yok)",
       [tutucu.slug, airpods.slug, isimli.slug, stoksuz.slug], [x["slug"] for x in ya])
    hiz = {x["slug"]: bool(x.get("hizli")) for x in ya}
    es("hızlı ekle: yalnız tek seçenekli, stokta, özel alansız ürün",
       {tutucu.slug: True, airpods.slug: False, isimli.slug: False, stoksuz.slug: False}, hiz)
    es("hızlı ekle varyantı doğru", "Tek", ya[0]["hizli"]["model_display"])
    es("benzer: seçim yokken aynı koleksiyondan otomatik", True,
       kardes.slug in [x["slug"] for x in d["related"]] and ana.slug not in [x["slug"] for x in d["related"]])

    ana2 = db.get(CatalogProduct, ana.id)
    ana2.benzer_slugs = [isimli.slug]
    ana2.benzer_koleksiyonlar = [kol2.slug]
    ana2.cross_sell_slugs, ana2.cross_sell_koleksiyonlar = None, None
    db.commit()
    d = c.get(f"/api/shop/{st.slug}/products/{ana.slug}").json()
    es("benzer: elle seçim + koleksiyon (kendisi hariç)", [isimli.slug, kardes.slug],
       [x["slug"] for x in d["related"]])
    es("Yanında Al seçimi yoksa bölüm boş (sayfada gösterilmez)", [], d["yaninda_al"])
finally:
    db.rollback()
    for k in (kol, kol2):
        kk = db.get(CatalogCollection, k.id); kk.products = []
    db.flush()
    for p in db.scalars(select(CatalogProduct).where(CatalogProduct.store_id == st.id)).all():
        db.delete(p)
    db.delete(db.get(CatalogCollection, kol.id)); db.delete(db.get(CatalogCollection, kol2.id))
    db.flush()
    db.delete(db.get(Store, st.id))
    db.commit()
    db.close()

print(f"\n{GECTI} GECTI, {KALDI} KALDI")
sys.exit(1 if KALDI else 0)
