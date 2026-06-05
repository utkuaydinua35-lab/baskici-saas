"""
Soyut platform interface.

Tüm adapter'lar bu sınıfı implement etmeli. Dönen veriler **Shopify-formatlı
dict** olmalı — bu sayede üst akış (pipeline, orders router) platform-bağımsız
çalışır. İkas gibi farklı API'lar adapter içinde Shopify formatına çevrilir.

Standart sipariş dict şeması (her adapter bunu döndürür):
    {
        "id": 12345,                    # platform-specific order id
        "order_number": 1421,            # short number
        "name": "#1421",                 # display name
        "created_at": "2026-05-17T...",  # ISO timestamp
        "fulfillment_status": "unfulfilled" | "fulfilled" | "partial" | null,
        "financial_status": "paid" | ...,
        "customer": {
            "first_name": "...",
            "last_name": "...",
            "email": "..."
        },
        "shipping_address": {...},
        "line_items": [
            {
                "id": ...,
                "product_id": ...,
                "title": "...",
                "variant_title": "...",     # "iPhone 14 / siyah" gibi
                "quantity": 1,
                "properties": [{"name": "...", "value": "..."}]
            }
        ],
        "note": "...",
        "tags": "...",
        "fulfillments": [...]
    }
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class StorePlatform(ABC):
    """Tüm e-ticaret platform adapter'ları için soyut taban sınıf."""

    PLATFORM_NAME: str = "unknown"

    def __init__(self, config: dict[str, Any]):
        """
        config: store.config JSONB içeriği. Platform-specific alanlar
        (Shopify: store_url, access_token vs. — İkas: store_id, api_key vs.).
        """
        self.config = config or {}

    # ─── Test ────────────────────────────────────────────────

    @abstractmethod
    def test_connection(self) -> tuple[bool, str]:
        """
        API bağlantısını test et.
        Dönüş: (success, message). UI'da "bağlantı çalışıyor mu" testi için.
        """
        ...

    # ─── Sipariş okuma ───────────────────────────────────────

    @abstractmethod
    def get_order_by_number(self, order_number: str | int) -> dict | None:
        """Sipariş numarasına göre tek bir sipariş çek. Yoksa None."""
        ...

    @abstractmethod
    def get_order_by_id(self, order_id: str | int) -> dict | None:
        """Platform-specific id'ye göre sipariş çek."""
        ...

    @abstractmethod
    def get_all_active_orders(self, limit: int = 250) -> list[dict]:
        """
        Tüm aktif (unfulfilled + partial) siparişleri çek.
        Pagination dahil. BERNZ pipeline'ının ana kullanım noktası.
        """
        ...

    # ─── Ürün ────────────────────────────────────────────────

    @abstractmethod
    def get_product_image(self, product_id: str | int) -> str | None:
        """Ürünün ana görsel URL'ini döndür. Cache'lenebilir."""
        ...

    # ─── Tracking ────────────────────────────────────────────

    @abstractmethod
    def add_tracking(
        self,
        order_id: str | int,
        tracking_number: str,
        tracking_company: str = "Sürat Kargo",
        tracking_url: str | None = None,
    ) -> tuple[bool, str]:
        """
        Siparişe kargo takip numarası ekle.
        Dönüş: (success, message).
        """
        ...

    # ─── Helpers (opsiyonel, override edilebilir) ────────────

    def get_fulfillments(self, order_id: str | int) -> list[dict]:
        """Sipariş için fulfillment listesi (varsayılan: boş)."""
        return []
