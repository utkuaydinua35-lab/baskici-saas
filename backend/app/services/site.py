"""Vitrin adresinin TEK kaynağı.

config.storefront_url elle girilen adrestir; girilmemişse shop_domain'den
türetilir. Bu geri düşüş kodun çoğunda vardı ama Meta CAPI ve tema yayınlama
sinyalinde YOKTU — sonuç: adres boşken ödeme çalışıyor ama piksel olayları
event_source_url'süz gidiyor ve tema değişimi vitrine 60 sn geç yansıyordu.
Aynı hesabın iki farklı yerde ayrı yazılmaması için burada toplandı.
"""
from __future__ import annotations


def site_url(store_or_config) -> str:
    """Mağazanın müşteriye görünen adresi (sonda / yok). Yoksa boş string."""
    config = getattr(store_or_config, "config", store_or_config) or {}
    url = (config.get("storefront_url") or "").strip()
    if url:
        return url.rstrip("/")
    domain = (config.get("shop_domain") or "").strip().rstrip("/")
    if not domain:
        return ""
    if domain.startswith(("http://", "https://")):
        return domain
    return f"https://{domain}"
