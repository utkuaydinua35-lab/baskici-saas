"""
Tenant ayarları — /api/tenant/settings
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Tenant, User
from app.services import storage

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
_LOGO_EXT = {"png", "jpg", "jpeg", "svg", "webp"}
_LOGO_MAX = 5 * 1024 * 1024  # 5 MB


async def _read_logo(file: UploadFile) -> tuple[bytes, str]:
    ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    if ext not in _LOGO_EXT:
        raise HTTPException(400, f"Izin verilen formatlar: {', '.join(sorted(_LOGO_EXT))}")
    data = await file.read()
    if len(data) > _LOGO_MAX:
        raise HTTPException(400, f"Dosya cok buyuk (max {_LOGO_MAX // 1024 // 1024} MB)")
    return data, ext


@router.post("/brand-logo", response_model=dict)
async def upload_brand_logo(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Marka (tenant) logosu yukle. Sol ust + markalama icin."""
    data, ext = await _read_logo(file)
    url = storage.save_logo(user.tenant_id, "brand", data, ext)
    tenant = db.scalar(select(Tenant).where(Tenant.id == user.tenant_id))
    if not tenant:
        raise HTTPException(404, "Tenant bulunamadi")
    tenant.logo_url = url
    db.commit()
    return {"ok": True, "logo_url": url}


@router.delete("/brand-logo", response_model=dict)
def delete_brand_logo(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tenant = db.scalar(select(Tenant).where(Tenant.id == user.tenant_id))
    if tenant:
        tenant.logo_url = None
        db.commit()
    return {"ok": True}


@router.post("/avatar", response_model=dict)
async def upload_avatar(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Profil avatari yukle (kullaniciya ozel)."""
    data, ext = await _read_logo(file)
    url = storage.save_logo(user.tenant_id, f"avatar-{user.id}", data, ext)
    u = db.scalar(select(User).where(User.id == user.id))
    if not u:
        raise HTTPException(404, "Kullanici bulunamadi")
    u.avatar_url = url
    db.commit()
    return {"ok": True, "avatar_url": url}


@router.delete("/avatar", response_model=dict)
def delete_avatar(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.id == user.id))
    if u:
        u.avatar_url = None
        db.commit()
    return {"ok": True}
