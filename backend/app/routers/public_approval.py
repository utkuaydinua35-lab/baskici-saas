"""
Public müşteri onay endpoint'leri — AUTH YOK (token ile erişim).

- GET  /onay/{token}            → onay sayfası (HTML)
- GET  /approval/{token}        → onay verisi (JSON, hassas veri yok)
- POST /approval/{token}/decision → müşteri kararı (onayla / revizyon)

Güvenlik: token tahmin edilemez (secrets.token_urlsafe). Hassas veri
(e-posta/telefon/adres) public payload'da YOK.
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DesignApproval, Notification, Order, OrderStatusHistory, Tenant
from app.routers.public_tracker import rate_limit
from app.services import approvals as ap_svc

router = APIRouter(tags=["public-approval"])

_HTML_PATH = Path(__file__).parent.parent / "public" / "onay.html"
try:
    _ONAY_HTML = _HTML_PATH.read_text(encoding="utf-8")
except OSError:
    _ONAY_HTML = "<h1>Onay sayfası yüklenemedi</h1>"


def _get_approval(db: Session, token: str) -> tuple[DesignApproval, Order]:
    ap = db.scalar(
        select(DesignApproval).where(DesignApproval.token == token)
        .execution_options(include_deleted=True)
    )
    if not ap:
        raise HTTPException(404, "Onay bağlantısı bulunamadı veya süresi dolmuş.")
    order = db.scalar(
        select(Order).where(Order.id == ap.order_id).execution_options(include_deleted=True)
    )
    if not order:
        raise HTTPException(404, "Sipariş bulunamadı.")
    return ap, order


@router.get("/onay/{token}", response_class=HTMLResponse)
@router.get("/onay", response_class=HTMLResponse)
def approval_page(token: str | None = None):
    return HTMLResponse(_ONAY_HTML)


@router.get("/approval/{token}", response_model=dict)
def get_approval(token: str, db: Session = Depends(get_db)):
    ap, order = _get_approval(db, token)
    data = ap_svc.public_payload(ap, order)
    tenant = db.get(Tenant, ap.tenant_id)
    data["atolye"] = (tenant.name if tenant else None) or "Atölye"
    data["logo_url"] = (tenant.logo_url if tenant else None)
    return data


class DecisionRequest(BaseModel):
    decision: str  # "onayla" | "revizyon"
    note: str = ""

    @field_validator("note")
    @classmethod
    def _n(cls, v: str) -> str:
        return (v or "").strip()[:1000]


@router.post("/approval/{token}/decision", response_model=dict)
def post_decision(
    token: str,
    payload: DecisionRequest,
    _rl: None = Depends(rate_limit),
    db: Session = Depends(get_db),
):
    ap, order = _get_approval(db, token)

    if ap.status != "bekliyor":
        # Zaten karar verilmiş — mevcut durumu döndür (idempotent)
        return {"ok": True, "status": ap.status, "already": True}

    order_no = order.name or f"#{order.order_number}"
    if payload.decision == "onayla":
        ap.status = "onaylandi"
        action = "musteri_onay"
        note = None
        notif_title = f"✅ Müşteri onayladı — {order_no}"
        notif_body = None
    elif payload.decision == "revizyon":
        ap.status = "revizyon"
        ap.customer_note = payload.note or None
        action = "musteri_revizyon"
        note = payload.note or None
        notif_title = f"✏️ Müşteri revizyon istedi — {order_no}"
        notif_body = payload.note or None
    else:
        raise HTTPException(400, "Geçersiz karar.")

    ap.decided_at = datetime.now(UTC)
    db.add(OrderStatusHistory(
        tenant_id=ap.tenant_id, order_id=ap.order_id,
        action=action, note=note, created_by="Müşteri",
    ))
    # Panel bildirimi (zil)
    db.add(Notification(
        tenant_id=ap.tenant_id, store_id=order.store_id,
        kind="info", title=notif_title, body=notif_body,
    ))
    db.commit()
    return {"ok": True, "status": ap.status}
