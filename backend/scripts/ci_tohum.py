"""CI için TOHUM VERİ — testlerin çalışabileceği en küçük gerçekçi veri kümesi.

⚠ NEDEN VAR: 34 test paketi veritabanı istiyor ve çoğu "sipariş yok, atlandı"
deyip ÇIKIŞ KODU 0 ile bitiyor. Boş bir veritabanında CI yemyeşil olur ama
HİÇBİR ŞEY sınanmamış olur — sessizce atlayan test, olmayan testten kötüdür.
Bu betik testlerin dayandığı asgari veriyi kurar.

⚠ ASLA CANLIDA ÇALIŞTIRILMAZ. `ENV=ci` değilse ve veritabanında zaten sipariş
varsa kendini durdurur.

Kurduğu: tenant · yönetici (DevAdmin12345!) · Shopify OLMAYAN mağaza (harici
çağrı olmasın) · telefon modelleri · tasarımlar · çok kalemli siparişler ·
kalıp + slotlar · boş kılıf stoğu.
"""
from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select  # noqa: E402

from app.auth.security import hash_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    CatalogProduct, CatalogVariant, Design, LineItem, Mold, MoldItem, Order,
    PhoneModel, StockGroup, StockItem, Store, Tenant, User,
)

SIFRE = "DevAdmin12345!"
# ⚠ ".test" AYRILMIŞ bir TLD; email-validator reddediyor ve giriş 422 veriyor.
# Gerçekçi ama bize ait olmayan bir alan adı kullanılıyor.
ALAN = "ci-atolye.com"
MODELLER = [
    ("IPHONE-15", "iPhone 15", 7.9, 16.2),
    ("IPHONE-14-PRO", "iPhone 14 Pro", 7.8, 15.9),
    ("IPHONE-16-PROMAX", "iPhone 16 Pro Max", 8.3, 17.1),
    ("SAMSUNG-S24", "Samsung S24", 7.7, 16.0),
]


def _guvenlik_kontrolu(db) -> None:
    """Canlı veriye dokunmayı ÖNLE."""
    if os.environ.get("ENV") == "ci":
        return
    mevcut = db.scalar(select(func.count(Order.id))) or 0
    if mevcut > 50:
        raise SystemExit(
            f"DURDURULDU: veritabanında {mevcut} sipariş var ve ENV=ci değil.\n"
            "Bu betik yalnız BOŞ/CI veritabanı içindir.")


def main() -> int:
    db = SessionLocal()
    _guvenlik_kontrolu(db)

    if db.scalar(select(Tenant).limit(1)):
        print("tohum: veri zaten var, atlandı")
        return 0

    t = Tenant(name="CI Atölye", slug="ci-atolye")
    db.add(t); db.flush()

    db.add(User(tenant_id=t.id, email="ci-admin@ci-atolye.com", full_name="CI Yönetici",
                role="yonetici", is_active=True, password_hash=hash_password(SIFRE)))
    # Platform yöneticisi ayrı: yedek/platform uçları bunu istiyor.
    db.add(User(tenant_id=t.id, email="ci-platform@ci-atolye.com", full_name="CI Platform",
                role="owner", is_active=True, is_platform_admin=True,
                password_hash=hash_password(SIFRE)))

    # ⚠ platform "shopify" DEĞİL: testler harici API'ye gitmesin.
    s = Store(tenant_id=t.id, slug="ci-magaza", name="CI Mağaza", platform="vitrin",
              is_active=True)
    db.add(s); db.flush()

    for key, ad, w, h in MODELLER:
        db.add(PhoneModel(spec_key=key, display_name=ad, width_cm=w, height_cm=h,
                          tenant_id=t.id))

    tasarimlar = []
    for i in range(3):
        d = Design(tenant_id=t.id, store_id=s.id, code=f"CI{i:03d}",
                   file_path=f"ci/tasarim-{i}.pdf", file_format="pdf",
                   name=f"CI Tasarım {i}")
        db.add(d); tasarimlar.append(d)
    db.flush()

    # Boş kılıf stoğu — kalıp planı stok uyarısı bunu okuyor
    g = StockGroup(tenant_id=t.id, name="Boş Kılıf", is_active=True)
    db.add(g); db.flush()
    for key, ad, _w, _h in MODELLER:
        for v in ("SİYAH", "ŞEFFAF"):
            db.add(StockItem(tenant_id=t.id, group_id=g.id, sku=f"{key}-{v}",
                             name=f"{v} {ad}", category="bos_kilif",
                             variation=v, model=ad, quantity=25, is_active=True))

    # Siparişler: biri TEK kalemli, ikisi ÇOK kalemli (testler ikisini de arıyor)
    simdi = datetime.now(UTC)
    for n in range(4):
        o = Order(
            tenant_id=t.id, store_id=s.id, external_id=str(9000 + n),
            order_number=str(9000 + n), name=f"#{9000 + n}",
            customer_name=f"CI Müşteri {n}", customer_email=f"ci{n}@ci-atolye.com",
            current_stage=3, created_at_platform=simdi - timedelta(days=n),
            raw={"id": 9000 + n, "shipping_address": {
                "first_name": "CI", "last_name": f"Müşteri {n}",
                "address1": "Test Cad. No:1", "city": "Kadıköy",
                "province": "İstanbul", "phone": "05321602442",
                "country": "Turkey", "country_code": "TR"}},
        )
        db.add(o); db.flush()
        kalem_sayisi = 1 if n == 0 else 3
        for k in range(kalem_sayisi):
            key, ad, _w, _h = MODELLER[k % len(MODELLER)]
            db.add(LineItem(
                tenant_id=t.id, order_id=o.id, external_id=f"{o.external_id}-{k}",
                title=f'CI "Tasarım {k}" Telefon Kılıfı - CI Serisi',
                quantity=1, device_model_override=ad,
                assigned_design_id=tasarimlar[k % len(tasarimlar)].id,
                kilif_varyasyon="SİYAH",
            ))
    db.flush()

    # Vitrin mağazası + satılabilir ürün — smoke_test (uçtan uca sipariş akışı)
    # bunu arıyor. Ayrı mağaza: yukarıdaki üretim mağazası "vitrin" platformunda
    # değil ve testlerin çoğu Shopify OLMAYAN bir mağaza istiyor.
    vs = Store(tenant_id=t.id, slug="ci-vitrin", name="CI Vitrin",
               platform="storefront", is_active=True)
    db.add(vs); db.flush()
    for i in range(2):
        cp = CatalogProduct(tenant_id=t.id, store_id=vs.id, slug=f"ci-urun-{i}",
                            title=f"CI Ürün {i}", base_price=299.0, status="active")
        db.add(cp); db.flush()
        for key, ad, _w, _h in MODELLER[:2]:
            db.add(CatalogVariant(tenant_id=t.id, product_id=cp.id,
                                  model_key=key, model_display=ad, is_active=True))

    # Kalıp + slotlar — kalıptan çıkarma/geri alma testleri buna dayanıyor
    o0 = db.scalar(select(Order).where(Order.tenant_id == t.id).limit(1))
    mo = Mold(tenant_id=t.id, kod="CI-A1", variation="SİYAH", kilif_sayisi=2,
              status="olusturuldu", current_stage=1)
    db.add(mo); db.flush()
    kalemler = db.scalars(select(LineItem).where(LineItem.tenant_id == t.id).limit(2)).all()
    for i, li in enumerate(kalemler):
        li.is_kaliba_eklendi = True
        db.add(MoldItem(tenant_id=t.id, mold_id=mo.id, line_item_id=li.id,
                        slot_index=i, kalip_kodu="IPHONE-15-GROUP|SIYAH",
                        design_code=f"CI{i:03d}", model="iPhone 15",
                        order_number=o0.order_number if o0 else None))

    db.commit()
    print(f"tohum: tenant={t.slug} · 4 sipariş · {len(MODELLER)} model · 1 kalıp hazır")
    return 0


if __name__ == "__main__":
    sys.exit(main())
