"""
Hızlı arama (⌘K komut paleti) — /api/search

Sipariş numarası/adı ve kalıp koduyla arama. İzin bazlı: siparişler için
'siparisler', kalıplar için 'kalip' (yönetici/owner tümünü görür).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Mold, Order, User

router = APIRouter(prefix="/api/search", tags=["search"])


def _can(user: User, perm: str) -> bool:
    if (user.role or "") in ("owner", "yonetici"):
        return True
    return perm in (user.permissions or [])


@router.get("", response_model=dict)
def quick_search(
    q: str = Query(""),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = (q or "").strip()
    out: dict = {"orders": [], "molds": []}
    if len(q) < 2:
        return out
    like = f"%{q}%"

    if _can(user, "siparisler"):
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

    if _can(user, "kalip"):
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

    return out
