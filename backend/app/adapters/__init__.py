"""
Platform adapter factory.

Kullanım:
    from app.adapters import get_adapter
    adapter = get_adapter(store)        # store: Store ORM nesnesi
    orders = adapter.get_all_active_orders()
"""
from app.adapters.base import StorePlatform
from app.adapters.ikas import IkasAdapter
from app.adapters.shopify import ShopifyAdapter
from app.models import Store

PLATFORM_REGISTRY: dict[str, type[StorePlatform]] = {
    "shopify": ShopifyAdapter,
    "ikas": IkasAdapter,
}


def get_adapter(store: Store) -> StorePlatform:
    """
    Store nesnesine göre uygun adapter'ı instantiate et.
    config JSONB field'ından parametreleri okur.
    """
    if not store:
        raise ValueError("Store gerekli")

    platform = (store.platform or "").lower()
    if platform not in PLATFORM_REGISTRY:
        raise ValueError(
            f"Bilinmeyen platform: '{platform}'. "
            f"Desteklenenler: {', '.join(PLATFORM_REGISTRY.keys())}"
        )

    adapter_cls = PLATFORM_REGISTRY[platform]
    return adapter_cls(store.config or {})


__all__ = ["get_adapter", "StorePlatform", "ShopifyAdapter", "IkasAdapter"]
