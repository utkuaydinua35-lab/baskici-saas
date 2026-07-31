"""
Mağaza aktivite günlüğü (okuma) — /api/store-activity

"Kim, ne zaman, neyi değiştirdi": ürün/koleksiyon/kupon/ayar/tema
değişiklikleri + para iadesi ve kargo gönderileri. Sipariş AŞAMA geçmişi
sipariş detayındaki zaman akışında kalır (burada tekrarlanmaz).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.database import get_db
from app.models import ActivityLog, User
from app.services.activity import ACTION_LABELS, label

router = APIRouter(
    prefix="/api/store-activity", tags=["store-activity"],
    dependencies=[Depends(require_permission("vitrin"))],
)

MAX_DAYS = 180


@router.get("", response_model=dict)
def list_activity(
    store_id: uuid.UUID | None = Query(None),
    action: str | None = Query(None),
    user_email: str | None = Query(None),
    days: int = Query(30, ge=1, le=MAX_DAYS),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    conds = [ActivityLog.tenant_id == user.tenant_id, ActivityLog.created_at >= since]
    if store_id:
        conds.append(ActivityLog.store_id == store_id)
    if action:
        conds.append(ActivityLog.action == action)
    if user_email:
        conds.append(ActivityLog.user_email == user_email)

    rows = db.scalars(
        select(ActivityLog).where(*conds)
        .order_by(desc(ActivityLog.created_at))
        .offset((page - 1) * per_page).limit(per_page + 1)
    ).all()
    has_more = len(rows) > per_page
    rows = rows[:per_page]

    return {
        "items": [
            {
                "id": str(r.id),
                "action": r.action,
                "action_label": label(r.action),
                "entity_type": r.entity_type,
                "entity_id": r.entity_id,
                "entity_label": r.entity_label,
                "detail": r.detail,
                "user_email": r.user_email,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
        "page": page,
        "has_more": has_more,
    }


@router.get("/_meta", response_model=dict)
def activity_meta(
    store_id: uuid.UUID | None = Query(None),
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Filtre seçenekleri: kayıtlarda geçen işlemler + kullanıcılar."""
    conds = [ActivityLog.tenant_id == user.tenant_id]
    if store_id:
        conds.append(ActivityLog.store_id == store_id)
    actions = db.scalars(select(ActivityLog.action).where(*conds).distinct()).all()
    users = db.scalars(
        select(ActivityLog.user_email).where(*conds, ActivityLog.user_email.isnot(None))
        .distinct()
    ).all()
    return {
        "actions": [{"key": a, "label": ACTION_LABELS.get(a, a)} for a in sorted(actions)],
        "users": sorted(users),
    }
