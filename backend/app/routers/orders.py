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
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import case, desc, func as sql_func, select
from sqlalchemy.orm import Session, selectinload

from app.adapters import get_adapter
from app.auth.dependencies import get_current_user, require_any_permission
from app.database import get_db
from app.models import LineItem, Mold, MoldItem, Order, Store, User

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
    item_count: int = 0
    kalipta_count: int = 0
    total_li_count: int = 0
    mold_kodlari: list[str] = []
    is_acil: bool = False
    kalip_haric: bool = False


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


def _upsert_order(db: Session, *, tenant_id, store_id, raw: dict) -> tuple[Order, bool, bool]:
    """Raw order dict'ten Order kaydı oluştur veya güncelle."""
    external_id = str(raw.get("id", ""))
    if not external_id:
        raise ValueError("raw order'da id yok")

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

    if existing:
        is_new = False
        was_updated = False
        for k, v in order_data.items():
            if k in ("tenant_id", "store_id", "external_id"):
                continue
            if getattr(existing, k) != v:
                setattr(existing, k, v)
                was_updated = True
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
                == sql_func.sum(case((LineItem.is_kaliba_eklendi == True, 1), else_=0))
            )
            .having(sql_func.count(LineItem.id) > 0)
        )
        q = q.where(Order.id.in_(all_in_mold))
    elif tab == "kalip_bekliyor":
        # En az bir line item kalıba eklenmemiş + tamamlanmamış + iptal değil
        has_pending = select(LineItem.order_id).where(LineItem.is_kaliba_eklendi == False)
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
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Siparişleri listele. Filtreler: store_id, status, tab (Paket 18), search."""
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

    # Tüm sipariş ID'leri için kalıp kodlarını tek query'de topla
    mold_codes_by_order = {}
    if rows:
        order_ids = [o.id for o in rows]
        mc_rows = db.execute(
            select(LineItem.order_id, Mold.kod)
            .join(MoldItem, MoldItem.line_item_id == LineItem.id)
            .join(Mold, Mold.id == MoldItem.mold_id)
            .where(LineItem.order_id.in_(order_ids))
            .distinct()
        ).all()
        for order_id, kod in mc_rows:
            mold_codes_by_order.setdefault(order_id, []).append(kod)
        for k in mold_codes_by_order:
            mold_codes_by_order[k].sort()

    acil_threshold = datetime.now(UTC) - timedelta(days=ACIL_THRESHOLD_DAYS)

    items = []
    for o in rows:
        item = OrderListItem.model_validate(o).model_dump(mode="json")
        item["item_count"] = len(o.line_items)
        item["total_li_count"] = len(o.line_items)
        item["kalipta_count"] = sum(
            1 for li in o.line_items if getattr(li, "is_kaliba_eklendi", False)
        )
        item["mold_kodlari"] = mold_codes_by_order.get(o.id, [])
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


@router.get("/{order_id}", response_model=OrderDetail)
def get_order(
    order_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = db.scalar(
        select(Order)
        .where(Order.id == order_id, Order.tenant_id == user.tenant_id)
        .options(selectinload(Order.line_items))
    )
    if not order:
        raise HTTPException(status_code=404, detail="Sipariş bulunamadı")

    data = OrderDetail.model_validate(order).model_dump(mode="json")
    data["item_count"] = len(order.line_items)
    data["total_li_count"] = len(order.line_items)
    data["kalipta_count"] = sum(
        1 for li in order.line_items if getattr(li, "is_kaliba_eklendi", False)
    )
    data["line_items"] = [
        LineItemResponse.model_validate(li).model_dump(mode="json")
        for li in order.line_items
    ]

    # Mold kodları
    mc_rows = db.execute(
        select(Mold.kod)
        .join(MoldItem, MoldItem.mold_id == Mold.id)
        .join(LineItem, MoldItem.line_item_id == LineItem.id)
        .where(LineItem.order_id == order.id)
        .distinct()
    ).all()
    data["mold_kodlari"] = sorted(r[0] for r in mc_rows)

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
    """Manuel sipariş dialog'u için store'un tasarım listesi."""
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

    # Çakışma kontrol
    existing = db.scalar(
        select(Order).where(
            Order.store_id == req.store_id,
            Order.external_id == req.external_id,
        )
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Bu sipariş kodu zaten kullanılıyor: {req.external_id}"
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

    db.commit()
    return {
        "ok": True,
        "order_id": str(order.id),
        "external_id": order.external_id,
        "message": f"Manuel sipariş oluşturuldu: {order.external_id}",
    }
