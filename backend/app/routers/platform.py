"""
Platform yönetimi (white-label) — /api/platform/*

Yalnızca platform sahibi (is_platform_admin). Atölyeleri (tenant) oluştur/yönet:
plan, abonelik süresi, aktif/pasif, markalama. Kiralama iş modelinin çekirdeği.

is_platform_admin yalnızca DB'den elle verilir (kasıtlı — bu bayrağı atayan
endpoint YOK). İlk platform admini:
  UPDATE users SET is_platform_admin = true WHERE email = '...';
"""
from __future__ import annotations

import re
import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func as sql_func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_platform_admin
from app.auth.schemas import slugify
from app.auth.security import hash_password
from app.database import get_db
from app.models import Order, Store, Tenant, User

router = APIRouter(
    prefix="/api/platform", tags=["platform"],
    dependencies=[Depends(require_platform_admin)],
)

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def _unique_slug(db: Session, name: str) -> str:
    base = slugify(name) or "atolye"
    slug = base
    i = 1
    while db.scalar(select(Tenant).where(Tenant.slug == slug)):
        i += 1
        slug = f"{base}-{i}"
    return slug


def _ser_tenant(db: Session, t: Tenant) -> dict:
    user_count = db.scalar(
        select(sql_func.count(User.id)).where(User.tenant_id == t.id)
    ) or 0
    order_count = db.scalar(
        select(sql_func.count(Order.id)).where(Order.tenant_id == t.id)
    ) or 0
    return {
        "id": str(t.id),
        "name": t.name,
        "slug": t.slug,
        "plan": t.plan,
        "is_active": t.is_active,
        "active_until": t.active_until.isoformat() if t.active_until else None,
        "logo_url": t.logo_url,
        "brand_color": t.brand_color,
        "app_name": t.app_name,
        "user_count": int(user_count),
        "order_count": int(order_count),
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


@router.get("/tenants", response_model=dict)
def list_tenants(user: User = Depends(require_platform_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(Tenant).order_by(Tenant.created_at.desc())).all()
    return {"items": [_ser_tenant(db, t) for t in rows]}


class CreateTenantRequest(BaseModel):
    tenant_name: str = Field(..., min_length=2, max_length=200)
    owner_email: EmailStr
    owner_password: str = Field(..., min_length=6, max_length=200)
    owner_name: str | None = None
    plan: str = "trial"
    active_until: date | None = None
    brand_color: str | None = None
    app_name: str | None = None


@router.post("/tenants", response_model=dict, status_code=201)
def create_tenant(
    req: CreateTenantRequest,
    user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    """Yeni atölye (tenant) + sahibi (owner) kullanıcı oluştur."""
    if db.scalar(select(User).where(User.email == req.owner_email.lower())):
        raise HTTPException(409, "Bu e-posta zaten kayıtlı.")
    if req.brand_color and not _HEX.match(req.brand_color):
        raise HTTPException(400, "Geçersiz renk (#rrggbb)")

    tenant = Tenant(
        name=req.tenant_name.strip(),
        slug=_unique_slug(db, req.tenant_name),
        plan=req.plan or "trial",
        is_active=True,
        active_until=req.active_until,
        brand_color=(req.brand_color or None),
        app_name=(req.app_name or "").strip()[:80] or None,
    )
    db.add(tenant)
    db.flush()

    owner = User(
        tenant_id=tenant.id,
        email=req.owner_email.lower(),
        password_hash=hash_password(req.owner_password),
        full_name=(req.owner_name or req.tenant_name).strip(),
        role="owner",
        is_active=True,
    )
    db.add(owner)
    db.commit()
    db.refresh(tenant)
    return _ser_tenant(db, tenant)


class UpdateTenantRequest(BaseModel):
    name: str | None = None
    plan: str | None = None
    is_active: bool | None = None
    active_until: date | None = None
    clear_active_until: bool = False
    brand_color: str | None = None
    app_name: str | None = None


@router.patch("/tenants/{tenant_id}", response_model=dict)
def update_tenant(
    tenant_id: uuid.UUID,
    req: UpdateTenantRequest,
    user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
):
    t = db.scalar(select(Tenant).where(Tenant.id == tenant_id))
    if not t:
        raise HTTPException(404, "Atölye bulunamadı")

    if req.name is not None:
        t.name = req.name.strip() or t.name
    if req.plan is not None:
        t.plan = req.plan.strip() or t.plan
    if req.is_active is not None:
        t.is_active = req.is_active
    if req.clear_active_until:
        t.active_until = None
    elif req.active_until is not None:
        t.active_until = req.active_until
    if req.brand_color is not None:
        c = req.brand_color.strip()
        if c and not _HEX.match(c):
            raise HTTPException(400, "Geçersiz renk (#rrggbb)")
        t.brand_color = c or None
    if req.app_name is not None:
        t.app_name = req.app_name.strip()[:80] or None

    db.commit()
    db.refresh(t)
    return _ser_tenant(db, t)
