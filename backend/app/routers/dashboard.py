"""
Dashboard — /api/dashboard/summary

Tek çağrıda tenant geneli özet. Opsiyonel store_id filtresi sipariş/kalıp/askı
metriklerine uygulanır; stok (fiziksel envanter) tenant geneli kalır.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func as sql_func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import AskiItem, Mold, Notification, Order, StockItem, User
from app.stages import all_stages_payload

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=dict)
def summary(
    store_id: uuid.UUID | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tid = user.tenant_id
    not_cancelled = Order.cancelled_at.is_(None)

    def ocount(*conds) -> int:
        q = select(sql_func.count(Order.id)).where(Order.tenant_id == tid, *conds)
        if store_id:
            q = q.where(Order.store_id == store_id)
        return db.scalar(q) or 0

    # ─── KPI'lar ───
    acik = ocount(not_cancelled, Order.current_stage < 9)
    acil = ocount(not_cancelled, Order.is_acil.is_(True), Order.current_stage < 9)

    start_today = datetime.combine(date.today(), time.min, tzinfo=timezone.utc)
    bugun = ocount(Order.created_at_platform >= start_today)

    paketleme_bekleyen = ocount(not_cancelled, Order.current_stage == 6)
    kargo_bekleyen = ocount(not_cancelled, Order.current_stage == 7)

    # ─── Üretim hattı (stage dağılımı) ───
    fq = (
        select(Order.current_stage, sql_func.count(Order.id))
        .where(Order.tenant_id == tid, not_cancelled)
        .group_by(Order.current_stage)
    )
    if store_id:
        fq = fq.where(Order.store_id == store_id)
    funnel_raw = {row[0]: row[1] for row in db.execute(fq).all()}
    funnel = [
        {"no": s["no"], "key": s["key"], "label": s["label"], "count": int(funnel_raw.get(s["no"], 0))}
        for s in all_stages_payload()
    ]

    # ─── Askı (adet) ───
    aq = select(sql_func.coalesce(sql_func.sum(AskiItem.quantity), 0)).where(AskiItem.tenant_id == tid)
    if store_id:
        aq = aq.where(AskiItem.store_id == store_id)
    aski_adet = int(db.scalar(aq) or 0)

    # ─── Açık kalıp (stage < 5 = tamamlanmamış) ───
    mq = select(sql_func.count(Mold.id)).where(Mold.tenant_id == tid, Mold.current_stage < 5)
    if store_id:
        mq = mq.where((Mold.store_id == store_id) | (Mold.store_id.is_(None)))
    acik_kalip = db.scalar(mq) or 0

    # ─── Düşük stok (tenant geneli) ───
    low_items = db.scalars(
        select(StockItem).where(
            StockItem.tenant_id == tid,
            StockItem.is_active.is_(True),
            StockItem.low_stock_threshold > 0,
            StockItem.quantity <= StockItem.low_stock_threshold,
        ).order_by(StockItem.quantity)
    ).all()
    low_stock = [
        {
            "id": str(i.id), "sku": i.sku, "name": i.name,
            "quantity": i.quantity, "threshold": i.low_stock_threshold,
            "variation": i.variation, "model": i.model, "category": i.category,
        }
        for i in low_items[:20]
    ]

    # ─── Son hareketler (bildirimler) ───
    nq = select(Notification).where(Notification.tenant_id == tid)
    if store_id:
        nq = nq.where((Notification.store_id == store_id) | (Notification.store_id.is_(None)))
    recents = db.scalars(nq.order_by(desc(Notification.created_at)).limit(8)).all()
    recent = [
        {
            "id": str(n.id), "kind": n.kind, "title": n.title, "body": n.body,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in recents
    ]

    return {
        "kpis": {
            "acik_siparis": acik,
            "bugun_gelen": bugun,
            "acil": acil,
            "paketleme_bekleyen": paketleme_bekleyen,
            "kargo_bekleyen": kargo_bekleyen,
            "aski_adet": aski_adet,
            "acik_kalip": acik_kalip,
            "dusuk_stok": len(low_stock),
        },
        "funnel": funnel,
        "low_stock": low_stock,
        "recent": recent,
    }
