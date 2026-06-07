"""
Panel Destek inbox — /api/support/* (AUTH gerekli, tenant-scoped).

- GET  /api/support/threads?status=        → thread listesi
- GET  /api/support/threads/{id}           → thread + mesajlar
- POST /api/support/threads/{id}/reply     → admin cevabı (müşteriye görünür)
- POST /api/support/threads/{id}/read      → okundu işaretle
- POST /api/support/threads/{id}/close     → kapat
- GET  /api/support/unread_count           → zil/badge icin
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import SupportMessage, SupportThread, User
from app.services import support as sup

router = APIRouter(prefix="/api/support", tags=["support"])


def _thread_summary(db: Session, t: SupportThread) -> dict:
    msg_count = db.scalar(
        select(func.count(SupportMessage.id)).where(SupportMessage.thread_id == t.id)
    ) or 0
    last = db.scalar(
        select(SupportMessage)
        .where(SupportMessage.thread_id == t.id)
        .order_by(SupportMessage.created_at.desc())
        .limit(1)
    )
    return {
        "id": str(t.id),
        "order_number": t.order_number,
        "shopify_order_id": t.shopify_order_id,
        "customer_email": t.customer_email,
        "status": t.status,
        "unread_admin": t.unread_admin or 0,
        "message_count": msg_count,
        "last_preview": (last.body[:120] if last else None),
        "last_sender": (last.sender if last else None),
        "last_message_at": t.last_message_at.isoformat() if t.last_message_at else None,
    }


@router.get("/threads", response_model=list[dict])
def list_threads(
    status: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = select(SupportThread).where(SupportThread.tenant_id == user.tenant_id)
    if status in ("acik", "cevaplandi", "kapali"):
        q = q.where(SupportThread.status == status)
    q = q.order_by(SupportThread.last_message_at.desc().nullslast())
    threads = db.scalars(q).all()
    return [_thread_summary(db, t) for t in threads]


@router.get("/unread_count", response_model=dict)
def unread_count(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.scalar(
        select(func.count(SupportThread.id)).where(
            SupportThread.tenant_id == user.tenant_id,
            SupportThread.unread_admin > 0,
        )
    ) or 0
    return {"unread_threads": int(n)}


def _get_thread(db: Session, thread_id: uuid.UUID, user: User) -> SupportThread:
    t = db.scalar(
        select(SupportThread).where(
            SupportThread.id == thread_id,
            SupportThread.tenant_id == user.tenant_id,
        )
    )
    if not t:
        raise HTTPException(404, "Konuşma bulunamadı")
    return t


@router.get("/threads/{thread_id}", response_model=dict)
def get_thread_detail(
    thread_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    t = _get_thread(db, thread_id, user)
    return {**_thread_summary(db, t), "messages": sup.messages_payload(db, t)}


class ReplyRequest(BaseModel):
    message: str

    @field_validator("message")
    @classmethod
    def _m(cls, v: str) -> str:
        v = (v or "").strip()
        if len(v) < 1:
            raise ValueError("Mesaj boş olamaz")
        return v[:sup.MAX_MESSAGE_LEN]


@router.post("/threads/{thread_id}/reply", response_model=dict)
def reply_thread(
    thread_id: uuid.UUID,
    payload: ReplyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    t = _get_thread(db, thread_id, user)
    t = sup.add_admin_message(db, t, payload.message)
    return {**_thread_summary(db, t), "messages": sup.messages_payload(db, t)}


@router.post("/threads/{thread_id}/read", response_model=dict)
def mark_read(
    thread_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    t = _get_thread(db, thread_id, user)
    t.unread_admin = 0
    db.commit()
    return {"ok": True}


@router.post("/threads/{thread_id}/close", response_model=dict)
def close_thread(
    thread_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    t = _get_thread(db, thread_id, user)
    t.status = "kapali"
    db.commit()
    return {"ok": True}
