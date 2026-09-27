#!/usr/bin/env python3
"""Ek seçenek fiyat farkı — ödeme doğrulaması (services/checkout).

Tutar YALNIZ ürün tanımından hesaplanmalı; istemcinin gönderdiği fiyat hiçbir
yerde okunmamalı. Aynı model farklı seçenekle ayrı satır olabilmeli ama
birebir aynı satır ve stoğu aşan toplam reddedilmeli. Kendi verisini kurar,
her şey TEK işlemde koşar ve ROLLBACK edilir.

Koşum: cd backend && .venv/bin/python scripts/ek_secenek_ucret_test.py
"""
import sys
import uuid
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import CatalogProduct, CatalogVariant, CheckoutSession, Store, Tenant  # noqa: E402
from app.routers.catalog import _clean_custom_fields  # noqa: E402
from app.services import checkout as co  # noqa: E402
from app.services.storefront_order import _build_raw  # noqa: E402

GECTI = KALDI = 0


def kontrol(ad, gercek, beklenen):
    global GECTI, KALDI
    if gercek == beklenen:
        GECTI += 1
        print(f"  ✓ {ad}")
    else:
        KALDI += 1
        print(f"  ✗ {ad}\n      beklenen: {beklenen!r}\n      gercek  : {gercek!r}")


def reddedilir(ad, fn):
    try:
        fn()
        kontrol(ad, "kabul edildi", "reddedildi")
    except co.CheckoutError:
        kontrol(ad, "reddedildi", "reddedildi")


def main() -> int:
    db = SessionLocal()
    ek = uuid.uuid4().hex[:6]
    try:
        print("── alan tanımı temizliği ──")
        alanlar = _clean_custom_fields([
            {"label": "Vernik", "type": "color", "options": ["Evet", "Hayır"],
             "option_prices": {"Evet": "50", "Hayır": "0", "Olmayan": "99"},
             "option_images": {"Evet": "/storage/a.jpg", "Hayır": "https://dis.site/x.jpg"}},
            {"label": "İsim", "type": "text", "price": "25,5"},
            {"label": "Not", "type": "text", "price": "-5"},
            {"label": "Pahalı", "type": "text", "price": "999999999"},
        ])
        kontrol("sıfır ve tanımsız seçenek ücreti atılır", alanlar[0].get("option_prices"), {"Evet": "50.00"})
        kontrol("yalnız kendi depomuzdaki görsel kabul edilir",
                alanlar[0].get("option_images"), {"Evet": "/storage/a.jpg"})
        kontrol("virgüllü ücret", alanlar[1].get("price"), "25.50")
        kontrol("negatif ücret atılır", "price" in alanlar[2], False)
        kontrol("üst sınırı aşan ücret atılır", "price" in alanlar[3], False)

        t = Tenant(name=f"Ek ücret {ek}", slug=f"eku-{ek}", plan="x")
        db.add(t)
        db.flush()
        store = Store(tenant_id=t.id, slug=f"eku-{ek}", name="Vitrin", platform="storefront", config={})
        db.add(store)
        db.flush()
        urun = CatalogProduct(tenant_id=t.id, store_id=store.id, slug=f"urun-{ek}", title="Test Kılıf",
                              status="active", base_price=Decimal("300.00"), custom_fields=alanlar[:2])
        db.add(urun)
        db.flush()
        v = CatalogVariant(tenant_id=t.id, product_id=urun.id, model_key="test-model",
                           model_display="Test Model", is_active=True, track_stock=True, quantity=3)
        db.add(v)
        db.flush()
        vid = str(v.id)

        print("── fiyat sunucuda hesaplanır ──")
        snap, toplam = co.validate_and_snapshot(db, store, [
            {"variant_id": vid, "quantity": 1, "price": "1.00", "unit_price": "1.00",
             "custom": {"vernik": "Evet", "isim": "Ayşe"}}])
        kontrol("birim = 300 + 50 + 25.50", Decimal(snap[0]["unit_price"]), Decimal("375.50"))
        kontrol("istemcinin gönderdiği 1 TL yok sayıldı", toplam, Decimal("375.50"))
        kontrol("taban fiyat kaydı", snap[0]["base_unit_price"], "300.00")
        snap, _ = co.validate_and_snapshot(db, store, [
            {"variant_id": vid, "quantity": 1, "custom": {"vernik": "Hayır"}}])
        kontrol("ücretsiz seçenek fiyatı değiştirmez", (snap[0]["unit_price"], "extras" in snap[0]),
                ("300.00", False))

        print("── aynı model, farklı seçenek ──")
        snap, toplam = co.validate_and_snapshot(db, store, [
            {"variant_id": vid, "quantity": 1, "custom": {"vernik": "Evet"}},
            {"variant_id": vid, "quantity": 2, "custom": {"vernik": "Hayır"}}])
        kontrol("iki ayrı satır kabul edilir", len(snap), 2)
        kontrol("toplam", toplam, Decimal("950.00"))
        reddedilir("birebir aynı satır reddedilir", lambda: co.validate_and_snapshot(db, store, [
            {"variant_id": vid, "quantity": 1, "custom": {"vernik": "Evet"}},
            {"variant_id": vid, "quantity": 1, "custom": {"vernik": "Evet"}}]))
        reddedilir("stok satırların TOPLAMIYLA kontrol edilir (3 stok, 4 adet)",
                   lambda: co.validate_and_snapshot(db, store, [
                       {"variant_id": vid, "quantity": 2, "custom": {"vernik": "Evet"}},
                       {"variant_id": vid, "quantity": 2, "custom": {"vernik": "Hayır"}}]))
        reddedilir("tanımsız seçenek reddedilir", lambda: co.validate_and_snapshot(db, store, [
            {"variant_id": vid, "quantity": 1, "custom": {"vernik": "Belki"}}]))

        print("── sipariş satırı ──")
        snap, toplam = co.validate_and_snapshot(db, store, [
            {"variant_id": vid, "quantity": 1, "custom": {"vernik": "Evet", "isim": "Ayşe"}}])
        ses = CheckoutSession(id=uuid.uuid4(), store_id=store.id, tenant_id=t.id, cart_snapshot=snap,
                              customer={}, amount=toplam, shipping_amount=0, discount_amount=0,
                              currency="TRY", provider="test")
        satir = _build_raw(ses, 1, store)["line_items"][0]
        ozellik = {p["name"]: p["value"] for p in satir["properties"]}
        kontrol("yazı alanı üretime olduğu gibi gider", ozellik.get("İsim"), "Ayşe")
        kontrol("ek ücret ayrı satırda", ozellik.get("Ek seçenek ücreti"),
                "Vernik: Evet +50,00 ₺, İsim +25,50 ₺")
        kontrol("satır fiyatı ek ücret dahil", satir["price"], "375.50")
    finally:
        db.rollback()
        db.close()

    print(f"\nGECTI: {GECTI}   KALDI: {KALDI}")
    return 1 if KALDI else 0


if __name__ == "__main__":
    sys.exit(main())
