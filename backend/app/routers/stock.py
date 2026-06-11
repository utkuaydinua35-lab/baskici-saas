"""
Stok Yönetimi — /api/stock/*

- GET    /api/stock                  → liste (kategori/arama/düşük-stok filtre)
- POST   /api/stock                  → kalem ekle
- PATCH  /api/stock/{id}             → kalem güncelle
- DELETE /api/stock/{id}             → kalem sil
- POST   /api/stock/{id}/adjust      → manuel giriş/çıkış (+/- delta, hareket kaydı)
- GET    /api/stock/{id}/movements   → hareket geçmişi
- GET    /api/stock/_meta            → kategori + varyasyon önerileri
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import StockItem, StockMovement, StockGroup, Order, LineItem, User
from app.services import stock as stock_svc

router = APIRouter(prefix="/api/stock", tags=["stock"])


# ─── Schemas ─────────────────────────────────────────────────
class StockItemCreate(BaseModel):
    sku: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    category: str = Field("bos_kilif", max_length=30)
    variation: str | None = Field(None, max_length=30)
    model: str | None = Field(None, max_length=100)
    quantity: int = Field(0, ge=0)
    low_stock_threshold: int = Field(0, ge=0)
    store_id: uuid.UUID | None = None
    product_id: str | None = Field(None, max_length=50)
    variant_id: str | None = Field(None, max_length=50)
    notes: str | None = None


class StockItemUpdate(BaseModel):
    sku: str | None = Field(None, max_length=100)
    name: str | None = Field(None, max_length=200)
    category: str | None = Field(None, max_length=30)
    variation: str | None = Field(None, max_length=30)
    model: str | None = Field(None, max_length=100)
    low_stock_threshold: int | None = Field(None, ge=0)
    store_id: uuid.UUID | None = None
    product_id: str | None = Field(None, max_length=50)
    variant_id: str | None = Field(None, max_length=50)
    notes: str | None = None
    is_active: bool | None = None


class AdjustRequest(BaseModel):
    delta: int
    reason: str = Field("manuel", max_length=40)
    note: str | None = None


# ─── Helpers ─────────────────────────────────────────────────
def _serialize(it: StockItem) -> dict:
    low = (it.low_stock_threshold or 0) > 0 and (it.quantity or 0) <= it.low_stock_threshold
    return {
        "id": str(it.id),
        "sku": it.sku,
        "name": it.name,
        "category": it.category,
        "variation": it.variation,
        "model": it.model,
        "quantity": it.quantity,
        "low_stock_threshold": it.low_stock_threshold,
        "is_low": low,
        "store_id": str(it.store_id) if it.store_id else None,
        "product_id": it.product_id,
        "variant_id": it.variant_id,
        "notes": it.notes,
        "is_active": it.is_active,
        "created_at": it.created_at.isoformat() if it.created_at else None,
        "updated_at": it.updated_at.isoformat() if it.updated_at else None,
    }


# ─── Endpoints ───────────────────────────────────────────────
@router.get("/_meta", response_model=dict)
def meta(user: User = Depends(get_current_user)):
    return {"categories": stock_svc.CATEGORIES, "variations": stock_svc.DEFAULT_VARIATIONS}


# ═══ ANA KALEM (StockGroup) — alt kalem (StockItem) hiyerarsisi ═══
class GroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    low_stock_threshold: int = Field(0, ge=0)
    notes: str | None = None


class GroupUpdate(BaseModel):
    name: str | None = Field(None, max_length=200)
    low_stock_threshold: int | None = Field(None, ge=0)
    notes: str | None = None
    is_active: bool | None = None
    linked_products: list | None = None


class GroupItemCreate(BaseModel):
    model: str = Field(..., min_length=1, max_length=100)
    variation: str | None = Field(None, max_length=30)
    quantity: int = Field(0, ge=0)
    low_stock_threshold: int | None = Field(None, ge=0)


def _serialize_group(g: StockGroup, items: list) -> dict:
    serialized_items = [_serialize(it) for it in items]
    toplam = sum((it.quantity or 0) for it in items)
    dusuk = [si for si in serialized_items if si["is_low"]]
    return {
        "id": str(g.id),
        "name": g.name,
        "linked_products": g.linked_products or [],
        "low_stock_threshold": g.low_stock_threshold,
        "notes": g.notes,
        "is_active": g.is_active,
        "toplam_stok": toplam,
        "item_count": len(items),
        "dusuk_count": len(dusuk),
        "items": serialized_items,
        "created_at": g.created_at.isoformat() if g.created_at else None,
    }


@router.get("/groups", response_model=dict)
def list_groups(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    groups = db.scalars(
        select(StockGroup).where(StockGroup.tenant_id == user.tenant_id)
        .order_by(StockGroup.name)
    ).all()
    out = []
    for g in groups:
        items = db.scalars(
            select(StockItem).where(StockItem.group_id == g.id, StockItem.is_active.is_(True))
            .order_by(StockItem.model)
        ).all()
        out.append(_serialize_group(g, items))
    return {"groups": out, "total": len(out)}


@router.post("/groups", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_group(body: GroupCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    exists = db.scalar(select(StockGroup).where(
        StockGroup.tenant_id == user.tenant_id, StockGroup.name == body.name.strip()))
    if exists:
        raise HTTPException(409, f"'{body.name}' adli ana kalem zaten var")
    g = StockGroup(
        tenant_id=user.tenant_id, name=body.name.strip(),
        low_stock_threshold=body.low_stock_threshold, notes=body.notes,
        linked_products=[],
    )
    db.add(g); db.commit(); db.refresh(g)
    return _serialize_group(g, [])


@router.patch("/groups/{group_id}", response_model=dict)
def update_group(group_id: uuid.UUID, body: GroupUpdate,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    g = db.scalar(select(StockGroup).where(
        StockGroup.id == group_id, StockGroup.tenant_id == user.tenant_id))
    if not g:
        raise HTTPException(404, "Ana kalem bulunamadi")
    data = body.model_dump(exclude_unset=True)
    if "name" in data and data["name"]:
        g.name = data["name"].strip()
    if "low_stock_threshold" in data and data["low_stock_threshold"] is not None:
        g.low_stock_threshold = data["low_stock_threshold"]
    if "notes" in data:
        g.notes = data["notes"]
    if "is_active" in data and data["is_active"] is not None:
        g.is_active = data["is_active"]
    if "linked_products" in data and data["linked_products"] is not None:
        g.linked_products = data["linked_products"]
    db.commit(); db.refresh(g)
    items = db.scalars(select(StockItem).where(
        StockItem.group_id == g.id, StockItem.is_active.is_(True)).order_by(StockItem.model)).all()
    return _serialize_group(g, items)


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(group_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    g = db.scalar(select(StockGroup).where(
        StockGroup.id == group_id, StockGroup.tenant_id == user.tenant_id))
    if not g:
        raise HTTPException(404, "Ana kalem bulunamadi")
    db.delete(g); db.commit()


@router.post("/groups/{group_id}/items", response_model=dict, status_code=status.HTTP_201_CREATED)
def add_group_item(group_id: uuid.UUID, body: GroupItemCreate,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    g = db.scalar(select(StockGroup).where(
        StockGroup.id == group_id, StockGroup.tenant_id == user.tenant_id))
    if not g:
        raise HTTPException(404, "Ana kalem bulunamadi")
    # Ayni grup + model + varyasyon zaten var mi?
    _var = (body.variation or "").strip() or None
    dup = db.scalar(select(StockItem).where(
        StockItem.group_id == g.id, StockItem.model == body.model.strip(),
        StockItem.variation.is_(None) if _var is None else (StockItem.variation == _var),
        StockItem.is_active.is_(True)))
    if dup:
        raise HTTPException(409, f"'{body.model}' modeli bu ana kalemde zaten var")
    # benzersiz sku uret
    import re as _re
    base_sku = _re.sub(r"[^A-Za-z0-9]+", "-", f"{g.name}-{body.model}-{_var or 'std'}").strip("-").upper()[:90]
    sku = base_sku
    n = 1
    while db.scalar(select(StockItem).where(StockItem.tenant_id == user.tenant_id, StockItem.sku == sku)):
        n += 1; sku = f"{base_sku}-{n}"[:100]
    it = StockItem(
        tenant_id=user.tenant_id, group_id=g.id,
        sku=sku, name=f"{g.name} · {body.model}", category="bos_kilif",
        variation=_var, model=body.model.strip(),
        quantity=body.quantity,
        low_stock_threshold=body.low_stock_threshold if body.low_stock_threshold is not None else (g.low_stock_threshold or 0),
    )
    db.add(it); db.commit(); db.refresh(it)
    return _serialize(it)


@router.get("/groups/_assignable-products", response_model=dict)
def assignable_products(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Ana kaleme baglanabilir Shopify urunleri (siparislerden cikarilan benzersiz urun listesi)."""
    rows = db.execute(
        select(LineItem.product_id, LineItem.title, Order.store_id)
        .join(Order, LineItem.order_id == Order.id)
        .where(Order.tenant_id == user.tenant_id, LineItem.product_id.isnot(None))
        .distinct()
        .limit(1000)
    ).all()
    seen = {}
    for pid, title, store_id in rows:
        if pid and pid not in seen:
            seen[pid] = {"product_id": str(pid), "title": title or "", "store_id": str(store_id) if store_id else None}
    return {"products": list(seen.values()), "total": len(seen)}


@router.get("", response_model=dict)
def list_items(
    category: str | None = Query(None),
    search: str | None = Query(None),
    low_only: bool = Query(False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = select(StockItem).where(StockItem.tenant_id == user.tenant_id)
    if category:
        q = q.where(StockItem.category == category)
    items = db.scalars(q.order_by(desc(StockItem.created_at))).all()

    out = []
    low_count = 0
    total_qty = 0
    for it in items:
        ser = _serialize(it)
        total_qty += it.quantity or 0
        if ser["is_low"]:
            low_count += 1
        if low_only and not ser["is_low"]:
            continue
        if search:
            ql = search.lower()
            hay = " ".join(filter(None, [it.sku, it.name, it.variation, it.model, it.notes])).lower()
            if ql not in hay:
                continue
        out.append(ser)

    return {
        "items": out,
        "total": len(out),
        "all_total": len(items),
        "low_count": low_count,
        "total_quantity": total_qty,
    }


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_item(
    body: StockItemCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.category not in stock_svc.CATEGORIES:
        raise HTTPException(400, f"Geçersiz kategori: {body.category}")
    existing = db.scalar(select(StockItem).where(
        StockItem.tenant_id == user.tenant_id, StockItem.sku == body.sku
    ))
    if existing:
        raise HTTPException(409, f"Bu stok kodu zaten var: '{body.sku}'")

    it = StockItem(
        tenant_id=user.tenant_id,
        sku=body.sku.strip(),
        name=body.name.strip(),
        category=body.category,
        variation=(body.variation or "").strip() or None,
        model=(body.model or "").strip() or None,
        quantity=body.quantity,
        low_stock_threshold=body.low_stock_threshold,
        store_id=body.store_id,
        product_id=(body.product_id or "").strip() or None,
        variant_id=(body.variant_id or "").strip() or None,
        notes=body.notes,
        is_active=True,
    )
    db.add(it)
    db.flush()
    if body.quantity:
        stock_svc.apply_adjustment(db, it, body.quantity, "ilk_giris",
                                   note="Kalem oluşturuldu", created_by=user.email)
    db.commit()
    db.refresh(it)
    return _serialize(it)


@router.patch("/{item_id}", response_model=dict)
def update_item(
    item_id: uuid.UUID,
    body: StockItemUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    it = db.scalar(select(StockItem).where(
        StockItem.id == item_id, StockItem.tenant_id == user.tenant_id
    ))
    if not it:
        raise HTTPException(404, "Stok kalemi bulunamadı")

    if body.category is not None and body.category not in stock_svc.CATEGORIES:
        raise HTTPException(400, f"Geçersiz kategori: {body.category}")
    if body.sku is not None and body.sku.strip() != it.sku:
        dup = db.scalar(select(StockItem).where(
            StockItem.tenant_id == user.tenant_id, StockItem.sku == body.sku.strip()
        ))
        if dup:
            raise HTTPException(409, f"Bu stok kodu zaten var: '{body.sku}'")
        it.sku = body.sku.strip()

    if body.name is not None:
        it.name = body.name.strip()
    if body.category is not None:
        it.category = body.category
    if body.variation is not None:
        it.variation = body.variation.strip() or None
    if body.model is not None:
        it.model = body.model.strip() or None
    if body.low_stock_threshold is not None:
        it.low_stock_threshold = body.low_stock_threshold
    if body.store_id is not None:
        it.store_id = body.store_id
    if body.product_id is not None:
        it.product_id = body.product_id.strip() or None
    if body.variant_id is not None:
        it.variant_id = body.variant_id.strip() or None
    if body.notes is not None:
        it.notes = body.notes
    if body.is_active is not None:
        it.is_active = body.is_active

    db.commit()
    db.refresh(it)
    return _serialize(it)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    item_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    it = db.scalar(select(StockItem).where(
        StockItem.id == item_id, StockItem.tenant_id == user.tenant_id
    ))
    if not it:
        raise HTTPException(404, "Stok kalemi bulunamadı")
    db.delete(it)
    db.commit()
    return None


@router.post("/{item_id}/adjust", response_model=dict)
def adjust_item(
    item_id: uuid.UUID,
    body: AdjustRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    it = db.scalar(select(StockItem).where(
        StockItem.id == item_id, StockItem.tenant_id == user.tenant_id
    ))
    if not it:
        raise HTTPException(404, "Stok kalemi bulunamadı")
    if body.delta == 0:
        raise HTTPException(400, "Değişim 0 olamaz")
    if (it.quantity or 0) + body.delta < 0:
        raise HTTPException(400, f"Stok eksiye düşemez (mevcut: {it.quantity})")

    reason = body.reason or ("manuel_giris" if body.delta > 0 else "manuel_cikis")
    stock_svc.apply_adjustment(db, it, body.delta, reason, note=body.note, created_by=user.email)
    db.commit()
    db.refresh(it)
    return _serialize(it)


@router.get("/{item_id}/movements", response_model=dict)
def movements(
    item_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    it = db.scalar(select(StockItem).where(
        StockItem.id == item_id, StockItem.tenant_id == user.tenant_id
    ))
    if not it:
        raise HTTPException(404, "Stok kalemi bulunamadı")
    rows = db.scalars(
        select(StockMovement)
        .where(StockMovement.stock_item_id == item_id)
        .order_by(desc(StockMovement.created_at))
        .limit(limit)
    ).all()
    return {
        "items": [
            {
                "id": str(m.id),
                "delta": m.delta,
                "balance_after": m.balance_after,
                "reason": m.reason,
                "ref_mold_id": str(m.ref_mold_id) if m.ref_mold_id else None,
                "ref_order_id": str(m.ref_order_id) if m.ref_order_id else None,
                "note": m.note,
                "created_by": m.created_by,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in rows
        ]
    }
