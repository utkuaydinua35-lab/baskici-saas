"""
İkas adapter — skeleton.

İkas API (REST + GraphQL hibrit) bir sonraki pakette doldurulacak.
Şimdilik bağlantı testi placeholder; diğer metotlar NotImplementedError.

İkas dokümantasyonu: https://ikas.dev/docs
- Auth: OAuth2 client_credentials
- Endpoint: https://api.myikas.com/api/v2/admin/graphql
- GraphQL ile çoğu işlem (orders, products)

Adapter Shopify-formatlı dict döndürecek — İkas response normalize edilecek.
"""
from __future__ import annotations

import logging

from app.adapters.base import StorePlatform

logger = logging.getLogger(__name__)


class IkasAdapter(StorePlatform):
    PLATFORM_NAME = "ikas"

    # config beklenen alanlar (planlanan):
    #   store_id:     mağaza ID
    #   client_id:    OAuth client ID
    #   client_secret: OAuth client secret
    #   api_url:      "https://api.myikas.com" (default)

    def __init__(self, config):
        super().__init__(config)
        self.store_id = config.get("store_id", "")
        self.client_id = config.get("client_id")
        self.client_secret = config.get("client_secret")
        self.api_url = config.get("api_url", "https://api.myikas.com")

    def test_connection(self) -> tuple[bool, str]:
        # TODO: gerçek implementasyon — OAuth token al + /shop bilgisi çek
        if not self.client_id or not self.client_secret:
            return False, "client_id ve client_secret eksik"
        return False, "İkas adapter henüz implement edilmedi (yakında)"

    def get_order_by_number(self, order_number):
        raise NotImplementedError("İkas adapter yakında")

    def get_order_by_id(self, order_id):
        raise NotImplementedError("İkas adapter yakında")

    def get_all_active_orders(self, limit: int = 250):
        raise NotImplementedError("İkas adapter yakında")

    def get_product_image(self, product_id):
        raise NotImplementedError("İkas adapter yakında")

    def add_tracking(self, order_id, tracking_number, tracking_company="Sürat Kargo",
                     tracking_url=None):
        raise NotImplementedError("İkas adapter yakında")
