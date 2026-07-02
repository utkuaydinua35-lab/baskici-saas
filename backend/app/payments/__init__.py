"""
Ödeme sağlayıcı factory — adapters/__init__.py deseni.

Kullanım:
    from app.payments import get_payment_provider
    provider = get_payment_provider(store)   # store: Store ORM (platform='storefront')
    init = provider.create_checkout(session, callback_url)
"""
from app.payments.base import CheckoutInit, PaymentProvider, PaymentResult
from app.payments.iyzico import IyzicoProvider
from app.payments.paytr import PayTRProvider

PROVIDER_REGISTRY: dict[str, type[PaymentProvider]] = {
    "iyzico": IyzicoProvider,
    "paytr": PayTRProvider,
}


def get_payment_provider(store) -> PaymentProvider:
    """Store.config['payment_provider'] değerine göre adapter instantiate et."""
    config = store.config or {}
    name = (config.get("payment_provider") or "").lower()
    if name not in PROVIDER_REGISTRY:
        raise ValueError(
            f"Bilinmeyen ödeme sağlayıcı: '{name}'. "
            f"Desteklenenler: {', '.join(PROVIDER_REGISTRY.keys())}"
        )
    return PROVIDER_REGISTRY[name](config)


__all__ = [
    "get_payment_provider", "PaymentProvider", "PaymentResult",
    "CheckoutInit", "IyzicoProvider", "PayTRProvider",
]
