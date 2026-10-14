"""Ürün akışı (Meta katalogu / Google Merchant) — içerik ve önbellek.

  • yalnız 'active' ürünler; taslak ve 'ozel' (linkle) ürünler YOK
  • stok: en az bir satılabilir varyant → in stock; hepsi tükenmiş → out of stock
  • product_type "A > B" (eskiden "&amp;gt;" çift kaçışla bozuk çıkıyordu)
  • önbellek: ikinci istek yeniden üretmez; süre dolunca yeni ürün görünür
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import CatalogCollection, CatalogProduct, CatalogVariant, Store, Tenant  # noqa: E402
from app.routers import public_shop  # noqa: E402

GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


db = SessionLocal()
IZ = f"akis{uuid.uuid4().hex[:6]}"
tenant = db.scalar(select(Tenant).limit(1))
st = Store(tenant_id=tenant.id, slug=f"{IZ}-v", name="Akış Test", platform="storefront",
           config={"storefront_url": "https://ornek.test"})
db.add(st); db.flush()
col_a = CatalogCollection(tenant_id=tenant.id, store_id=st.id, slug=f"{IZ}-a", title="Kılıflar")
col_b = CatalogCollection(tenant_id=tenant.id, store_id=st.id, slug=f"{IZ}-b", title="Anime & Manga")
db.add_all([col_a, col_b]); db.flush()


def urun(slug, status, stoklar):
    p = CatalogProduct(tenant_id=tenant.id, store_id=st.id, slug=f"{IZ}-{slug}", title=slug,
                       status=status, base_price=299)
    db.add(p); db.flush()
    for i, (takip, adet) in enumerate(stoklar):
        db.add(CatalogVariant(tenant_id=tenant.id, product_id=p.id, model_key=f"m{i}",
                              model_display=f"Model {i}", track_stock=takip, quantity=adet))
    return p


stokta = urun("stokta", "active", [(True, 0), (False, 0)])        # biri sınırsız → stokta
stokta.collections = [col_a, col_b]
urun("tukendi", "active", [(True, 0), (True, 0)])
urun("taslak", "draft", [(False, 0)])
urun("ozel", "ozel", [(False, 0)])
db.commit()
c = TestClient(app)
onbellek = Path(tempfile.gettempdir()) / "baskici-feed" / f"{st.id}-meta.xml"
try:
    xml = c.get(f"/api/shop/{st.slug}/feed/meta.xml").text
    ogeler = {blok.split("</g:id>")[0]: blok for blok in xml.split("<g:id>")[1:]}
    es("yalnız yayındaki ürünler (taslak ve 'ozel' yok)", sorted([f"{IZ}-stokta", f"{IZ}-tukendi"]), sorted(ogeler))
    es("sınırsız varyantı olan ürün stokta", True, "<g:availability>in stock<" in ogeler.get(f"{IZ}-stokta", ""))
    es("tüm varyantları tükenen ürün stok dışı", True, "<g:availability>out of stock<" in ogeler.get(f"{IZ}-tukendi", ""))
    es("kategori metni tek kaçışlı ('>' ve '&' doğru)", True,
       "<g:product_type>Kılıflar &gt; Anime &amp; Manga</g:product_type>" in xml or
       "<g:product_type>Anime &amp; Manga &gt; Kılıflar</g:product_type>" in xml)
    es("çift kaçış yok", False, "&amp;gt;" in xml)

    print("\n── Önbellek ──")
    urun("yeni", "active", [(False, 0)])
    db.commit()
    es("süre dolmadan: yeni ürün henüz akışta değil (yeniden üretilmedi)", False,
       f"{IZ}-yeni" in c.get(f"/api/shop/{st.slug}/feed/meta.xml").text)
    eski = time.time() - public_shop.FEED_TTL_SN - 5
    os.utime(onbellek, (eski, eski))
    es("süre dolunca: yeni ürün akışta", True, f"{IZ}-yeni" in c.get(f"/api/shop/{st.slug}/feed/meta.xml").text)
    g = c.get(f"/api/shop/{st.slug}/feed/google.xml")
    es("Google akışı: varyant başına satır", (200, 5), (g.status_code, g.text.count("<item>")))
    es("Google: barkodsuz özel üretim bildirildi (GTIN uyarısı çıkmaz)", 5,
       g.text.count("<g:identifier_exists>no</g:identifier_exists>"))
    es("Google: model başına ürün grubu", True, "<g:item_group_id>" in g.text)
finally:
    db.rollback()
    for p in db.scalars(select(CatalogProduct).where(CatalogProduct.store_id == st.id)).all():
        p.collections = []
        db.delete(p)
    db.flush()
    db.delete(col_a); db.delete(col_b)
    db.delete(db.get(Store, st.id))
    db.commit()
    for tur in ("meta", "google"):
        (Path(tempfile.gettempdir()) / "baskici-feed" / f"{st.id}-{tur}.xml").unlink(missing_ok=True)
    db.close()

print(f"\n{GECTI} GECTI, {KALDI} KALDI")
sys.exit(1 if KALDI else 0)
