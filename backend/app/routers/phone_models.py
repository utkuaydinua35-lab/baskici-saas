"""
Telefon Modelleri — /api/phone-models/*

Panelden telefon modeli ekle / düzenle / sil. DB'ye eklenen modeller baseline'ı
(gizli case_dimensions, 339 model) EZER. Yeni telefon çıkınca deploy gerektirmez.

GÜVENLİK: Baseline ölçüleri ASLA dönülmez. Sadece DB kayıtlarının (tenant'ın
kendi eklediği) ölçüsü gösterilir. /check endpoint'i baseline için yalnızca
"tanınıyor" der, ölçü vermez.

Endpoint'ler:
- GET    /api/phone-models            → DB modelleri + baseline adedi
- POST   /api/phone-models            → ekle (baseline override veya yeni model)
- PATCH  /api/phone-models/{id}       → güncelle
- DELETE /api/phone-models/{id}       → sil
- POST   /api/phone-models/check      → model tanınıyor mu? (kaynak: db/baseline)
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import PhoneModel, User
from app.services import phone_models as pm
from app.services._private import case_dimensions as cd

router = APIRouter(prefix="/api/phone-models", tags=["phone-models"])


# ─── Schemas ─────────────────────────────────────────────────
class PhoneModelCreate(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=120)
    brand: str | None = Field(None, max_length=40)
    width_cm: float = Field(..., gt=0, lt=40)
    height_cm: float = Field(..., gt=0, lt=40)
    radius_cm: float = Field(0, ge=0, lt=10)
    spec_key: str | None = Field(None, max_length=60)  # boşsa display_name'den türetilir
    notes: str | None = None


class PhoneModelUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=120)
    brand: str | None = Field(None, max_length=40)
    width_cm: float | None = Field(None, gt=0, lt=40)
    height_cm: float | None = Field(None, gt=0, lt=40)
    radius_cm: float | None = Field(None, ge=0, lt=10)
    is_active: bool | None = None
    notes: str | None = None


class CheckRequest(BaseModel):
    model: str


# ─── Helpers ─────────────────────────────────────────────────
def _serialize(m: PhoneModel) -> dict:
    return {
        "id": str(m.id),
        "spec_key": m.spec_key,
        "display_name": m.display_name,
        "brand": m.brand,
        "width_cm": m.width_cm,
        "height_cm": m.height_cm,
        "radius_cm": m.radius_cm,
        "is_active": m.is_active,
        "notes": m.notes,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }


# ─── Endpoints ───────────────────────────────────────────────
@router.get("", response_model=dict)
def list_models(
    search: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(PhoneModel)
        .where(PhoneModel.tenant_id == user.tenant_id)
        .order_by(desc(PhoneModel.created_at))
    ).all()

    out = []
    for m in rows:
        if search:
            q = search.lower()
            hay = " ".join(filter(None, [
                m.display_name, m.brand, m.spec_key, m.notes,
            ])).lower()
            if q not in hay:
                continue
        out.append(_serialize(m))

    return {
        "items": out,
        "total": len(out),
        "db_total": len(rows),
        "baseline_count": pm.baseline_count(),
    }


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_model(
    body: PhoneModelCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    key = (body.spec_key or "").strip().upper() or pm.normalize_key(body.display_name)
    if not key:
        raise HTTPException(400, "Geçerli bir model adı gir (anahtar üretilemedi)")

    existing = db.scalar(
        select(PhoneModel).where(
            PhoneModel.tenant_id == user.tenant_id,
            PhoneModel.spec_key == key,
        )
    )
    if existing:
        raise HTTPException(
            409,
            f"Bu model anahtarı zaten var: '{key}'. Düzenlemek için mevcut kaydı kullan.",
        )

    m = PhoneModel(
        tenant_id=user.tenant_id,
        spec_key=key,
        display_name=body.display_name.strip(),
        brand=(body.brand or "").strip() or None,
        width_cm=body.width_cm,
        height_cm=body.height_cm,
        radius_cm=body.radius_cm,
        notes=body.notes,
        is_active=True,
    )
    db.add(m)
    db.commit()
    db.refresh(m)

    # baseline'da da var mıydı → override bilgisi
    overrides_baseline = cd.get_spec(body.display_name) is not None

    res = _serialize(m)
    res["overrides_baseline"] = overrides_baseline
    return res


@router.patch("/{model_id}", response_model=dict)
def update_model(
    model_id: uuid.UUID,
    body: PhoneModelUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    m = db.scalar(
        select(PhoneModel).where(
            PhoneModel.id == model_id,
            PhoneModel.tenant_id == user.tenant_id,
        )
    )
    if not m:
        raise HTTPException(404, "Model bulunamadı")

    if body.display_name is not None:
        m.display_name = body.display_name.strip()
    if body.brand is not None:
        m.brand = body.brand.strip() or None
    if body.width_cm is not None:
        m.width_cm = body.width_cm
    if body.height_cm is not None:
        m.height_cm = body.height_cm
    if body.radius_cm is not None:
        m.radius_cm = body.radius_cm
    if body.is_active is not None:
        m.is_active = body.is_active
    if body.notes is not None:
        m.notes = body.notes

    db.commit()
    db.refresh(m)
    return _serialize(m)


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model(
    model_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    m = db.scalar(
        select(PhoneModel).where(
            PhoneModel.id == model_id,
            PhoneModel.tenant_id == user.tenant_id,
        )
    )
    if not m:
        raise HTTPException(404, "Model bulunamadı")
    db.delete(m)
    db.commit()
    return None


@router.post("/check", response_model=dict)
def check_model(
    body: CheckRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Model tanınıyor mu? Kaynağı söyler ama BASELINE ölçüsünü vermez."""
    source = pm.resolve_source(db, user.tenant_id, body.model)
    res = {
        "model": body.model,
        "normalized_key": pm.normalize_key(body.model),
        "recognized": source is not None,
        "source": source,  # 'db' | 'baseline' | None
    }
    # Sadece DB kaynaklıysa ölçü göster (tenant'ın kendi verisi)
    if source == "db":
        spec = pm.get_spec(db, user.tenant_id, body.model)
        if spec:
            res["width_cm"], res["height_cm"], res["radius_cm"] = spec
    return res
