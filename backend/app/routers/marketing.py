"""Pazarlama paneli — /api/marketing/* (auth, require_permission('pazarlama')).

Abone listesi/sayım, manuel ekleme (çift opt-in onay maili), CSV dışa aktarma,
tekil abonelikten çıkarma, public abonelik formu linki.
"""
from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_permission
from app.config import get_settings
from app.database import get_db
from app.models import MarketingSubscriber, Tenant, User
from app.services import marketing

router = APIRouter(
    prefix="/api/marketing", tags=["marketing"],
    dependencies=[Depends(require_permission("pazarlama"))],
)


def _ser(s: MarketingSubscriber) -> dict:
    return {
        "id": str(s.id),
        "email": s.email,
        "name": s.name,
        "status": s.status,
        "source": s.source,
        "consent_at": s.consent_at.isoformat() if s.consent_at else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@router.get("/subscribers", response_model=dict)
def list_subscribers(
    status: str | None = None,
    q: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    qy = select(MarketingSubscriber).where(MarketingSubscriber.tenant_id == user.tenant_id)
    if status in ("subscribed", "pending", "unsubscribed", "bounced"):
        qy = qy.where(MarketingSubscriber.status == status)
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        qy = qy.where(MarketingSubscriber.email.ilike(like))
    qy = qy.order_by(MarketingSubscriber.created_at.desc()).limit(2000)
    rows = db.scalars(qy).all()
    return {"counts": marketing.counts(db, user.tenant_id), "subscribers": [_ser(s) for s in rows]}


class _AddRequest(BaseModel):
    email: str
    name: str = ""


@router.post("/subscribers", response_model=dict)
def add_subscriber(
    req: _AddRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manuel ekle — KVKK gereği yine çift opt-in (onay maili gönderilir)."""
    sub, st = marketing.subscribe_public(db, user.tenant_id, req.email, req.name, "panel-manual")
    if st == "invalid":
        raise HTTPException(400, "Geçerli bir e-posta adresi girin")
    msg = "Onay e-postası gönderildi (müşteri onaylayınca listeye eklenir)." if st == "pending" \
        else "Bu e-posta zaten abone."
    return {"ok": True, "status": st, "message": msg}


@router.post("/subscribers/{sub_id}/unsubscribe", response_model=dict)
def unsubscribe_subscriber(
    sub_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        sid = uuid.UUID(sub_id)
    except (ValueError, AttributeError):
        raise HTTPException(400, "Geçersiz id")
    s = db.scalar(select(MarketingSubscriber).where(
        MarketingSubscriber.id == sid,
        MarketingSubscriber.tenant_id == user.tenant_id,
    ))
    if not s:
        raise HTTPException(404, "Abone bulunamadı")
    s.status = "unsubscribed"
    s.unsubscribed_at = datetime.now(UTC)
    db.commit()
    return {"ok": True}


@router.get("/subscribers/export.csv")
def export_csv(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Onaylı aboneleri CSV indir (e-posta servisine aktarım için)."""
    rows = db.scalars(
        select(MarketingSubscriber).where(
            MarketingSubscriber.tenant_id == user.tenant_id,
            MarketingSubscriber.status == "subscribed",
        ).order_by(MarketingSubscriber.created_at)
    ).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["email", "name", "status", "consent_at", "source"])
    for s in rows:
        w.writerow([s.email, s.name or "", s.status,
                    s.consent_at.isoformat() if s.consent_at else "", s.source or ""])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="aboneler.csv"'},
    )


@router.get("/public-link", response_model=dict)
def public_link(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Müşterilere paylaşılacak public abonelik formu linki."""
    t = db.get(Tenant, user.tenant_id)
    base = (get_settings().panel_base_url or "").rstrip("/")
    return {"url": f"{base}/api/pazarlama/abone/{t.slug}" if t and t.slug else None}
