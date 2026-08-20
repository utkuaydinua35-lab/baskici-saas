"""
Hızlı arama (⌘K komut paleti) — /api/search

İKİ PANELİ birden besler:
  • Baskıcı paneli  → sipariş + kalıp kodu
  • Mağaza paneli   → sipariş + ürün + müşteri (store_id ile daraltılır)

İzin bazlı: siparişler için 'siparisler', kalıplar için 'kalip', ürün ve
müşteri için 'vitrin' (yönetici/owner tümünü görür). İstenmeyen kova hiç
sorgulanmaz — palet her tuş vuruşunda çağrıldığı için gereksiz sorgu yok.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import CatalogProduct, Customer, Mold, Order, User

router = APIRouter(prefix="/api/search", tags=["search"])


def _can(user: User, perm: str) -> bool:
    if (user.role or "") in ("owner", "yonetici"):
        return True
    return perm in (user.permissions or [])


@router.get("", response_model=dict)
def quick_search(
    q: str = Query(""),
    store_id: uuid.UUID | None = Query(None, description="Mağaza paneli: ürün/müşteri bu mağazadan"),
    kovalar: str = Query("", description="Virgüllü liste; boşsa hepsi (ör. 'orders,products')"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = (q or "").strip()
    out: dict = {"orders": [], "molds": [], "products": [], "customers": []}
    if len(q) < 2:
        return out
    like = f"%{q}%"
    istenen = {k.strip() for k in kovalar.split(",") if k.strip()}
    ister = lambda k: not istenen or k in istenen  # noqa: E731

    if ister("orders") and _can(user, "siparisler"):
        rows = db.scalars(
            select(Order)
            .where(
                Order.tenant_id == user.tenant_id,
                or_(
                    Order.order_number.ilike(like),
                    Order.name.ilike(like),
                    Order.customer_name.ilike(like),
                    Order.kargo_info["takip_no"].astext.ilike(like),
                ),
            )
            .order_by(Order.created_at_platform.desc())
            .limit(8)
        ).all()
        out["orders"] = [
            {
                "id": str(o.id),
                "order_number": o.order_number,
                "name": o.name,
                "customer": o.customer_name,
            }
            for o in rows
        ]

    if ister("molds") and _can(user, "kalip"):
        rows = db.scalars(
            select(Mold)
            .where(Mold.tenant_id == user.tenant_id, Mold.kod.ilike(like))
            .order_by(Mold.created_at.desc())
            .limit(8)
        ).all()
        out["molds"] = [
            {"id": str(m.id), "kod": m.kod, "variation": m.variation}
            for m in rows
        ]

    if ister("products") and _can(user, "vitrin"):
        kosul = [CatalogProduct.tenant_id == user.tenant_id]
        if store_id:
            kosul.append(CatalogProduct.store_id == store_id)
        rows = db.scalars(
            select(CatalogProduct)
            .where(*kosul, or_(CatalogProduct.title.ilike(like),
                               CatalogProduct.slug.ilike(like)))
            .order_by(CatalogProduct.updated_at.desc().nulls_last())
            .limit(6)
        ).all()
        out["products"] = [
            {"id": str(p.id), "title": p.title, "status": p.status} for p in rows
        ]

    if ister("customers") and _can(user, "vitrin"):
        rows = db.scalars(
            select(Customer)
            .where(Customer.tenant_id == user.tenant_id,
                   or_(Customer.email.ilike(like),
                       Customer.name.ilike(like),
                       Customer.phone.ilike(like)))
            .order_by(Customer.last_order_at.desc().nulls_last())
            .limit(6)
        ).all()
        out["customers"] = [
            {"id": str(c.id), "email": c.email, "name": c.name,
             "orders_count": c.orders_count} for c in rows
        ]

    return out
