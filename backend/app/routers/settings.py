"""
Tenant ayarları — /api/tenant/settings
"""
from __future__ import annotations

import hmac
import re

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_permission, require_role
from app.config import get_settings as get_app_settings
from app.database import get_db
from app.models import Tenant, User
from app.services import storage

_AI_MODELS = {"haiku", "sonnet", "opus"}

# NOT: router-seviyesi gate YOK — avatar endpoint'leri (self-servis, kullaniciya ozel)
# herkese acik olmali. Tenant-admin endpoint'leri (settings/brand-logo) tek tek ayarlar ister.
router = APIRouter(prefix="/api/tenant", tags=["tenant"])


class TenantSettings(BaseModel):
    custom_design_keywords: list[str] = Field(default_factory=list)


class UpdateTenantSettings(BaseModel):
    custom_design_keywords: list[str] | None = None
    brand_color: str | None = None     # "#rrggbb" veya "" (temizle)
    app_name: str | None = None        # uygulama adı veya "" (temizle)


def _get_tenant(db: Session, tenant_id) -> Tenant:
    t = db.scalar(select(Tenant).where(Tenant.id == tenant_id))
    if not t:
        raise HTTPException(status_code=404, detail="Tenant bulunamadı")
    return t


@router.get("/settings", response_model=None)
def get_settings(
    user: User = Depends(require_permission("ayarlar")),
    db: Session = Depends(get_db),
):
    """Mevcut tenant ayarlarını döndür."""
    t = _get_tenant(db, user.tenant_id)
    return {
        "custom_design_keywords": list(t.custom_design_keywords or []),
        "brand_color": t.brand_color,
        "app_name": t.app_name,
    }


@router.patch("/settings", response_model=None)
def update_settings(
    payload: UpdateTenantSettings,
    user: User = Depends(require_permission("ayarlar")),
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

    if payload.brand_color is not None:
        c = (payload.brand_color or "").strip()
        if c and not re.match(r"^#[0-9a-fA-F]{6}$", c):
            raise HTTPException(400, "Geçersiz renk (#rrggbb)")
        t.brand_color = c or None

    if payload.app_name is not None:
        t.app_name = (payload.app_name or "").strip()[:80] or None

    db.commit()
    db.refresh(t)
    return {
        "custom_design_keywords": list(t.custom_design_keywords or []),
        "brand_color": t.brand_color,
        "app_name": t.app_name,
    }
# ─── Kargo etiketi şablonu ───────────────────────────────────────────────


@router.get("/etiket-ayarlari", response_model=dict)
def get_etiket_ayarlari(
    user: User = Depends(require_permission("ayarlar")),
    db: Session = Depends(get_db),
):
    """Kayıtlı şablon + varsayılanlar + panelin alan listesi."""
    from app.services import label_pdf
    t = _get_tenant(db, user.tenant_id)
    return {
        "ayarlar": label_pdf.ayarlari_birlestir(t.etiket_ayarlari or {}),
        "varsayilan": dict(label_pdf.VARSAYILAN_AYARLAR),
        "sinirlar": {k: list(v) for k, v in label_pdf._SAYISAL_SINIR.items()},
    }


@router.put("/etiket-ayarlari", response_model=dict)
def put_etiket_ayarlari(
    payload: dict,
    user: User = Depends(require_permission("ayarlar")),
    db: Session = Depends(get_db),
):
    """Şablonu kaydet. Bilinmeyen anahtar atılır, sayısallar SINIRLANIR —
    punto 200 yapılırsa etiket kullanılamaz hale gelir ve bunu ancak baskıda
    fark ederiz."""
    from app.services import label_pdf
    t = _get_tenant(db, user.tenant_id)
    temiz = label_pdf.ayarlari_birlestir(payload or {})
    t.etiket_ayarlari = temiz
    db.commit()
    return {"ok": True, "ayarlar": temiz}


# ─── AI Destek Yanıtı ayarları (yalnızca yönetici; model değişikliği master password ister) ───

class UpdateAISettings(BaseModel):
    enabled: bool
    model: str
    master_password: str = ""


@router.get("/ai-settings", response_model=dict)
def get_ai_settings(
    user: User = Depends(require_role("yonetici", "owner")),
    db: Session = Depends(get_db),
):
    """AI destek yanıtı ayarları (yalnızca yönetici)."""
    t = _get_tenant(db, user.tenant_id)
    app_settings = get_app_settings()
    return {
        "enabled": bool(t.ai_reply_enabled),
        "model": t.ai_reply_model or "opus",
        # Sunucu tarafı hazır mı? (UI bilgilendirme için)
        "api_key_configured": bool(app_settings.anthropic_api_key),
        "master_configured": bool(app_settings.ai_model_master_password),
    }


@router.patch("/ai-settings", response_model=dict)
def update_ai_settings(
    payload: UpdateAISettings,
    user: User = Depends(require_role("yonetici", "owner")),
    db: Session = Depends(get_db),
):
    """AI ayarlarını güncelle. Değişiklik master password ister (yalnızca yönetici)."""
    t = _get_tenant(db, user.tenant_id)
    app_settings = get_app_settings()

    if payload.model not in _AI_MODELS:
        raise HTTPException(400, "Geçersiz model (haiku, sonnet veya opus)")

    # Değişiklik var mı?
    changed = (bool(payload.enabled) != bool(t.ai_reply_enabled)) or (payload.model != (t.ai_reply_model or "opus"))
    if not changed:
        return {"enabled": bool(t.ai_reply_enabled), "model": t.ai_reply_model or "opus"}

    # Master password kontrolü
    if not app_settings.ai_model_master_password:
        raise HTTPException(422, "Master password sunucuda yapılandırılmamış (AI_MODEL_MASTER_PASSWORD).")
    if not hmac.compare_digest(payload.master_password or "", app_settings.ai_model_master_password):
        raise HTTPException(403, "Master password hatalı.")

    t.ai_reply_enabled = bool(payload.enabled)
    t.ai_reply_model = payload.model
    db.commit()
    db.refresh(t)
    return {"enabled": bool(t.ai_reply_enabled), "model": t.ai_reply_model or "opus"}


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
    user: User = Depends(require_permission("ayarlar")),
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
def delete_brand_logo(user: User = Depends(require_permission("ayarlar")), db: Session = Depends(get_db)):
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
