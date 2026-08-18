"""Vitrin adresinin TEK kaynağı.

config.storefront_url elle girilen adrestir; girilmemişse mağazanın BAĞLI
ALAN ADINDAN türetilir. Bu geri düşüş kodun çoğunda vardı ama Meta CAPI ve
tema yayınlama sinyalinde YOKTU — sonuç: adres boşken ödeme çalışıyor ama
piksel olayları event_source_url'süz gidiyor ve tema değişimi vitrine 60 sn
geç yansıyordu. Aynı hesabın iki farklı yerde ayrı yazılmaması için burada
toplandı.

custom_domain SIRALAMAYA SONRADAN GİRDİ: panelden "Alan Adı" kaydedilince
yazılan anahtar odur, storefront_url ise elle doldurulan ayrı bir alandır.
Yeni açılan mağazada yalnız custom_domain dolu oluyordu ve burası boş string
dönüyordu; PayTR'ye giden merchant_ok_url "/odeme/sonuc" gibi GÖRELİ bir
adrese düşüp sağlayıcı isteği reddediyordu (panelde "Expecting value: line 1
column 1" olarak görünüyordu — PayTR'nin cevabı JSON bile değildi).
"""
from __future__ import annotations


def site_url(store_or_config) -> str:
    """Mağazanın müşteriye görünen adresi (sonda / yok). Yoksa boş string."""
    config = getattr(store_or_config, "config", store_or_config) or {}
    url = (config.get("storefront_url") or "").strip()
    if url:
        return url.rstrip("/")
    # custom_domain = panelden bağlanan kendi alan adı (müşteriye görünen);
    # shop_domain = platformdan gelen teknik adres. Öncelik ilkinde.
    domain = next(
        (d for d in ((config.get("custom_domain") or "").strip().rstrip("/"),
                     (config.get("shop_domain") or "").strip().rstrip("/")) if d),
        "",
    )
    if not domain:
        return ""
    if domain.startswith(("http://", "https://")):
        return domain
    return f"https://{domain}"
