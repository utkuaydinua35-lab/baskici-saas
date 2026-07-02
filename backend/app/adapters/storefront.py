"""
Storefront (kendi mağazamız) platform adapter.

Siparişler harici bir API'den çekilmez — ödeme doğrulandığında checkout servisi
tarafından yerel olarak oluşturulur. Tüm metotlar güvenli/boş döner; saatlik
sync ve fetch akışlarında hata vermez (bayii adapter'ı ile aynı desen).
"""
from typing import Any

from app.adapters.base import StorePlatform


class StorefrontAdapter(StorePlatform):
    """Kendi e-ticaret vitrinimiz — sipariş verisi yerelde doğar."""

    def test_connection(self) -> tuple[bool, str]:
        return True, "Kendi mağazanız — sipariş verisi yerel olarak oluşturulur"

    def get_order_by_number(self, order_number: str | int) -> dict | None:
        return None

    def get_order_by_id(self, order_id: str | int) -> dict | None:
        return None

    def get_all_active_orders(self, limit: int = 250) -> list[dict]:
        return []  # yerel kanal — otomatik çekilecek sipariş yok

    def get_product_image(self, product_id: str | int) -> str | None:
        return None

    def add_tracking(self, *args: Any, **kwargs: Any) -> tuple[bool, str]:
        # kargo_info zaten Order üzerinde tutuluyor; platforma yazılacak yer yok.
        return True, "Vitrin siparişi — takip bilgisi yerelde tutulur"

    def get_fulfillments(self, order_id: str | int) -> list[dict]:
        return []
