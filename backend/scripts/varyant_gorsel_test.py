"""Varyant görseli, koleksiyonlu cross-sell ve koleksiyon görseli kırpma.

  • görsel → varyant eşleştirme yalnız ürünün KENDİ varyantlarını kabul eder
  • vitrin, yalnız ürünün 'varyant görseli' ayarı açıkken eşleşmeyi gönderir
  • cross-sell'de seçilen koleksiyon, koleksiyon olarak değil ÜRÜNLERİ olarak gelir
  • koleksiyon kırpma ayarı temizlenir (geçersiz oran/sınır dışı değer)
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.auth.security import create_access_token  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (CatalogCollection, CatalogImage, CatalogProduct, CatalogVariant,  # noqa: E402
                        Store, Tenant, User)

GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


db = SessionLocal()
IZ = f"vg{uuid.uuid4().hex[:6]}"
tenant = db.scalar(select(Tenant).limit(1))
admin = db.scalar(select(User).where(User.tenant_id == tenant.id,
                                     User.role.in_(["owner", "yonetici"])).limit(1))
H = {"Authorization": "Bearer " + create_access_token(
    user_id=str(admin.id), tenant_id=str(admin.tenant_id), email=admin.email, expires_minutes=30)}
c = TestClient(app)

st = Store(tenant_id=tenant.id, slug=f"{IZ}-v", name="VG", platform="storefront", config={})
db.add(st); db.flush()


def urun(slug, modeller):
    p = CatalogProduct(tenant_id=tenant.id, store_id=st.id, slug=f"{IZ}-{slug}", title=slug,
                       status="active", base_price=100, position=len(slug))
    db.add(p); db.flush()
    for m in modeller:
        db.add(CatalogVariant(tenant_id=tenant.id, product_id=p.id, model_key=m, model_display=m.title(),
                              track_stock=False, quantity=0))
    return p


airpods = urun("airpods", ["kirmizi", "beyaz"])
g1 = CatalogImage(tenant_id=tenant.id, product_id=airpods.id, file_path="x/genel.jpg", position=0)
g2 = CatalogImage(tenant_id=tenant.id, product_id=airpods.id, file_path="x/kirmizi.jpg", position=1)
db.add_all([g1, g2])
a, b, d = urun("a", ["m"]), urun("b", ["m"]), urun("d", ["m"])
kol = CatalogCollection(tenant_id=tenant.id, store_id=st.id, slug=f"{IZ}-kol", title="Aksesuar")
db.add(kol); db.flush()
kol.products = [a, b]
db.commit()
try:
    print("\n── Varyant görseli ──")
    r = c.patch(f"/api/catalog/images/{g2.id}/varyantlar", headers=H, json={"varyant_anahtarlari": ["kirmizi"]})
    es("görsel varyanta eşlendi", (200, ["kirmizi"]), (r.status_code, r.json().get("varyant_anahtarlari")))
    yanlis = c.patch(f"/api/catalog/images/{g2.id}/varyantlar", headers=H, json={"varyant_anahtarlari": ["iphone-15"]})
    es("üründe olmayan varyant reddedilir", 422, yanlis.status_code)

    def vitrin():
        return {im["url"]: im["varyantlar"] for im in
                c.get(f"/api/shop/{st.slug}/products/{airpods.slug}").json()["images"]}
    es("ayar KAPALIYKEN vitrine eşleşme gitmez", {"/storage/x/genel.jpg": [], "/storage/x/kirmizi.jpg": []}, vitrin())
    c.patch(f"/api/catalog/products/{airpods.id}", headers=H, json={"varyant_gorsel": True})
    es("ayar AÇIKKEN kırmızı görsel kırmızı varyanta bağlı", ["kirmizi"], vitrin().get("/storage/x/kirmizi.jpg"))
    c.patch(f"/api/catalog/products/{airpods.id}", headers=H, json={"title": "AirPods Kılıfı"})
    db.expire_all()
    es("başka alan güncellenince ayar kapanmaz", True, db.get(CatalogProduct, airpods.id).varyant_gorsel)
    c.patch(f"/api/catalog/images/{g2.id}/varyantlar", headers=H, json={"varyant_anahtarlari": []})
    es("bağ kaldırılabilir (geri alma)", [], vitrin().get("/storage/x/kirmizi.jpg"))

    print("\n── Cross-sell: koleksiyon → ürünleri ──")
    c.patch(f"/api/catalog/products/{airpods.id}", headers=H,
            json={"cross_sell_slugs": [d.slug], "cross_sell_koleksiyonlar": [kol.slug]})
    oneri = [x["slug"] for x in c.get(f"/api/shop/{st.slug}/cart-suggestions",
                                      params={"slugs": airpods.slug, "limit": 3}).json()["items"]]
    es("önce elle seçilen ürün, sonra koleksiyonun ürünleri", [d.slug, a.slug, b.slug], oneri[:3])
    es("koleksiyonun kendisi değil ürünleri gelir", False, kol.slug in oneri)

    print("\n── Koleksiyon görseli kırpma ──")
    k = c.patch(f"/api/catalog/collections/{kol.id}", headers=H,
                json={"gorsel_kirp": {"oran": "16:9", "x": 130, "y": 20, "zoom": 9}}).json()
    es("kırpma temizlendi (x≤100, zoom≤3, varsayılan düzen yan/sağ)",
       {"oran": "16:9", "x": 100.0, "y": 20.0, "zoom": 3.0, "duzen": "yan", "taraf": "sag"}, k["gorsel_kirp"])
    k = c.patch(f"/api/catalog/collections/{kol.id}", headers=H, json={"gorsel_kirp": {"oran": "7:3"}}).json()
    es("bilinmeyen oran → doğal", "dogal", k["gorsel_kirp"]["oran"])
    vk = next(x for x in c.get(f"/api/shop/{st.slug}/collections").json() if x["slug"] == kol.slug)
    es("vitrin kırpma ayarını alır", "dogal", (vk.get("gorsel_kirp") or {}).get("oran"))
finally:
    db.rollback()
    kol = db.get(CatalogCollection, kol.id)
    kol.products = []
    db.flush()
    for p in db.scalars(select(CatalogProduct).where(CatalogProduct.store_id == st.id)).all():
        db.delete(p)
    db.delete(kol)
    db.flush()
    db.delete(db.get(Store, st.id))
    db.commit()
    db.close()

print(f"\n{GECTI} GECTI, {KALDI} KALDI")
sys.exit(1 if KALDI else 0)
