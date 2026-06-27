"""
Denetim kaydı (Audit Log) — /api/audit

OrderStatusHistory verisini okuma amaçlı, filtreli + sayfalı sunar.
"Kim, ne zaman, hangi siparişi/aşamayı değiştirdi" görünürlüğü.

Yetki: yalnızca yönetici (ayarlar). Soft-delete edilmiş siparişlerin
geçmişi de görünür (silme işleminin kim tarafından yapıldığını görmek için).
"""
from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func as sql_func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.database import get_db
from app.models import Order, OrderStatusHistory, User
from app.stages import stage_info

router = APIRouter(
    prefix="/api/audit", tags=["audit"],
    dependencies=[Depends(require_permission("ayarlar"))],
)

_TR = ZoneInfo("Europe/Istanbul")

# action -> Türkçe etiket (frontend ile aynı sözlük)
ACTION_LABELS: dict[str, str] = {
    "stage_change": "Aşama değişikliği",
    "acil": "Acil işaretlendi",
    "acil_kaldir": "Acil kaldırıldı",
    "iptal": "İptal edildi",
    "iptal_geri": "İptal geri alındı",
    "hatali_gonderildi": "Hatalı gönderildi",
    "tedarik_bekle": "Tedarik beklemeye alındı",
    "tedarik_devam": "Tedarik bekleme kapatıldı",
    "list_add": "Listeye eklendi",
    "list_remove": "Listeden çıkarıldı",
    "paketlendi": "Paketlendi",
    "kargoya_verildi": "Kargoya verildi",
    "teslim_edildi": "Teslim edildi",
    "kargo_durumu": "Kargo durumu güncellendi",
    "kargo_sorunu": "Kargo sorunu",
    "askidan_karsilandi": "Askıdan karşılandı",
    "onay_gonderildi": "Müşteri onayına gönderildi",
    "musteri_onay": "Müşteri onayladı",
    "musteri_revizyon": "Müşteri revizyon istedi",
}


def _action_label(action: str) -> str:
    return ACTION_LABELS.get(action, action)


@router.get("", response_model=dict)
def list_audit(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    order_number: str | None = Query(None),
    created_by: str | None = Query(None),
    action: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    user: User = Depends(require_permission("ayarlar")),
    db: Session = Depends(get_db),
):
    """Filtreli + sayfalı denetim kaydı."""
    tid = user.tenant_id

    # OrderStatusHistory + Order JOIN (order_number için).
    # include_deleted: silinmiş siparişlerin geçmişi de görünmeli.
    base = (
        select(OrderStatusHistory, Order.order_number)
        .join(Order, Order.id == OrderStatusHistory.order_id)
        .where(OrderStatusHistory.tenant_id == tid)
        .execution_options(include_deleted=True)
    )

    if order_number:
        base = base.where(Order.order_number.ilike(f"%{order_number}%"))
    if created_by:
        base = base.where(OrderStatusHistory.created_by.ilike(f"%{created_by}%"))
    if action:
        base = base.where(OrderStatusHistory.action == action)
    if date_from:
        try:
            dt = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=_TR)
            base = base.where(OrderStatusHistory.created_at >= dt)
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.strptime(date_to, "%Y-%m-%d").replace(tzinfo=_TR) + timedelta(days=1)
            base = base.where(OrderStatusHistory.created_at < dt)
        except ValueError:
            pass

    # Toplam sayım
    count_q = (
        select(sql_func.count())
        .select_from(base.order_by(None).subquery())
    )
    total = db.scalar(count_q) or 0

    rows = db.execute(
        base.order_by(desc(OrderStatusHistory.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = []
    for h, ord_no in rows:
        items.append({
            "id": str(h.id),
            "order_id": str(h.order_id),
            "order_number": ord_no,
            "action": h.action,
            "action_label": _action_label(h.action),
            "from_stage": h.from_stage,
            "to_stage": h.to_stage,
            "from_label": stage_info(h.from_stage)["label"] if h.from_stage else None,
            "to_label": stage_info(h.to_stage)["label"] if h.to_stage else None,
            "note": h.note,
            "created_by": h.created_by,
            "created_at": h.created_at.isoformat() if h.created_at else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


@router.get("/_meta", response_model=dict)
def audit_meta(
    user: User = Depends(require_permission("ayarlar")),
    db: Session = Depends(get_db),
):
    """Filtre açılır menüleri için: kullanılan eylemler + kullanıcılar."""
    tid = user.tenant_id

    actions = db.scalars(
        select(OrderStatusHistory.action)
        .where(OrderStatusHistory.tenant_id == tid)
        .distinct()
    ).all()
    users = db.scalars(
        select(OrderStatusHistory.created_by)
        .where(
            OrderStatusHistory.tenant_id == tid,
            OrderStatusHistory.created_by.isnot(None),
        )
        .distinct()
    ).all()

    return {
        "actions": [
            {"value": a, "label": _action_label(a)}
            for a in sorted(actions) if a
        ],
        "users": sorted([u for u in users if u]),
    }
