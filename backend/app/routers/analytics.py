"""
Satış Analitiği — /api/analytics/summary

Dashboard'un ciro desenini (raw.total_price, telafi/iptal/iade hariç) keyfi
tarih aralığına genelleştirir + ürün/model/kanal kırılımları ve checkout hunisi.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Numeric, cast, func as sql_func, select
from sqlalchemy.orm import Session

from app.services import gun as _gun
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
    start_dt, end_dt = _gun.aralik(start, end)   # İstanbul günleri (bkz. services/gun)

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

    # ⚠ PARA BİRİMİNE DUYARLI (services/ciro): USD bayi siparişi TL'ye EKLENMEZ,
    # bayi kargosu (TL) eklenir. Kur çevrilmez; USD ayrı döner.
    from app.services import ciro as _ciro_svc
    total_price = _ciro_svc.tl_tutar()
    usd_price = _ciro_svc.usd_tutar()

    # ── Özet: ciro + sipariş sayısı + AOV ──
    row = db.execute(
        select(
            sql_func.coalesce(sql_func.sum(total_price), 0),
            sql_func.count(Order.id),
            sql_func.coalesce(sql_func.sum(usd_price), 0),
            sql_func.count(Order.id).filter(_ciro_svc.tl_siparis_mi()),
        ).where(*base_conds)
    ).one()
    revenue = float(row[0] or 0)
    orders_count = int(row[1] or 0)
    revenue_usd = float(row[2] or 0)
    # AOV paydası yalnız TL siparişleri: USD siparişlerini adede katıp TL
    # ciroya bölmek ortalama sepeti yapay olarak düşürürdü.
    _tl_adet = int(row[3] or 0)
    aov = round(revenue / _tl_adet, 2) if _tl_adet else 0.0

    # ── Günlük ciro serisi (eksik günler 0) ──
    day_col = _gun.gun_sql(Order.created_at_platform)
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
                sql_func.count(Order.id),
                sql_func.coalesce(sql_func.sum(usd_price), 0)) \
        .join(Order, Order.store_id == Store.id).where(*base_conds) \
        .group_by(Store.id).order_by(sql_func.sum(total_price).desc())
    by_store = [
        {"store": r[0], "platform": r[1], "revenue": float(r[2] or 0), "orders": int(r[3] or 0),
         "revenue_usd": float(r[4] or 0)}
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
        "revenue_usd": round(revenue_usd, 2),   # USD bayi siparişleri — TL'ye çevrilmez
        "orders_count": orders_count,
        "aov": aov,
        "daily": daily,
        "top_products": top_products,
        "top_models": top_models,
        "by_store": by_store,
        "funnel": funnel,
    }


# ─── Kâr marjı raporu ────────────────────────────────────────
# Shopify'da yalnız "Ürün maliyeti" (COGS) girilir; burada gerçek net kâra
# ulaşmak için komisyon, kargo ve paketleme de düşülür. Maliyet kaynağı:
# ürünün cost_price'ı → yoksa mağaza ayarındaki varsayılan birim maliyet.

COST_KEYS = {
    "unit": "profit_default_unit_cost",     # adet başına varsayılan maliyet
    "ship": "profit_shipping_cost",         # sipariş başına kargo gideri
    "pack": "profit_packaging_cost",        # sipariş başına paketleme
    "commission": "profit_commission_pct",  # ciro üzerinden ödeme komisyonu %
}


def _cost_settings(db: Session, tid, store_id) -> dict:
    """Maliyet ayarları — mağaza config'inden (store_id verilmemişse ilk vitrin)."""
    q = select(Store).where(Store.tenant_id == tid)
    q = q.where(Store.id == store_id) if store_id else q.where(Store.platform == "storefront")
    store = db.scalar(q.limit(1))
    config = (store.config if store else None) or {}

    def num(key, default="0"):
        try:
            return float(str(config.get(key, default) or default).replace(",", "."))
        except ValueError:
            return 0.0

    return {
        "unit_cost": num(COST_KEYS["unit"]),
        "shipping_cost": num(COST_KEYS["ship"]),
        "packaging_cost": num(COST_KEYS["pack"]),
        "commission_pct": num(COST_KEYS["commission"]),
    }


@router.get("/profit")
def profit_report(
    start: date = Query(...),
    end: date = Query(...),
    store_id: uuid.UUID | None = Query(None),
    user: User = Depends(require_permission("dashboard")),
    db: Session = Depends(get_db),
):
    """Kâr marjı raporu: ciro − (ürün maliyeti + komisyon + kargo + paketleme).

    Ürün maliyeti eşleşmesi ADA göre (LineItem.title ↔ CatalogProduct.title);
    eşleşmeyen kalemlerde varsayılan birim maliyet kullanılır ve kaç kalemin
    varsayılana düştüğü raporda ayrıca bildirilir (körlük yaratmasın)."""
    if end < start:
        raise HTTPException(422, "Bitiş tarihi başlangıçtan önce olamaz")
    if (end - start).days > MAX_RANGE_DAYS:
        raise HTTPException(422, f"Aralık en fazla {MAX_RANGE_DAYS} gün olabilir")

    from app.models import CatalogProduct

    tid = user.tenant_id
    start_dt, end_dt = _gun.aralik(start, end)   # İstanbul günleri (bkz. services/gun)
    ayar = _cost_settings(db, tid, store_id)

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

    # ⚠ Kâr hesabı YALNIZ TL siparişleri: maliyetler TL, USD bayi siparişini
    # katmak ya ciroyu (kur yok) ya maliyeti çarpıtırdı. Dışarıda kalan USD
    # siparişi sayısı yanıtta açıkça söylenir.
    from app.services import ciro as _ciro_svc
    _usd_disarida = int(db.scalar(select(sql_func.count(Order.id)).where(
        *base_conds, ~_ciro_svc.tl_siparis_mi())) or 0)
    base_conds.append(_ciro_svc.tl_siparis_mi())
    total_price = _ciro_svc.tl_tutar()
    row = db.execute(
        select(sql_func.coalesce(sql_func.sum(total_price), 0), sql_func.count(Order.id))
        .where(*base_conds)
    ).one()
    revenue = float(row[0] or 0)
    orders_count = int(row[1] or 0)

    # Ürün adı → birim maliyet (yalnız maliyeti girilmiş ürünler)
    cost_map = {
        (t or "").strip().casefold(): float(c)
        for t, c in db.execute(
            select(CatalogProduct.title, CatalogProduct.cost_price)
            .where(CatalogProduct.tenant_id == tid, CatalogProduct.cost_price.isnot(None))
        ).all()
    }

    # Satılan kalemler: ada göre grupla (adet + maliyet + ciro payı)
    li_rows = db.execute(
        select(LineItem.title, sql_func.sum(LineItem.quantity))
        .join(Order, LineItem.order_id == Order.id)
        .where(*base_conds).group_by(LineItem.title)
    ).all()

    cogs = 0.0
    units = 0
    varsayilana_dusen = 0
    urunler = []
    for title, adet in li_rows:
        adet = int(adet or 0)
        key = (title or "").strip().casefold()
        birim = cost_map.get(key)
        if birim is None:
            birim = ayar["unit_cost"]
            varsayilana_dusen += adet
        cogs += birim * adet
        units += adet
        urunler.append({"title": title or "—", "quantity": adet,
                        "unit_cost": round(birim, 2), "cost": round(birim * adet, 2),
                        "cost_source": "urun" if key in cost_map else "varsayilan"})

    commission = revenue * ayar["commission_pct"] / 100
    shipping = ayar["shipping_cost"] * orders_count
    packaging = ayar["packaging_cost"] * orders_count
    giderler = cogs + commission + shipping + packaging
    profit = revenue - giderler

    urunler.sort(key=lambda x: x["cost"], reverse=True)
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "revenue": round(revenue, 2),
        "orders_count": orders_count,
        "units": units,
        "costs": {
            "cogs": round(cogs, 2),
            "commission": round(commission, 2),
            "shipping": round(shipping, 2),
            "packaging": round(packaging, 2),
            "total": round(giderler, 2),
        },
        "profit": round(profit, 2),
        "margin_pct": round(100 * profit / revenue, 1) if revenue else 0.0,
        "profit_per_order": round(profit / orders_count, 2) if orders_count else 0.0,
        "haric_usd_siparis": _usd_disarida,
        "settings": ayar,
        # Maliyeti girilmemiş kalemler varsayılana düştü — panelde uyarı çıkar
        "fallback_units": varsayilana_dusen,
        "top_cost_products": urunler[:15],
    }


@router.get("/export.csv")
def analytics_export(
    start: date = Query(...),
    end: date = Query(...),
    store_id: uuid.UUID | None = Query(None),
    user: User = Depends(require_permission("dashboard")),
    db: Session = Depends(get_db),
):
    """Günlük satış raporu CSV — summary ile aynı kurallar (iptal/iade hariç)."""
    import csv
    import io

    from fastapi.responses import StreamingResponse

    data = analytics_summary(start=start, end=end, store_id=store_id, user=user, db=db)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["gun", "ciro_try", "siparis_adedi"])
    for row in data["daily"]:
        w.writerow([row["gun"], row["tutar"], row["adet"]])
    w.writerow([])
    w.writerow(["TOPLAM", data["revenue"], data["orders_count"]])
    w.writerow(["ortalama_sepet", data["aov"], ""])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=satis-raporu-{start}-{end}.csv"},
    )


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
    start_today = _gun.gun_basi(_gun.bugun(now))
    m15 = now - timedelta(minutes=15)
    from app.services import ciro as _ciro_svc
    total_price = _ciro_svc.tl_tutar()
    usd_price = _ciro_svc.usd_tutar()

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
                   sql_func.coalesce(sql_func.sum(total_price), 0),
                   sql_func.coalesce(sql_func.sum(usd_price), 0))
            .where(*ciro_conds, Order.created_at_platform >= since)
        ).one()
        return {"orders": int(row[0] or 0), "revenue": float(row[1] or 0),
                "revenue_usd": float(row[2] or 0)}

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
