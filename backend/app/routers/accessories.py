"""
Aksesuar ürün yönetimi — /api/accessories/*

Tenant, mağazadaki belirli Shopify ürünlerini "aksesuar" olarak işaretler
(ekran koruyucu, lens, vb). Aksesuarlar kalıp planına ve eksik-tasarım
listesine dahil EDİLMEZ (KisiyeOzelProduct gibi hariç tutulur).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import AccessoryProduct, Store, User

router = APIRouter(prefix="/api/accessories", tags=["accessories"])


def _get_store(db: Session, store_id: uuid.UUID, tenant_id: uuid.UUID) -> Store:
    store = db.scalar(select(Store).where(Store.id == store_id, Store.tenant_id == tenant_id))
    if not store:
        raise HTTPException(404, "Mağaza bulunamadı")
    return store


class MarkRequest(BaseModel):
    store_id: uuid.UUID
    product_id: str
    product_title: str | None = None
    product_image_url: str | None = None


@router.get("", response_model=None)
def list_accessories(
    store_id: uuid.UUID = Query(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_store(db, store_id, user.tenant_id)
    rows = db.scalars(
        select(AccessoryProduct).where(AccessoryProduct.store_id == store_id)
    ).all()
    return {
        "items": [
            {
                "id": str(a.id),
                "product_id": a.product_id,
                "product_title": a.product_title,
                "product_image_url": a.product_image_url,
            }
            for a in rows
        ],
        "product_ids": [a.product_id for a in rows],
    }


@router.post("", response_model=None)
def mark_accessory(
    body: MarkRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_store(db, body.store_id, user.tenant_id)
    existing = db.scalar(
        select(AccessoryProduct).where(
            AccessoryProduct.store_id == body.store_id,
            AccessoryProduct.product_id == str(body.product_id),
        )
    )
    if existing:
        return {"ok": True, "already": True, "id": str(existing.id)}
    a = AccessoryProduct(
        tenant_id=user.tenant_id,
        store_id=body.store_id,
        product_id=str(body.product_id),
        product_title=body.product_title,
        product_image_url=body.product_image_url,
    )
    db.add(a)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"ok": True, "already": True}
    db.refresh(a)
    return {"ok": True, "id": str(a.id)}


@router.delete("/{store_id}/{product_id}", response_model=None)
def unmark_accessory(
    store_id: uuid.UUID,
    product_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_store(db, store_id, user.tenant_id)
    a = db.scalar(
        select(AccessoryProduct).where(
            AccessoryProduct.store_id == store_id,
            AccessoryProduct.product_id == str(product_id),
        )
    )
    if a:
        db.delete(a)
        db.commit()
    return {"ok": True}
