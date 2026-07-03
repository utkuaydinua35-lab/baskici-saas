"""
Terk Edilmiş Sepetler (admin) — /api/checkout-sessions/*

Ödemesi tamamlanmamış (pending/expired/failed) ama e-postası bilinen checkout
oturumları + tek seferlik hatırlatma e-postası.

KVKK: hatırlatma, müşterinin KENDİ başlattığı satın alma işleminin tek seferlik
bildirimi (meşru menfaat); PII 90 günlük saklama penceresi içinde zaten mevcut.
Session başına EN FAZLA 1 hatırlatma gönderilir (reminder_sent_at kilidi).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.database import get_db
from app.models import CheckoutSession, Store, User
from app.services import email_service

router = APIRouter(
    prefix="/api/checkout-sessions", tags=["checkout-admin"],
    dependencies=[Depends(require_permission("vitrin"))],
)

ABANDONED_STATUSES = ("pending", "expired", "failed")


def _serialize(s: CheckoutSession) -> dict:
    cust = s.customer or {}
    return {
        "id": str(s.id),
        "status": s.status,
        "customer_name": f"{cust.get('first_name', '')} {cust.get('last_name', '')}".strip(),
        "email": cust.get("email"),
        "amount": str(s.amount),
        "item_count": sum(int(i.get("quantity", 1)) for i in (s.cart_snapshot or [])),
        "discount_code": s.discount_code,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "reminder_sent_at": s.reminder_sent_at.isoformat() if s.reminder_sent_at else None,
    }


@router.get("", response_model=dict)
def list_abandoned(
    store_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    conds = [
        CheckoutSession.tenant_id == user.tenant_id,
        CheckoutSession.status.in_(ABANDONED_STATUSES),
        CheckoutSession.order_id.is_(None),
        CheckoutSession.customer["email"].astext != "",
    ]
    if store_id:
        conds.append(CheckoutSession.store_id == store_id)

    total, total_amount = db.execute(
        select(func.count(CheckoutSession.id),
               func.coalesce(func.sum(CheckoutSession.amount), 0)).where(*conds)
    ).one()
    rows = db.scalars(
        select(CheckoutSession).where(*conds)
        .order_by(CheckoutSession.created_at.desc())
        .offset((page - 1) * per_page).limit(per_page)
    ).all()

    return {"total": total, "total_amount": str(total_amount),
            "page": page, "per_page": per_page,
            "items": [_serialize(s) for s in rows]}


@router.post("/{session_id}/reminder", response_model=dict)
def send_reminder(
    session_id: uuid.UUID,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    session = db.scalar(
        select(CheckoutSession).where(
            CheckoutSession.id == session_id,
            CheckoutSession.tenant_id == user.tenant_id,
        ).with_for_update()
    )
    if not session or session.status not in ABANDONED_STATUSES or session.order_id:
        raise HTTPException(404, "Uygun oturum bulunamadı")
    if session.reminder_sent_at:
        raise HTTPException(409, "Bu sepet için hatırlatma zaten gönderildi")
    email = (session.customer or {}).get("email")
    if not email:
        raise HTTPException(422, "Oturumda e-posta yok")

    store = db.get(Store, session.store_id)
    ok = _send_reminder_email(db, session, store)
    if not ok:
        raise HTTPException(502, "E-posta gönderilemedi (SMTP ayarlarını kontrol edin)")
    session.reminder_sent_at = datetime.now(timezone.utc)
    db.commit()
    return {"sent": True, "email": email}


def _send_reminder_email(db: Session, session: CheckoutSession, store: Store) -> bool:
    cust = session.customer or {}
    email = cust.get("email")
    if not email:
        return False
    tenant = getattr(store, "tenant", None)
    brand = email_service.brand_kwargs(tenant) if tenant else {}

    config = store.config or {}
    site = (config.get("storefront_url") or f"https://{config.get('shop_domain', '')}").rstrip("/")
    restore_url = f"{site}/sepet?restore={session.lookup_token}"

    rows = "".join(
        f"<tr><td style='padding:5px 0;color:#374151;font-size:14px'>"
        f"{i.get('title', '')} — {i.get('model_display', '')} × {i.get('quantity', 1)}</td>"
        f"<td align='right' style='padding:5px 0;font-size:14px;white-space:nowrap'>"
        f"{Decimal(str(i.get('unit_price', '0'))) * int(i.get('quantity', 1)):.2f} ₺</td></tr>"
        for i in (session.cart_snapshot or [])
    )
    body = (
        f"<p>Merhaba {cust.get('first_name', '')},</p>"
        f"<p>Sepetinizde bıraktığınız ürünler sizi bekliyor. Tek tıkla kaldığınız "
        f"yerden devam edebilirsiniz:</p>"
        f"<table width='100%' style='border-collapse:collapse;margin:10px 0'>{rows}</table>"
        f"<p style='color:#6b7280;font-size:12px'>Bu e-posta, tamamlanmayan "
        f"siparişinizle ilgili tek seferlik bir hatırlatmadır.</p>"
    )
    html = email_service.render_email(
        title="Sepetiniz sizi bekliyor",
        body_html=body,
        button_text="Sepetime Dön",
        button_url=restore_url,
        preheader="Sepetinizdeki ürünler tükenmeden tamamlayın",
        emoji="🛒",
        **brand,
    )
    return email_service.send_email(email, "Sepetinizdeki ürünler sizi bekliyor 🛒", html)
