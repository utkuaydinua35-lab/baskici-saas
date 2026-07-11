"""
Tasarım Talepleri (admin) — /api/design-requests/*

Müşterilerin hesaplarından yükledikleri tasarım talepleri; panel inceler,
durum + not günceller (müşteri hesabında görünür).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.database import get_db
from app.models import DesignRequest, User

router = APIRouter(
    prefix="/api/design-requests", tags=["design-requests"],
    dependencies=[Depends(require_permission("vitrin"))],
)

STATUSES = {"acik", "incelendi", "teklif", "tamam", "red"}


class DesignRequestUpdate(BaseModel):
    status: str | None = None
    admin_note: str | None = Field(None, max_length=2000)
    notify_customer: bool = False  # true ise müşteriye durum/not e-postası gider


@router.get("", response_model=dict)
def list_requests(
    store_id: uuid.UUID = Query(...),
    status_f: str | None = Query(None, alias="status"),
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    q = select(DesignRequest).where(
        DesignRequest.tenant_id == user.tenant_id,
        DesignRequest.store_id == store_id,
    ).order_by(DesignRequest.created_at.desc()).limit(200)
    if status_f in STATUSES:
        q = q.where(DesignRequest.status == status_f)
    rows = db.scalars(q).all()
    return {"requests": [
        {"id": str(r.id), "customer_email": r.customer_email,
         "customer_name": r.customer_name, "image_url": r.image_url,
         "message": r.message, "phone_model": r.phone_model,
         "status": r.status, "admin_note": r.admin_note,
         "created_at": r.created_at.isoformat() if r.created_at else None}
        for r in rows
    ]}


@router.patch("/{request_id}", response_model=dict)
def update_request(
    request_id: uuid.UUID,
    body: DesignRequestUpdate,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    r = db.scalar(select(DesignRequest).where(
        DesignRequest.id == request_id, DesignRequest.tenant_id == user.tenant_id))
    if not r:
        raise HTTPException(404, "Talep bulunamadı")
    if body.status is not None:
        if body.status not in STATUSES:
            raise HTTPException(422, "Geçersiz durum")
        r.status = body.status
    if body.admin_note is not None:
        r.admin_note = body.admin_note.strip() or None
    db.commit()

    # Bildirim istendiyse her zaman gönder — değişiklik olmasa da mevcut
    # durum+notu yeniden iletmek meşru (admin açıkça istedi).
    notified = False
    if body.notify_customer and r.customer_email:
        notified = _notify_customer(db, r)
    return {"ok": True, "status": r.status, "notified": notified}


STATUS_TR = {"acik": "İnceleme bekliyor", "incelendi": "İncelendi",
             "teklif": "Teklif hazırlandı", "tamam": "Tamamlandı", "red": "Uygun değil"}


def _notify_customer(db: Session, r: DesignRequest) -> bool:
    """Müşteriye durum/not e-postası — best-effort (SMTP yoksa sessizce False)."""
    try:
        from xml.sax.saxutils import escape

        from app.models import Store
        from app.services import email_service

        store = db.get(Store, r.store_id)
        if not store:
            return False
        cfg = store.config or {}
        site = (cfg.get("storefront_url")
                or (f"https://{cfg['shop_domain']}" if cfg.get("shop_domain") else "")).rstrip("/")
        tenant = getattr(store, "tenant", None)
        brand = email_service.brand_kwargs(tenant) if tenant else {}
        label = STATUS_TR.get(r.status, r.status)
        note_html = ""
        if r.admin_note:
            note_html = email_service.highlight_box(
                f"💬 {escape(r.admin_note)}")
        html = email_service.render_email(
            title="Tasarım talebiniz güncellendi",
            body_html=(
                f"<p>Merhaba{' ' + escape(r.customer_name) if r.customer_name else ''},</p>"
                f"<p>Yüklediğiniz tasarım için talebinizin durumu: <b>{escape(label)}</b></p>"
                f"{note_html}"
            ),
            button_text="Talebimi Görüntüle" if site else "",
            button_url=f"{site}/hesap" if site else "",
            preheader=f"Talep durumu: {label}",
            emoji="🎨",
            **brand,
        )
        return email_service.send_email(
            r.customer_email, f"Tasarım talebiniz: {label}", html)
    except Exception:  # noqa: BLE001 — bildirim talebi düşürmez
        return False
