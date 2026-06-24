"""
Kişiye Özel sipariş yönetimi — /api/kisiye-ozel/*

Paket 11c: keyword tabanlı tespit kaldırıldı.
Yeni yaklaşım: tenant her mağazada belirli Shopify ürünlerini "kişiye özel"
olarak işaretler. Sipariş bu product_id'lerden birini içeriyorsa kişiye özel.

Status logic:
- "bekliyor": en az bir kişiye özel line_item'ın assigned_design_id'si null
- "hazir": tüm kişiye özel line_item'lara design atanmış
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import desc, exists, func as sql_func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import get_current_user, require_permission
from app.database import get_db
from app.models import Design, KisiyeOzelProduct, LineItem, Order, Store, User
from app.services import storage

router = APIRouter(prefix="/api/kisiye-ozel", tags=["kisiye_ozel"],
    dependencies=[Depends(require_permission("kisiye_ozel"))],
)


# ─── Helpers ────────────────────────────────────────────────

def _get_store(db: Session, store_id: uuid.UUID, tenant_id: uuid.UUID) -> Store:
    store = db.scalar(
        select(Store).where(Store.id == store_id, Store.tenant_id == tenant_id)
    )
    if not store:
        raise HTTPException(status_code=404, detail="Mağaza bulunamadı")
    return store


def _get_kop_product_ids(db: Session, store_id: uuid.UUID) -> set[str]:
    """Mağaza için kişiye özel olarak işaretlenmiş ürün ID'leri."""
    rows = db.scalars(
        select(KisiyeOzelProduct.product_id).where(KisiyeOzelProduct.store_id == store_id)
    ).all()
    return {str(p) for p in rows if p}


def _kisiye_ozel_exists(product_ids: set[str]):
    """Order üzerinde — en az bir line_item'ın product_id'si listede mi?"""
    if not product_ids:
        return None
    return exists().where(
        LineItem.order_id == Order.id,
        LineItem.product_id.in_(product_ids),
    )


def _is_li_kisiye_ozel(li: LineItem, product_ids: set[str]) -> bool:
    return bool(li.product_id) and str(li.product_id) in product_ids


def _serialize_line_item(li: LineItem, product_ids: set[str]) -> dict:
    is_kisiye = _is_li_kisiye_ozel(li, product_ids)

    # Müşterinin yüklediği görsel + notlar
    customer_image_url = None
    customer_props_text: list[dict] = []
    customer_note = None
    for p in li.properties or []:
        if not isinstance(p, dict):
            continue
        name = p.get("name") or ""
        val = p.get("value") or ""
        if name.startswith("_") or not val:
            continue
        if isinstance(val, str) and val.startswith("http") and not customer_image_url:
            customer_image_url = val
            continue
        name_lower = name.lower()
        if any(k in name_lower for k in ["not", "açıklama", "aciklama", "talep", "notes", "note"]):
            if not customer_note:
                customer_note = val
        customer_props_text.append({"name": name, "value": val})

    model_info = li.variant_title or ""

    assigned = None
    if li.assigned_design_id and li.assigned_design:
        d = li.assigned_design
        assigned = {
            "id": str(d.id),
            "code": d.code,
            "name": d.name,
            "thumbnail_url": storage.get_thumbnail_url(d.file_path, d.file_format),
            "file_url": storage.get_design_url(d.file_path),
            "file_format": d.file_format,
        }

    return {
        "id": str(li.id),
        "title": li.title,
        "variant_title": li.variant_title,
        "model_info": model_info,
        "quantity": li.quantity,
        "product_id": li.product_id,
        "is_kisiye_ozel": is_kisiye,
        "customer_image_url": customer_image_url,
        "customer_note": customer_note,
        "customer_props": customer_props_text,
        "assigned_design": assigned,
        "birincil_renk": li.birincil_renk,
        "ikincil_renk": li.ikincil_renk,
        "ucuncu_renk": li.ucuncu_renk,
        "status": "hazir" if assigned else "bekliyor",
    }


def _order_kisiye_status(order: Order, product_ids: set[str]) -> tuple[str, int, int]:
    bekliyor = 0
    hazir = 0
    for li in order.line_items or []:
        if not _is_li_kisiye_ozel(li, product_ids):
            continue
        qty = li.quantity or 1
        if li.assigned_design_id:
            hazir += qty
        else:
            bekliyor += qty
    status_ = "hazir" if (bekliyor == 0 and hazir > 0) else "bekliyor"
    return status_, bekliyor, hazir


def _serialize_order_row(o: Order, product_ids: set[str]) -> dict:
    status_, bekliyor_qty, hazir_qty = _order_kisiye_status(o, product_ids)
    total_items = sum((li.quantity or 1) for li in (o.line_items or []))

    renkler: list[str] = []
    for li in o.line_items or []:
        for r in [li.birincil_renk, li.ikincil_renk, li.ucuncu_renk]:
            if r and r not in renkler:
                renkler.append(r)

    return {
        "id": str(o.id),
        "store_id": str(o.store_id),
        "order_number": o.order_number,
        "name": o.name,
        "customer_name": o.customer_name,
        "customer_email": o.customer_email,
        "fulfillment_status": o.fulfillment_status,
        "total_items": total_items,
        "kisiye_ozel_count": bekliyor_qty + hazir_qty,
        "bekliyor_qty": bekliyor_qty,
        "hazir_qty": hazir_qty,
        "kilif_renkleri": renkler[:5],
        "created_at_platform": o.created_at_platform.isoformat() if o.created_at_platform else None,
        "status": status_,
    }


# ─── Liste ──────────────────────────────────────────────────

@router.get("/orders", response_model=None)
def list_kisiye_ozel_orders(
    store_id: uuid.UUID = Query(...),
    status: str | None = Query(None, description="bekliyor / hazir / null=hepsi"),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_store(db, store_id, user.tenant_id)

    product_ids = _get_kop_product_ids(db, store_id)
    if not product_ids:
        return {
            "items": [], "total": 0, "page": page, "per_page": per_page, "pages": 0,
            "products_configured": False,
        }

    kisiye_filter = _kisiye_ozel_exists(product_ids)

    q = (
        select(Order)
        .where(Order.store_id == store_id)
        .where(kisiye_filter)
        # Gonderilen (fulfilled) siparisleri kisiye ozel bekleyenler listesinden cikar
        .where(
            or_(
                Order.fulfillment_status.is_(None),
                sql_func.lower(Order.fulfillment_status) != "fulfilled",
            )
        )
        # Iptal / iade edilen siparisleri de cikar
        .where(Order.cancelled_at.is_(None))
        .where(or_(Order.financial_status.is_(None), Order.financial_status != "refunded"))
    )

    if search:
        like = f"%{search.lower()}%"
        q = q.where(
            or_(
                sql_func.lower(Order.order_number).like(like),
                sql_func.lower(Order.customer_name).like(like),
                sql_func.lower(Order.customer_email).like(like),
            )
        )

    q = (
        q.order_by(desc(Order.created_at_platform), desc(Order.created_at))
        .options(selectinload(Order.line_items).selectinload(LineItem.assigned_design))
    )
    all_rows = db.scalars(q).all()

    serialized = [_serialize_order_row(o, product_ids) for o in all_rows]
    if status == "bekliyor":
        serialized = [r for r in serialized if r["status"] == "bekliyor"]
    elif status == "hazir":
        serialized = [r for r in serialized if r["status"] == "hazir"]

    total = len(serialized)
    start = (page - 1) * per_page
    end = start + per_page
    page_items = serialized[start:end]

    return {
        "items": page_items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if total else 0,
        "products_configured": True,
    }


# ─── Stats ──────────────────────────────────────────────────

@router.get("/_stats", response_model=None)
def stats(
    store_id: uuid.UUID = Query(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_store(db, store_id, user.tenant_id)

    product_ids = _get_kop_product_ids(db, store_id)
    if not product_ids:
        return {
            "tasarim_bekliyor": 0, "tasarim_hazir": 0, "renk_bekliyor": 0,
            "toplam": 0, "products_configured": False,
        }

    kisiye_filter = _kisiye_ozel_exists(product_ids)
    q = (
        select(Order)
        .where(Order.store_id == store_id, kisiye_filter)
        # Gonderilen (fulfilled) siparisleri istatistige dahil etme
        .where(
            or_(
                Order.fulfillment_status.is_(None),
                sql_func.lower(Order.fulfillment_status) != "fulfilled",
            )
        )
        # Iptal / iade edilen siparisleri de cikar
        .where(Order.cancelled_at.is_(None))
        .where(or_(Order.financial_status.is_(None), Order.financial_status != "refunded"))
        .options(selectinload(Order.line_items))
    )
    rows = db.scalars(q).all()

    bekliyor = 0
    hazir = 0
    renk_bekliyor = 0
    for o in rows:
        st, _, _ = _order_kisiye_status(o, product_ids)
        if st == "bekliyor":
            bekliyor += 1
        else:
            hazir += 1
        for li in o.line_items or []:
            if _is_li_kisiye_ozel(li, product_ids) and not li.birincil_renk:
                renk_bekliyor += 1
                break

    return {
        "tasarim_bekliyor": bekliyor,
        "tasarim_hazir": hazir,
        "renk_bekliyor": renk_bekliyor,
        "toplam": bekliyor + hazir,
        "products_configured": True,
    }


# ─── Tek sipariş detayı ─────────────────────────────────────

@router.get("/orders/{order_id}", response_model=None)
def get_order_detail(
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

    product_ids = _get_kop_product_ids(db, order.store_id)

    return {
        "id": str(order.id),
        "store_id": str(order.store_id),
        "order_number": order.order_number,
        "name": order.name,
        "customer_name": order.customer_name,
        "customer_email": order.customer_email,
        "fulfillment_status": order.fulfillment_status,
        "financial_status": order.financial_status,
        "created_at_platform": order.created_at_platform.isoformat() if order.created_at_platform else None,
        "shipping_address": (order.raw or {}).get("shipping_address"),
        "billing_address": (order.raw or {}).get("billing_address"),
        "note": order.note,
        "tags": order.tags,
        "line_items": [_serialize_line_item(li, product_ids) for li in (order.line_items or [])],
    }


# ─── Line item update ───────────────────────────────────────

class LineItemPatch(BaseModel):
    birincil_renk: str | None = None
    ikincil_renk: str | None = None
    ucuncu_renk: str | None = None
    assigned_design_id: str | None = None
    fields_to_update: list[str] = []


@router.patch("/line-items/{line_item_id}", response_model=None)
def update_line_item(
    line_item_id: uuid.UUID,
    payload: LineItemPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    li = db.scalar(
        select(LineItem)
        .where(LineItem.id == line_item_id, LineItem.tenant_id == user.tenant_id)
        .options(selectinload(LineItem.assigned_design))
    )
    if not li:
        raise HTTPException(status_code=404, detail="Line item bulunamadı")

    fields = set(payload.fields_to_update)

    if "birincil_renk" in fields:
        li.birincil_renk = (payload.birincil_renk or "").strip() or None
    if "ikincil_renk" in fields:
        li.ikincil_renk = (payload.ikincil_renk or "").strip() or None
    if "ucuncu_renk" in fields:
        li.ucuncu_renk = (payload.ucuncu_renk or "").strip() or None
    if "assigned_design_id" in fields:
        if not payload.assigned_design_id:
            li.assigned_design_id = None
        else:
            d = db.scalar(
                select(Design).where(
                    Design.id == uuid.UUID(payload.assigned_design_id),
                    Design.tenant_id == user.tenant_id,
                )
            )
            if not d:
                raise HTTPException(status_code=404, detail="Tasarım bulunamadı")
            li.assigned_design_id = d.id

    db.commit()
    db.refresh(li)

    # Bu line item'ın bağlı olduğu mağazadaki kişiye özel ürün ID'leri
    order = db.scalar(select(Order).where(Order.id == li.order_id))
    product_ids = _get_kop_product_ids(db, order.store_id) if order else set()
    return _serialize_line_item(li, product_ids)


# ═══════════════════════════════════════════════════════════
# KISIYE OZEL PRODUCTS — yönetim CRUD (Paket 11c yeni)
# ═══════════════════════════════════════════════════════════

class AddProductRequest(BaseModel):
    store_id: uuid.UUID
    product_id: str
    product_title: str | None = None
    product_image_url: str | None = None


def _serialize_kop(kop: KisiyeOzelProduct) -> dict:
    return {
        "id": str(kop.id),
        "store_id": str(kop.store_id),
        "product_id": kop.product_id,
        "product_title": kop.product_title,
        "product_image_url": kop.product_image_url,
        "created_at": kop.created_at.isoformat() if kop.created_at else None,
    }


@router.get("/products", response_model=None)
def list_kop_products(
    store_id: uuid.UUID = Query(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mağazaya tanımlanmış kişiye özel ürünler."""
    _get_store(db, store_id, user.tenant_id)
    rows = db.scalars(
        select(KisiyeOzelProduct)
        .where(KisiyeOzelProduct.store_id == store_id)
        .order_by(desc(KisiyeOzelProduct.created_at))
    ).all()
    return {"items": [_serialize_kop(r) for r in rows], "count": len(rows)}


@router.post("/products", response_model=None, status_code=status.HTTP_201_CREATED)
def add_kop_product(
    payload: AddProductRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bir Shopify ürününü kişiye özel olarak işaretle."""
    _get_store(db, payload.store_id, user.tenant_id)

    pid = (payload.product_id or "").strip()
    if not pid:
        raise HTTPException(status_code=400, detail="product_id boş olamaz")

    kop = KisiyeOzelProduct(
        tenant_id=user.tenant_id,
        store_id=payload.store_id,
        product_id=pid,
        product_title=(payload.product_title or "").strip() or None,
        product_image_url=(payload.product_image_url or "").strip() or None,
    )
    db.add(kop)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Bu ürün zaten kişiye özel olarak işaretlenmiş",
        ) from e

    db.refresh(kop)
    return _serialize_kop(kop)


@router.delete("/products/{kop_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_kop_product(
    kop_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bir ürünün kişiye özel işaretini kaldır."""
    kop = db.scalar(
        select(KisiyeOzelProduct).where(
            KisiyeOzelProduct.id == kop_id,
            KisiyeOzelProduct.tenant_id == user.tenant_id,
        )
    )
    if not kop:
        raise HTTPException(status_code=404, detail="Kayıt bulunamadı")
    db.delete(kop)
    db.commit()
    return None
