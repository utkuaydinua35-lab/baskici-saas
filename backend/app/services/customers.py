"""
Müşteri CRM servisi — sipariş verisinden Customer kayıtları türetme.

upsert_from_order her sipariş upsert'inde çağrılır (orders._upsert_order sonu);
agregalar YENİDEN hesaplandığı için tekrarlanan sync'lerde idempotenttir.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Numeric, cast, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import Customer, Order


def _extract_phone(raw: dict | None) -> str | None:
    """Sipariş raw'ından telefon çıkar (shipping_address öncelikli)."""
    if not isinstance(raw, dict):
        return None
    ship = raw.get("shipping_address") or {}
    phone = ship.get("phone") or (raw.get("customer") or {}).get("phone")
    return str(phone)[:40] if phone else None


def upsert_from_order(db: Session, order: Order) -> None:
    """Siparişin müşterisini customers tablosuna işle + agregaları yenile.

    Commit ETMEZ — çağıranın transaction'ı içinde çalışır.
    """
    email = (order.customer_email or "").strip().lower()
    if not email or "@" not in email:
        return

    name = (order.customer_name or "").strip() or None
    phone = _extract_phone(order.raw)

    stmt = pg_insert(Customer).values(
        tenant_id=order.tenant_id, email=email, name=name, phone=phone,
    ).on_conflict_do_update(
        constraint="uq_customer_tenant_email",
        set_={
            # En güncel ad/telefon kazanır (boşsa mevcut korunur)
            "name": func.coalesce(pg_insert(Customer).excluded.name, Customer.name),
            "phone": func.coalesce(pg_insert(Customer).excluded.phone, Customer.phone),
            "updated_at": func.now(),
        },
    )
    db.execute(stmt)

    recompute_stats(db, order.tenant_id, email)


def _ciro_tl_tutar():
    from app.services.ciro import tl_tutar
    return tl_tutar()


def recompute_stats(db: Session, tenant_id, email: str) -> None:
    """Müşteri agregalarını sipariş tablosundan yeniden hesapla.

    Dashboard cirosuyla aynı dışlamalar: iptal + telafi siparişleri sayılmaz.
    """
    row = db.execute(
        select(
            func.count(Order.id),
            # TL harcama (services/ciro): USD bayi siparişi TL'ye eklenmez.
            func.coalesce(func.sum(_ciro_tl_tutar()), 0),
            func.min(Order.created_at_platform),
            func.max(Order.created_at_platform),
        ).where(
            Order.tenant_id == tenant_id,
            func.lower(Order.customer_email) == email,
            Order.is_iptal.is_(False),
            Order.is_telafi.is_(False),
        )
    ).one()

    customer = db.scalar(select(Customer).where(
        Customer.tenant_id == tenant_id, Customer.email == email))
    if not customer:
        return
    customer.orders_count = int(row[0] or 0)
    customer.total_spent = Decimal(str(row[1] or 0))
    customer.first_order_at = row[2]
    customer.last_order_at = row[3]


def backfill(db: Session, tenant_id) -> dict:
    """Mevcut tüm siparişlerden müşteri kayıtlarını (yeniden) türet."""
    emails = db.execute(
        select(func.lower(Order.customer_email)).where(
            Order.tenant_id == tenant_id,
            Order.customer_email.isnot(None),
            Order.customer_email != "",
        ).distinct()
    ).scalars().all()

    processed = 0
    for email in emails:
        if not email or "@" not in email:
            continue
        # Ad/telefon için en yeni siparişi örnek al
        latest = db.scalar(
            select(Order).where(
                Order.tenant_id == tenant_id,
                func.lower(Order.customer_email) == email,
            ).order_by(Order.created_at_platform.desc().nulls_last()).limit(1)
        )
        if latest:
            upsert_from_order(db, latest)
            processed += 1
    db.commit()
    return {"customers": processed}
