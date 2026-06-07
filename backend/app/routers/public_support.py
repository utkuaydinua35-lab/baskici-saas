"""
Public destek (inbox) — AUTH YOK, sipariş no+e-posta doğrulamasıyla (Paket 3).

- POST /support/thread   {order_number, email}        → siparişin mesaj geçmişi
- POST /support/message  {order_number, email, body}  → yeni müşteri mesajı

Kurallar:
  - Her istekte Shopify'dan sipariş+e-posta doğrulanır (sahte/anonim mesaj olmaz).
  - Spam: admin son cevaplayan değilse, müşteri mesajları arası en az 12 saat.
    Admin cevap verince sınır sıfırlanır (müşteri anında yazabilir).
  - Mesaj başına 2000 karakter sınırı.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Notification, SupportMessage, SupportThread
from app.routers.public_tracker import rate_limit
from app.services import tracker as tk

router = APIRouter(tags=["public-support"])

CUSTOMER_COOLDOWN = timedelta(hours=12)


class ThreadRequest(BaseModel):
    order_number: str
    email: EmailStr


class MessageRequest(BaseModel):
    order_number: str
    email: EmailStr
    body: str = Field(..., min_length=1, max_length=2000)


def _verify_order(db: Session, order_number: str, email: str) -> tuple:
    """Sipariş+e-posta doğrula → (store, info). Eşleşmezse 404."""
    store = tk.resolve_tracker_store(db)
    if not store:
        raise HTTPException(503, "Destek servisi şu an kullanılamıyor.")
    order = tk.fetch_order_for_tracking(store, order_number, email)
    if not order:
        raise HTTPException(404, "Sipariş bulunamadı. Bilgilerinizi kontrol edin.")
    return store, tk.extract_tracking_info(order)


def _serialize_messages(thread: SupportThread | None) -> list[dict]:
    if not thread:
        return []
    return [
        {
            "sender": m.sender,
            "body": m.body,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in thread.messages
    ]


@router.post("/support/thread")
def get_thread(payload: ThreadRequest, request: Request, _rl: None = Depends(rate_limit), db: Session = Depends(get_db)):
    _store, info = _verify_order(db, payload.order_number, str(payload.email))
    thread = db.scalar(
        select(SupportThread).where(SupportThread.shopify_order_id == info["shopify_order_id"])
    )
    return {
        "order_name": info["order_name"],
        "status": thread.status if thread else None,
        "messages": _serialize_messages(thread),
    }


@router.post("/support/message")
def post_message(payload: MessageRequest, request: Request, _rl: None = Depends(rate_limit), db: Session = Depends(get_db)):
    store, info = _verify_order(db, payload.order_number, str(payload.email))
    now = datetime.now(timezone.utc)

    thread = db.scalar(
        select(SupportThread).where(SupportThread.shopify_order_id == info["shopify_order_id"])
    )

    # 12 saat kuralı — admin son cevaplayan değilse
    if thread and thread.messages:
        last = thread.messages[-1]
        if last.sender != "admin":
            lc = thread.last_customer_message_at
            if lc is not None:
                if lc.tzinfo is None:
                    lc = lc.replace(tzinfo=timezone.utc)
                if now - lc < CUSTOMER_COOLDOWN:
                    kalan = CUSTOMER_COOLDOWN - (now - lc)
                    saat = int(kalan.total_seconds() // 3600) + 1
                    raise HTTPException(
                        429,
                        f"Henüz cevaplanmamış bir mesajınız var. Yeni mesaj için ~{saat} saat sonra tekrar deneyebilirsiniz.",
                    )

    if not thread:
        thread = SupportThread(
            tenant_id=store.tenant_id,
            store_id=store.id,
            shopify_order_id=info["shopify_order_id"],
            order_number=info["order_number"],
            customer_email=str(payload.email).lower().strip(),
        )
        db.add(thread)
        db.flush()

    msg = SupportMessage(thread_id=thread.id, sender="musteri", body=payload.body.strip())
    db.add(msg)
    thread.status = "acik"
    thread.last_message_at = now
    thread.last_customer_message_at = now
    thread.unread_admin = (thread.unread_admin or 0) + 1

    # Panel bildirimi
    db.add(Notification(
        tenant_id=store.tenant_id,
        store_id=store.id,
        kind="info",
        title="Yeni destek mesajı",
        body=f"#{info['order_number']}: {payload.body.strip()[:80]}",
    ))

    db.commit()
    db.refresh(thread)
    return {
        "order_name": info["order_name"],
        "status": thread.status,
        "messages": _serialize_messages(thread),
    }
