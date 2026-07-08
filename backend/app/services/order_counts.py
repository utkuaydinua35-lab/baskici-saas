"""Sipariş sayıları — TEK KAYNAK.

dashboard, daily_summary (sabah özeti), worklist (sabah görev listesi) ve
sipariş listesi 'acil' tab'ı ARTIK aynı tanımları buradan kullanır. Böylece
"dashboard 0 acil derken listede 17" ya da "paketleme(16) > açık(14)" gibi
ekranlar-arası tutarsızlıklar oluşmaz.

Tanımlar:
- GERÇEK AÇIK = iptal değil (cancelled_at null) + kargolanmamış (fulfilled değil)
  + iade değil (refunded değil). Telafiler her zaman hariç (ayrı panelde).
- ACİL = açık + ACIL_THRESHOLD_DAYS günden eski (YAŞ bazlı; sipariş listesi
  'acil' tab'ıyla birebir aynı — is_acil manuel bayrağı DEĞİL).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func as sql_func, select

from app.models import Order

# Bir açık sipariş kaç günden sonra "acil" sayılır (sipariş listesi tab'ı ile ortak).
ACIL_THRESHOLD_DAYS = 5


def open_conds():
    """'Gerçek açık' SQL koşulları (iptal/fulfilled/iade değil)."""
    return (
        Order.cancelled_at.is_(None),
        (Order.fulfillment_status != "fulfilled") | (Order.fulfillment_status.is_(None)),
        (Order.financial_status != "refunded") | (Order.financial_status.is_(None)),
    )


def _count(db, tid, *conds, store_id=None) -> int:
    q = select(sql_func.count(Order.id)).where(
        Order.tenant_id == tid, Order.is_telafi.is_(False), *conds
    )
    if store_id:
        q = q.where(Order.store_id == store_id)
    return db.scalar(q) or 0


def acik(db, tid, *, store_id=None) -> int:
    """Açık sipariş: gerçek açık + henüz teslim edilmemiş (stage < 9)."""
    return _count(db, tid, *open_conds(), Order.current_stage < 9, store_id=store_id)


def paketleme(db, tid, *, store_id=None) -> int:
    """Paketleme bekleyen: gerçek açık + stage == 6."""
    return _count(db, tid, *open_conds(), Order.current_stage == 6, store_id=store_id)


def kargo(db, tid, *, store_id=None) -> int:
    """Kargoya verilecek: gerçek açık + stage == 7."""
    return _count(db, tid, *open_conds(), Order.current_stage == 7, store_id=store_id)


def acil(db, tid, *, store_id=None) -> int:
    """Acil: iptal değil + fulfilled değil + ACIL_THRESHOLD_DAYS günden eski.
    (Sipariş listesi 'acil' tab filtresiyle birebir aynı.)"""
    threshold = datetime.now(timezone.utc) - timedelta(days=ACIL_THRESHOLD_DAYS)
    return _count(
        db, tid,
        Order.cancelled_at.is_(None),
        (Order.fulfillment_status != "fulfilled") | (Order.fulfillment_status.is_(None)),
        Order.created_at_platform < threshold,
        store_id=store_id,
    )
