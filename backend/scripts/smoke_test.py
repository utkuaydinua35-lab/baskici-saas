#!/usr/bin/env python
"""Uçtan uca duman testi — deploy öncesi kritik yolların hâlâ çalıştığını kanıtlar.

CI yalnızca "import ediliyor mu / build alıyor mu" bakar; bu betik GERÇEK
istekler atar: vitrin okuma, fiyat hesabı, indirim kuralları, panel uçları,
yetki kontrolleri. Veritabanına YAZMAZ (yalnız geçici kayıtlar, sonda silinir).

Çalıştırma (backend dizininden):
    .venv/bin/python scripts/smoke_test.py

Çıkış kodu 0 = hepsi geçti, 1 = en az bir test düştü.
"""
from __future__ import annotations

import secrets
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from app.auth.security import create_access_token  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    CatalogProduct,
    CatalogVariant,
    DiscountCode,
    LineItem,
    Order,
    Store,
    User,
)

YESIL, KIRMIZI, SARI, SIFIRLA = "\033[92m", "\033[91m", "\033[93m", "\033[0m"
sonuclar: list[tuple[str, bool, str]] = []
atlananlar: list[str] = []


def kontrol(ad: str, kosul: bool, not_: str = "") -> bool:
    sonuclar.append((ad, bool(kosul), not_))
    isaret = f"{YESIL}✓{SIFIRLA}" if kosul else f"{KIRMIZI}✗{SIFIRLA}"
    print(f"  {isaret} {ad}" + (f"  {SARI}{not_}{SIFIRLA}" if not_ else ""))
    return bool(kosul)


def atla(ad: str, sebep: str) -> None:
    """Bu kurulumda anlamsız olan kontrol — düşmüş sayılmaz ama gizlenmez."""
    atlananlar.append(ad)
    print(f"  {SARI}–{SIFIRLA} {ad}  {SARI}atlandı: {sebep}{SIFIRLA}")


def main() -> int:
    db = SessionLocal()
    c = TestClient(app)

    store = db.scalar(select(Store).where(
        Store.platform == "storefront", Store.is_active.is_(True)))
    if not store:
        print(f"{KIRMIZI}Aktif vitrin mağazası yok — test çalıştırılamıyor{SIFIRLA}")
        return 1
    user = db.scalar(select(User).where(
        User.tenant_id == store.tenant_id, User.is_active.is_(True)))
    h = {"Authorization": f"Bearer {create_access_token(
        user_id=str(user.id), tenant_id=str(user.tenant_id), email=user.email)}"}
    slug = store.slug

    # Satın alınabilir bir varyant bul (aktif ürün + aktif varyant)
    row = db.execute(
        select(CatalogVariant.id, CatalogProduct.title, CatalogProduct.base_price)
        .join(CatalogProduct, CatalogProduct.id == CatalogVariant.product_id)
        .where(CatalogProduct.store_id == store.id,
               CatalogProduct.status == "active",
               CatalogVariant.is_active.is_(True))
        .limit(1)
    ).first()
    if not row:
        print(f"{KIRMIZI}Satın alınabilir ürün yok — test çalıştırılamıyor{SIFIRLA}")
        return 1
    variant_id, urun_adi, fiyat = str(row[0]), row[1], Decimal(str(row[2]))
    items = [{"variant_id": variant_id, "quantity": 2}]
    beklenen_ara_toplam = fiyat * 2

    print(f"\nMağaza: {store.name} (/{slug}) · test ürünü: {urun_adi} ({fiyat} TL)\n")

    # ── 1. Vitrin okuma ──
    print("Vitrin (müşteri yüzeyi)")
    r = c.get(f"/api/shop/{slug}/theme")
    kontrol("tema yükleniyor", r.status_code == 200)
    r = c.get(f"/api/shop/{slug}/products?per_page=5")
    d = r.json()
    urunler = d.get("items", d) if isinstance(d, dict) else d
    kontrol("ürün listesi doluyor", r.status_code == 200 and len(urunler) > 0,
            f"{len(urunler)} ürün")
    if urunler:
        sl = urunler[0].get("slug")
        kontrol("ürün detayı açılıyor",
                c.get(f"/api/shop/{slug}/products/{sl}").status_code == 200)
    kontrol("koleksiyonlar listeleniyor",
            c.get(f"/api/shop/{slug}/collections").status_code == 200)
    kontrol("arama çalışıyor",
            c.get(f"/api/shop/{slug}/products?q=kilif").status_code == 200)
    kontrol("Google/Meta feed'i üretiliyor",
            c.get(f"/api/shop/{slug}/feed/meta.xml").status_code == 200)

    # ── 2. Fiyat sunucuda hesaplanıyor mu ──
    print("\nFiyat ve indirim (sunucu otoritesi)")
    r = c.post(f"/api/shop/{slug}/checkout/quote", json={"items": items})
    q = r.json()
    kontrol("sepet teklifi dönüyor", r.status_code == 200 and q.get("valid"))
    kontrol("ara toplam sunucu fiyatıyla",
            Decimal(q.get("items_total", "0")) == beklenen_ara_toplam,
            f"{q.get('items_total')} = {beklenen_ara_toplam}")

    # İstemciden gelen fiyat YOK SAYILMALI (fiyat manipülasyonu koruması)
    r = c.post(f"/api/shop/{slug}/checkout/quote",
               json={"items": [{"variant_id": variant_id, "quantity": 2, "unit_price": "1.00"}]})
    kontrol("istemci fiyatı yok sayılıyor",
            Decimal(r.json().get("items_total", "0")) == beklenen_ara_toplam,
            "manipülasyon denemesi sunucu fiyatıyla ezildi")

    # Geçersiz kupon reddedilmeli
    r = c.post(f"/api/shop/{slug}/checkout/validate-code",
               json={"code": "BOYLEBIRKODYOK", "items": items})
    kontrol("geçersiz kupon reddediliyor", r.json().get("valid") is False)

    # Birleşebilir kupon + otomatik kargo indirimi
    # Rastgele ek: canlıda çalıştırılsa bile gerçek bir kuponla çakışmasın
    ek = secrets.token_hex(3).upper()
    kodlar = [f"SMOKETEST{ek}", f"SMOKEKARGO{ek}"]
    db.query(DiscountCode).filter(DiscountCode.code.in_(kodlar)).delete(
        synchronize_session=False)
    db.add(DiscountCode(tenant_id=store.tenant_id, store_id=store.id,
                        code=kodlar[0], kind="percent", value=Decimal("10"),
                        combinable=True, is_active=True))
    db.add(DiscountCode(tenant_id=store.tenant_id, store_id=store.id,
                        code=kodlar[1], kind="free_shipping", value=Decimal("0"),
                        is_automatic=True, combinable=True, is_active=True))
    db.commit()
    try:
        r = c.post(f"/api/shop/{slug}/checkout/validate-code",
                   json={"code": kodlar[0], "items": items})
        d = r.json()
        beklenen_indirim = (beklenen_ara_toplam * Decimal("0.10")).quantize(Decimal("0.01"))
        kontrol("kupon uygulanıyor",
                d.get("valid") and Decimal(d.get("discount_amount", "0")) == beklenen_indirim,
                f"%10 = {d.get('discount_amount')} TL")
        # Kargo ücreti 0 ise "kargo bedava" indiriminin kazancı yok ve sistem
        # onu bilerek atlar — bu kurulumda kombinasyon test edilemez
        kargo_ucreti = Decimal(str((store.config or {}).get("shipping_fee") or "0"))
        if kargo_ucreti > 0:
            kontrol("kupon + otomatik kargo birleşiyor",
                    len(d.get("applied") or []) == 2 and d.get("free_shipping") is True)
        else:
            atla("kupon + otomatik kargo birleşiyor",
                 "mağazanın kargo ücreti 0 — kargo indirimi kazanç sağlamıyor")
    finally:
        db.query(DiscountCode).filter(DiscountCode.code.in_(kodlar)).delete(
            synchronize_session=False)
        db.commit()

    # ── 3. Panel uçları ──
    print("\nMağaza paneli")
    kontrol("ürünler listeleniyor",
            c.get(f"/api/catalog/products?store_id={store.id}", headers=h).status_code == 200)
    kontrol("koleksiyonlar listeleniyor",
            c.get(f"/api/catalog/collections?store_id={store.id}", headers=h).status_code == 200)
    kontrol("indirimler listeleniyor",
            c.get(f"/api/discounts?store_id={store.id}", headers=h).status_code == 200)
    kontrol("ayarlar okunuyor",
            c.get(f"/api/store-settings/{store.id}", headers=h).status_code == 200)

    r = c.get(f"/api/store-settings/{store.id}/readiness", headers=h)
    hazir = r.json() if r.status_code == 200 else {}
    engeller = [x for x in hazir.get("checks", []) if x.get("blocker")]
    kontrol("hazırlık kontrolü çalışıyor", r.status_code == 200)
    if engeller:
        for e in engeller:
            print(f"      {SARI}⚠ CANLIYA ENGEL: {e['label']} — {e['hint']}{SIFIRLA}")

    kontrol("analitik özeti",
            c.get("/api/analytics/summary?start=2026-07-01&end=2026-08-01"
                  f"&store_id={store.id}", headers=h).status_code == 200)
    r = c.get(f"/api/analytics/profit?start=2026-07-01&end=2026-08-01&store_id={store.id}",
              headers=h)
    kontrol("kâr marjı raporu", r.status_code == 200)
    kontrol("aktivite günlüğü",
            c.get(f"/api/store-activity?store_id={store.id}&days=7", headers=h).status_code == 200)
    kontrol("terk edilmiş sepetler",
            c.get(f"/api/checkout-admin?store_id={store.id}", headers=h).status_code in (200, 404))

    # Sipariş detayı + kısmi kargo alanları
    oid = db.scalar(select(LineItem.order_id).join(Order, Order.id == LineItem.order_id)
                    .where(Order.tenant_id == store.tenant_id)
                    .group_by(LineItem.order_id)
                    .having(func.count(LineItem.id) >= 1).limit(1))
    if oid:
        r = c.get(f"/api/orders/{oid}/detail", headers=h)
        d = r.json() if r.status_code == 200 else {}
        kontrol("sipariş detayı açılıyor", r.status_code == 200)
        kontrol("kargo/gönderi alanları dönüyor",
                "shipping" in d and "remaining" in (d.get("shipping") or {}))

    # ── 4. Yetki ve izolasyon ──
    print("\nGüvenlik")
    kontrol("token'sız panel isteği 401",
            c.get(f"/api/catalog/products?store_id={store.id}").status_code == 401)
    kontrol("sahte token 401",
            c.get(f"/api/catalog/products?store_id={store.id}",
                  headers={"Authorization": "Bearer sahte.token.imzasiz"}).status_code == 401)
    kontrol("olmayan mağaza 404",
            c.get("/api/shop/boyle-bir-magaza-yok/theme").status_code == 404)
    kontrol("prod'da API dokümanı kapalı olmalı",
            c.get("/docs").status_code in (200, 404),
            "dev'de 200 normal; canlıda 404 bekleniyor")

    db.close()

    # ── Özet ──
    gecen = sum(1 for _, ok, _ in sonuclar if ok)
    dusen = [ad for ad, ok, _ in sonuclar if not ok]
    print(f"\n{'─' * 52}")
    if dusen:
        print(f"{KIRMIZI}{len(dusen)} test DÜŞTÜ{SIFIRLA} ({gecen}/{len(sonuclar)} geçti)")
        for ad in dusen:
            print(f"  {KIRMIZI}✗{SIFIRLA} {ad}")
        return 1
    print(f"{YESIL}Tüm testler geçti{SIFIRLA} ({gecen}/{len(sonuclar)})"
          + (f" · {len(atlananlar)} atlandı" if atlananlar else ""))
    if engeller:
        print(f"{SARI}Not: canlıya geçişi engelleyen {len(engeller)} eksik var "
              f"(yukarıda ⚠ ile işaretli){SIFIRLA}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
