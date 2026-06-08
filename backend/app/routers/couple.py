"""
Couple (cift kilif) urun yonetimi — /api/couple/*

Tenant, mağazadaki couple ürünleri işaretler ve her birine 2 tasarım atar.
plan_molds bu ürünler için 2 ayrı birim üretir (aynı model, 2 tasarım).
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
from app.models import CoupleProduct, Design, Store, User
from app.services import storage

router = APIRouter(prefix="/api/couple", tags=["couple"])


def _get_store(db: Session, store_id: uuid.UUID, tenant_id: uuid.UUID) -> Store:
    store = db.scalar(select(Store).where(Store.id == store_id, Store.tenant_id == tenant_id))
    if not store:
        raise HTTPException(404, "Mağaza bulunamadı")
    return store


def _design_brief(db: Session, design_id) -> dict | None:
    if not design_id:
        return None
    d = db.scalar(select(Design).where(Design.id == design_id))
    if not d:
        return None
    return {
        "id": str(d.id),
        "code": d.code,
        "kalip_tipi": d.kalip_tipi,
        "product_title": d.product_title,
        "product_image_url": d.product_image_url,
        "thumbnail_url": storage.get_thumbnail_url(d.file_path, d.file_format) if d.file_path else None,
    }


class CoupleUpsert(BaseModel):
    store_id: uuid.UUID
    product_id: str
    product_title: str | None = None
    product_image_url: str | None = None
    design_id_1: uuid.UUID | None = None
    design_id_2: uuid.UUID | None = None


@router.get("", response_model=None)
def list_couple(
    store_id: uuid.UUID = Query(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_store(db, store_id, user.tenant_id)
    rows = db.scalars(select(CoupleProduct).where(CoupleProduct.store_id == store_id)).all()
    items = []
    for c in rows:
        items.append({
            "id": str(c.id),
            "product_id": c.product_id,
            "product_title": c.product_title,
            "product_image_url": c.product_image_url,
            "design_1": _design_brief(db, c.design_id_1),
            "design_2": _design_brief(db, c.design_id_2),
        })
    return {"items": items, "product_ids": [c.product_id for c in rows]}


@router.post("", response_model=None)
def upsert_couple(
    body: CoupleUpsert,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_store(db, body.store_id, user.tenant_id)
    # tasarimlar bu magazaya mi ait — dogrula
    for did in (body.design_id_1, body.design_id_2):
        if did:
            d = db.scalar(select(Design).where(Design.id == did, Design.store_id == body.store_id))
            if not d:
                raise HTTPException(400, "Tasarım bu mağazaya ait değil")
    existing = db.scalar(
        select(CoupleProduct).where(
            CoupleProduct.store_id == body.store_id,
            CoupleProduct.product_id == str(body.product_id),
        )
    )
    if existing:
        existing.product_title = body.product_title or existing.product_title
        existing.product_image_url = body.product_image_url or existing.product_image_url
        existing.design_id_1 = body.design_id_1
        existing.design_id_2 = body.design_id_2
        db.commit()
        return {"ok": True, "id": str(existing.id), "updated": True}
    c = CoupleProduct(
        tenant_id=user.tenant_id,
        store_id=body.store_id,
        product_id=str(body.product_id),
        product_title=body.product_title,
        product_image_url=body.product_image_url,
        design_id_1=body.design_id_1,
        design_id_2=body.design_id_2,
    )
    db.add(c)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"ok": True, "already": True}
    db.refresh(c)
    return {"ok": True, "id": str(c.id)}


@router.delete("/{store_id}/{product_id}", response_model=None)
def delete_couple(
    store_id: uuid.UUID,
    product_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_store(db, store_id, user.tenant_id)
    c = db.scalar(
        select(CoupleProduct).where(
            CoupleProduct.store_id == store_id,
            CoupleProduct.product_id == str(product_id),
        )
    )
    if c:
        db.delete(c)
        db.commit()
    return {"ok": True}
