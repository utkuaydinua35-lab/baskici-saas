"""
Destek inbox — panel (authenticated) tarafı (Paket 3).

- GET  /api/support/threads?status=    → konuşma listesi (tenant'a ait)
- GET  /api/support/threads/{id}       → mesajlar (+ admin-okundu işaretle)
- POST /api/support/threads/{id}/reply → admin cevabı (12 saat sınırını sıfırlar)
- POST /api/support/threads/{id}/close → kapat
- GET  /api/support/unread             → toplam okunmamış (zil rozeti için)
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import SupportMessage, SupportThread, User

router = APIRouter(prefix="/api/support", tags=["support"])


def _thread_summary(t: SupportThread) -> dict:
    last = t.messages[-1] if t.messages else None
    return {
        "id": str(t.id),
        "order_number": t.order_number,
        "customer_email": t.customer_email,
        "status": t.status,
        "unread_admin": t.unread_admin or 0,
        "last_message_at": t.last_message_at.isoformat() if t.last_message_at else None,
        "last_preview": (last.body[:120] if last else ""),
        "last_sender": (last.sender if last else None),
        "message_count": len(t.messages),
    }


def _msg(m: SupportMessage) -> dict:
    return {
        "id": str(m.id),
        "sender": m.sender,
        "body": m.body,
        "created_at": m.created_at.isoformat() if m.created_at else None,
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
    return [_thread_summary(t) for t in threads]


@router.get("/unread")
def unread_count(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    total = db.scalar(
        select(func.coalesce(func.sum(SupportThread.unread_admin), 0)).where(
            SupportThread.tenant_id == user.tenant_id
        )
    )
    open_threads = db.scalar(
        select(func.count()).select_from(SupportThread).where(
            SupportThread.tenant_id == user.tenant_id, SupportThread.status == "acik"
        )
    )
    return {"unread_messages": int(total or 0), "open_threads": int(open_threads or 0)}


def _get_thread(db: Session, thread_id, tenant_id) -> SupportThread:
    t = db.scalar(
        select(SupportThread).where(SupportThread.id == thread_id, SupportThread.tenant_id == tenant_id)
    )
    if not t:
        raise HTTPException(404, "Konuşma bulunamadı")
    return t


@router.get("/threads/{thread_id}")
def get_thread(thread_id, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = _get_thread(db, thread_id, user.tenant_id)
    # müşteri mesajlarını okundu işaretle + sayacı sıfırla
    for m in t.messages:
        if m.sender == "musteri" and not m.is_read_by_admin:
            m.is_read_by_admin = True
    t.unread_admin = 0
    db.commit()
    db.refresh(t)
    return {
        "id": str(t.id),
        "order_number": t.order_number,
        "customer_email": t.customer_email,
        "customer_name": t.customer_name,
        "status": t.status,
        "messages": [_msg(m) for m in t.messages],
    }


class ReplyRequest(BaseModel):
    body: str = Field(..., min_length=1, max_length=4000)


@router.post("/threads/{thread_id}/reply")
def reply_thread(thread_id, payload: ReplyRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = _get_thread(db, thread_id, user.tenant_id)
    now = datetime.now(timezone.utc)
    db.add(SupportMessage(thread_id=t.id, sender="admin", body=payload.body.strip(), is_read_by_admin=True))
    t.status = "cevaplandi"
    t.last_message_at = now
    db.commit()
    db.refresh(t)
    return {"id": str(t.id), "status": t.status, "messages": [_msg(m) for m in t.messages]}


@router.post("/threads/{thread_id}/close")
def close_thread(thread_id, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = _get_thread(db, thread_id, user.tenant_id)
    t.status = "kapali"
    db.commit()
    return {"id": str(t.id), "status": t.status}
