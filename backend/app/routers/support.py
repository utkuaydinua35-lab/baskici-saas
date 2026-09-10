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

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_permission
from app.database import get_db
from app.models import Order, SupportMessage, SupportThread, User
from app.services import support as sup
from app.services import uploads as uploads_service

router = APIRouter(prefix="/api/support", tags=["support"],
    dependencies=[Depends(require_permission("destek"))],
)


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


_STAGE_LABEL = {
    1: "Yeni", 2: "Tasarım", 3: "Barkod", 4: "Baskı", 5: "Baskı Tamam",
    6: "Paketleme", 7: "Paketlendi", 8: "Kargoda", 9: "Teslim",
}


def _order_detail_for_thread(db: Session, t: SupportThread) -> dict | None:
    """Konuşmanın sipariş numarasına göre sipariş özetini (kalemler/durum/kargo) döndür."""
    from app.models import LineItem
    onum = (t.order_number or "").strip()
    if not onum:
        return None
    o = db.scalar(
        select(Order).where(Order.tenant_id == t.tenant_id, Order.order_number == onum)
    )
    if not o and t.shopify_order_id:
        o = db.scalar(select(Order).where(
            Order.tenant_id == t.tenant_id, Order.external_id == str(t.shopify_order_id)))
    if not o:
        return {"found": False, "order_number": onum}
    from app.services.mold_planner import extract_phone_model
    lis = db.scalars(select(LineItem).where(LineItem.order_id == o.id).order_by(LineItem.position)).all()
    items = [{
        "title": li.title,
        "model": (extract_phone_model(li) or li.device_model_override or li.variant_title or None),
        "quantity": li.quantity or 1,
        "is_hazir": bool(getattr(li, "is_hazir", False)),
    } for li in lis]
    _ki = o.kargo_info or {}
    return {
        "found": True,
        # Panel içi bağlantı için sipariş kimliği — order_number mağazalar arasında
        # tekrar edebiliyor, UUID tek anlamlı.
        "id": str(o.id),
        "order_number": o.order_number,
        "customer_name": o.customer_name,
        "stage": o.current_stage,
        "stage_label": (_STAGE_LABEL.get(o.current_stage) if o.current_stage else None),
        "fulfillment_status": o.fulfillment_status,
        "cancelled": o.cancelled_at is not None or bool(o.is_iptal),
        "takip_no": _ki.get("takip_no"),
        "kargo_firma": _ki.get("handler_name"),
        "total_qty": sum(i["quantity"] for i in items),
        "items": items,
        "note": o.note,
        "created_at": o.created_at_platform.isoformat() if o.created_at_platform else None,
    }


@router.get("/threads/{thread_id}", response_model=dict)
def get_thread_detail(
    thread_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    t = _get_thread(db, thread_id, user)
    return {
        **_thread_summary(db, t),
        "messages": sup.messages_payload(db, t),
        "order_detail": _order_detail_for_thread(db, t),
    }


class EditMessageIn(BaseModel):
    body: str = ""


@router.patch("/threads/{thread_id}/messages/{message_id}", response_model=dict)
def edit_message(
    thread_id: uuid.UUID,
    message_id: uuid.UUID,
    req: EditMessageIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Kendi (admin) mesajını düzenle. Müşteri mesajı düzenlenemez."""
    t = _get_thread(db, thread_id, user)
    m = db.scalar(select(SupportMessage).where(
        SupportMessage.id == message_id, SupportMessage.thread_id == t.id))
    if not m:
        raise HTTPException(404, "Mesaj bulunamadı")
    if m.sender != "admin":
        raise HTTPException(400, "Yalnızca kendi mesajlarınızı düzenleyebilirsiniz")
    body = (req.body or "").strip()[:sup.MAX_MESSAGE_LEN]
    if not body:
        raise HTTPException(400, "Mesaj boş olamaz")
    m.body = body
    db.commit()
    return {**_thread_summary(db, t), "messages": sup.messages_payload(db, t),
            "order_detail": _order_detail_for_thread(db, t)}


class ReplyRequest(BaseModel):
    message: str = ""
    image_url: str | None = None
    send_email: bool = False  # müşteriye e-posta olarak da gönder

    @field_validator("message")
    @classmethod
    def _m(cls, v: str) -> str:
        return (v or "").strip()[:sup.MAX_MESSAGE_LEN]


def _send_reply_email(db: Session, thread: SupportThread, body: str, img_url: str | None) -> tuple[bool, str | None]:
    """Admin cevabını müşteriye 'destek talebiniz yanıtlandı' e-postası olarak gönder."""
    from html import escape
    from app.config import get_settings
    from app.models import Tenant
    from app.services import email_service

    to = (thread.customer_email or "").strip()
    if not to:
        return False, "Müşteri e-postası yok"
    if not email_service.is_configured():
        return False, "SMTP yapılandırılmamış"

    onum = thread.order_number or thread.shopify_order_id or ""
    ad = (thread.customer_name or "").split()[0] if thread.customer_name else ""
    track = (get_settings().support_public_base_url or "").rstrip("/")

    # White-label: yanıt müşteriye gider — atölyenin markası (logo/ad/renk)
    tenant = db.get(Tenant, thread.tenant_id) if thread.tenant_id else None
    bk = email_service.brand_kwargs(tenant)
    accent = bk.get("accent", email_service.DEFAULT_ACCENT)

    reply_html = escape((body or "").strip()).replace("\n", "<br>") or "—"
    box = email_service.highlight_box(reply_html, accent=accent)
    if img_url:
        box += (f'<p style="margin:0 0 16px"><img src="{escape(img_url)}" alt="" '
                f'style="max-width:100%;border-radius:10px"></p>')
    body_html = (
        f"<p style='margin:0 0 14px'>Merhaba {escape(ad)},</p>"
        f"<p style='margin:0 0 14px'><b>Sipariş #{escape(onum)}</b> ile ilgili destek talebinize "
        "yanıt verdik:</p>"
        f"{box}"
        "<p style='margin:0;font-size:14px;color:#6b7280'>Yanıtlamak veya siparişinizi takip etmek "
        "için aşağıdaki butonu kullanabilirsiniz.</p>"
    )
    # Pazarlama daveti (KVKK: tıklayan kendi gelen kutusundan onaylamış sayılır)
    from app.services import marketing as _mkt
    _join = _mkt.join_url(thread.tenant_id, to, thread.customer_name or "", "support_mail")
    body_html += (
        "<p style='margin:18px 0 0;padding-top:14px;border-top:1px solid #f0f1f3;font-size:13px;color:#6b7280'>"
        f"📣 Kampanya ve yeni ürünlerden haberdar olmak ister misiniz? "
        f"<a href='{_join}' style='color:{accent};font-weight:600'>Abone olun</a></p>"
    )
    html = email_service.render_email(
        title="Destek talebiniz yanıtlandı",
        emoji="💬",
        body_html=body_html,
        button_text="Görüntüle / Yanıtla",
        button_url=track,
        preheader=f"Sipariş #{onum} destek talebinize yanıt verildi",
        footer="Bu e-posta, siparişinizle ilgili destek talebinize verilen yanıttır.",
        **bk,
    )
    text = (f"Destek talebiniz yanıtlandı — Sipariş #{onum}\n\nMerhaba {ad},\n\n"
            f"{(body or '').strip()}\n\nGörüntüle/Yanıtla: {track}")
    subject = f"Destek talebiniz yanıtlandı — Sipariş #{onum}"
    from app.services import email_log
    # SupportThread siparişe order_number ile bağlı (FK yok). Çözebilirsek
    # e-posta siparişin altında görünsün; çözemezsek kayıt yine tutulur —
    # teşhis için gönderimin kendisi de değerli.
    _oid = None
    if thread.order_number:
        _oid = db.scalar(select(Order.id).where(
            Order.tenant_id == thread.tenant_id,
            Order.order_number == str(thread.order_number)).limit(1))
    ok = email_log.gonder_ve_kaydet(
        db, tenant_id=thread.tenant_id, to=to, subject=subject, html=html,
        text=text, order_id=_oid, template_key="destek_yanit")
    return ok, (None if ok else "Gönderim başarısız — e-posta geçmişindeki hataya bakın")


@router.post("/threads/{thread_id}/reply", response_model=dict)
def reply_thread(
    thread_id: uuid.UUID,
    payload: ReplyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    t = _get_thread(db, thread_id, user)
    img = payload.image_url if uploads_service.is_valid_image_url(payload.image_url) else None
    if not payload.message.strip() and not img:
        raise HTTPException(422, "Mesaj veya görsel gerekli.")
    t = sup.add_admin_message(db, t, payload.message, image_url=img)
    # Her cevapta müşteriye otomatik "Destek talebiniz yanıtlandı" e-postası (e-postası varsa)
    email_sent, email_error = (False, None)
    if t.customer_email:
        email_sent, email_error = _send_reply_email(db, t, payload.message, img)
    return {
        **_thread_summary(db, t),
        "messages": sup.messages_payload(db, t),
        "email_sent": email_sent,
        "email_error": email_error,
    }


@router.post("/threads/{thread_id}/ai-draft", response_model=dict)
def ai_draft(
    thread_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Müşterinin son mesajına Claude ile bir yanıt taslağı üret (gönderilmez)."""
    from app.services import ai_reply
    t = _get_thread(db, thread_id, user)
    try:
        result = ai_reply.draft_reply(db, t)
    except ai_reply.DraftError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"draft": result["draft"], "note": result.get("note", "")}


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


@router.post("/upload", response_model=dict)
def upload_support_image_admin(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    """Admin panelden görsel yükler (cevaba eklemek için). URL döner."""
    rel = uploads_service.save_image(file)
    return {"url": uploads_service.public_url(rel)}
