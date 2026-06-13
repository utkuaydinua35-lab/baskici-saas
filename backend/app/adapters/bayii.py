"""
Bayii (manuel) platform adapter.
Bayii magazalari hicbir API'ye baglanmaz — siparisler manuel girilir.
Tum metotlar guvenli/bos doner; fetch ve sync akislarinda hata vermez.
"""
from typing import Any

from app.adapters.base import StorePlatform


class BayiiAdapter(StorePlatform):
    """Manuel bayii magazasi — API yok, siparisler elle girilir."""

    def test_connection(self) -> tuple[bool, str]:
        return True, "Manuel bayii mağazası (API gerektirmez)"

    def get_order_by_number(self, order_number: str | int) -> dict | None:
        return None

    def get_order_by_id(self, order_id: str | int) -> dict | None:
        return None

    def get_all_active_orders(self, limit: int = 250) -> list[dict]:
        return []  # manuel — otomatik cekilecek siparis yok

    def get_product_image(self, product_id: str | int) -> str | None:
        return None

    def add_tracking(self, *args: Any, **kwargs: Any) -> tuple[bool, str]:
        return False, "Manuel bayii — kargo takibi desteklenmiyor"

    def get_fulfillments(self, order_id: str | int) -> list[dict]:
        return []
