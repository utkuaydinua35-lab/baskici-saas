"""
Shopify platform adapter.

Token-based veya OAuth credentials desteği.
BERNZ projesinden port edildi.
"""
from __future__ import annotations

import requests

from app.adapters.base import StorePlatform


class ShopifyAdapter(StorePlatform):
    """Shopify mağazaları için adapter."""

    def __init__(self, store):
        self.store = store
        if hasattr(store, 'config'):
            # SQLAlchemy ORM Store
            cfg = store.config or {}
        elif isinstance(store, dict):
            # Store-like dict ({"config": {...}, "platform": "..."})
            if 'config' in store and isinstance(store['config'], dict):
                cfg = store['config']
            # Veya doğrudan config dict ({"store_url": "...", "access_token": "..."})
            else:
                cfg = store
        else:
            cfg = {}
        self.store_url = cfg.get("store_url", "")
        self.auth_type = cfg.get("auth_type", "token")
        self.access_token = cfg.get("access_token", "")
        self.client_id = cfg.get("client_id", "")
        self.client_secret = cfg.get("client_secret", "")
        self.api_version = cfg.get("api_version", "2024-01")

        self.session = requests.Session()
        self._image_cache: dict[str, str] = {}

    # ─── Auth header ─────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        token = self.access_token or self.client_secret
        return {
            "X-Shopify-Access-Token": token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _base_url(self) -> str:
        return f"https://{self.store_url}/admin/api/{self.api_version}"

    # ─── Test ────────────────────────────────────────────────

    def test_connection(self) -> tuple[bool, str]:
        """Mağazayla bağlantı testi. (success: bool, message: str) döndürür."""
        url = f"{self._base_url()}/shop.json"
        try:
            r = self.session.get(url, headers=self._headers(), timeout=15)
            if r.status_code == 200:
                shop = r.json().get("shop", {})
                name = shop.get("name", "?")
                domain = shop.get("domain", "?")
                return True, f"Bağlandı: {name} ({domain})"
            return False, f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as e:
            return False, f"Bağlantı hatası: {str(e)[:200]}"

    # ─── Orders ──────────────────────────────────────────────

    def get_order_by_number(self, order_number: str) -> dict | None:
        url = f"{self._base_url()}/orders.json"
        params = {"name": f"#{order_number}", "status": "any", "limit": 1}
        r = self.session.get(url, headers=self._headers(), params=params, timeout=20)
        r.raise_for_status()
        orders = r.json().get("orders", [])
        return orders[0] if orders else None

    def get_order_by_id(self, order_id: str) -> dict | None:
        url = f"{self._base_url()}/orders/{order_id}.json"
        r = self.session.get(url, headers=self._headers(), timeout=20)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json().get("order")

    def get_all_active_orders(self, limit: int = 250) -> list[dict]:
        """Aktif ve son 60 günün tüm siparişleri (status=any: read_all_orders gerektirmez)."""
        url = f"{self._base_url()}/orders.json"
        params = {
            "status": "any",
            "limit": min(limit, 250),
        }
        all_orders: list[dict] = []
        next_url: str | None = url
        max_pages = 10
        page = 0
        while next_url and page < max_pages:
            page += 1
            if page == 1:
                r = self.session.get(next_url, headers=self._headers(), params=params, timeout=30)
            else:
                r = self.session.get(next_url, headers=self._headers(), timeout=30)
            r.raise_for_status()
            data = r.json()
            all_orders.extend(data.get("orders", []))

            # Pagination via Link header
            link = r.headers.get("Link", "")
            next_url = None
            if 'rel="next"' in link:
                for part in link.split(","):
                    if 'rel="next"' in part:
                        next_url = part.split(";")[0].strip().strip("<>")
                        break
        return all_orders

    # ─── Products ────────────────────────────────────────────

    def get_all_products(self, limit: int = 250, search: str | None = None) -> list[dict]:
        """
        Mağazadaki ürünleri çek. Tasarım yüklerken picker için.

        Returns: [{id, title, image_url, status, product_type, tags}, ...]
        """
        url = f"{self._base_url()}/products.json"
        params: dict = {
            "limit": min(limit, 250),
            "status": "active",
            "fields": "id,title,image,images,status,product_type,tags,handle",
        }
        # Search'i client-side yapacağız (Shopify title partial match desteklemiyor)
        all_products: list[dict] = []
        next_url: str | None = url
        max_pages = 10
        page = 0

        while next_url and page < max_pages:
            page += 1
            if page == 1:
                r = self.session.get(next_url, headers=self._headers(), params=params, timeout=30)
            else:
                r = self.session.get(next_url, headers=self._headers(), timeout=30)
            r.raise_for_status()
            data = r.json()
            for p in data.get("products", []):
                image_url = ""
                if p.get("image") and isinstance(p["image"], dict):
                    image_url = p["image"].get("src", "")
                elif p.get("images") and isinstance(p["images"], list) and p["images"]:
                    image_url = p["images"][0].get("src", "")
                all_products.append({
                    "id": str(p.get("id", "")),
                    "title": p.get("title", ""),
                    "image_url": image_url,
                    "status": p.get("status", ""),
                    "product_type": p.get("product_type", ""),
                    "tags": p.get("tags", ""),
                    "handle": p.get("handle", ""),
                })

            link = r.headers.get("Link", "")
            next_url = None
            if 'rel="next"' in link:
                for part in link.split(","):
                    if 'rel="next"' in part:
                        next_url = part.split(";")[0].strip().strip("<>")
                        break

        if search:
            s = search.lower()
            all_products = [p for p in all_products if s in (p.get("title") or "").lower()]

        return all_products

    def get_product_image(self, product_id: str | None) -> str | None:
        if not product_id:
            return None
        if product_id in self._image_cache:
            return self._image_cache[product_id]
        url = f"{self._base_url()}/products/{product_id}.json"
        try:
            r = self.session.get(url, headers=self._headers(), timeout=15)
            if r.status_code == 200:
                product = r.json().get("product", {})
                image = product.get("image") or {}
                img_url = image.get("src", "")
                self._image_cache[product_id] = img_url
                return img_url
        except Exception:
            pass
        self._image_cache[product_id] = ""
        return ""

    # ─── Tracking ────────────────────────────────────────────

    def add_tracking(
        self,
        order_id: str,
        tracking_number: str,
        tracking_company: str = "Sürat Kargo",
        tracking_url: str | None = None,
    ) -> dict:
        # İlk önce fulfillment_order_id'yi al
        url = f"{self._base_url()}/orders/{order_id}/fulfillment_orders.json"
        r = self.session.get(url, headers=self._headers(), timeout=20)
        r.raise_for_status()
        fos = r.json().get("fulfillment_orders", [])
        if not fos:
            return {"ok": False, "error": "Fulfillment order bulunamadı"}

        fo_id = fos[0]["id"]
        # quantity zorunlu: fulfillment_order line item'in kalan miktarini kullan
        line_items = []
        for li in fos[0].get("line_items", []):
            qty = li.get("fulfillable_quantity")
            if qty is None:
                qty = li.get("quantity") or 1
            line_items.append({"id": li["id"], "quantity": qty})

        url2 = f"{self._base_url()}/fulfillments.json"
        payload = {
            "fulfillment": {
                "line_items_by_fulfillment_order": [{
                    "fulfillment_order_id": fo_id,
                    "fulfillment_order_line_items": line_items,
                }],
                "tracking_info": {
                    "number": tracking_number,
                    "company": tracking_company,
                    **({"url": tracking_url} if tracking_url else {}),
                },
                "notify_customer": True,
            }
        }
        r2 = self.session.post(url2, headers=self._headers(), json=payload, timeout=30)
        if r2.status_code in (200, 201):
            return {"ok": True, "fulfillment": r2.json().get("fulfillment", {})}
        return {"ok": False, "error": f"HTTP {r2.status_code}: {r2.text[:200]}"}

    def update_tracking(
        self,
        fulfillment_id: str,
        tracking_number: str,
        tracking_company: str = "Kargo",
        tracking_url: str | None = None,
        notify_customer: bool = False,
    ) -> dict:
        """Mevcut bir fulfillment'ın takip bilgisini güncelle (no sonradan geldiğinde)."""
        url = f"{self._base_url()}/fulfillments/{fulfillment_id}/update_tracking.json"
        payload = {
            "fulfillment": {
                "notify_customer": notify_customer,
                "tracking_info": {
                    "number": tracking_number,
                    "company": tracking_company,
                    **({"url": tracking_url} if tracking_url else {}),
                },
            }
        }
        r = self.session.post(url, headers=self._headers(), json=payload, timeout=30)
        if r.status_code in (200, 201):
            return {"ok": True, "fulfillment": r.json().get("fulfillment", {})}
        return {"ok": False, "error": f"HTTP {r.status_code}: {r.text[:200]}"}
