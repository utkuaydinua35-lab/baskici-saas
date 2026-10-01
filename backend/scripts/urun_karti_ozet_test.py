"""Ürün kartı özeti — veritabanında hesaplanan (_kart_ozetleri) ile eski
Python hesabı (tüm varyantları yükleyip saymak) BİREBİR aynı olmalı.

Liste ucu artık varyantları yüklemiyor (canlıda 24'lük sayfa ~7.400 varyant
satırı çekiyordu, 1-2 sn). "N model için uygun" ve "Son N adet" rozetleri
değişmemeli: aktif/pasif varyant, stok takipli/takipsiz karışımı, eksi stok.
"""
import sys
import uuid
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import CatalogProduct, CatalogVariant, Store  # noqa: E402
from app.routers.public_shop import _kart_ozetleri, _serialize_product_card  # noqa: E402

GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen: {beklenen!r}\n      gercek  : {gercek!r}")


db = SessionLocal()
IZ = f"kot{uuid.uuid4().hex[:6]}"
try:
    store = db.scalar(select(Store).limit(1))
    senaryolar = {
        # ad: [(model, aktif, takipli, adet)]
        "hepsi takipli": [("iPhone 15", True, True, 3), ("iPhone 15", True, True, 1), ("iPhone 16", True, True, 0)],
        "karışık takip": [("A", True, True, 5), ("B", True, False, 0)],
        "pasif varyant sayılmaz": [("A", True, True, 2), ("B", False, True, 9), ("C", False, False, 0)],
        "eksi stok sıfır sayılır": [("A", True, True, -4), ("B", True, True, 2)],
        "yalnız pasif": [("A", False, True, 3)],
        "varyantsız": [],
    }
    urunler = {}
    for i, (ad, vs) in enumerate(senaryolar.items()):
        p = CatalogProduct(tenant_id=store.tenant_id, store_id=store.id, slug=f"{IZ}-{i}", title=ad,
                           status="active", base_price=Decimal("100"), currency="TRY")
        db.add(p); db.flush()
        for j, (model, aktif, takip, adet) in enumerate(vs):
            db.add(CatalogVariant(tenant_id=store.tenant_id, product_id=p.id, model_key=f"{model}-{j}",
                                  model_display=model, is_active=aktif,
                                  track_stock=takip, quantity=adet, sku=f"{IZ}-{i}-{j}"))
        urunler[ad] = p.id
    db.flush()
    yuklu = {p.id: p for p in db.scalars(select(CatalogProduct).where(CatalogProduct.id.in_(urunler.values()))
                                         .options(selectinload(CatalogProduct.variants),
                                                  selectinload(CatalogProduct.images))).all()}
    ozet = _kart_ozetleri(db, list(urunler.values()))
    bos = {"model_count": 0, "total_stock": None}
    for ad, pid in urunler.items():
        eski = _serialize_product_card(yuklu[pid])
        yeni = _serialize_product_card(yuklu[pid], ozet.get(pid, bos))
        es(ad, (eski["model_count"], eski["total_stock"]), (yeni["model_count"], yeni["total_stock"]))
finally:
    db.rollback()
    db.close()

print(f"\nGECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
