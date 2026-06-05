"""
Tenant ayarları — /api/tenant/settings
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Tenant, User

router = APIRouter(prefix="/api/tenant", tags=["tenant"])


class TenantSettings(BaseModel):
    custom_design_keywords: list[str] = Field(default_factory=list)


class UpdateTenantSettings(BaseModel):
    custom_design_keywords: list[str] | None = None


def _get_tenant(db: Session, tenant_id) -> Tenant:
    t = db.scalar(select(Tenant).where(Tenant.id == tenant_id))
    if not t:
        raise HTTPException(status_code=404, detail="Tenant bulunamadı")
    return t


@router.get("/settings", response_model=None)
def get_settings(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mevcut tenant ayarlarını döndür."""
    t = _get_tenant(db, user.tenant_id)
    return {
        "custom_design_keywords": list(t.custom_design_keywords or []),
    }


@router.patch("/settings", response_model=None)
def update_settings(
    payload: UpdateTenantSettings,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Tenant ayarlarını güncelle (şimdilik sadece custom_design_keywords)."""
    t = _get_tenant(db, user.tenant_id)

    if payload.custom_design_keywords is not None:
        # Temizle: boş/dup'sız + lowercase + trim
        cleaned: list[str] = []
        seen: set[str] = set()
        for kw in payload.custom_design_keywords:
            k = (kw or "").strip().lower()
            if not k:
                continue
            if k in seen:
                continue
            seen.add(k)
            cleaned.append(k)
        t.custom_design_keywords = cleaned

    db.commit()
    db.refresh(t)
    return {
        "custom_design_keywords": list(t.custom_design_keywords or []),
    }
