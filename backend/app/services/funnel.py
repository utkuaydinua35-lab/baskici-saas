"""Terk edilme aşaması analizi — "müşteri nerede vazgeçti?"

Shopify terk edilmiş sepeti yalnızca "checkout başladı ama ödenmedi" olarak
bilir. Biz ziyaretçinin ulaştığı EN İLERİ noktayı takip edip vazgeçme
sebebine dair somut çıkarım üretiriz — çünkü her aşamanın kendine özgü
tipik nedeni vardır:

  browsing          ürüne baktı, sepete eklemedi   → ürün/fiyat ilgisini çekmedi
  cart              sepete ekledi, ödemeye geçmedi → kararsız / fiyat karşılaştırıyor
  checkout_opened   ödeme sayfasını açtı, formu doldurmadı
                                                   → KARGO ÜCRETİ ilk burada görünür
  form_completed    formu doldurdu, ödemeye basmadı → son an tereddüt / güven
  provider_redirect ödeme sağlayıcısına gitti, dönmedi
                                                   → kart/limit/3D veya POS sorunu
  payment_failed    banka reddetti                 → yetersiz bakiye / 3D hatası
"""
from __future__ import annotations

# Sıra: büyük = daha ileri. Aşama asla geriye gitmez.
STAGE_ORDER = {
    "browsing": 10,
    "cart": 20,
    "checkout_opened": 30,
    "form_completed": 40,
    "provider_redirect": 50,
    "payment_failed": 55,
    "purchased": 60,
}

STAGE_LABEL = {
    "browsing": "Ürünlere baktı",
    "cart": "Sepete ekledi",
    "checkout_opened": "Ödeme sayfasını açtı",
    "form_completed": "Bilgileri doldurdu",
    "provider_redirect": "Ödeme sayfasına yönlendi",
    "payment_failed": "Ödeme başarısız",
    "purchased": "Satın aldı",
}

# Her aşama için: (olası sebep, önerilen aksiyon)
STAGE_INSIGHT = {
    "browsing": (
        "Ürün ilgisini çekmedi ya da fiyat/görsel yeterli gelmedi.",
        "Ürün görsellerini ve açıklamayı güçlendirin; ilk siparişe özel kupon deneyin.",
    ),
    "cart": (
        "Sepete ekledi ama ödemeye geçmedi — genelde kararsızlık ya da "
        "fiyat karşılaştırması.",
        "Terk sepet hatırlatma e-postası + küçük bir indirim kodu gönderin.",
    ),
    "checkout_opened": (
        "KARGO ÜCRETİ ilk burada görünür — en sık vazgeçme sebebi budur.",
        "Ücretsiz kargo eşiğini düşürmeyi ya da kargo ücretini fiyata katmayı deneyin.",
    ),
    "form_completed": (
        "Bilgilerini yazdı ama ödemeye basmadı — son an tereddüdü, güven eksikliği "
        "ya da toplam tutar şoku.",
        "Güven rozetleri ve iade politikasını ödeme sayfasında öne çıkarın; "
        "bu müşteriye kişisel e-posta/WhatsApp ile ulaşın (bilgileri elinizde).",
    ),
    "provider_redirect": (
        "Ödeme sağlayıcısına gitti ama dönmedi — kart limiti, 3D şifresi ya da "
        "sanal POS kaynaklı sorun olabilir.",
        "Müşteriye ödeme linki gönderin; sorun sürerse farklı kart/taksit "
        "seçeneğini önerin. Sık tekrarlıyorsa sağlayıcıyla görüşün.",
    ),
    "payment_failed": (
        "Banka ödemeyi reddetti (yetersiz bakiye, 3D doğrulama, limit).",
        "Ödeme linkiyle tekrar deneme daveti gönderin — bu müşteriler "
        "genelde satın almaya en yakın olanlardır.",
    ),
}


def merge_stage(current: str | None, new: str | None) -> str | None:
    """En ileri aşamayı koru — kullanıcı sepete dönse bile geri sayılmaz."""
    if not new:
        return current
    if not current:
        return new
    return new if STAGE_ORDER.get(new, 0) > STAGE_ORDER.get(current, 0) else current


def stage_from_path(path: str | None, cart_items: int = 0) -> str:
    """Vitrin yolundan aşama çıkar (presence ping'i için)."""
    p = (path or "/").lower()
    if p.startswith("/odeme/sonuc"):
        return "provider_redirect"
    if p.startswith("/odeme"):
        return "checkout_opened"
    if p.startswith("/sepet") and cart_items > 0:
        return "cart"
    return "cart" if cart_items > 0 else "browsing"


def describe(stage: str | None) -> dict:
    """Aşama → {stage, label, reason, action} (panel gösterimi)."""
    s = stage or "browsing"
    reason, action = STAGE_INSIGHT.get(s, ("", ""))
    return {
        "stage": s,
        "label": STAGE_LABEL.get(s, s),
        "order": STAGE_ORDER.get(s, 0),
        "reason": reason,
        "action": action,
    }
