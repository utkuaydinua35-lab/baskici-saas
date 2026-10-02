"""Ürün araması uçtan uca — /products?q=… + kayıt + panel "ne aradılar" raporu."""
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
from app.models import CatalogProduct, CatalogVariant, Store, Tenant, User  # noqa: E402
from app.services import arama  # noqa: E402

GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen: {beklenen!r}\n      gercek  : {gercek!r}")


db = SessionLocal()
IZ = f"ara{uuid.uuid4().hex[:6]}"
tenant = db.scalar(select(Tenant).limit(1))
yon = db.scalar(select(User).where(User.tenant_id == tenant.id, User.role.in_(["owner", "yonetici"])).limit(1))
H = {"Authorization": "Bearer " + create_access_token(user_id=str(yon.id), tenant_id=str(tenant.id),
                                                       email=yon.email, expires_minutes=30)}
c = TestClient(app)
try:
    st = Store(tenant_id=tenant.id, name="Arama testi", slug=f"{IZ}-v", platform="storefront",
               config={"shop_domain": f"{IZ}.example.com"})
    db.add(st); db.flush()
    for i, (ad, etiket) in enumerate([("Sarı Kırmızı Tasarım Kılıfı", ""), ("Güneş Çiçek Kılıfı", "doğa"),
                                      ("Ferrari Ascend Kılıfı", "f1")]):
        p = CatalogProduct(tenant_id=tenant.id, store_id=st.id, slug=f"{IZ}-{i}", title=ad, tags=etiket,
                           status="active", base_price=Decimal("299.90"), currency="TRY", position=i)
        db.add(p); db.flush()
        db.add(CatalogVariant(tenant_id=tenant.id, product_id=p.id, model_key="ip15",
                              model_display="iPhone 15", quantity=5))
    db.commit()
    arama.dusur()
    U = f"/api/shop/{st.slug}/products"

    print("\n── Arama ucu ──")
    r = c.get(U, params={"q": "cicek kilif"}).json()
    es("Türkçe harfsiz çok kelimeli", [f"{IZ}-1"], [x["slug"] for x in r["items"]])
    r = c.get(U, params={"q": "ferari"}).json()
    es("yazım hatası", f"{IZ}-2", r["items"][0]["slug"] if r["items"] else None)
    r = c.get(U, params={"q": "sari"}).json()
    es("'tasarım' içinden eşleşmez", [f"{IZ}-0"], [x["slug"] for x in r["items"]])
    r = c.get(U, params={"q": "iphone 15", "sort": "fiyat-artan"}).json()
    es("başka sıralamayla da çalışır", 3, r["total"])
    r = c.get(U, params={"q": "kilif", "collection": "yok-boyle-koleksiyon"}).json()
    es("diğer süzgeçlerle birleşir", 0, r["total"])

    print("\n── Katalog değişince: bekletmeden eski dizin, arkada yenisi ──")
    import time as _t
    p = CatalogProduct(tenant_id=tenant.id, store_id=st.id, slug=f"{IZ}-9", title="Uzay Gemisi Kılıfı",
                       status="active", base_price=Decimal("299.90"), currency="TRY", position=9)
    db.add(p); db.commit()
    from app.services import vitrin_cache
    vitrin_cache.markalari_dusur(); arama.dusur()
    r = c.get(U, params={"q": "uzay"}).json()
    es("ilk arama eski dizinle hemen yanıtlanır", 0, r["total"])
    for _ in range(50):
        _t.sleep(0.1)
        if c.get(U, params={"q": "uzay"}).json()["total"]:
            break
    es("yeni ürün arkadaki yenilemeden sonra bulunur", 1, c.get(U, params={"q": "uzay"}).json()["total"])
    db.delete(p); db.commit(); arama.dusur()
    for _ in range(50):
        _t.sleep(0.1)
        if not c.get(U, params={"q": "uzay"}).json()["total"]:
            break

    print("\n── Kayıt ve rapor ──")
    c.get(U, params={"q": "Uzay Gemisi", "kaydet": 1})
    c.get(U, params={"q": "uzay gemisi", "kaydet": 1})
    c.get(U, params={"q": "kılıf", "kaydet": 1})
    c.get(U, params={"q": "kılıf"})                 # öneri (kaydet yok) → yazılmaz
    rap = c.get(f"/api/store-settings/{st.id}/arama-raporu", headers=H).json()
    es("toplam / sonuçsuz", (3, 2), (rap["toplam"], rap["sonucsuz_toplam"]))
    es("sonuçsuz normalleştirilip gruplanır", [{"sorgu": "uzay gemisi", "adet": 2}],
       [{"sorgu": x["sorgu"], "adet": x["adet"]} for x in rap["sonucsuz"]])
    es("popüler listede", {"uzay gemisi", "kilif"}, {x["sorgu"] for x in rap["populer"]})
    es("rapor yetkisiz kapalı", 401, c.get(f"/api/store-settings/{st.id}/arama-raporu").status_code)
finally:
    db.rollback()
    db.execute(text("delete from stores where slug like :s"), {"s": f"{IZ}-%"})
    db.commit()
    db.close()

print(f"\n{'='*46}\nGECTI: {GECTI}   KALDI: {KALDI}\n{'='*46}")
sys.exit(1 if KALDI else 0)
