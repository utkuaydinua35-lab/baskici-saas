"""
Kısayollar yönetimi — /api/shortcuts/*

Endpoint'ler:
- GET    /api/shortcuts?store_id=...   → mağazaya ait kısayollar
- POST   /api/shortcuts                → tek kısayol ekle
- PATCH  /api/shortcuts/{id}           → güncelle
- DELETE /api/shortcuts/{id}           → sil
- POST   /api/shortcuts/import         → JSON dosyasından toplu import
- POST   /api/shortcuts/bulk-delete    → çoklu silme
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Shortcut, Store, User
from app.services.pipeline_helpers import clean_kisayollar_dict, normalize_text

router = APIRouter(prefix="/api/shortcuts", tags=["shortcuts"])


# ─── Schemas ─────────────────────────────────────────────────

class ShortcutCreate(BaseModel):
    store_id: uuid.UUID
    key: str = Field(..., min_length=1, max_length=200)
    value: str = Field(..., min_length=1)


class ShortcutUpdate(BaseModel):
    key: str | None = Field(None, min_length=1, max_length=200)
    value: str | None = Field(None, min_length=1)


class ShortcutResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    store_id: uuid.UUID
    key: str
    value: str
    created_at: datetime
    updated_at: datetime

    # Hangi tipte olduğunu UI'da gösterelim
    @property
    def kind(self) -> str:
        v_upper = self.value.upper()
        if v_upper.startswith("COUPLE::"):
            return "couple"
        if v_upper.startswith("VARIANT::"):
            return "variant"
        if "|" in self.value:
            return "color"
        return "simple"


class ImportRequest(BaseModel):
    store_id: uuid.UUID
    data: dict[str, Any]                    # raw JSON içerik
    mode: str = Field("merge", pattern="^(merge|replace)$")
    # merge: mevcut kısayolların üstüne yaz, ekle
    # replace: önce hepsini sil, sonra ekle


class ImportResponse(BaseModel):
    success: bool
    added: int
    updated: int
    skipped: int
    total_after: int
    message: str


class BulkDeleteRequest(BaseModel):
    ids: list[uuid.UUID]


# ─── Helpers ─────────────────────────────────────────────────

def _ensure_store_belongs_to_tenant(db: Session, store_id: uuid.UUID, tenant_id: uuid.UUID) -> Store:
    store = db.scalar(
        select(Store).where(Store.id == store_id, Store.tenant_id == tenant_id)
    )
    if not store:
        raise HTTPException(status_code=404, detail="Mağaza bulunamadı")
    return store


def _serialize(s: Shortcut) -> dict:
    """Shortcut ORM → response dict + 'kind' alanı."""
    v_upper = s.value.upper()
    if v_upper.startswith("COUPLE::"):
        kind = "couple"
    elif v_upper.startswith("VARIANT::"):
        kind = "variant"
    elif "|" in s.value:
        kind = "color"
    else:
        kind = "simple"

    return {
        "id": str(s.id),
        "store_id": str(s.store_id),
        "key": s.key,
        "value": s.value,
        "kind": kind,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


# ─── Endpoints ───────────────────────────────────────────────

@router.get("", response_model=None)
def list_shortcuts(
    store_id: uuid.UUID = Query(...),
    search: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mağazaya ait kısayollar (search ile filtrelenebilir)."""
    _ensure_store_belongs_to_tenant(db, store_id, user.tenant_id)

    q = select(Shortcut).where(Shortcut.store_id == store_id)
    if search:
        like = f"%{search.lower()}%"
        q = q.where((Shortcut.key.ilike(like)) | (Shortcut.value.ilike(like)))
    q = q.order_by(Shortcut.key)

    rows = db.scalars(q).all()
    return [_serialize(s) for s in rows]


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_shortcut(
    req: ShortcutCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Tek bir kısayol ekle. Key otomatik normalize edilir."""
    _ensure_store_belongs_to_tenant(db, req.store_id, user.tenant_id)

    normalized_key = normalize_text(req.key)
    if not normalized_key:
        raise HTTPException(status_code=400, detail="Geçersiz anahtar")

    shortcut = Shortcut(
        tenant_id=user.tenant_id,
        store_id=req.store_id,
        key=normalized_key,
        value=req.value.strip(),
    )
    db.add(shortcut)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Bu anahtar zaten kayıtlı: {normalized_key}",
        ) from e

    db.refresh(shortcut)
    return _serialize(shortcut)


@router.patch("/{shortcut_id}", response_model=dict)
def update_shortcut(
    shortcut_id: uuid.UUID,
    req: ShortcutUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    shortcut = db.scalar(
        select(Shortcut).where(
            Shortcut.id == shortcut_id,
            Shortcut.tenant_id == user.tenant_id,
        )
    )
    if not shortcut:
        raise HTTPException(status_code=404, detail="Kısayol bulunamadı")

    if req.key is not None:
        new_key = normalize_text(req.key)
        if not new_key:
            raise HTTPException(status_code=400, detail="Geçersiz anahtar")
        shortcut.key = new_key
    if req.value is not None:
        shortcut.value = req.value.strip()

    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail="Bu anahtar zaten kayıtlı") from e

    db.refresh(shortcut)
    return _serialize(shortcut)


@router.delete("/{shortcut_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shortcut(
    shortcut_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    shortcut = db.scalar(
        select(Shortcut).where(
            Shortcut.id == shortcut_id,
            Shortcut.tenant_id == user.tenant_id,
        )
    )
    if not shortcut:
        raise HTTPException(status_code=404, detail="Kısayol bulunamadı")
    db.delete(shortcut)
    db.commit()
    return None


@router.post("/bulk-delete", response_model=dict)
def bulk_delete(
    req: BulkDeleteRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Çoklu silme — tablo görünümünde checkbox ile kullanım için."""
    if not req.ids:
        return {"deleted": 0}

    result = db.execute(
        Shortcut.__table__.delete().where(
            Shortcut.id.in_(req.ids),
            Shortcut.tenant_id == user.tenant_id,
        )
    )
    db.commit()
    return {"deleted": result.rowcount}


@router.post("/import", response_model=ImportResponse)
def import_shortcuts(
    req: ImportRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    BERNZ'in eski JSON formatından toplu import:
        {
            "design name normalized": "B580",
            "another design": "B580|siyah",
            "couple design": "COUPLE::d1|siyah::d2|beyaz",
            "_meta_note": "Bu kayıt atlanır",
            ...
        }

    mode:
      - merge   → mevcut anahtarları günceller, yenilerini ekler
      - replace → önce mağazanın TÜM kısayollarını siler, sonra ekler
    """
    store = _ensure_store_belongs_to_tenant(db, req.store_id, user.tenant_id)

    # JSON'u temizle (combining dot, meta key'ler vs.)
    clean = clean_kisayollar_dict(req.data)
    if not clean:
        raise HTTPException(
            status_code=400,
            detail="Geçerli kısayol bulunamadı (boş veya sadece _ ile başlayan key'ler)",
        )

    if req.mode == "replace":
        deleted = db.execute(
            Shortcut.__table__.delete().where(Shortcut.store_id == store.id)
        ).rowcount
    else:
        deleted = 0

    # PostgreSQL ON CONFLICT — merge için tek SQL ile upsert
    values = [
        {
            "tenant_id": user.tenant_id,
            "store_id": store.id,
            "key": k,
            "value": v.strip() if isinstance(v, str) else str(v),
        }
        for k, v in clean.items()
    ]

    # Mevcut sayı (sonra delta hesaplamak için)
    before_count = db.scalar(
        select(__import__("sqlalchemy").func.count(Shortcut.id)).where(
            Shortcut.store_id == store.id
        )
    ) or 0

    added = 0
    updated = 0
    skipped = 0

    stmt = pg_insert(Shortcut).values(values)
    # ON CONFLICT (store_id, key) DO UPDATE SET value = EXCLUDED.value
    stmt = stmt.on_conflict_do_update(
        constraint="uq_shortcut_store_key",
        set_={"value": stmt.excluded.value, "updated_at": __import__("sqlalchemy").func.now()},
    )

    try:
        db.execute(stmt)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Import hatası: {str(e)[:200]}",
        ) from e

    after_count = db.scalar(
        select(__import__("sqlalchemy").func.count(Shortcut.id)).where(
            Shortcut.store_id == store.id
        )
    ) or 0

    added = max(0, after_count - before_count)
    updated = max(0, len(values) - added)

    msg_parts = []
    if req.mode == "replace":
        msg_parts.append(f"{deleted} mevcut kayıt silindi")
    if added:
        msg_parts.append(f"{added} yeni eklendi")
    if updated and req.mode == "merge":
        msg_parts.append(f"{updated} güncellendi")
    if skipped:
        msg_parts.append(f"{skipped} atlandı")

    return ImportResponse(
        success=True,
        added=added,
        updated=updated,
        skipped=skipped,
        total_after=after_count,
        message=" · ".join(msg_parts) or f"{added + updated} kısayol işlendi",
    )


@router.get("/_stats", response_model=dict)
def stats(
    store_id: uuid.UUID = Query(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mağaza kısayollarının özet sayıları."""
    _ensure_store_belongs_to_tenant(db, store_id, user.tenant_id)

    from sqlalchemy import case, func as sql_func

    total = db.scalar(
        select(sql_func.count(Shortcut.id)).where(Shortcut.store_id == store_id)
    ) or 0

    # Tip bazlı sayı
    rows = db.execute(
        select(
            sql_func.count(Shortcut.id),
            case(
                (Shortcut.value.ilike("COUPLE::%"), "couple"),
                (Shortcut.value.ilike("VARIANT::%"), "variant"),
                (Shortcut.value.ilike("%|%"), "color"),
                else_="simple",
            ).label("kind"),
        )
        .where(Shortcut.store_id == store_id)
        .group_by("kind")
    ).all()

    by_kind = {row[1]: row[0] for row in rows}

    return {
        "total": total,
        "by_kind": by_kind,
    }
