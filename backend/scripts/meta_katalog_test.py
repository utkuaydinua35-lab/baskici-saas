"""Koleksiyon → Meta ürün seti eşitlemesi (Meta'ya GİDİLMEZ; çağrılar yakalanır).

  • her aktif, ürünlü koleksiyon için set açılır; filtre = ürün slug'ları
    (akıştaki g:id ile aynı → set üyeliği birebir)
  • ikinci eşitlemede aynı set GÜNCELLENİR (yeniden açılmaz)
  • taslak/özel ürün sete girmez; boş koleksiyon atlanır
  • koleksiyon pasifleşince/silinince BİZİM açtığımız set silinir
  • Meta'da elle silinmiş set yeniden açılır
  • anahtar yoksa anlaşılır hata
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import CatalogCollection, CatalogProduct, Store, Tenant  # noqa: E402
from app.services import meta_katalog  # noqa: E402

GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


cagrilar: list[tuple] = []
silinmis: set[str] = set()
sayac = [0]


def sahte_istek(yontem, yol, token, veri=None):
    cagrilar.append((yontem, yol, veri))
    if yol in silinmis:
        raise meta_katalog.KatalogHatasi("100: Unsupported post request. Object does not exist")
    if yontem == "POST" and yol.endswith("/product_sets"):
        sayac[0] += 1
        return {"id": f"set{sayac[0]}"}
    return {"success": True}


meta_katalog._istek = sahte_istek

db = SessionLocal()
IZ = f"mk{uuid.uuid4().hex[:6]}"
tenant = db.scalar(select(Tenant).limit(1))
st = Store(tenant_id=tenant.id, slug=f"{IZ}-v", name="MK", platform="storefront",
           config={"meta_catalog_id": "111", "meta_catalog_token": "EAAgizli"})
db.add(st); db.flush()


def urun(slug, status="active"):
    p = CatalogProduct(tenant_id=tenant.id, store_id=st.id, slug=f"{IZ}-{slug}", title=slug,
                       status=status, base_price=100)
    db.add(p)
    return p


a, b, taslak, ozel = urun("a"), urun("b"), urun("t", "draft"), urun("o", "ozel")
k1 = CatalogCollection(tenant_id=tenant.id, store_id=st.id, slug=f"{IZ}-anime", title="Anime")
k2 = CatalogCollection(tenant_id=tenant.id, store_id=st.id, slug=f"{IZ}-bos", title="Boş")
db.add_all([k1, k2]); db.flush()
k1.products = [a, b, taslak, ozel]
db.commit()
try:
    print("\n── İlk eşitleme ──")
    s = meta_katalog.esitle(db, st)
    es("bir set açıldı, boş koleksiyon atlandı", (1, 0, 1), (s["acilan"], s["guncellenen"], s["atlanan"]))
    y, yol, veri = cagrilar[0]
    es("doğru kataloğa açıldı, adı koleksiyon adı", ("POST", "111/product_sets", "Anime"), (y, yol, veri["name"]))
    es("filtre: yalnız yayındaki ürünlerin slug'ları (taslak/özel yok)",
       {"retailer_id": {"is_any": sorted([a.slug, b.slug])}}, json.loads(veri["filter"]))
    db.expire_all()
    es("eşleşme kaydedildi", {str(k1.id): "set1"}, db.get(Store, st.id).config["meta_urun_setleri"])

    print("\n── İkinci eşitleme ──")
    cagrilar.clear()
    s = meta_katalog.esitle(db, db.get(Store, st.id))
    es("aynı set güncellendi (yeni açılmadı)", (0, 1, [("POST", "set1")]),
       (s["acilan"], s["guncellenen"], [(c[0], c[1]) for c in cagrilar]))

    print("\n── Meta'da elle silinmiş set ──")
    silinmis.add("set1"); cagrilar.clear()
    s = meta_katalog.esitle(db, db.get(Store, st.id))
    db.expire_all()
    es("yeniden açıldı", (1, "set2"), (s["acilan"], db.get(Store, st.id).config["meta_urun_setleri"][str(k1.id)]))

    print("\n── Koleksiyon pasifleşince ──")
    db.get(CatalogCollection, k1.id).is_active = False
    db.commit(); cagrilar.clear()
    s = meta_katalog.esitle(db, db.get(Store, st.id))
    db.expire_all()
    es("bizim açtığımız set silindi", (1, [("DELETE", "set2")], {}),
       (s["silinen"], [(c[0], c[1]) for c in cagrilar], db.get(Store, st.id).config["meta_urun_setleri"]))

    print("\n── Ayarsız mağaza ──")
    st2 = Store(tenant_id=tenant.id, slug=f"{IZ}-y", name="Y", platform="storefront", config={})
    try:
        meta_katalog.esitle(db, st2)
        es("anahtar yoksa anlaşılır hata", True, False)
    except meta_katalog.KatalogHatasi as e:
        es("anahtar yoksa anlaşılır hata", True, "anahtar" in str(e))
finally:
    db.rollback()
    for k in (k1, k2):
        kk = db.get(CatalogCollection, k.id)
        kk.products = []
    db.flush()
    for p in db.scalars(select(CatalogProduct).where(CatalogProduct.store_id == st.id)).all():
        db.delete(p)
    db.delete(db.get(CatalogCollection, k1.id)); db.delete(db.get(CatalogCollection, k2.id))
    db.flush()
    db.delete(db.get(Store, st.id))
    db.commit()
    db.close()

print(f"\n{GECTI} GECTI, {KALDI} KALDI")
sys.exit(1 if KALDI else 0)
