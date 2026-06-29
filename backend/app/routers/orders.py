"""
Sipariş yönetimi — /api/orders/*

Endpoint'ler:
- POST   /api/orders/fetch          → mağazadan sipariş çek + DB'ye upsert
- GET    /api/orders                → listele (filterli + tab'li + paginated)
- GET    /api/orders/_tab_counts    → tab sayaçları (Paket 18)
- GET    /api/orders/_stats         → özet istatistikler
- GET    /api/orders/{id}           → detay (line items dahil)
- DELETE /api/orders/{id}           → tek sipariş sil
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, time, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import case, desc, func as sql_func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.adapters import get_adapter
from app.auth.dependencies import get_current_user, require_any_permission, require_permission
from app.database import get_db
from app.models import LineItem, Mold, MoldItem, Order, OrderStatusHistory, Store, User
from app.stages import is_valid_stage

router = APIRouter(prefix="/api/orders", tags=["orders"],
    dependencies=[Depends(require_any_permission("siparisler", "bayii", "stok"))],
)

# Acil eşik: kaç gün geçince "Acil" sayılır
ACIL_THRESHOLD_DAYS = 5

TAB_KEYS = ["tumu", "acil", "barkod", "tedarik", "kaliplanmis", "kalip_bekliyor", "tamamlandi"]


# ─── Schemas ─────────────────────────────────────────────────
class FetchRequest(BaseModel):
    store_id: uuid.UUID


class FetchResponse(BaseModel):
    success: bool
    store_id: uuid.UUID
    fetched_count: int
    new_count: int
    updated_count: int
    duration_seconds: float
    message: str


class LineItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    variant_title: str | None
    quantity: int
    product_id: str | None
    sku: str | None
    properties: list[dict[str, Any]]
    is_kaliba_eklendi: bool = False
    is_hazir: bool = False
    tedarik_status: str = "bekliyor"
    molds: list[dict] = []  # [{id, kod}] — bu kalemin eklendiği kalıp(lar)


class OrderListItem(BaseModel):
    """Liste için kompakt sipariş."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    store_id: uuid.UUID
    external_id: str
    order_number: str
    name: str | None
    fulfillment_status: str | None
    financial_status: str | None
    cancelled_at: datetime | None = None
    customer_name: str | None
    created_at_platform: datetime | None
    fetched_at: datetime
    kargo_deadline: datetime | None = None
    item_count: int = 0
    kalipta_count: int = 0
    total_li_count: int = 0
    mold_kodlari: list[str] = []
    molds: list[dict] = []  # [{id, kod}] — tıklanabilir kalıp linkleri
    is_acil: bool = False
    kalip_haric: bool = False
    current_stage: int = 1


class OrderDetail(OrderListItem):
    """Detay sayfası için — line items dahil."""
    customer_email: str | None
    note: str | None
    tags: str | None
    line_items: list[LineItemResponse]
    raw: dict


# ─── Yardımcılar ─────────────────────────────────────────────
def _extract_customer_name(raw: dict) -> str | None:
    customer = raw.get("customer") or {}
    first = customer.get("first_name") or ""
    last = customer.get("last_name") or ""
    full = f"{first} {last}".strip()
    if full:
        return full
    addr = raw.get("shipping_address") or {}
    name = addr.get("name") or f"{addr.get('first_name', '')} {addr.get('last_name', '')}".strip()
    return name or None


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _store_sla_days(store: Store | None) -> int | None:
    """Mağaza config'inden SLA (kargo sözü) gün sayısı. Yoksa None."""
    if not store or not isinstance(store.config, dict):
        return None
    val = store.config.get("sla_days")
    try:
        n = int(val)
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def _compute_deadline(created_at_platform: datetime | None, sla_days: int | None) -> datetime | None:
    """created_at_platform + sla_days. Eksik veri varsa None."""
    if not created_at_platform or not sla_days:
        return None
    return created_at_platform + timedelta(days=sla_days)


def _upsert_order(db: Session, *, tenant_id, store_id, raw: dict) -> tuple[Order, bool, bool]:
    """Raw order dict'ten Order kaydı oluştur veya güncelle."""
    external_id = str(raw.get("id", ""))
    if not external_id:
        raise ValueError("raw order'da id yok")

    # Kargo sözü hesabı için mağaza config (db.get identity-map ile cache'lenir)
    _store = db.get(Store, store_id)
    _sla_days = _store_sla_days(_store)

    existing = db.scalar(
        select(Order).where(
            Order.store_id == store_id,
            Order.external_id == external_id,
        )
    )

    customer = raw.get("customer") or {}
    order_data = {
        "tenant_id": tenant_id,
        "store_id": store_id,
        "external_id": external_id,
        "order_number": str(raw.get("order_number", "")),
        "name": raw.get("name"),
        "fulfillment_status": raw.get("fulfillment_status"),
        "financial_status": raw.get("financial_status"),
        "cancelled_at": _parse_iso(raw.get("cancelled_at")),
        "customer_name": _extract_customer_name(raw),
        "customer_email": customer.get("email") or raw.get("email"),
        "created_at_platform": _parse_iso(raw.get("created_at")),
        "note": raw.get("note"),
        "tags": raw.get("tags"),
        "raw": raw,
    }

    _deadline = _compute_deadline(order_data["created_at_platform"], _sla_days)

    if existing:
        is_new = False
        was_updated = False
        for k, v in order_data.items():
            if k in ("tenant_id", "store_id", "external_id"):
                continue
            if getattr(existing, k) != v:
                setattr(existing, k, v)
                was_updated = True
        # Kargo sözü: yalnızca boşsa doldur (elle override'ı sync ezmesin)
        if existing.kargo_deadline is None and _deadline is not None:
            existing.kargo_deadline = _deadline
        order = existing
        # Sync sirasinda line item'lar silinip yeniden olusturuluyor; design bağlamasini
        # (assigned_design_id) Shopify line item id'si (external_id) bazinda koru.
        _preserved_assign = {}
        _preserved_ko = {}
        _preserved_flow = {}  # uretim akisi alanlari (is_kaliba_eklendi vb) — cift baski riskini onler
        for _li in order.line_items:
            if _li.external_id:
                if _li.assigned_design_id:
                    _preserved_assign[_li.external_id] = _li.assigned_design_id
                if getattr(_li, "is_kisiye_ozel", None):
                    _preserved_ko[_li.external_id] = _li.is_kisiye_ozel
                _preserved_flow[_li.external_id] = {
                    "is_kaliba_eklendi": getattr(_li, "is_kaliba_eklendi", False),
                    "is_hazir": getattr(_li, "is_hazir", False),
                    "tedarik_status": getattr(_li, "tedarik_status", "bekliyor"),
                    "device_model_override": getattr(_li, "device_model_override", None),
                    "birincil_renk": getattr(_li, "birincil_renk", None),
                    "ikincil_renk": getattr(_li, "ikincil_renk", None),
                    "ucuncu_renk": getattr(_li, "ucuncu_renk", None),
                }
        order.line_items.clear()
        db.flush()
    else:
        is_new = True
        was_updated = False
        order = Order(**order_data)
        if _deadline is not None:
            order.kargo_deadline = _deadline
        db.add(order)
        db.flush()

    _preserved_assign = locals().get("_preserved_assign", {})
    _preserved_ko = locals().get("_preserved_ko", {})
    _preserved_flow = locals().get("_preserved_flow", {})
    for pos, li_raw in enumerate(raw.get("line_items", [])):
        _ext = str(li_raw.get("id", "")) if li_raw.get("id") else None
        li = LineItem(
            tenant_id=tenant_id,
            order_id=order.id,
            external_id=_ext,
            product_id=str(li_raw.get("product_id", "")) if li_raw.get("product_id") else None,
            variant_id=str(li_raw.get("variant_id", "")) if li_raw.get("variant_id") else None,
            title=li_raw.get("title", ""),
            variant_title=li_raw.get("variant_title"),
            sku=li_raw.get("sku"),
            quantity=li_raw.get("quantity", 1),
            position=pos,
            properties=li_raw.get("properties") or [],
            raw=li_raw,
        )
        # Sync oncesi uretim akisi alanlarini koru (is_kaliba_eklendi -> cift baski riskini onler)
        if _ext and _ext in locals().get("_preserved_flow", {}):
            _fl = _preserved_flow[_ext]
            li.is_kaliba_eklendi = _fl["is_kaliba_eklendi"]
            li.is_hazir = _fl["is_hazir"]
            li.tedarik_status = _fl["tedarik_status"]
            li.device_model_override = _fl["device_model_override"]
            li.birincil_renk = _fl["birincil_renk"]
            li.ikincil_renk = _fl["ikincil_renk"]
            li.ucuncu_renk = _fl["ucuncu_renk"]
        # Sync oncesi bağlama varsa koru (PDF/design line item'a bağli kalsin)
        if _ext and _ext in _preserved_assign:
            li.assigned_design_id = _preserved_assign[_ext]
        if _ext and _ext in _preserved_ko:
            li.is_kisiye_ozel = _preserved_ko[_ext]
        db.add(li)

    return order, is_new, was_updated


# ─── Tab filtreleri (Paket 18) ───────────────────────────────
def _build_tab_filter(q, tab: str):
    """Order üzerinde base query'ye tab filtresini ekle."""
    if tab == "acil":
        threshold = datetime.now(UTC) - timedelta(days=ACIL_THRESHOLD_DAYS)
        q = q.where(
            Order.cancelled_at.is_(None),
            (Order.fulfillment_status != "fulfilled") | (Order.fulfillment_status.is_(None)),
            Order.created_at_platform < threshold,
        )
    elif tab == "barkod":
        # En az bir line item hazır değil (barkod basılması bekleyen)
        q = q.where(
            Order.id.in_(select(LineItem.order_id).where(LineItem.is_hazir == False))
        )
    elif tab == "tedarik":
        # En az bir line item tedarik bekliyor
        q = q.where(
            Order.id.in_(select(LineItem.order_id).where(LineItem.tedarik_status == "bekliyor"))
        )
    elif tab == "kaliplanmis":
        # Tüm line item'lar kalıba eklendi (en az 1 line item olmalı)
        all_in_mold = (
            select(LineItem.order_id)
            .group_by(LineItem.order_id)
            .having(
                sql_func.count(LineItem.id)
                == sql_func.sum(case(
                    ((LineItem.is_kaliba_eklendi == True) | (LineItem.is_hazir == True), 1), else_=0))
            )
            .having(sql_func.count(LineItem.id) > 0)
        )
        q = q.where(Order.id.in_(all_in_mold))
    elif tab == "kalip_bekliyor":
        # En az bir line item kalıba eklenmemiş + hazır değil + tamamlanmamış + iptal değil
        has_pending = select(LineItem.order_id).where(
            LineItem.is_kaliba_eklendi == False, LineItem.is_hazir == False)
        q = q.where(
            Order.id.in_(has_pending),
            Order.cancelled_at.is_(None),
            (Order.fulfillment_status != "fulfilled") | (Order.fulfillment_status.is_(None)),
        )
    elif tab == "tamamlandi":
        q = q.where(
            (Order.fulfillment_status == "fulfilled") | (Order.cancelled_at.is_not(None))
        )
    # "tumu" → filtre yok
    return q


# ─── Endpoints ───────────────────────────────────────────────
@router.post("/fetch", response_model=FetchResponse)
def fetch_orders(
    req: FetchRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mağazadan tüm aktif siparişleri çek + DB'ye upsert."""
    store = db.scalar(
        select(Store).where(Store.id == req.store_id, Store.tenant_id == user.tenant_id)
    )
    if not store:
        raise HTTPException(status_code=404, detail="Mağaza bulunamadı")
    if not store.is_active:
        raise HTTPException(status_code=400, detail="Mağaza pasif")

    start = datetime.now(UTC)
    try:
        adapter = get_adapter(store)
        orders_raw = adapter.get_all_active_orders(limit=250)
    except Exception as e:
        raise HTTPException(
            status_code=502, detail=f"Mağazadan veri alınamadı: {str(e)[:200]}"
        ) from e

    new_count = 0
    updated_count = 0
    errors = []
    for raw in orders_raw:
        try:
            _, is_new, was_updated = _upsert_order(
                db, tenant_id=user.tenant_id, store_id=store.id, raw=raw
            )
            if is_new:
                new_count += 1
            elif was_updated:
                updated_count += 1
        except Exception as e:
            errors.append(f"Sipariş {raw.get('id', '?')}: {str(e)[:100]}")

    store.last_fetched_at = datetime.now(UTC)
    db.commit()

    duration = (datetime.now(UTC) - start).total_seconds()
    msg_parts = [f"{len(orders_raw)} sipariş çekildi"]
    if new_count:
        msg_parts.append(f"{new_count} yeni")
    if updated_count:
        msg_parts.append(f"{updated_count} güncellendi")
    if errors:
        msg_parts.append(f"{len(errors)} hata")

    return FetchResponse(
        success=True,
        store_id=store.id,
        fetched_count=len(orders_raw),
        new_count=new_count,
        updated_count=updated_count,
        duration_seconds=round(duration, 2),
        message=" · ".join(msg_parts),
    )


@router.get("/_tab_counts", response_model=dict)
def tab_counts(
    store_id: uuid.UUID | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Her sekme için sipariş sayısı."""
    base = select(Order.id).where(Order.tenant_id == user.tenant_id)
    if store_id:
        base = base.where(Order.store_id == store_id)

    counts = {}
    for tab in TAB_KEYS:
        q = _build_tab_filter(base, tab)
        c = db.scalar(select(sql_func.count()).select_from(q.subquery())) or 0
        counts[tab] = c
    return counts


@router.get("", response_model=dict)
def list_orders(
    store_id: uuid.UUID | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    tab: str | None = Query(None),
    search: str | None = Query(None),
    deadline: str | None = Query(None),  # bugun | overdue | soon
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Siparişleri listele. Filtreler: store_id, status, tab (Paket 18), search, deadline."""
    q = select(Order).where(
        Order.tenant_id == user.tenant_id,
        Order.is_telafi == False,  # noqa: E712  telafiler kendi panelinde
    )
    if store_id:
        q = q.where(Order.store_id == store_id)
    if status_filter:
        q = q.where(Order.fulfillment_status == status_filter)
    if tab and tab in TAB_KEYS and tab != "tumu":
        q = _build_tab_filter(q, tab)
    if deadline:
        # Kargo sözü filtresi — yalnızca GERÇEK açık sipariş: iptal/iade değil,
        # Shopify'da fulfilled (kargolanmış) değil, pipeline'da da stage < 8.
        # (Sadece stage<8 yetersizdi: pipeline'a hiç girmemis ama Shopify'da
        #  fulfilled olan eski siparisler yanlislikla sayiliyordu.)
        now = datetime.now(UTC)
        _dl_base = (
            Order.kargo_deadline.isnot(None),
            Order.cancelled_at.is_(None),
            (Order.fulfillment_status != "fulfilled") | (Order.fulfillment_status.is_(None)),
            (Order.financial_status != "refunded") | (Order.financial_status.is_(None)),
            Order.current_stage < 8,
        )
        if deadline == "overdue":
            q = q.where(*_dl_base, Order.kargo_deadline < now)
        elif deadline == "bugun":
            _end = datetime.combine(now.date(), time.max, tzinfo=UTC)
            q = q.where(*_dl_base, Order.kargo_deadline >= now, Order.kargo_deadline <= _end)
        elif deadline == "soon":
            _soon = now + timedelta(days=2)
            q = q.where(*_dl_base, Order.kargo_deadline >= now, Order.kargo_deadline <= _soon)
    if search:
        like = f"%{search}%"
        q = q.where(
            (Order.order_number.ilike(like))
            | (Order.customer_name.ilike(like))
            | (Order.customer_email.ilike(like))
        )

    count_q = select(sql_func.count()).select_from(q.subquery())
    total = db.scalar(count_q) or 0

    q = q.order_by(desc(Order.created_at_platform), desc(Order.fetched_at))
    q = q.limit(per_page).offset((page - 1) * per_page)

    rows = db.scalars(q.options(selectinload(Order.line_items))).all()

    # Sipariş -> kalıp(lar) {id, kod}. order_number stabil (line_item_id senkronda NULL olur).
    mold_links_by_onum: dict = {}
    if rows:
        onums = [str(o.order_number) for o in rows if o.order_number is not None]
        if onums:
            for onum, mid, kod in db.execute(
                select(MoldItem.order_number, Mold.id, Mold.kod)
                .join(Mold, Mold.id == MoldItem.mold_id)
                .where(Mold.tenant_id == user.tenant_id, MoldItem.order_number.in_(onums))
                .distinct()
            ).all():
                lst = mold_links_by_onum.setdefault(str(onum), [])
                if not any(x["id"] == str(mid) for x in lst):
                    lst.append({"id": str(mid), "kod": kod})

    acil_threshold = datetime.now(UTC) - timedelta(days=ACIL_THRESHOLD_DAYS)

    # Mağaza adı haritası (bayii dahil — "?" sorununu önler)
    store_names = {
        s.id: s.name for s in db.scalars(
            select(Store).where(Store.tenant_id == user.tenant_id)
        )
    }

    items = []
    for o in rows:
        item = OrderListItem.model_validate(o).model_dump(mode="json")
        item["store_name"] = store_names.get(o.store_id)
        item["item_count"] = len(o.line_items)
        item["total_li_count"] = len(o.line_items)
        item["kalipta_count"] = sum(
            1 for li in o.line_items if getattr(li, "is_kaliba_eklendi", False)
        )
        _links = sorted(mold_links_by_onum.get(str(o.order_number), []), key=lambda m: m["kod"] or "")
        item["molds"] = _links
        item["mold_kodlari"] = [m["kod"] for m in _links]
        _ki = o.kargo_info or {}
        item["kargo_status"] = _ki.get("status")
        item["kargo_takip"] = _ki.get("takip_no")
        item["kargo_firma"] = _ki.get("handler_name")
        item["is_acil"] = bool(
            o.cancelled_at is None
            and (o.fulfillment_status != "fulfilled")
            and o.created_at_platform is not None
            and o.created_at_platform < acil_threshold
        )
        items.append(item)

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if total else 0,
    }


@router.get("/_stats", response_model=dict)
def stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Dashboard için özet sayılar."""
    total = db.scalar(
        select(sql_func.count(Order.id)).where(Order.tenant_id == user.tenant_id)
    ) or 0

    by_status_rows = db.execute(
        select(Order.fulfillment_status, sql_func.count(Order.id))
        .where(Order.tenant_id == user.tenant_id)
        .group_by(Order.fulfillment_status)
    ).all()
    by_status = {row[0] or "null": row[1] for row in by_status_rows}

    by_store_rows = db.execute(
        select(Store.name, sql_func.count(Order.id))
        .join(Order, Order.store_id == Store.id)
        .where(Order.tenant_id == user.tenant_id)
        .group_by(Store.name)
    ).all()
    by_store = {row[0]: row[1] for row in by_store_rows}

    return {"total": total, "by_status": by_status, "by_store": by_store}


@router.get("/_trash", response_model=dict)
def list_trash(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Silinmis (cop kutusu) siparisler — telafiler haric."""
    rows = db.scalars(
        select(Order)
        .where(
            Order.tenant_id == user.tenant_id,
            Order.deleted_at.isnot(None),
            Order.is_telafi == False,  # noqa: E712
        )
        .order_by(desc(Order.deleted_at))
        .limit(200)
        .execution_options(include_deleted=True)
    ).all()
    return {"items": [
        {
            "id": str(o.id), "order_number": o.order_number,
            "customer_name": o.customer_name,
            "deleted_at": o.deleted_at.isoformat() if o.deleted_at else None,
        }
        for o in rows
    ]}


@router.get("/_export")
def export_orders(
    format: str = Query("xlsx", pattern="^(xlsx|csv)$"),
    store_id: uuid.UUID | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Siparişleri Excel (.xlsx) veya CSV olarak indir."""
    import io
    from fastapi.responses import StreamingResponse
    from app.services.export_service import build_xlsx, build_csv

    tid = user.tenant_id
    kwargs = dict(store_id=store_id, date_from=date_from, date_to=date_to)

    if format == "xlsx":
        data = build_xlsx(db, tid, **kwargs)
        return StreamingResponse(
            io.BytesIO(data),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=siparisler.xlsx"},
        )
    data = build_csv(db, tid, **kwargs)
    return StreamingResponse(
        io.BytesIO(data),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=siparisler.csv"},
    )


# ═════════════════════════════════════════════════════════════════════
# Toplu işlemler — çoklu seçim
# ═════════════════════════════════════════════════════════════════════

# order_detail.VALID_LISTS ile aynı (iç etiketler)
_BULK_VALID_LISTS = {"isaretlenenler", "bugun", "sonra", "kontrol", "export", "baski"}

_BULK_ACTIONS = {"stage", "acil", "acil_kaldir", "list_add", "list_remove", "delete"}


class BulkRequest(BaseModel):
    ids: list[uuid.UUID]
    action: str
    value: Any | None = None   # stage için int, list_* için etiket adı


def _bulk_log(db, order, user, action, from_stage=None, to_stage=None, note=None):
    db.add(OrderStatusHistory(
        tenant_id=order.tenant_id, order_id=order.id,
        from_stage=from_stage, to_stage=to_stage, action=action, note=note,
        created_by=user.full_name or user.email,
    ))


def _adjust_dealer_debt(db, order, *, reverse: bool):
    """Bayi siparişinin cari borcunu sil(reverse=True)/geri al(reverse=False).

    Sil-geri al kesin sıralı (silinmiş tekrar silinemez, silinmeden geri alınamaz)
    olduğundan bakiye tutarlı kalır. Her işlem bir 'duzeltme' hareketi yazar.
    """
    from decimal import Decimal as _Dec
    from app.models import Dealer as _Dealer, DealerTransaction as _DTx

    txs = db.scalars(
        select(_DTx).where(_DTx.ref_order_id == order.id, _DTx.kind == "siparis")
    ).all()
    for tx in txs:
        dealer = db.scalar(select(_Dealer).where(_Dealer.id == tx.dealer_id))
        if not dealer:
            continue
        delta = -_Dec(str(tx.amount)) if reverse else _Dec(str(tx.amount))
        cur = (tx.currency or "TRY").upper()
        if cur == "USD":
            new_bal = _Dec(str(dealer.balance_usd or 0)) + delta
            dealer.balance_usd = new_bal
        else:
            new_bal = _Dec(str(dealer.balance or 0)) + delta
            dealer.balance = new_bal
        _desc = (f"Sipariş #{order.order_number} silindi — borç iptali" if reverse
                 else f"Sipariş #{order.order_number} geri alındı — borç tekrar")
        db.add(_DTx(
            tenant_id=order.tenant_id, dealer_id=dealer.id,
            amount=delta, kind="duzeltme", currency=cur,
            description=_desc, ref_order_id=order.id, balance_after=new_bal,
        ))


@router.post("/_bulk", response_model=dict)
def bulk_action(
    payload: BulkRequest,
    user: User = Depends(require_permission("siparisler")),
    db: Session = Depends(get_db),
):
    """Birden çok sipariş üzerinde toplu işlem (aşama/acil/etiket/sil).

    Telafiler bu işlemin dışındadır (kendi panelinde yönetilir).
    Tüm değişiklikler tek transaction'da uygulanır ve geçmişe loglanır.
    """
    if payload.action not in _BULK_ACTIONS:
        raise HTTPException(status_code=400, detail="Geçersiz işlem")
    if not payload.ids:
        raise HTTPException(status_code=400, detail="Sipariş seçilmedi")
    if len(payload.ids) > 500:
        raise HTTPException(status_code=400, detail="Tek seferde en fazla 500 sipariş")

    # stage doğrulaması
    stage_val = None
    if payload.action == "stage":
        try:
            stage_val = int(payload.value)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Geçersiz aşama")
        if not is_valid_stage(stage_val):
            raise HTTPException(status_code=400, detail="Geçersiz aşama numarası")

    # etiket doğrulaması
    label_val = None
    if payload.action in ("list_add", "list_remove"):
        label_val = str(payload.value or "").strip()
        if label_val not in _BULK_VALID_LISTS:
            raise HTTPException(status_code=400, detail="Geçersiz etiket")

    orders = db.scalars(
        select(Order).where(
            Order.id.in_(payload.ids),
            Order.tenant_id == user.tenant_id,
            Order.is_telafi.is_(False),
        )
    ).all()

    affected = 0
    for order in orders:
        if payload.action == "stage":
            if order.current_stage != stage_val:
                old = order.current_stage
                order.current_stage = stage_val
                _bulk_log(db, order, user, "stage_change", from_stage=old, to_stage=stage_val,
                          note="Toplu işlem")
                affected += 1
        elif payload.action == "acil":
            if not order.is_acil:
                order.is_acil = True
                _bulk_log(db, order, user, "acil", note="Toplu işlem")
                affected += 1
        elif payload.action == "acil_kaldir":
            if order.is_acil:
                order.is_acil = False
                _bulk_log(db, order, user, "acil_kaldir", note="Toplu işlem")
                affected += 1
        elif payload.action == "list_add":
            lists = list(order.internal_lists or [])
            if label_val not in lists:
                lists.append(label_val)
                order.internal_lists = lists
                _bulk_log(db, order, user, "list_add", note=label_val)
                affected += 1
        elif payload.action == "list_remove":
            lists = list(order.internal_lists or [])
            if label_val in lists:
                lists.remove(label_val)
                order.internal_lists = lists
                _bulk_log(db, order, user, "list_remove", note=label_val)
                affected += 1
        elif payload.action == "delete":
            if order.deleted_at is None:
                order.deleted_at = datetime.now(UTC)
                _adjust_dealer_debt(db, order, reverse=True)
                affected += 1

    db.commit()
    return {"ok": True, "affected": affected, "requested": len(payload.ids)}


@router.post("/_recompute-deadlines", response_model=dict)
def recompute_deadlines(
    overwrite: bool = Query(False),
    user: User = Depends(require_permission("siparisler")),
    db: Session = Depends(get_db),
):
    """Mevcut siparişlerin kargo sözü tarihini store SLA'sına göre (yeniden) hesapla.

    overwrite=false (varsayılan): yalnızca kargo_deadline'ı boş olanları doldurur.
    overwrite=true: tümünü store SLA'sına göre yeniden yazar (elle override'ları da ezer).
    """
    # store sla_days haritası (tek query)
    stores = db.scalars(select(Store).where(Store.tenant_id == user.tenant_id)).all()
    sla_by_store = {s.id: _store_sla_days(s) for s in stores}

    orders = db.scalars(
        select(Order).where(Order.tenant_id == user.tenant_id)
    ).all()

    updated = 0
    for o in orders:
        sla = sla_by_store.get(o.store_id)
        if not sla:
            continue
        if o.kargo_deadline is not None and not overwrite:
            continue
        new_dl = _compute_deadline(o.created_at_platform, sla)
        if new_dl and o.kargo_deadline != new_dl:
            o.kargo_deadline = new_dl
            updated += 1

    db.commit()
    return {"ok": True, "updated": updated, "total": len(orders)}


def _nk_model(s: str | None) -> str:
    try:
        from app.services import phone_models as _pm
        return _pm.normalize_key(s or "")
    except Exception:  # noqa: BLE001
        return (s or "").strip().lower()


def _molds_by_line_item(db: Session, tenant_id, order) -> dict:
    """order.line_items -> {line_item_id: [{id, kod}]}. Sipariş senkronu line_item_id'yi
    NULL'a düşürdüğü için kademeli eşleşme: line_item_id > (order_no+design_code) > (order_no+model)."""
    from app.services.mold_planner import extract_phone_model
    onum = str(order.order_number) if order.order_number is not None else None
    if not onum:
        return {}
    rows = db.execute(
        select(MoldItem, Mold.id, Mold.kod)
        .join(Mold, Mold.id == MoldItem.mold_id)
        .where(Mold.tenant_id == tenant_id, MoldItem.order_number == onum)
    ).all()
    if not rows:
        return {}
    li_by_id = {li.id: li for li in order.line_items}
    li_by_code: dict = {}
    li_by_model: dict = {}
    for li in order.line_items:
        code = li.assigned_design.code if getattr(li, "assigned_design", None) else None
        if code:
            li_by_code.setdefault(code, []).append(li)
        mk = _nk_model(extract_phone_model(li))
        if mk:
            li_by_model.setdefault(mk, []).append(li)
    out: dict = {}
    for mi, mid, kod in rows:
        target = None
        if mi.line_item_id and mi.line_item_id in li_by_id:
            target = li_by_id[mi.line_item_id]
        elif mi.design_code and li_by_code.get(mi.design_code):
            target = li_by_code[mi.design_code][0]
        elif mi.model and li_by_model.get(_nk_model(mi.model)):
            target = li_by_model[_nk_model(mi.model)][0]
        if not target:
            continue
        lst = out.setdefault(target.id, [])
        if not any(x["id"] == str(mid) for x in lst):
            lst.append({"id": str(mid), "kod": kod})
    return out


@router.post("/{order_id}/line-items/{li_id}/remove-from-molds", response_model=None)
def remove_line_item_from_molds(
    order_id: uuid.UUID,
    li_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Kalemi eklendiği kalıp(lar)dan çıkar (Hazır işaretlenince). Kademeli eşleşme;
    en kesin tier (line_item_id > design_code > model) kullanılır. is_kaliba_eklendi=False."""
    from app.services import mold_planner
    from app.services.mold_planner import extract_phone_model
    order = db.scalar(
        select(Order).where(Order.id == order_id, Order.tenant_id == user.tenant_id)
        .options(selectinload(Order.line_items).selectinload(LineItem.assigned_design))
    )
    if not order:
        raise HTTPException(status_code=404, detail="Sipariş bulunamadı")
    li = next((x for x in order.line_items if x.id == li_id), None)
    if not li:
        raise HTTPException(status_code=404, detail="Kalem bulunamadı")
    onum = str(order.order_number) if order.order_number is not None else None
    code = li.assigned_design.code if getattr(li, "assigned_design", None) else None
    mk = _nk_model(extract_phone_model(li))
    mis = db.scalars(select(MoldItem).where(
        MoldItem.tenant_id == user.tenant_id, MoldItem.order_number == onum)).all() if onum else []
    by_id = [mi for mi in mis if li.id and mi.line_item_id == li.id]
    by_code = [mi for mi in mis if code and mi.design_code == code]
    by_model = [mi for mi in mis if mk and _nk_model(mi.model) == mk]
    targets = by_id or by_code or by_model
    affected = set()
    for mi in targets:
        affected.add(mi.mold_id)
        db.delete(mi)
    if targets:
        db.flush()
        for mid in affected:
            mo = db.get(Mold, mid)
            if not mo:
                continue
            items = db.scalars(select(MoldItem).where(MoldItem.mold_id == mid)).all()
            mo.kilif_sayisi = len(items)
            if items:
                placed = mold_planner.pr.assign_slots(
                    [{"kod": x.kalip_kodu, "model": x.model, "_ref": x} for x in items])
                for d in placed:
                    d["_ref"].slot_index = d["slot_index"]
    li.is_kaliba_eklendi = False
    db.commit()
    return {"ok": True, "removed": len(targets)}


@router.get("/{order_id}", response_model=OrderDetail)
def get_order(
    order_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = db.scalar(
        select(Order)
        .where(Order.id == order_id, Order.tenant_id == user.tenant_id)
        .options(selectinload(Order.line_items).selectinload(LineItem.assigned_design))
    )
    if not order:
        raise HTTPException(status_code=404, detail="Sipariş bulunamadı")

    data = OrderDetail.model_validate(order).model_dump(mode="json")
    data["item_count"] = len(order.line_items)
    data["total_li_count"] = len(order.line_items)
    data["kalipta_count"] = sum(
        1 for li in order.line_items if getattr(li, "is_kaliba_eklendi", False)
    )
    # Kalem -> eklendiği kalıp(lar). Sipariş senkronu line_item_id'yi NULL'a düşürdüğü
    # için kademeli eşleşme: line_item_id > (order_number+design_code) > (order_number+model).
    molds_by_li = _molds_by_line_item(db, user.tenant_id, order)

    _li_dicts = []
    for li in order.line_items:
        d = LineItemResponse.model_validate(li).model_dump(mode="json")
        d["molds"] = sorted(molds_by_li.get(li.id, []), key=lambda m: m["kod"] or "")
        _li_dicts.append(d)
    data["line_items"] = _li_dicts

    # Mold kodları (sipariş geneli)
    data["mold_kodlari"] = sorted({m["kod"] for v in molds_by_li.values() for m in v if m["kod"]})

    # is_acil
    acil_threshold = datetime.now(UTC) - timedelta(days=ACIL_THRESHOLD_DAYS)
    data["is_acil"] = bool(
        order.cancelled_at is None
        and order.fulfillment_status != "fulfilled"
        and order.created_at_platform is not None
        and order.created_at_platform < acil_threshold
    )

    return data


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_order(
    order_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Soft-delete: kalici silmek yerine deleted_at isaretler (cop kutusundan geri alinabilir)."""
    order = db.scalar(
        select(Order).where(Order.id == order_id, Order.tenant_id == user.tenant_id)
    )
    if not order:
        raise HTTPException(status_code=404, detail="Sipariş bulunamadı")
    order.deleted_at = datetime.now(UTC)
    _adjust_dealer_debt(db, order, reverse=True)
    db.commit()
    return None


@router.post("/{order_id}/restore", response_model=dict)
def restore_order(
    order_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Silinmis siparisi geri al (deleted_at temizle)."""
    order = db.scalar(
        select(Order)
        .where(Order.id == order_id, Order.tenant_id == user.tenant_id)
        .execution_options(include_deleted=True)
    )
    if not order:
        raise HTTPException(status_code=404, detail="Sipariş bulunamadı")
    order.deleted_at = None
    _adjust_dealer_debt(db, order, reverse=False)  # geri alınınca borcu tekrar uygula
    db.commit()
    return {"ok": True}

# ═════════════════════════════════════════════════════════════════════
# Paket 18 — Manuel Sipariş (WhatsApp/telefon vb.)
# ═════════════════════════════════════════════════════════════════════

class ManualLineItemInput(BaseModel):
    title: str
    design_id: uuid.UUID | None = None
    device_model: str | None = None
    quantity: int = 1
    color: str | None = None
    notes: str | None = None


class ManualOrderRequest(BaseModel):
    dealer_id: uuid.UUID | None = None
    apply_shipping: bool = True
    store_id: uuid.UUID
    external_id: str
    customer_name: str
    customer_phone: str | None = None
    customer_email: str | None = None
    note: str | None = None
    address: str | None = None
    city: str | None = None
    province: str | None = None
    zip: str | None = None
    line_items: list[ManualLineItemInput]


@router.get("/_meta/store-designs", response_model=dict)
def store_designs(
    store_id: uuid.UUID = Query(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manuel sipariş dialog'u için store'un (bayi dahil) kendi tasarım listesi."""
    from app.models import Design
    from app.services import storage as _storage
    designs = db.scalars(
        select(Design)
        .where(Design.store_id == store_id, Design.tenant_id == user.tenant_id)
        .order_by(Design.code)
    ).all()
    return {
        "items": [
            {
                "id": str(d.id),
                "code": d.code,
                "name": d.name,
                "thumbnail_url": _storage.get_thumbnail_url(d.file_path, d.file_format) if d.file_path else None,
                "is_kisiye_ozel": d.is_kisiye_ozel,
                "birincil_renk": d.birincil_renk,
            }
            for d in designs
        ]
    }


class KalipHaricIn(BaseModel):
    haric: bool


@router.patch("/{order_id}/kalip-haric", response_model=dict)
def toggle_kalip_haric(
    order_id: uuid.UUID,
    body: KalipHaricIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Siparisi kalip olusturucudan haric tut / tekrar dahil et."""
    o = db.scalar(select(Order).where(Order.id == order_id, Order.tenant_id == user.tenant_id))
    if not o:
        raise HTTPException(status_code=404, detail="Siparis bulunamadi")
    o.kalip_haric = bool(body.haric)
    db.commit()
    return {"ok": True, "kalip_haric": o.kalip_haric}


@router.post("/manual", response_model=dict)
def create_manual_order(
    req: ManualOrderRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """WhatsApp/telefon gibi platform dışı kanaldan gelen siparişi elle oluştur."""
    from app.models import Design as _Design

    store = db.scalar(
        select(Store).where(Store.id == req.store_id, Store.tenant_id == user.tenant_id)
    )
    if not store:
        raise HTTPException(status_code=404, detail="Mağaza bulunamadı")

    if not req.external_id.strip():
        raise HTTPException(status_code=400, detail="Sipariş kodu zorunlu (örn 'wa_001')")
    if not req.customer_name.strip():
        raise HTTPException(status_code=400, detail="Müşteri adı zorunlu")
    if not req.line_items:
        raise HTTPException(status_code=400, detail="En az bir ürün eklemelisin")

    # Çakışma kontrol — silinmiş (çöp) siparişleri de kapsar (DB unique constraint
    # soft-delete'i bilmez; aksi halde insert IntegrityError -> 500 verirdi).
    existing = db.scalar(
        select(Order).where(
            Order.store_id == req.store_id,
            Order.external_id == req.external_id,
        ).execution_options(include_deleted=True)
    )
    if existing:
        _silinmis = getattr(existing, "deleted_at", None) is not None
        raise HTTPException(
            status_code=400,
            detail=(
                f"Bu sipariş kodu silinmiş bir siparişte kullanılıyor: {req.external_id}. "
                "Farklı bir kod gir ya da çöp kutusundan geri al."
                if _silinmis else
                f"Bu sipariş kodu zaten kullanılıyor: {req.external_id}"
            ),
        )

    # Address dict
    shipping = {}
    if req.address or req.city:
        shipping = {
            "name": req.customer_name,
            "address1": req.address or "",
            "city": req.city or "",
            "province": req.province or "",
            "zip": req.zip or "",
            "phone": req.customer_phone or "",
        }

    order = Order(
        tenant_id=user.tenant_id,
        store_id=req.store_id,
        external_id=req.external_id,
        order_number=req.external_id,
        name=f"#{req.external_id}",
        fulfillment_status=None,
        financial_status=None,
        customer_name=req.customer_name,
        customer_email=req.customer_email,
        created_at_platform=datetime.now(UTC),
        note=req.note,
        tags="manual",
        raw={
            "manual": True,
            "customer_phone": req.customer_phone,
            "shipping_address": shipping,
        },
    )
    db.add(order)
    db.flush()

    # Line items
    for pos, li in enumerate(req.line_items):
        if not (li.title or "").strip():
            raise HTTPException(status_code=400, detail=f"Ürün #{pos+1}: başlık zorunlu")

        design = None
        if li.design_id:
            # Tasarım siparişin mağazasına (bayi dahil) ait olmalı
            design = db.scalar(
                select(_Design).where(
                    _Design.id == li.design_id,
                    _Design.store_id == req.store_id,
                    _Design.tenant_id == user.tenant_id,
                )
            )
            if not design:
                raise HTTPException(status_code=400, detail=f"Ürün #{pos+1}: tasarım bulunamadı")

        if li.device_model:
            from app.services._private import case_dimensions as _cd
            if not _cd.has_spec(li.device_model):
                raise HTTPException(
                    status_code=400,
                    detail=f"Ürün #{pos+1}: model tanınmadı '{li.device_model}'"
                )

        properties = []
        if li.device_model:
            properties.append({"name": "Telefon Modeli", "value": li.device_model})
        if li.notes:
            properties.append({"name": "Not", "value": li.notes})

        db.add(LineItem(
            tenant_id=user.tenant_id,
            order_id=order.id,
            title=li.title.strip(),
            quantity=max(1, int(li.quantity or 1)),
            position=pos,
            properties=properties,
            raw={"manual": True, "notes": li.notes},
            assigned_design_id=design.id if design else None,
            device_model_override=li.device_model,
            birincil_renk=li.color,
        ))

    # Bayii siparisi ise cari borc ekle
    if req.dealer_id:
        from decimal import Decimal as _Dec
        from app.models import Dealer as _Dealer, DealerTransaction as _DTx
        _d = db.scalar(select(_Dealer).where(_Dealer.id == req.dealer_id, _Dealer.tenant_id == user.tenant_id))
        if _d:
            _qty = sum(max(1, int(li.quantity or 1)) for li in req.line_items)
            _unit = _Dec(str(_d.unit_price or 0))
            _ship = _Dec(str(_d.shipping_fee or 0)) if (req.apply_shipping and _d.shipping_fee) else _Dec("0")
            _toplam = _unit * _Dec(_qty) + _ship
            _cur = (getattr(_d, "currency", "TRY") or "TRY").upper()
            if _cur == "USD":
                _newbal = _Dec(str(_d.balance_usd or 0)) + _toplam
                _d.balance_usd = _newbal
            else:
                _newbal = _Dec(str(_d.balance or 0)) + _toplam
                _d.balance = _newbal
            order.raw = {**(order.raw or {}), "dealer_id": str(_d.id), "total_price": str(_toplam), "currency": _cur, "source": "bayii"}
            db.add(_DTx(
                tenant_id=user.tenant_id, dealer_id=_d.id, amount=_toplam, kind="siparis", currency=_cur,
                description=f"Sipariş #{order.external_id} — {_qty} adet" + (f" (+kargo)" if _ship else ""),
                ref_order_id=order.id, balance_after=_newbal,
            ))

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Bu sipariş kodu zaten kullanılıyor (silinmiş olabilir): {req.external_id}. Farklı bir kod dene.",
        )
    return {
        "ok": True,
        "order_id": str(order.id),
        "external_id": order.external_id,
        "message": f"Manuel sipariş oluşturuldu: {order.external_id}",
    }
