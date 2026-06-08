"""
Paketleme — /api/packaging/*

- GET  /api/packaging/order/{order_ref}            → sipariş + aksesuar eşleşme önerileri
- POST /api/packaging/order/{order_ref}/complete   → düşümleri uygula + stage 7
- GET  /api/packaging/order/{order_ref}/label      → kargo etiketi PDF
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Design, LineItem, MoldItem, Order, OrderStatusHistory, Store, User
from app.services import label_pdf, packaging as pkg, storage
from app import stages as stage_defs

router = APIRouter(prefix="/api/packaging", tags=["packaging"])


def _resolve_order(db: Session, ref: str, tenant_id) -> Order:
    q = select(Order).where(Order.tenant_id == tenant_id).options(
        selectinload(Order.line_items)
    )
    order = None
    try:
        oid = uuid.UUID(str(ref))
        order = db.scalar(q.where(Order.id == oid))
    except (ValueError, AttributeError):
        order = None
    if not order:
        order = db.scalar(
            q.where((Order.order_number == ref) | (Order.name == ref))
            .order_by(desc(Order.created_at))
        )
    if not order:
        raise HTTPException(404, "Sipariş bulunamadı")
    return order


def _store_name(db: Session, order: Order) -> str | None:
    if not order.store_id:
        return None
    s = db.scalar(select(Store).where(Store.id == order.store_id))
    return s.name if s else None


class Deduction(BaseModel):
    stock_item_id: uuid.UUID
    quantity: int = 1


class CompleteRequest(BaseModel):
    deductions: list[Deduction] = []
    note: str | None = None


@router.get("/order/{order_ref}", response_model=dict)
def get_order(
    order_ref: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = _resolve_order(db, order_ref, user.tenant_id)
    return {
        "order": {
            "id": str(order.id),
            "order_number": order.order_number,
            "name": order.name,
            "customer_name": order.customer_name,
            "current_stage": order.current_stage,
            "barkod_kodu": order.barkod_kodu,
            "store_name": _store_name(db, order),
        },
        "is_packaged": pkg.is_packaged(db, user.tenant_id, order),
        "suggestions": pkg.suggest_for_order(db, user.tenant_id, order),
    }


@router.post("/order/{order_ref}/complete", response_model=dict)
def complete(
    order_ref: str,
    body: CompleteRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = _resolve_order(db, order_ref, user.tenant_id)
    deductions = [{"stock_item_id": d.stock_item_id, "quantity": d.quantity} for d in body.deductions]
    result = pkg.complete_packaging(db, user.tenant_id, order, deductions, user)

    if result["stage_changed"]:
        db.add(OrderStatusHistory(
            tenant_id=order.tenant_id,
            order_id=order.id,
            from_stage=None,
            to_stage=7,
            action="paketlendi",
            note=body.note or f"Paketlendi · {result['deducted']} stok düşüldü",
            created_by=user.full_name or user.email,
        ))

    db.commit()
    return result


@router.get("/order/{order_ref}/label")
def label(
    order_ref: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = _resolve_order(db, order_ref, user.tenant_id)
    pdf = label_pdf.render_label_pdf(order, _store_name(db, order))
    filename = f"etiket_{order.order_number or order.id}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ─── Paketleme Kuyrugu (Paket: paketleme yeniden tasarim) ─────────────
def _queue_filter(tenant_id):
    """Acik (gonderilmemis, iptal olmayan) siparisler."""
    return (
        (Order.tenant_id == tenant_id)
        & (Order.is_iptal == False)  # noqa: E712
        & (or_(Order.fulfillment_status.is_(None), Order.fulfillment_status != "fulfilled"))
    )


def _addr(raw: dict) -> dict:
    sa = (raw.get("shipping_address") or {})
    lines = raw.get("shipping_lines") or []
    kargo = (lines[0].get("title") if lines else None) or None
    a1 = sa.get("address1") or ""
    a2 = sa.get("address2") or ""
    full_addr = (a1 + (" " + a2 if a2 else "")).strip() or None
    return {
        "address": full_addr,
        "district": sa.get("city") or None,     # ilce
        "province": sa.get("province") or None,  # il
        "phone": sa.get("phone") or raw.get("phone") or None,
        "kargo_sirketi": kargo,
    }


def _design_for_line_item(db, order, li, mi):
    """Gorsel cozumleme: MoldItem.design -> assigned_design -> product_id eslesme."""
    d = None
    if mi and mi.design_id:
        d = db.scalar(select(Design).where(Design.id == mi.design_id))
    if not d and li.assigned_design_id:
        d = db.scalar(select(Design).where(Design.id == li.assigned_design_id))
    if not d and li.product_id:
        d = db.scalar(
            select(Design).where(
                Design.store_id == order.store_id,
                Design.product_id == li.product_id,
            ).limit(1)
        )
    if d and d.file_path:
        return storage.get_thumbnail_url(d.file_path, d.file_format)
    return None


def _extract_model(li) -> str | None:
    if getattr(li, "device_model_override", None):
        return li.device_model_override
    for p in (li.properties or []):
        if isinstance(p, dict):
            name = (p.get("name") or "")
            if name.endswith("Model") and not name.startswith("_"):
                v = (p.get("value") or "").strip()
                if v:
                    return v
    return li.variant_title or None


def _kalip_kodu_for(db, li) -> str | None:
    """MoldItem varsa kalip kodu (+ ayni kod birden fazla kalipta ise part). Yoksa None."""
    mis = db.scalars(select(MoldItem).where(MoldItem.line_item_id == li.id)).all()
    if not mis:
        return None, None
    mi = mis[0]
    kod = mi.kalip_kodu or None
    # ayni kalip_kodu birden fazla farkli moldda ise part no (nadir)
    part = None
    if kod:
        molds = sorted({str(m.mold_id) for m in mis if m.kalip_kodu == kod})
        if len(molds) > 1:
            part = 1  # ilk; pratikte tek
    label = kod
    if kod and part:
        label = f"{kod} P{part}"
    return label, mi


def _order_payload(db, order) -> dict:
    raw = order.raw or {}
    info = _addr(raw)
    si = stage_defs.stage_info(order.current_stage or 1)
    items = []
    for li in (order.line_items or []):
        kod_label, mi = _kalip_kodu_for(db, li)
        thumb = _design_for_line_item(db, order, li, mi)
        items.append({
            "line_item_id": str(li.id),
            "title": li.title,
            "model": _extract_model(li),
            "quantity": li.quantity or 1,
            "kalip_kodu": kod_label,        # "A5" / "A5 P1" / None
            "thumbnail_url": thumb,         # gorsel ya da None
        })
    return {
        "id": str(order.id),
        "order_number": order.order_number,
        "name": order.name,
        "customer_name": order.customer_name,
        "address": info["address"],
        "district": info["district"],
        "province": info["province"],
        "phone": info["phone"],
        "kargo_sirketi": info["kargo_sirketi"],
        "note": order.note,
        "created_at_platform": order.created_at_platform.isoformat() if order.created_at_platform else None,
        "current_stage": order.current_stage or 1,
        "stage": si,                        # {no,key,label,icon}
        "progress_percent": stage_defs.progress_percent(order.current_stage or 1),
        "store_name": _store_name(db, order),
        "items": items,
        "total_units": sum((li.quantity or 1) for li in (order.line_items or [])),
    }


@router.get("/queue", response_model=dict)
def packaging_queue(
    index: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Acik siparis kuyrugu — EN ESKIDEN sirali. index'teki siparisi tam detayla dondurur."""
    flt = _queue_filter(user.tenant_id)
    total = db.scalar(select(func.count(Order.id)).where(flt)) or 0
    if total == 0:
        return {"total": 0, "index": 0, "order": None, "stages": stage_defs.all_stages_payload()}
    idx = max(0, min(index, total - 1))
    order = db.scalar(
        select(Order)
        .where(flt)
        .options(selectinload(Order.line_items))
        .order_by(asc(Order.created_at_platform), asc(Order.id))
        .offset(idx).limit(1)
    )
    return {
        "total": total,
        "index": idx,
        "order": _order_payload(db, order) if order else None,
        "stages": stage_defs.all_stages_payload(),
    }
