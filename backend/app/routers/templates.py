"""Kalıp şablonu — /api/templates/* (PDF yükle, kutu koordinatlarını oku)"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import MoldTemplate, User
from app.services import storage, template_parser

router = APIRouter(prefix="/api/templates", tags=["templates"])


def _serialize(t: MoldTemplate) -> dict:
    return {
        "id": str(t.id),
        "name": t.name,
        "page_w_pt": t.page_w_pt, "page_h_pt": t.page_h_pt,
        "page_w_cm": round(t.page_w_pt / 28.3464567, 2) if t.page_w_pt else 0,
        "page_h_cm": round(t.page_h_pt / 28.3464567, 2) if t.page_h_pt else 0,
        "cols": t.cols, "rows": t.rows, "box_count": t.box_count,
        "boxes": t.boxes, "is_active": t.is_active,
        "has_file": bool(t.file_path),
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if getattr(t, "updated_at", None) else None,
    }


@router.get("", response_model=None)
def get_template(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Tenant'ın aktif kalıp şablonu (yoksa null)."""
    t = db.scalar(
        select(MoldTemplate).where(MoldTemplate.tenant_id == user.tenant_id, MoldTemplate.is_active == True)  # noqa: E712
        .order_by(MoldTemplate.created_at.desc())
    )
    return _serialize(t) if t else None


@router.post("/upload", response_model=None)
async def upload_template(
    file: UploadFile = File(...),
    name: str = Query("Varsayılan Kalıp"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Şablon PDF yükle, kutu koordinatlarını otomatik çıkar ve kaydet."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Sadece PDF şablon kabul edilir")
    data = await file.read()
    if len(data) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Dosya çok büyük (max 50MB)")

    try:
        parsed = template_parser.parse_template(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Şablon okunamadı: {e}")

    if parsed["box_count"] == 0:
        raise HTTPException(status_code=400, detail="Şablonda kutu bulunamadı")

    # Şablon PDF'ini sakla (tenant klasörüne)
    storage.ensure_storage_root()
    rel_dir = f"tenants/{user.tenant_id}/templates"
    (storage.STORAGE_ROOT / rel_dir).mkdir(parents=True, exist_ok=True)
    tid = uuid.uuid4()
    rel_path = f"{rel_dir}/{tid}.pdf"
    (storage.STORAGE_ROOT / rel_path).write_bytes(data)

    # Eski aktif şablonları pasifleştir
    for old in db.scalars(select(MoldTemplate).where(
        MoldTemplate.tenant_id == user.tenant_id, MoldTemplate.is_active == True)).all():  # noqa: E712
        old.is_active = False

    t = MoldTemplate(
        id=tid, tenant_id=user.tenant_id, name=name, file_path=rel_path,
        page_w_pt=parsed["page_w_pt"], page_h_pt=parsed["page_h_pt"],
        cols=parsed["cols"], rows=parsed["rows"],
        box_count=parsed["box_count"], boxes=parsed["boxes"], is_active=True,
    )
    db.add(t)
    db.commit()
    return _serialize(t)
