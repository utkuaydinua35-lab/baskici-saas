"""
İndirim Kuponları (admin) — /api/discounts/*

Vitrin mağazaları için kupon CRUD. Public doğrulama routers/public_shop.py'de
(validate-code), kullanım sayacı services/storefront_order.py'de (yalnızca paid).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.database import get_db
from app.models import DiscountCode, Store, User

router = APIRouter(
    prefix="/api/discounts", tags=["discounts"],
    dependencies=[Depends(require_permission("vitrin"))],
)

KINDS = {"percent", "amount", "free_shipping"}


class DiscountCreate(BaseModel):
    store_id: uuid.UUID
    code: str = Field(..., min_length=2, max_length=40)
    kind: str = Field(...)
    value: Decimal = Field(0, ge=0)
    min_subtotal: Decimal | None = Field(None, ge=0)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    usage_limit: int | None = Field(None, ge=1)
    once_per_customer: bool = False
    is_active: bool = True

    @field_validator("kind")
    @classmethod
    def _kind_ok(cls, v: str) -> str:
        if v not in KINDS:
            raise ValueError(f"kind şunlardan biri olmalı: {', '.join(sorted(KINDS))}")
        return v

    @field_validator("code")
    @classmethod
    def _code_norm(cls, v: str) -> str:
        code = v.strip().upper()
        if not code.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Kod yalnızca harf, rakam, - ve _ içerebilir")
        return code


class DiscountUpdate(BaseModel):
    value: Decimal | None = Field(None, ge=0)
    min_subtotal: Decimal | None = Field(None, ge=0)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    usage_limit: int | None = Field(None, ge=1)
    once_per_customer: bool | None = None
    is_active: bool | None = None


def _serialize(dc: DiscountCode) -> dict:
    return {
        "id": str(dc.id),
        "store_id": str(dc.store_id),
        "code": dc.code,
        "kind": dc.kind,
        "value": str(dc.value),
        "min_subtotal": str(dc.min_subtotal) if dc.min_subtotal is not None else None,
        "starts_at": dc.starts_at.isoformat() if dc.starts_at else None,
        "ends_at": dc.ends_at.isoformat() if dc.ends_at else None,
        "usage_limit": dc.usage_limit,
        "usage_count": dc.usage_count,
        "once_per_customer": dc.once_per_customer,
        "is_active": dc.is_active,
        "created_at": dc.created_at.isoformat() if dc.created_at else None,
    }


def _validate_kind_value(kind: str, value: Decimal) -> None:
    if kind == "percent" and not (Decimal("1") <= value <= Decimal("99")):
        raise HTTPException(422, "Yüzde indirimi 1-99 arasında olmalı (%100 desteklenmez)")
    if kind == "amount" and value <= 0:
        raise HTTPException(422, "Tutar indirimi 0'dan büyük olmalı")


@router.get("", response_model=list[dict])
def list_discounts(
    store_id: uuid.UUID | None = Query(None),
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    q = select(DiscountCode).where(DiscountCode.tenant_id == user.tenant_id) \
        .order_by(DiscountCode.created_at.desc())
    if store_id:
        q = q.where(DiscountCode.store_id == store_id)
    return [_serialize(dc) for dc in db.scalars(q).all()]


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_discount(
    body: DiscountCreate,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    store = db.scalar(select(Store).where(
        Store.id == body.store_id, Store.tenant_id == user.tenant_id,
        Store.platform == "storefront",
    ))
    if not store:
        raise HTTPException(404, "Vitrin mağazası bulunamadı")

    _validate_kind_value(body.kind, body.value)
    if body.starts_at and body.ends_at and body.ends_at <= body.starts_at:
        raise HTTPException(422, "Bitiş tarihi başlangıçtan sonra olmalı")

    exists = db.scalar(select(DiscountCode).where(
        DiscountCode.store_id == body.store_id, DiscountCode.code == body.code))
    if exists:
        raise HTTPException(409, "Bu kod zaten mevcut")

    dc = DiscountCode(tenant_id=user.tenant_id, **body.model_dump())
    db.add(dc)
    db.commit()
    db.refresh(dc)
    return _serialize(dc)


@router.patch("/{discount_id}", response_model=dict)
def update_discount(
    discount_id: uuid.UUID,
    body: DiscountUpdate,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    dc = db.scalar(select(DiscountCode).where(
        DiscountCode.id == discount_id, DiscountCode.tenant_id == user.tenant_id))
    if not dc:
        raise HTTPException(404, "Kupon bulunamadı")

    updates = body.model_dump(exclude_unset=True)
    if "value" in updates and updates["value"] is not None:
        _validate_kind_value(dc.kind, updates["value"])
    for k, v in updates.items():
        setattr(dc, k, v)
    db.commit()
    db.refresh(dc)
    return _serialize(dc)


@router.delete("/{discount_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_discount(
    discount_id: uuid.UUID,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    dc = db.scalar(select(DiscountCode).where(
        DiscountCode.id == discount_id, DiscountCode.tenant_id == user.tenant_id))
    if not dc:
        raise HTTPException(404, "Kupon bulunamadı")
    db.delete(dc)
    db.commit()
