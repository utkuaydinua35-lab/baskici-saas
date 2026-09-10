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

from sqlalchemy import or_

from app.models import Order

# Bir açık sipariş kaç günden sonra "acil" sayılır (sipariş listesi tab'ı ile ortak).
ACIL_THRESHOLD_DAYS = 5


def open_conds():
    """'Gerçek açık' SQL koşulları — TEK KAYNAK: services/order_scope.

    ⚠ Burada elle yazılmış bir kopya vardı ve `current_stage >= 8` (kargoya
    verilmiş/teslim) kontrolü EKSİKTİ. Sonuç: paketleme kuyruğu 60 sipariş
    gösterirken bu sayaç 171 gösteriyordu — aynı soruya iki farklı cevap.
    """
    from app.services.order_scope import acik_kosullar
    return acik_kosullar()


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


def acil_threshold_dt():
    return datetime.now(timezone.utc) - timedelta(days=ACIL_THRESHOLD_DAYS)


def acil_extra_conds(tid=None):
    """'Acil' için open_conds ÜZERİNE ek elemeler — bayii dahil TÜM siparişler için
    aynı: gecikmiş AMA henüz kargoya verilmemiş/teslim edilmemiş olanlar kalsın.
    - Kargoya verilmiş/teslim (stage >= 8: 8 Kargoda, 9 Teslim) HARİÇ.
    - Takip no'su olan (kargo_info.takip_no) HARİÇ: Shopify'da kargolanıp takibi
      panele çekilmiş siparişler (fulfillment_status geç güncellense de) elenir.
    Böylece teslim/kargoda bayii siparişi acil olmaz; geciken açık bayii siparişi olur."""
    return (
        or_(Order.current_stage.is_(None), Order.current_stage < 8),
        or_(
            Order.kargo_info.is_(None),
            Order.kargo_info["takip_no"].astext.is_(None),
            Order.kargo_info["takip_no"].astext == "",
        ),
    )


def acil(db, tid, *, store_id=None) -> int:
    """Acil: GERÇEK açık (open_conds) + 5 günden eski + acil_extra_conds
    (bayii/kargoda/takipli hariç). Sipariş listesi 'acil' tab'ıyla birebir aynı."""
    return _count(
        db, tid, *open_conds(), *acil_extra_conds(tid),
        Order.created_at_platform < acil_threshold_dt(),
        store_id=store_id,
    )
