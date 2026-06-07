"""
Public destek endpoint'leri — AUTH YOK (müşteriye açık).

Güvenlik: her istekte sipariş no + e-posta Shopify'dan doğrulanır (anonim/sahte
mesaj olmaz). Rate-limit + 12 saat mesaj kuralı uygulanır.

- POST /support/thread   → siparişe ait mesajları getir (müşteri cevabı görür)
- POST /support/message  → müşteri yeni mesaj yazar
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.public_tracker import rate_limit
from app.services import support as sup
from app.services import tracker as tk
from app.services import uploads as uploads_service

router = APIRouter(tags=["public-support"])


class ThreadRequest(BaseModel):
    order_number: str
    email: EmailStr


class MessageRequest(BaseModel):
    order_number: str
    email: EmailStr
    message: str = ""
    image_url: str | None = None


def _verify_order(db: Session, order_number: str, email: str) -> dict:
    store = tk.resolve_tracker_store(db)
    if not store:
        raise HTTPException(503, "Servis şu an kullanılamıyor.")
    order = tk.fetch_order_for_tracking(store, order_number, email)
    if not order:
        raise HTTPException(404, "Sipariş bulunamadı. Sipariş numarası ve e-posta eşleşmiyor.")
    info = tk.extract_tracking_info(order)
    info["email"] = (order.get("email") or "").lower()
    return store, info


@router.post("/support/thread")
def get_support_thread(
    payload: ThreadRequest,
    request: Request,
    _rl: None = Depends(rate_limit),
    db: Session = Depends(get_db),
):
    _store, info = _verify_order(db, payload.order_number, str(payload.email))
    thread = sup.get_thread(db, info["shopify_order_id"])
    return sup.public_thread_payload(db, thread)


@router.post("/support/message")
def post_support_message(
    payload: MessageRequest,
    request: Request,
    _rl: None = Depends(rate_limit),
    db: Session = Depends(get_db),
):
    store, info = _verify_order(db, payload.order_number, str(payload.email))
    thread = sup.get_thread(db, info["shopify_order_id"])

    msg = (payload.message or "").strip()
    img = payload.image_url if uploads_service.is_valid_image_url(payload.image_url) else None
    if not msg and not img:
        raise HTTPException(422, "Mesaj veya görsel gerekli.")

    allowed, wait = sup.can_customer_post(thread)
    if not allowed:
        hours = max(1, round(wait / 3600))
        raise HTTPException(
            429,
            f"Yeni mesaj için lütfen bekleyin. Yaklaşık {hours} saat sonra tekrar yazabilirsiniz.",
        )

    thread = sup.add_customer_message(db, store, info, msg, image_url=img)
    return sup.public_thread_payload(db, thread)


@router.post("/support/upload")
def upload_support_image(
    request: Request,
    file: UploadFile = File(...),
    _rl: None = Depends(rate_limit),
):
    """Müşteri görsel yükler (mesaj göndermeden önce). URL döner."""
    rel = uploads_service.save_image(file)
    return {"url": uploads_service.public_url(rel)}
