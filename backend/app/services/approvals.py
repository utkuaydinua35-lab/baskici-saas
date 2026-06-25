"""Müşteri tasarım onayı — servis katmanı.

Onay kaydı oluşturma, görsel/telefon/mesaj çözümleme, public payload.
Token'lı public sayfa (siparistakip/onay/{token}) üzerinden müşteri onaylar.
"""
from __future__ import annotations

import secrets

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import DesignApproval, Order

STATUS_LABELS = {
    "bekliyor": "Onay bekliyor",
    "onaylandi": "Onaylandı",
    "revizyon": "Revizyon istendi",
}


def resolve_phone(order: Order) -> str | None:
    """Sipariş ham verisinden müşteri telefonu (Shopify customer/shipping)."""
    raw = order.raw or {}
    cust = raw.get("customer") or {}
    ship = raw.get("shipping_address") or {}
    for c in (cust.get("phone"), ship.get("phone"), raw.get("phone")):
        if c and str(c).strip():
            return str(c).strip()
    return None


def build_items(db: Session, order: Order) -> list[dict]:
    """Sipariş kalemlerinden müşteriye gösterilecek tasarım görselleri."""
    from app.routers.telafiler import _li_thumbnail  # aynı thumbnail mantığı
    items = []
    for li in (order.line_items or []):
        img = None
        try:
            img = _li_thumbnail(li, db)
        except Exception:
            img = getattr(li, "product_image_url", None)
        items.append({
            "image_url": img,
            "title": li.title or "Ürün",
            "quantity": getattr(li, "quantity", 1) or 1,
        })
    return items


def approval_link(token: str) -> str:
    base = get_settings().support_public_base_url.rstrip("/")
    return f"{base}/onay/{token}"


def build_message(order: Order, link: str) -> str:
    """Müşteriye gönderilmeye hazır mesaj (operatör elle WhatsApp/Instagram'dan yollar)."""
    ad = (order.customer_name or "").split()[0] if order.customer_name else ""
    no = order.name or f"#{order.order_number}"
    merhaba = f"Merhaba {ad}," if ad else "Merhaba,"
    return (
        f"{merhaba}\n\n{no} numaralı siparişinizin tasarımını hazırladık. "
        f"Lütfen aşağıdaki linkten inceleyip onaylar mısınız?\n\n{link}\n\n"
        f"Onayınızın ardından baskıya alıyoruz. Teşekkürler!"
    )


def create_approval(db: Session, order: Order, user, note: str | None = None) -> DesignApproval:
    """Sipariş için yeni onay kaydı (versiyon = mevcut max + 1)."""
    existing = order.approvals or []
    version = max((a.version for a in existing), default=0) + 1
    token = secrets.token_urlsafe(24)
    ap = DesignApproval(
        tenant_id=order.tenant_id, order_id=order.id, token=token,
        status="bekliyor", version=version, items=build_items(db, order),
        note=(note or None),
        created_by=(getattr(user, "full_name", None) or getattr(user, "email", None)) if user else None,
    )
    db.add(ap)
    db.flush()
    return ap


def serialize(ap: DesignApproval, with_secrets: bool = False) -> dict:
    d = {
        "id": str(ap.id),
        "status": ap.status,
        "status_label": STATUS_LABELS.get(ap.status, ap.status),
        "version": ap.version,
        "items": ap.items or [],
        "note": ap.note,
        "customer_note": ap.customer_note,
        "decided_at": ap.decided_at.isoformat() if ap.decided_at else None,
        "created_by": ap.created_by,
        "created_at": ap.created_at.isoformat() if ap.created_at else None,
    }
    if with_secrets:
        d["token"] = ap.token
        d["link"] = approval_link(ap.token)
    return d


def public_payload(ap: DesignApproval, order: Order) -> dict:
    """Public onay sayfası için — hassas veri (email/telefon/adres) YOK."""
    return {
        "order_no": order.name or f"#{order.order_number}",
        "atolye": None,  # router dolduracak (tenant adı)
        "status": ap.status,
        "status_label": STATUS_LABELS.get(ap.status, ap.status),
        "version": ap.version,
        "items": [
            {"image_url": it.get("image_url"), "title": it.get("title"), "quantity": it.get("quantity", 1)}
            for it in (ap.items or [])
        ],
        "note": ap.note,
        "customer_note": ap.customer_note,
        "decided_at": ap.decided_at.isoformat() if ap.decided_at else None,
    }
