#!/usr/bin/env python3
"""iyzico sepeti — ağa çıkmadan, gönderilecek istek yakalanıp denetlenir.

  • Kalem kategorisi mağazanın ürün türünden gelir (eskiden koda "Telefon
    Kılıfı" sabitti ve her kiracıya gidiyordu); boşsa nötr "Genel".
  • Aynı model farklı ek seçenekle iki satır olabilir → kalem kimlikleri
    çakışmamalı; tek satırlı sepette kimlik eskisi gibi varyant kimliği.
  • Kalem toplamı iyzico'nun "price" alanına TAM eşit olmalı (indirim
    oransal dağıtılır, kargo ayrı kalem).

Veritabanı kullanmaz. Koşum: cd backend && .venv/bin/python scripts/iyzico_sepet_test.py
"""
import sys
import uuid
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.payments.iyzico import IyzicoProvider  # noqa: E402

GECTI = KALDI = 0


def kontrol(ad, gercek, beklenen):
    global GECTI, KALDI
    if gercek == beklenen:
        GECTI += 1
        print(f"  ✓ {ad}")
    else:
        KALDI += 1
        print(f"  ✗ {ad}\n      beklenen: {beklenen!r}\n      gercek  : {gercek!r}")


def sepet_gonder(config: dict, satirlar: list[dict], kargo="0", indirim="0") -> dict:
    """create_checkout'u çalıştırır; iyzico'ya gidecek gövdeyi döndürür."""
    ara = sum(Decimal(s["unit_price"]) * s["quantity"] for s in satirlar)
    toplam = ara - Decimal(indirim) + Decimal(kargo)
    oturum = SimpleNamespace(
        id=uuid.uuid4(), token="t", customer={}, amount=toplam, currency="TRY",
        shipping_amount=Decimal(kargo), discount_amount=Decimal(indirim),
        cart_snapshot=satirlar, client_ip=None,
    )
    p = IyzicoProvider({"iyzico_api_key": "k", "iyzico_secret_key": "s", **config})
    yakalanan = {}

    def sahte_post(_yol, govde):
        yakalanan.update(govde)
        return {"status": "success", "paymentPageUrl": "https://ornek", "token": "x"}

    p._post = sahte_post
    p.create_checkout(oturum, "https://geri-donus")
    return yakalanan


def kalem_toplami(govde) -> Decimal:
    return sum((Decimal(k["price"]) for k in govde["basketItems"]), Decimal(0))


def main() -> int:
    tek = [{"variant_id": "v1", "title": "Kupa", "model_display": "", "unit_price": "250.00", "quantity": 1}]

    print("── kategori ──")
    g = sepet_gonder({"isletme_urun_turu": "Seramik Kupa"}, tek)
    kontrol("ürün türünden gelir", g["basketItems"][0]["category1"], "Seramik Kupa")
    g = sepet_gonder({}, tek)
    kontrol("ürün türü yoksa 'Genel'", g["basketItems"][0]["category1"], "Genel")
    g = sepet_gonder({"isletme_urun_turu": "   "}, tek)
    kontrol("yalnız boşluksa 'Genel'", g["basketItems"][0]["category1"], "Genel")
    g = sepet_gonder({"isletme_urun_turu": "telefon kılıfı"}, tek)
    kontrol("küçük harf girişi Türkçe kurala göre büyütülür", g["basketItems"][0]["category1"], "Telefon Kılıfı")
    g = sepet_gonder({"isletme_urun_turu": "iç giyim"}, tek)
    kontrol("baştaki i → İ (Türkçe)", g["basketItems"][0]["category1"], "İç Giyim")
    kontrol("BERNZ'e özel sabit artık yok",
            any(k["category1"] == "Telefon Kılıfı" for k in g["basketItems"]), False)

    print("── kalem kimlikleri ──")
    kontrol("tek satırda kimlik = varyant kimliği", g["basketItems"][0]["id"], "v1")
    iki = [
        {"variant_id": "v1", "title": "Kılıf", "model_display": "A", "unit_price": "350.00", "quantity": 1},
        {"variant_id": "v1", "title": "Kılıf", "model_display": "A", "unit_price": "300.00", "quantity": 2},
    ]
    g = sepet_gonder({}, iki, kargo="40")
    urun_kimlikleri = [k["id"] for k in g["basketItems"] if k["category1"] != "Kargo"]
    kontrol("aynı varyant iki satırda kimlikler ayrışır", len(set(urun_kimlikleri)), 2)

    print("── tutar eşitliği ──")
    kontrol("kalem toplamı = price (kargo dahil)", kalem_toplami(g), Decimal(g["price"]))
    g = sepet_gonder({}, iki, kargo="40", indirim="95.55")
    kontrol("indirimli sepette kalem toplamı = price", kalem_toplami(g), Decimal(g["price"]))

    print(f"\nGECTI: {GECTI}   KALDI: {KALDI}")
    return 1 if KALDI else 0


if __name__ == "__main__":
    sys.exit(main())
