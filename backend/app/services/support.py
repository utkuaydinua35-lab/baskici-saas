"""
Destek inbox servisi (Paket 3).

Müşteri takip sayfasından (sipariş no + e-posta doğrulanmış) mesaj yazar →
siparişe bağlı tek thread'e düşer. Admin baskıcı panelinden cevaplar.

Kural: müşteri ardışık iki mesaj arasında 12 saat beklemeli; ama admin cevap
verdiyse sınır sıfırlanır (müşteri hemen devam edebilir).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Notification, SupportMessage, SupportThread

COOLDOWN_HOURS = 12
MAX_MESSAGE_LEN = 2000


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def get_thread(db: Session, shopify_order_id: str) -> SupportThread | None:
    return db.scalar(
        select(SupportThread).where(SupportThread.shopify_order_id == shopify_order_id)
    )


def can_customer_post(thread: SupportThread | None) -> tuple[bool, int]:
    """(izin, kalan_saniye). Thread yoksa/ilk mesajsa izin."""
    if thread is None:
        return True, 0
    lc = _aware(thread.last_customer_message_at)
    la = _aware(thread.last_admin_message_at)
    if lc is None:
        return True, 0
    if la is not None and la > lc:
        return True, 0
    elapsed = _now() - lc
    if elapsed >= timedelta(hours=COOLDOWN_HOURS):
        return True, 0
    return False, int((timedelta(hours=COOLDOWN_HOURS) - elapsed).total_seconds())


def add_customer_message(db: Session, store, order_info: dict, body: str, image_url: str | None = None) -> SupportThread:
    """Thread'i bul/oluştur, müşteri mesajı ekle, admin'e bildirim düş."""
    now = _now()
    soid = order_info["shopify_order_id"]
    thread = get_thread(db, soid)
    if thread is None:
        thread = SupportThread(
            tenant_id=store.tenant_id,
            store_id=store.id,
            shopify_order_id=soid,
            order_number=order_info.get("order_number"),
            customer_email=(order_info.get("email") or "").lower() or None,
            status="acik",
        )
        db.add(thread)
        db.flush()

    msg = SupportMessage(thread_id=thread.id, sender="musteri", body=body.strip()[:MAX_MESSAGE_LEN], image_url=image_url)
    db.add(msg)

    thread.status = "acik"
    thread.unread_admin = (thread.unread_admin or 0) + 1
    thread.last_customer_message_at = now
    thread.last_message_at = now

    db.add(Notification(
        tenant_id=thread.tenant_id,
        store_id=thread.store_id,
        kind="info",
        title=f"Yeni destek mesajı — {thread.order_number or thread.shopify_order_id}",
        body=(body.strip()[:200] or "📷 Görsel"),
    ))
    db.commit()
    db.refresh(thread)
    return thread


def add_admin_message(db: Session, thread: SupportThread, body: str, image_url: str | None = None) -> SupportThread:
    now = _now()
    db.add(SupportMessage(thread_id=thread.id, sender="admin", body=body.strip()[:MAX_MESSAGE_LEN], image_url=image_url))
    thread.status = "cevaplandi"
    thread.unread_admin = 0
    thread.last_admin_message_at = now
    thread.last_message_at = now
    db.commit()
    db.refresh(thread)
    return thread


def messages_payload(db: Session, thread: SupportThread) -> list[dict]:
    msgs = db.scalars(
        select(SupportMessage)
        .where(SupportMessage.thread_id == thread.id)
        .order_by(SupportMessage.created_at.asc())
    ).all()
    return [
        {
            "id": str(m.id),
            "sender": m.sender,
            "body": m.body,
            "image_url": m.image_url,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in msgs
    ]


def public_thread_payload(db: Session, thread: SupportThread | None) -> dict:
    """Müşteriye dönen thread görünümü (takip sayfası)."""
    allowed, wait = can_customer_post(thread)
    return {
        "exists": thread is not None,
        "status": thread.status if thread else None,
        "can_post": allowed,
        "cooldown_seconds": wait,
        "messages": messages_payload(db, thread) if thread else [],
    }
