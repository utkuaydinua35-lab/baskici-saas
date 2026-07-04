"""
Satış Analitiği — /api/analytics/summary

Dashboard'un ciro desenini (raw.total_price, telafi/iptal/iade hariç) keyfi
tarih aralığına genelleştirir + ürün/model/kanal kırılımları ve checkout hunisi.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Numeric, cast, func as sql_func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.database import get_db
from app.models import CheckoutSession, LineItem, Order, Store, User

router = APIRouter(
    prefix="/api/analytics", tags=["analytics"],
    dependencies=[Depends(require_permission("dashboard"))],
)

MAX_RANGE_DAYS = 366


@router.get("/summary")
def analytics_summary(
    start: date = Query(...),
    end: date = Query(...),
    store_id: uuid.UUID | None = Query(None),
    user: User = Depends(require_permission("dashboard")),
    db: Session = Depends(get_db),
):
    if end < start:
        raise HTTPException(422, "Bitiş tarihi başlangıçtan önce olamaz")
    if (end - start).days > MAX_RANGE_DAYS:
        raise HTTPException(422, f"Aralık en fazla {MAX_RANGE_DAYS} gün olabilir")

    tid = user.tenant_id
    start_dt = datetime.combine(start, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(end + timedelta(days=1), time.min, tzinfo=timezone.utc)

    # Dashboard ciro kuralları birebir: telafi + iptal + tam iade hariç
    base_conds = [
        Order.tenant_id == tid,
        Order.is_telafi.is_(False),
        Order.cancelled_at.is_(None),
        (Order.financial_status != "refunded") | (Order.financial_status.is_(None)),
        Order.created_at_platform >= start_dt,
        Order.created_at_platform < end_dt,
    ]
    if store_id:
        base_conds.append(Order.store_id == store_id)

    total_price = cast(Order.raw["total_price"].astext, Numeric)

    # ── Özet: ciro + sipariş sayısı + AOV ──
    row = db.execute(
        select(
            sql_func.coalesce(sql_func.sum(total_price), 0),
            sql_func.count(Order.id),
        ).where(*base_conds)
    ).one()
    revenue = float(row[0] or 0)
    orders_count = int(row[1] or 0)
    aov = round(revenue / orders_count, 2) if orders_count else 0.0

    # ── Günlük ciro serisi (eksik günler 0) ──
    day_col = sql_func.date_trunc("day", Order.created_at_platform)
    daily_map: dict[str, dict] = {}
    for r in db.execute(
        select(day_col.label("gun"),
               sql_func.coalesce(sql_func.sum(total_price), 0).label("tutar"),
               sql_func.count(Order.id).label("adet"))
        .where(*base_conds).group_by(day_col)
    ).all():
        if r.gun is not None:
            daily_map[r.gun.date().isoformat()] = {
                "tutar": float(r.tutar or 0), "adet": int(r.adet or 0)}
    daily = []
    d = start
    while d <= end:
        key = d.isoformat()
        entry = daily_map.get(key, {"tutar": 0.0, "adet": 0})
        daily.append({"gun": key, "tutar": round(entry["tutar"], 2), "adet": entry["adet"]})
        d += timedelta(days=1)

    # ── En çok satan ürünler (adet bazlı) ──
    li_base = select(LineItem.title, sql_func.sum(LineItem.quantity).label("adet")) \
        .join(Order, LineItem.order_id == Order.id).where(*base_conds) \
        .group_by(LineItem.title).order_by(sql_func.sum(LineItem.quantity).desc()).limit(10)
    top_products = [
        {"title": r[0] or "—", "quantity": int(r[1] or 0)}
        for r in db.execute(li_base).all()
    ]

    # ── En çok satan telefon modelleri ──
    # Model bilgisi platforma göre farklı yerde (properties / variant_title /
    # override) — üretim hattının kullandığı extract_phone_model ile çıkarılır.
    from collections import Counter
    from app.services.mold_planner import extract_phone_model
    model_counts: Counter[str] = Counter()
    li_rows = db.scalars(
        select(LineItem).join(Order, LineItem.order_id == Order.id).where(*base_conds)
    ).all()
    for li in li_rows:
        model = (extract_phone_model(li) or "").strip()
        # Tek karakterlik/sayısal çöp değerleri ele
        if len(model) >= 3:
            model_counts[model] += int(li.quantity or 1)
    top_models = [
        {"model": m, "quantity": q} for m, q in model_counts.most_common(10)
    ]

    # ── Kanal/mağaza bazında ciro ──
    sq = select(Store.name, Store.platform,
                sql_func.coalesce(sql_func.sum(total_price), 0),
                sql_func.count(Order.id)) \
        .join(Order, Order.store_id == Store.id).where(*base_conds) \
        .group_by(Store.id).order_by(sql_func.sum(total_price).desc())
    by_store = [
        {"store": r[0], "platform": r[1], "revenue": float(r[2] or 0), "orders": int(r[3] or 0)}
        for r in db.execute(sq).all()
    ]

    # ── Checkout hunisi (yalnızca vitrin) ──
    cs_conds = [
        CheckoutSession.tenant_id == tid,
        CheckoutSession.created_at >= start_dt,
        CheckoutSession.created_at < end_dt,
    ]
    if store_id:
        cs_conds.append(CheckoutSession.store_id == store_id)
    funnel_rows = db.execute(
        select(CheckoutSession.status,
               sql_func.count(CheckoutSession.id),
               sql_func.coalesce(sql_func.sum(CheckoutSession.amount), 0))
        .where(*cs_conds).group_by(CheckoutSession.status)
    ).all()
    by_status = {r[0]: {"count": int(r[1] or 0), "amount": float(r[2] or 0)} for r in funnel_rows}
    created = sum(v["count"] for v in by_status.values())
    paid = by_status.get("paid", {"count": 0})["count"]
    abandoned = {k: by_status.get(k, {"count": 0, "amount": 0.0}) for k in ("pending", "expired", "failed")}
    funnel = {
        "created": created,
        "paid": paid,
        "conversion": round(100 * paid / created, 1) if created else 0.0,
        "abandoned_count": sum(v["count"] for v in abandoned.values()),
        "abandoned_amount": round(sum(v["amount"] for v in abandoned.values()), 2),
        "by_status": by_status,
    }

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "revenue": round(revenue, 2),
        "orders_count": orders_count,
        "aov": aov,
        "daily": daily,
        "top_products": top_products,
        "top_models": top_models,
        "by_store": by_store,
        "funnel": funnel,
    }


@router.get("/live")
def analytics_live(
    store_id: uuid.UUID | None = Query(None),
    user: User = Depends(require_permission("dashboard")),
    db: Session = Depends(get_db),
):
    """Canlı görünüm — panel dashboard'u 30 sn'de bir çeker.

    Bugün + son 15 dk sipariş/ciro, aktif checkout sayısı ve son 10 aktivite
    (yeni siparişler + checkout oturumları, ad maskeli).
    """
    tid = user.tenant_id
    now = datetime.now(timezone.utc)
    start_today = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
    m15 = now - timedelta(minutes=15)
    total_price = cast(Order.raw["total_price"].astext, Numeric)

    ciro_conds = [
        Order.tenant_id == tid, Order.is_telafi.is_(False),
        Order.cancelled_at.is_(None),
        (Order.financial_status != "refunded") | (Order.financial_status.is_(None)),
    ]
    if store_id:
        ciro_conds.append(Order.store_id == store_id)

    def _agg(since):
        row = db.execute(
            select(sql_func.count(Order.id),
                   sql_func.coalesce(sql_func.sum(total_price), 0))
            .where(*ciro_conds, Order.created_at_platform >= since)
        ).one()
        return {"orders": int(row[0] or 0), "revenue": float(row[1] or 0)}

    cs_conds = [CheckoutSession.tenant_id == tid]
    if store_id:
        cs_conds.append(CheckoutSession.store_id == store_id)
    active_checkouts = db.scalar(
        select(sql_func.count(CheckoutSession.id)).where(
            *cs_conds, CheckoutSession.status == "pending",
            CheckoutSession.created_at >= now - timedelta(hours=2))
    ) or 0

    def _mask(name: str | None) -> str:
        parts = (name or "").strip().split()
        if not parts:
            return "Misafir"
        first = parts[0]
        rest = " ".join(f"{p[0]}." for p in parts[1:] if p)
        return f"{first} {rest}".strip()

    activity = []
    order_conds = [Order.tenant_id == tid, Order.is_telafi.is_(False)]
    if store_id:
        order_conds.append(Order.store_id == store_id)
    for o in db.scalars(
        select(Order).where(*order_conds)
        .order_by(Order.created_at_platform.desc().nulls_last()).limit(10)
    ).all():
        activity.append({
            "type": "order",
            "at": o.created_at_platform.isoformat() if o.created_at_platform else None,
            "who": _mask(o.customer_name),
            "text": f"{o.name or '#' + o.order_number} sipariş verdi",
            "amount": (o.raw or {}).get("total_price"),
        })
    for s in db.scalars(
        select(CheckoutSession).where(
            *cs_conds, CheckoutSession.created_at >= now - timedelta(hours=24))
        .order_by(CheckoutSession.created_at.desc()).limit(10)
    ).all():
        cust = s.customer or {}
        who = _mask(f"{cust.get('first_name', '')} {cust.get('last_name', '')}".strip())
        label = {"pending": "ödeme sayfasında", "paid": "ödemeyi tamamladı",
                 "failed": "ödemesi başarısız oldu", "expired": "sepeti terk etti"}
        activity.append({
            "type": f"checkout_{s.status}",
            "at": s.created_at.isoformat() if s.created_at else None,
            "who": who,
            "text": label.get(s.status, s.status),
            "amount": str(s.amount),
        })
    activity.sort(key=lambda a: a["at"] or "", reverse=True)

    return {
        "now": now.isoformat(),
        "today": _agg(start_today),
        "last_15m": _agg(m15),
        "active_checkouts": int(active_checkouts),
        "activity": activity[:10],
    }
