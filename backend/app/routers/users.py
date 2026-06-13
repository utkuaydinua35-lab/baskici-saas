"""
Kullanici yonetimi — /api/users
Yalniz 'kullanici_yonetimi' yetkisi olanlar (yonetici) erisebilir.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import permissions as perms
from app.auth.dependencies import get_current_user, require_permission
from app.auth.security import hash_password
from app.database import get_db
from app.models import User

router = APIRouter(prefix="/api/users", tags=["users"])


# ─── Semalar ───
class UserOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    email: str
    full_name: str | None
    role: str
    permissions: list[str] = []
    is_active: bool
    avatar_url: str | None = None
    has_pin: bool = False


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=200)
    password: str = Field(..., min_length=6, max_length=200)
    role: str = Field("baskici", max_length=30)
    permissions: list[str] | None = None


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: str | None = None
    permissions: list[str] | None = None
    is_active: bool | None = None
    password: str | None = Field(None, min_length=6, max_length=200)


class PinSet(BaseModel):
    pin: str | None = Field(None, min_length=4, max_length=8)  # None => PIN kaldir


def _ser(u: User) -> dict:
    return {
        "id": u.id, "email": u.email, "full_name": u.full_name,
        "role": u.role, "permissions": list(u.permissions or []),
        "is_active": u.is_active, "avatar_url": u.avatar_url,
        "has_pin": bool(u.pin_hash),
    }


def _resolve_perms(role: str, explicit: list[str] | None) -> list[str]:
    """Yetkiler: acikca verildiyse onu, yoksa rol sablonundan."""
    if explicit is not None:
        return [p for p in explicit if p in perms.ALL_PERMISSIONS]
    return list(perms.ROLE_TEMPLATES.get(role, []))


@router.get("", response_model=list[UserOut])
def list_users(user: User = Depends(require_permission("kullanici_yonetimi")), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(User).where(User.tenant_id == user.tenant_id).order_by(User.created_at)
    ).all()
    return [_ser(u) for u in rows]


@router.get("/_roles", response_model=dict)
def role_templates(user: User = Depends(require_permission("kullanici_yonetimi"))):
    return {"all_permissions": perms.ALL_PERMISSIONS, "templates": perms.ROLE_TEMPLATES}


@router.post("", response_model=UserOut, status_code=201)
def create_user(req: UserCreate, user: User = Depends(require_permission("kullanici_yonetimi")), db: Session = Depends(get_db)):
    nu = User(
        tenant_id=user.tenant_id,
        email=req.email.lower(),
        password_hash=hash_password(req.password),
        full_name=req.full_name,
        role=req.role,
        permissions=_resolve_perms(req.role, req.permissions),
        is_active=True,
        last_login_at=None,
    )
    db.add(nu)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail="Bu email zaten kullanimda") from e
    db.refresh(nu)
    return _ser(nu)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: uuid.UUID, req: UserUpdate, user: User = Depends(require_permission("kullanici_yonetimi")), db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.id == user_id, User.tenant_id == user.tenant_id))
    if not u:
        raise HTTPException(404, "Kullanici bulunamadi")
    # Kendi rolunu/aktifligini dusurmeyi engelle (kilitlenmesin)
    if u.id == user.id and req.is_active is False:
        raise HTTPException(400, "Kendi hesabini pasif yapamazsin")
    if req.full_name is not None: u.full_name = req.full_name
    if req.role is not None: u.role = req.role
    if req.permissions is not None:
        u.permissions = [p for p in req.permissions if p in perms.ALL_PERMISSIONS]
    if req.is_active is not None: u.is_active = req.is_active
    if req.password: u.password_hash = hash_password(req.password)
    db.commit(); db.refresh(u)
    return _ser(u)


@router.post("/{user_id}/pin", response_model=UserOut)
def set_pin(user_id: uuid.UUID, req: PinSet, user: User = Depends(require_permission("kullanici_yonetimi")), db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.id == user_id, User.tenant_id == user.tenant_id))
    if not u:
        raise HTTPException(404, "Kullanici bulunamadi")
    u.pin_hash = hash_password(req.pin) if req.pin else None
    db.commit(); db.refresh(u)
    return _ser(u)


@router.delete("/{user_id}", response_model=dict)
def delete_user(user_id: uuid.UUID, user: User = Depends(require_permission("kullanici_yonetimi")), db: Session = Depends(get_db)):
    if user_id == user.id:
        raise HTTPException(400, "Kendini silemezsin")
    u = db.scalar(select(User).where(User.id == user_id, User.tenant_id == user.tenant_id))
    if not u:
        raise HTTPException(404, "Kullanici bulunamadi")
    db.delete(u); db.commit()
    return {"ok": True}
