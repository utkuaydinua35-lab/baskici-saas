"""
Dashboard — /api/dashboard/summary

Tek çağrıda tenant geneli özet. Opsiyonel store_id filtresi sipariş/kalıp/askı
metriklerine uygulanır; stok (fiziksel envanter) tenant geneli kalır.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Numeric, cast, desc, func as sql_func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import AskiItem, Mold, Notification, Order, StockItem, User
from app.stages import all_stages_payload

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/worklist", response_model=dict)
def worklist(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Kullanıcının rol/izin bazlı sabah görev listesi."""
    from app.services.worklist_service import build_worklist
    return build_worklist(db, user)


@router.post("/_test-daily-summary", response_model=dict)
def test_daily_summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Sabah Telegram ozetini hemen gonder (test). 08:00 cron'u beklemeden."""
    from app.services import daily_summary
    sent = daily_summary.send_daily_summary(db)
    return {"ok": True, "sent": sent}


@router.get("/summary", response_model=dict)
def summary(
    store_id: uuid.UUID | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tid = user.tenant_id
    not_cancelled = Order.cancelled_at.is_(None)
    # Gercek acik siparis: iptal degil + kargoya verilmemis (fulfilled degil) + iade degil (refunded degil)
    _acik_kosul = (
        Order.cancelled_at.is_(None),
        (Order.fulfillment_status != "fulfilled") | (Order.fulfillment_status.is_(None)),
        (Order.financial_status != "refunded") | (Order.financial_status.is_(None)),
    )

    # Telafiler ayri panelde — normal siparis KPI'larina dahil edilmez
    _not_telafi = Order.is_telafi.is_(False)

    def ocount(*conds) -> int:
        q = select(sql_func.count(Order.id)).where(Order.tenant_id == tid, _not_telafi, *conds)
        if store_id:
            q = q.where(Order.store_id == store_id)
        return db.scalar(q) or 0

    # ─── KPI'lar ───
    acik = ocount(*_acik_kosul, Order.current_stage < 9)
    acil = ocount(not_cancelled, Order.is_acil.is_(True), Order.current_stage < 9)

    start_today = datetime.combine(date.today(), time.min, tzinfo=timezone.utc)
    bugun = ocount(Order.created_at_platform >= start_today)

    paketleme_bekleyen = ocount(not_cancelled, Order.current_stage == 6)
    kargo_bekleyen = ocount(not_cancelled, Order.current_stage == 7)

    # ─── Üretim hattı (stage dağılımı) ───
    fq = (
        select(Order.current_stage, sql_func.count(Order.id))
        .where(Order.tenant_id == tid, _not_telafi, *_acik_kosul)
        .group_by(Order.current_stage)
    )
    if store_id:
        fq = fq.where(Order.store_id == store_id)
    funnel_raw = {row[0]: row[1] for row in db.execute(fq).all()}
    funnel = [
        {"no": s["no"], "key": s["key"], "label": s["label"], "count": int(funnel_raw.get(s["no"], 0))}
        for s in all_stages_payload()
    ]

    # ─── Net ciro (iptal + iade haric) — raw.total_price toplami ───
    _ciro_kosul = (
        Order.cancelled_at.is_(None),
        (Order.financial_status != "refunded") | (Order.financial_status.is_(None)),
    )
    def _ciro(*conds) -> float:
        q = select(sql_func.coalesce(sql_func.sum(
            cast(Order.raw["total_price"].astext, Numeric)
        ), 0)).where(Order.tenant_id == tid, _not_telafi, *conds)
        if store_id:
            q = q.where(Order.store_id == store_id)
        try:
            return float(db.scalar(q) or 0)
        except Exception:
            return 0.0
    _today = date.today()
    _start_week = datetime.combine(_today - timedelta(days=_today.weekday()), time.min, tzinfo=timezone.utc)
    _start_month = datetime.combine(_today.replace(day=1), time.min, tzinfo=timezone.utc)
    ciro_bugun = _ciro(*_ciro_kosul, Order.created_at_platform >= start_today)
    ciro_hafta = _ciro(*_ciro_kosul, Order.created_at_platform >= _start_week)
    ciro_ay = _ciro(*_ciro_kosul, Order.created_at_platform >= _start_month)

    # Son 30 gun gunluk ciro serisi (grafik icin)
    _start_30 = datetime.combine(_today - timedelta(days=29), time.min, tzinfo=timezone.utc)
    _gun_col = sql_func.date_trunc("day", Order.created_at_platform)
    _gq = (
        select(_gun_col.label("gun"), sql_func.coalesce(sql_func.sum(cast(Order.raw["total_price"].astext, Numeric)), 0).label("tutar"))
        .where(Order.tenant_id == tid, _not_telafi, *_ciro_kosul, Order.created_at_platform >= _start_30)
        .group_by(_gun_col)
    )
    if store_id:
        _gq = _gq.where(Order.store_id == store_id)
    _gunluk_map = {}
    try:
        for row in db.execute(_gq).all():
            if row.gun is not None:
                _gunluk_map[row.gun.date().isoformat()] = float(row.tutar or 0)
    except Exception:
        _gunluk_map = {}
    # Eksik gunleri 0 ile doldur (30 gun tam seri)
    ciro_gunluk = []
    for i in range(30):
        d = (_today - timedelta(days=29 - i)).isoformat()
        ciro_gunluk.append({"gun": d, "tutar": round(_gunluk_map.get(d, 0.0), 2)})

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

    # ─── Telafiler (ayri panel) ───
    def tcount(*conds) -> int:
        q = select(sql_func.count(Order.id)).where(
            Order.tenant_id == tid, Order.is_telafi.is_(True), *conds)
        if store_id:
            q = q.where(Order.store_id == store_id)
        return db.scalar(q) or 0

    telafi_toplam = tcount()
    telafi_acik = tcount(Order.cancelled_at.is_(None), Order.current_stage < 9)
    # En sik telafi sebepleri (ilk 5)
    _sq = (
        select(Order.telafi_sebep, sql_func.count(Order.id).label("adet"))
        .where(Order.tenant_id == tid, Order.is_telafi.is_(True), Order.telafi_sebep.isnot(None))
        .group_by(Order.telafi_sebep)
        .order_by(desc(sql_func.count(Order.id)))
        .limit(5)
    )
    if store_id:
        _sq = _sq.where(Order.store_id == store_id)
    telafi_sebepler = [
        {"sebep": row[0], "adet": int(row[1])} for row in db.execute(_sq).all()
    ]

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
            "telafi_acik": telafi_acik,
        },
        "telafi": {
            "toplam": telafi_toplam,
            "acik": telafi_acik,
            "sebepler": telafi_sebepler,
        },
        "ciro": {
            "bugun": round(ciro_bugun, 2),
            "hafta": round(ciro_hafta, 2),
            "ay": round(ciro_ay, 2),
            "gunluk": ciro_gunluk,
            "currency": "TRY",
        },
        "funnel": funnel,
        "low_stock": low_stock,
        "recent": recent,
    }
