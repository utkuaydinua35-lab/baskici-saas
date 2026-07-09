"""
Müşteriler (CRM) — /api/customers/*

Siparişlerden türetilen birleşik müşteri görünümü: sipariş sayısı, toplam
harcama, ilk/son sipariş + serbest notlar. Kayıtlar orders._upsert_order
kancasıyla otomatik güncellenir; backfill mevcut siparişleri işler.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.database import get_db
from app.models import Customer, Order, User
from app.services import customers as customers_svc

router = APIRouter(
    prefix="/api/customers", tags=["customers"],
    dependencies=[Depends(require_permission("musteri"))],
)

SORTS = {
    "total_spent": Customer.total_spent,
    "orders_count": Customer.orders_count,
    "last_order_at": Customer.last_order_at,
    "created_at": Customer.created_at,
}


class NotesUpdate(BaseModel):
    notes: str | None = Field(None, max_length=5000)


def _serialize(c: Customer) -> dict:
    return {
        "id": str(c.id),
        "email": c.email,
        "name": c.name,
        "phone": c.phone,
        "orders_count": c.orders_count,
        "total_spent": str(c.total_spent),
        "first_order_at": c.first_order_at.isoformat() if c.first_order_at else None,
        "last_order_at": c.last_order_at.isoformat() if c.last_order_at else None,
        "notes": c.notes,
        "accepts_marketing": c.accepts_marketing,
    }


@router.get("", response_model=dict)
def list_customers(
    q: str | None = Query(None, max_length=200),
    sort: str = Query("last_order_at"),
    store_id: uuid.UUID | None = Query(None),
    subscribed: bool = Query(False),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    user: User = Depends(require_permission("musteri")),
    db: Session = Depends(get_db),
):
    base = select(Customer).where(Customer.tenant_id == user.tenant_id)
    if q:
        needle = f"%{q.strip()}%"
        base = base.where(or_(Customer.email.ilike(needle), Customer.name.ilike(needle)))
    if subscribed:
        # Bülten aboneleri: siparişsiz kayıt da olabilir (footer formu) —
        # mağaza sipariş kapsamı uygulanmaz, tenant tekil vitrine sahiptir
        base = base.where(Customer.accepts_marketing.is_(True))
    elif store_id:
        # Mağaza kapsamı (Mağaza Paneli): o mağazada siparişi olan müşteriler
        base = base.where(Customer.email.in_(
            select(func.lower(Order.customer_email)).where(
                Order.store_id == store_id,
                Order.customer_email.isnot(None),
            )
        ))

    total = db.scalar(select(func.count()).select_from(base.subquery()))
    col = SORTS.get(sort, Customer.last_order_at)
    rows = db.scalars(
        base.order_by(col.desc().nulls_last())
        .offset((page - 1) * per_page).limit(per_page)
    ).all()

    return {"total": total, "page": page, "per_page": per_page,
            "items": [_serialize(c) for c in rows]}


@router.get("/export/subscribers.csv")
def export_subscribers(
    user: User = Depends(require_permission("musteri")),
    db: Session = Depends(get_db),
):
    """Bülten abonelerini CSV indir (e-posta pazarlama aracına aktarım için)."""
    import csv
    import io

    from fastapi.responses import StreamingResponse

    rows = db.scalars(
        select(Customer).where(
            Customer.tenant_id == user.tenant_id,
            Customer.accepts_marketing.is_(True),
        ).order_by(Customer.created_at)
    ).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["email", "name", "opted_at", "orders_count"])
    for c in rows:
        w.writerow([
            c.email, c.name or "",
            c.marketing_opted_at.isoformat() if c.marketing_opted_at else "",
            c.orders_count,
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=bulten-aboneleri.csv"},
    )


@router.get("/{customer_id}", response_model=dict)
def get_customer(
    customer_id: uuid.UUID,
    user: User = Depends(require_permission("musteri")),
    db: Session = Depends(get_db),
):
    customer = db.scalar(select(Customer).where(
        Customer.id == customer_id, Customer.tenant_id == user.tenant_id))
    if not customer:
        raise HTTPException(404, "Müşteri bulunamadı")

    orders = db.scalars(
        select(Order).where(
            Order.tenant_id == user.tenant_id,
            func.lower(Order.customer_email) == customer.email,
        ).order_by(Order.created_at_platform.desc().nulls_last()).limit(100)
    ).all()

    return {
        **_serialize(customer),
        "orders": [
            {
                "id": str(o.id),
                "order_number": o.order_number,
                "name": o.name,
                "created_at": o.created_at_platform.isoformat() if o.created_at_platform else None,
                "financial_status": o.financial_status,
                "fulfillment_status": o.fulfillment_status,
                "current_stage": o.current_stage,
                "is_iptal": o.is_iptal,
                "is_telafi": o.is_telafi,
                "total_price": (o.raw or {}).get("total_price"),
                "item_count": len(o.line_items),
            }
            for o in orders
        ],
    }


@router.patch("/{customer_id}", response_model=dict)
def update_notes(
    customer_id: uuid.UUID,
    body: NotesUpdate,
    user: User = Depends(require_permission("musteri")),
    db: Session = Depends(get_db),
):
    customer = db.scalar(select(Customer).where(
        Customer.id == customer_id, Customer.tenant_id == user.tenant_id))
    if not customer:
        raise HTTPException(404, "Müşteri bulunamadı")
    customer.notes = body.notes
    db.commit()
    return _serialize(customer)


@router.post("/backfill", response_model=dict)
def backfill_customers(
    user: User = Depends(require_permission("musteri")),
    db: Session = Depends(get_db),
):
    """Mevcut tüm siparişlerden müşteri kayıtlarını türet/güncelle."""
    return customers_svc.backfill(db, user.tenant_id)
