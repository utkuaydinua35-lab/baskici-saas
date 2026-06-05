"""
Askıda Kontrolü — /api/aski/*

"Askıda" = hatalı üretilip dükkanda hazır bekleyen, yeniden üretilmeden gönderim
yapılabilen ürünler. Eşleşme: design_id + model (variation opsiyonel).

Endpoint'ler:
- GET    /api/aski                       → liste
- POST   /api/aski                       → manuel ekle
- PATCH  /api/aski/{id}                  → güncelle (quantity, note)
- DELETE /api/aski/{id}                  → sil
- POST   /api/aski/from-line-item/{id}   → bir sipariş kalemini askıya at
- POST   /api/aski/check-orders          → açık siparişleri tara + otomatik karşıla
"""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import (
    AskiItem, Design, LineItem, Order, OrderStatusHistory, Store, User,
)
from app.services import storage

router = APIRouter(prefix="/api/aski", tags=["aski"])


# ─── Schemas ─────────────────────────────────────────────────
class AskiItemCreate(BaseModel):
    store_id: uuid.UUID
    design_id: uuid.UUID
    model: str
    variation: str | None = None
    quantity: int = 1
    note: str | None = None


class AskiItemUpdate(BaseModel):
    quantity: int | None = None
    note: str | None = None


# ─── Yardımcılar ─────────────────────────────────────────────
def _extract_model_for_aski(li: LineItem) -> str | None:
    """Line item'tan telefon modeli çıkar (Askı eşleşmesi için)."""
    if li.device_model_override:
        return li.device_model_override
    props = li.properties or []
    # Marka + "{Marka} Model" property kombinasyonu
    marka_prop = next(
        (p for p in props if isinstance(p, dict) and (p.get("name") or "").lower() == "marka"),
        None,
    )
    marka = marka_prop.get("value") if marka_prop else None
    if marka:
        for p in props:
            if isinstance(p, dict):
                name = (p.get("name") or "").lower()
                if name == f"{marka.lower()} model" or name.endswith(" model"):
                    val = p.get("value")
                    if val:
                        return f"{marka} {val}".strip()
    # Direct "Model" / "Telefon Modeli" / "Cihaz Modeli"
    for p in props:
        if isinstance(p, dict):
            name = (p.get("name") or "").lower()
            if name in ("model", "telefon modeli", "cihaz modeli"):
                val = p.get("value")
                if val:
                    return val
    # variant_title fallback
    if li.variant_title:
        return li.variant_title.split("/")[0].strip()
    return None


def _resolve_design_for_aski(li: LineItem, store_id, db: Session) -> Design | None:
    """Line item için Design çöz (assigned_design veya product_id eşlesi)."""
    if li.assigned_design_id:
        d = db.scalar(select(Design).where(Design.id == li.assigned_design_id))
        if d:
            return d
    if li.product_id:
        return db.scalar(
            select(Design)
            .where(Design.store_id == store_id, Design.product_id == li.product_id)
            .limit(1)
        )
    return None


def _try_aski_consume(db: Session, li: LineItem, tenant_id, store_id) -> AskiItem | None:
    """Bir line item için askıda eşleşme arar, varsa karşılar."""
    if li.is_kaliba_eklendi or li.is_hazir:
        return None
    design = _resolve_design_for_aski(li, store_id, db)
    if not design:
        return None
    model = _extract_model_for_aski(li)
    if not model:
        return None

    aski = db.scalar(
        select(AskiItem)
        .where(
            AskiItem.tenant_id == tenant_id,
            AskiItem.store_id == store_id,
            AskiItem.design_id == design.id,
            AskiItem.model == model,
            AskiItem.quantity > 0,
        )
        .order_by(AskiItem.created_at)
        .limit(1)
    )
    if not aski:
        return None

    aski.quantity -= 1
    li.is_hazir = True
    li.is_kaliba_eklendi = True

    db.add(OrderStatusHistory(
        tenant_id=tenant_id,
        order_id=li.order_id,
        from_stage=None, to_stage=None,
        action="askidan_karsilandi",
        note=f"Askıdan karşılandı: {design.code} · {model}",
        created_by=None,
    ))
    return aski


def _serialize_aski(item: AskiItem, dmap: dict | None = None) -> dict:
    d = dmap.get(item.design_id) if dmap else None
    return {
        "id": str(item.id),
        "store_id": str(item.store_id),
        "design_id": str(item.design_id),
        "design_code": d.code if d else None,
        "design_name": d.name if d else None,
        "design_thumbnail_url": (
            storage.get_thumbnail_url(d.file_path, d.file_format)
            if d and d.file_path else None
        ),
        "model": item.model,
        "variation": item.variation,
        "quantity": item.quantity,
        "note": item.note,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


# ─── Endpoints ───────────────────────────────────────────────
@router.get("", response_model=dict)
def list_aski(
    store_id: uuid.UUID | None = Query(None),
    search: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = select(AskiItem).where(AskiItem.tenant_id == user.tenant_id)
    if store_id:
        q = q.where(AskiItem.store_id == store_id)
    items = db.scalars(q.order_by(desc(AskiItem.created_at))).all()

    design_ids = {it.design_id for it in items}
    dmap: dict = {}
    if design_ids:
        for d in db.scalars(select(Design).where(Design.id.in_(design_ids))).all():
            dmap[d.id] = d

    out = []
    for it in items:
        d = dmap.get(it.design_id)
        if search:
            q_lower = search.lower()
            haystack = " ".join(filter(None, [
                d.code if d else None,
                d.name if d else None,
                it.model,
                it.variation,
                it.note,
            ])).lower()
            if q_lower not in haystack:
                continue
        out.append(_serialize_aski(it, dmap))

    total_qty = sum(it.quantity for it in items)
    return {"items": out, "total": len(out), "total_quantity": total_qty}


@router.post("", response_model=dict)
def create_aski(
    body: AskiItemCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manuel olarak askıya ürün ekle. Aynı (design+model+variation) varsa quantity artırır."""
    store = db.scalar(select(Store).where(
        Store.id == body.store_id, Store.tenant_id == user.tenant_id
    ))
    if not store:
        raise HTTPException(404, "Mağaza bulunamadı")

    design = db.scalar(select(Design).where(
        Design.id == body.design_id,
        Design.store_id == body.store_id,
        Design.tenant_id == user.tenant_id,
    ))
    if not design:
        raise HTTPException(404, "Tasarım bulunamadı")

    from app.services._private import case_dimensions as cd
    if not cd.has_spec(body.model):
        raise HTTPException(400, f"Model tanınmadı: '{body.model}'")

    if body.quantity < 1:
        raise HTTPException(400, "Miktar en az 1 olmalı")

    existing = db.scalar(select(AskiItem).where(
        AskiItem.tenant_id == user.tenant_id,
        AskiItem.store_id == body.store_id,
        AskiItem.design_id == body.design_id,
        AskiItem.model == body.model,
        AskiItem.variation == body.variation,
    ))

    if existing:
        existing.quantity += body.quantity
        if body.note:
            existing.note = (existing.note + "\n" + body.note) if existing.note else body.note
        aski = existing
    else:
        aski = AskiItem(
            tenant_id=user.tenant_id,
            store_id=body.store_id,
            design_id=body.design_id,
            model=body.model,
            variation=body.variation,
            quantity=body.quantity,
            note=body.note,
        )
        db.add(aski)

    db.flush()
    db.commit()
    db.refresh(aski)
    return _serialize_aski(aski, {design.id: design})


@router.patch("/{aski_id}", response_model=dict)
def update_aski(
    aski_id: uuid.UUID,
    body: AskiItemUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    aski = db.scalar(select(AskiItem).where(
        AskiItem.id == aski_id, AskiItem.tenant_id == user.tenant_id
    ))
    if not aski:
        raise HTTPException(404, "Askı kaydı bulunamadı")

    if body.quantity is not None:
        if body.quantity < 0:
            raise HTTPException(400, "Miktar 0'dan küçük olamaz")
        aski.quantity = body.quantity
    if body.note is not None:
        aski.note = body.note

    db.commit()
    design = db.scalar(select(Design).where(Design.id == aski.design_id))
    return _serialize_aski(aski, {aski.design_id: design} if design else None)


@router.delete("/{aski_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_aski(
    aski_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    aski = db.scalar(select(AskiItem).where(
        AskiItem.id == aski_id, AskiItem.tenant_id == user.tenant_id
    ))
    if not aski:
        raise HTTPException(404, "Askı kaydı bulunamadı")
    db.delete(aski)
    db.commit()
    return None


@router.post("/from-line-item/{line_item_id}", response_model=dict)
def from_line_item(
    line_item_id: uuid.UUID,
    quantity: int = Query(1, ge=1),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bir sipariş kalemini askıya at (hatalı üretildi, stokta bekliyor)."""
    li = db.scalar(
        select(LineItem)
        .join(Order, LineItem.order_id == Order.id)
        .where(LineItem.id == line_item_id, Order.tenant_id == user.tenant_id)
        .options(selectinload(LineItem.order))
    )
    if not li:
        raise HTTPException(404, "Sipariş kalemi bulunamadı")

    design = _resolve_design_for_aski(li, li.order.store_id, db)
    if not design:
        raise HTTPException(400, "Bu kalem için tasarım bulunamadı")
    model = _extract_model_for_aski(li)
    if not model:
        raise HTTPException(400, "Bu kalem için telefon modeli belirlenemedi")

    existing = db.scalar(select(AskiItem).where(
        AskiItem.tenant_id == user.tenant_id,
        AskiItem.store_id == li.order.store_id,
        AskiItem.design_id == design.id,
        AskiItem.model == model,
        AskiItem.variation == li.birincil_renk,
    ))
    if existing:
        existing.quantity += quantity
        aski = existing
    else:
        aski = AskiItem(
            tenant_id=user.tenant_id,
            store_id=li.order.store_id,
            design_id=design.id,
            model=model,
            variation=li.birincil_renk,
            quantity=quantity,
            note=f"Sipariş #{li.order.order_number}'dan askıya alındı",
            source_line_item_id=li.id,
        )
        db.add(aski)

    db.commit()
    db.refresh(aski)
    return {
        "ok": True,
        "aski_id": str(aski.id),
        "quantity": aski.quantity,
        "message": f"{design.code} · {model} askıya eklendi (toplam: {aski.quantity})",
    }


@router.post("/check-orders", response_model=dict)
def check_open_orders(
    store_id: uuid.UUID | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Açık siparişlerin line item'larını askıda eşleşme için tara, eşleşenleri otomatik karşıla."""
    q = (
        select(Order)
        .where(
            Order.tenant_id == user.tenant_id,
            Order.cancelled_at.is_(None),
            (Order.fulfillment_status != "fulfilled") | (Order.fulfillment_status.is_(None)),
        )
        .options(selectinload(Order.line_items))
    )
    if store_id:
        q = q.where(Order.store_id == store_id)

    orders = db.scalars(q).all()
    matched = []

    for o in orders:
        for li in o.line_items:
            consumed = _try_aski_consume(db, li, user.tenant_id, o.store_id)
            if consumed:
                matched.append({
                    "order_number": o.order_number,
                    "model": consumed.model,
                })

    db.commit()
    return {
        "ok": True,
        "matched_count": len(matched),
        "matched": matched[:50],
        "message": f"{len(matched)} kalem askıdan karşılandı.",
    }
