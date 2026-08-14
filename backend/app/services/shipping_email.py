"""
Otomatik kargo bildirimi — vitrin siparişinin takip numarası İLK kez
yazıldığında müşteriye e-posta gönderir.

Yalnızca platform=storefront mağazalar (Shopify siparişlerinin maili
Shopify'dan gider). Tekrar koruması: OrderStatusHistory action="kargo_email"
kaydı varsa yeniden gönderilmez. Çağıran akışı asla bloklamaz — hata loglanır.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CheckoutSession, Order, OrderStatusHistory, Store
from app.services import email_service

log = logging.getLogger("shipping_email")


def maybe_send_tracking_email(db: Session, order: Order) -> bool:
    """Uygunsa kargo e-postası gönder; gönderildiyse True.

    Commit ETMEZ — history kaydını session'a ekler, çağıranın commit'iyle
    kalıcılaşır (kargo akışının kendi transaction'ı içinde).
    """
    try:
        return _send(db, order)
    except Exception:
        log.exception("kargo e-postası gönderilemedi (order=%s)", order.id)
        return False


def _send(db: Session, order: Order) -> bool:
    ki = order.kargo_info or {}
    takip_no = (ki.get("takip_no") or "").strip()
    if not takip_no:
        return False

    store = db.get(Store, order.store_id) if order.store_id else None
    if not store or store.platform != "storefront":
        return False
    config = store.config or {}
    if config.get("shipping_email_enabled") is False:  # varsayılan açık
        return False

    email = (order.customer_email or "").strip()
    if not email:
        return False

    already = db.scalar(
        select(OrderStatusHistory.id).where(
            OrderStatusHistory.order_id == order.id,
            OrderStatusHistory.action == "kargo_email",
        ).limit(1)
    )
    if already:
        return False

    # Sipariş takip sayfası linki (varsa) — müşteri durumu buradan izler
    session = db.scalar(select(CheckoutSession).where(
        CheckoutSession.order_id == order.id).limit(1))
    site = (config.get("storefront_url")
            or f"https://{config.get('shop_domain', '')}").rstrip("/")
    status_url = f"{site}/siparis/{session.lookup_token}" if session else None
    takip_url = ki.get("takip_url")

    brand = email_service.store_brand_kwargs(store)
    firma = ki.get("handler_name") or "Kargo"
    first_name = ""
    if session and isinstance(session.customer, dict):
        first_name = session.customer.get("first_name") or ""

    subj_over, intro_over = email_service.store_email_text(store, "kargo")
    rows = "".join(
        f"<tr><td style='padding:4px 0;color:#374151;font-size:14px'>"
        f"{li.title} — {li.variant_title or ''} × {li.quantity}</td></tr>"
        for li in (order.line_items or [])
    )
    body = (
        f"<p>Merhaba {first_name},</p>"
        + (intro_over or "")
        + f"<p><b>{order.name or ('#' + str(order.order_number or ''))}</b> numaralı "
        f"siparişiniz kargoya verildi! 🎉</p>"
        f"<p style='font-size:14px'>Kargo firması: <b>{firma}</b><br/>"
        f"Takip numarası: <b style='font-family:monospace'>{takip_no}</b></p>"
        + (f"<table width='100%' style='border-collapse:collapse;margin:10px 0'>{rows}</table>" if rows else "")
        + (f"<p style='font-size:13px'><a href='{takip_url}'>Kargo firmasında takip et →</a></p>" if takip_url else "")
    )
    html = email_service.render_email(
        title="Siparişiniz kargoda! 📦",
        body_html=body,
        button_text="Siparişimi Takip Et" if status_url else "",
        button_url=status_url or "",
        preheader=f"{firma} · takip no {takip_no}",
        emoji="📦",
        **brand,
    )
    ok = email_service.send_email(email, subj_over or "Siparişiniz kargoya verildi 📦", html)
    if not ok:
        return False

    db.add(OrderStatusHistory(
        tenant_id=order.tenant_id,
        order_id=order.id,
        from_stage=order.current_stage,
        to_stage=order.current_stage,
        action="kargo_email",
        note=f"Kargo bildirimi gönderildi → {email} ({firma} {takip_no})",
        created_by="sistem",
    ))
    return True
