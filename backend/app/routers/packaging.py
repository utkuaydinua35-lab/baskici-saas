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
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Order, OrderStatusHistory, Store, User
from app.services import label_pdf, packaging as pkg

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
