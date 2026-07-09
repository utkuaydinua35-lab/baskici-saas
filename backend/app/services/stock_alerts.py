"""
Gelince haber ver — stoksuz varyanta bırakılan e-postalara, stok girilince
tek seferlik bildirim gönderir.

Tetikleme: varyant miktarı 0'dan >0'a geçen HER yerde notify_variant çağrılır
(varyant PATCH, envanter toplu güncelleme, CSV import). Commit ETMEZ —
çağıranın transaction'ı içinde notified_at işaretlenir. Hata bloklamaz.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CatalogProduct, CatalogVariant, StockAlert, Store
from app.services import email_service

log = logging.getLogger("stock_alerts")


def notify_variant(db: Session, variant: CatalogVariant) -> int:
    """Varyantın bekleyen stok bildirimlerini gönder; gönderilen sayısı döner."""
    try:
        return _notify(db, variant)
    except Exception:
        log.exception("stok bildirimi gönderilemedi (variant=%s)", variant.id)
        return 0


def _notify(db: Session, variant: CatalogVariant) -> int:
    if variant.track_stock and variant.quantity <= 0:
        return 0  # hâlâ stoksuz

    alerts = db.scalars(select(StockAlert).where(
        StockAlert.variant_id == variant.id,
        StockAlert.notified_at.is_(None),
    )).all()
    if not alerts:
        return 0

    product = db.get(CatalogProduct, variant.product_id)
    if not product or product.status != "active":
        return 0
    store = db.get(Store, product.store_id)
    if not store:
        return 0
    config = store.config or {}
    site = (config.get("storefront_url")
            or f"https://{config.get('shop_domain', '')}").rstrip("/")
    url = f"{site}/urun/{product.slug}"

    tenant = getattr(store, "tenant", None)
    brand = email_service.brand_kwargs(tenant) if tenant else {}
    variant_label = variant.model_display + (f" · {variant.variation}" if variant.variation else "")

    sent = 0
    now = datetime.now(timezone.utc)
    for alert in alerts:
        body = (
            f"<p>Merhaba,</p>"
            f"<p>Beklediğiniz ürün yeniden stokta:</p>"
            f"<p style='font-size:15px'><b>{product.title}</b><br/>"
            f"<span style='color:#6b7280'>{variant_label}</span></p>"
            f"<p style='color:#6b7280;font-size:12px'>Stoklar sınırlı olabilir — "
            f"bu bildirim, isteğiniz üzerine tek seferlik gönderilmiştir.</p>"
        )
        html = email_service.render_email(
            title="Beklediğiniz ürün stokta! 🎉",
            body_html=body,
            button_text="Ürüne Git",
            button_url=url,
            preheader=f"{product.title} yeniden stokta",
            emoji="🔔",
            **brand,
        )
        if email_service.send_email(alert.email, f"{product.title} yeniden stokta 🔔", html):
            alert.notified_at = now
            sent += 1
    return sent
