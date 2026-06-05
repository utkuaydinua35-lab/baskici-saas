"""
Sipariş detay + iş akışı yönetimi — /api/orders/{order_ref}/*  (Paket 12)

order_ref: UUID veya order_number olabilir (kullanıcı dostu URL).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.adapters.shopify import ShopifyAdapter
from app.models import Design, KisiyeOzelProduct, LineItem, Mold, MoldItem, Order, OrderStatusHistory, User
from app.services import storage
from app.stages import all_stages_payload, is_valid_stage, progress_percent, stage_info

router = APIRouter(prefix="/api/orders", tags=["order_detail"])

VALID_LISTS = {
    "isaretlenenler", "bugun", "sonra", "kontrol", "export", "baski",
}


# ─── Helpers ────────────────────────────────────────────────

def _build_adapter(order):
    """Order'ın mağazasından Shopify adapter (yalnız platform shopify ise)."""
    try:
        store = order.store
        if store and (store.platform or "").lower() == "shopify":
            return ShopifyAdapter(store)
    except Exception:
        pass
    return None


def _resolve_order(db: Session, order_ref: str, tenant_id, *, with_rels=True) -> Order:
    """order_ref UUID veya order_number olabilir."""
    opts = []
    if with_rels:
        opts = [
            selectinload(Order.line_items).selectinload(LineItem.assigned_design),
            selectinload(Order.status_history),
            selectinload(Order.customer_requests),
            selectinload(Order.email_logs),
        ]

    order = None
    # Önce UUID dene
    try:
        oid = uuid.UUID(order_ref)
        q = select(Order).where(Order.id == oid, Order.tenant_id == tenant_id)
        for o in opts:
            q = q.options(o)
        order = db.scalar(q)
    except (ValueError, AttributeError):
        pass

    # UUID değilse veya bulunamadıysa order_number ile ara
    if not order:
        q = select(Order).where(
            Order.order_number == order_ref,
            Order.tenant_id == tenant_id,
        )
        for o in opts:
            q = q.options(o)
        # Birden fazla mağazada aynı numara olabilir — en yeni
        q = q.order_by(desc(Order.created_at))
        order = db.scalar(q)

    if not order:
        raise HTTPException(status_code=404, detail="Sipariş bulunamadı")
    return order


def _log_history(db: Session, order: Order, user: User, action: str,
                 from_stage: int | None = None, to_stage: int | None = None,
                 note: str | None = None):
    db.add(OrderStatusHistory(
        tenant_id=order.tenant_id,
        order_id=order.id,
        from_stage=from_stage,
        to_stage=to_stage,
        action=action,
        note=note,
        created_by=user.full_name or user.email,
    ))


def _money_from_raw(raw: dict, *keys) -> float | None:
    cur = raw or {}
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    try:
        return float(cur) if cur is not None else None
    except (TypeError, ValueError):
        return None


def _mold_info(li: LineItem, db) -> dict:
    """Line item bir kalıba bağlıysa kalıp kodu + id döndür."""
    if db is None or not getattr(li, "is_kaliba_eklendi", False):
        return {"kalip_kodu": None, "mold_id": None}
    row = db.execute(
        select(Mold.kod, Mold.id).join(MoldItem, MoldItem.mold_id == Mold.id)
        .where(MoldItem.line_item_id == li.id)
        .order_by(Mold.created_at.desc()).limit(1)
    ).first()
    if row:
        return {"kalip_kodu": row[0], "mold_id": str(row[1])}
    return {"kalip_kodu": None, "mold_id": None}


def _serialize_line_item(li: LineItem, db: Session | None = None, adapter=None) -> dict:
    assigned = None
    if li.assigned_design_id and li.assigned_design:
        d = li.assigned_design
        assigned = {
            "id": str(d.id),
            "code": d.code,
            "name": d.name,
            "thumbnail_url": storage.get_thumbnail_url(d.file_path, d.file_format),
            "file_url": storage.get_design_url(d.file_path),
        }

    image_url = None
    raw = li.raw or {}
    for path in [("image",), ("image_url",), ("product", "image")]:
        v = raw
        ok = True
        for p in path:
            if isinstance(v, dict):
                v = v.get(p)
            else:
                ok = False
                break
        if ok and isinstance(v, str) and v.startswith("http"):
            image_url = v
            break

    # Fallback: line item raw'da görsel yok -> Design / KisiyeOzelProduct cache'inden product_id ile bul
    if not image_url and db is not None and li.product_id:
        pid = str(li.product_id)
        d = db.scalar(
            select(Design).where(Design.product_id == pid, Design.product_image_url.isnot(None))
        )
        if d and d.product_image_url:
            image_url = d.product_image_url
        else:
            kop = db.scalar(
                select(KisiyeOzelProduct).where(
                    KisiyeOzelProduct.product_id == pid,
                    KisiyeOzelProduct.product_image_url.isnot(None),
                )
            )
            if kop and kop.product_image_url:
                image_url = kop.product_image_url
    # Shopify'dan canlı ürün görseli (raw'da görsel yok -> product_id ile)
    if not image_url and adapter is not None and li.product_id:
        try:
            img = adapter.get_product_image(str(li.product_id))
            if img:
                image_url = img
        except Exception:
            pass
    # Son çare: atanmış tasarımın thumbnail'i
    if not image_url and li.assigned_design_id and li.assigned_design:
        image_url = storage.get_thumbnail_url(li.assigned_design.file_path, li.assigned_design.file_format)

    return {
        "id": str(li.id),
        "title": li.title,
        "variant_title": li.variant_title,
        "device_model_override": li.device_model_override,
        "quantity": li.quantity,
        "sku": li.sku,
        "product_id": li.product_id,
        "image_url": image_url,
        "tedarik_status": li.tedarik_status,
        "is_hazir": li.is_hazir,
        "is_kaliba_eklendi": li.is_kaliba_eklendi,
        **_mold_info(li, db),
        "assigned_design": assigned,
        "birincil_renk": li.birincil_renk,
        "ikincil_renk": li.ikincil_renk,
        "ucuncu_renk": li.ucuncu_renk,
        "properties": [
            p for p in (li.properties or [])
            if isinstance(p, dict) and not (p.get("name") or "").startswith("_")
        ],
    }


def _serialize_detail(order: Order, db: Session | None = None) -> dict:
    adapter = _build_adapter(order)
    raw = order.raw or {}

    subtotal = _money_from_raw(raw, "subtotal_price") or _money_from_raw(raw, "current_subtotal_price")
    total = _money_from_raw(raw, "total_price") or _money_from_raw(raw, "current_total_price")
    shipping = None
    shipping_lines = raw.get("shipping_lines") or []
    if shipping_lines and isinstance(shipping_lines, list):
        shipping = _money_from_raw(shipping_lines[0], "price")
    total_tax = _money_from_raw(raw, "total_tax") or _money_from_raw(raw, "current_total_tax")
    total_discount = _money_from_raw(raw, "total_discounts") or _money_from_raw(raw, "current_total_discounts")
    currency = raw.get("currency") or raw.get("presentment_currency") or "TRY"

    payment_method = None
    gateway_names = raw.get("payment_gateway_names") or []
    if gateway_names:
        payment_method = ", ".join(str(g) for g in gateway_names)

    si = stage_info(order.current_stage)

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
        "note": order.note,
        "tags": order.tags,

        "current_stage": order.current_stage,
        "current_stage_info": si,
        "progress_percent": progress_percent(order.current_stage),
        "is_acil": order.is_acil,
        "is_tedarik_bekleme": order.is_tedarik_bekleme,
        "is_hatali_gonderildi": order.is_hatali_gonderildi,
        "is_iptal": order.is_iptal,
        "internal_lists": order.internal_lists or [],
        "barkod_kodu": order.barkod_kodu,

        "shipping_address": raw.get("shipping_address"),
        "billing_address": raw.get("billing_address"),

        "financial": {
            "subtotal": subtotal,
            "shipping": shipping,
            "total_tax": total_tax,
            "total_discount": total_discount,
            "total": total,
            "currency": currency,
            "payment_method": payment_method,
            "payment_status": order.financial_status,
        },

        "line_items": [_serialize_line_item(li, db, adapter) for li in (order.line_items or [])],
        "status_history": [
            {
                "id": str(h.id),
                "from_stage": h.from_stage,
                "to_stage": h.to_stage,
                "from_label": stage_info(h.from_stage)["label"] if h.from_stage else None,
                "to_label": stage_info(h.to_stage)["label"] if h.to_stage else None,
                "action": h.action,
                "note": h.note,
                "created_by": h.created_by,
                "created_at": h.created_at.isoformat() if h.created_at else None,
            }
            for h in (order.status_history or [])
        ],
        "customer_requests": [
            {
                "id": str(r.id),
                "request_type": r.request_type,
                "message": r.message,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in (order.customer_requests or [])
        ],
        "email_logs": [
            {
                "id": str(e.id),
                "template_key": e.template_key,
                "to_email": e.to_email,
                "subject": e.subject,
                "status": e.status,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in (order.email_logs or [])
        ],
    }


# ─── Stage meta ─────────────────────────────────────────────

@router.get("/_meta/stages", response_model=None)
def get_stages(user: User = Depends(get_current_user)):
    return {"stages": all_stages_payload()}


# ─── Detay ──────────────────────────────────────────────────

@router.get("/{order_ref}/detail", response_model=None)
def get_order_detail(
    order_ref: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = _resolve_order(db, order_ref, user.tenant_id)
    return _serialize_detail(order, db)


# ─── Durum güncelleme ───────────────────────────────────────

class StageUpdate(BaseModel):
    stage: int | None = None
    is_iptal: bool | None = None
    note: str | None = None


@router.patch("/{order_ref}/stage", response_model=None)
def update_stage(
    order_ref: str,
    payload: StageUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = _resolve_order(db, order_ref, user.tenant_id, with_rels=False)

    if payload.is_iptal is not None:
        order.is_iptal = payload.is_iptal
        _log_history(db, order, user, action="iptal" if payload.is_iptal else "iptal_geri",
                     note=payload.note)

    if payload.stage is not None:
        if not is_valid_stage(payload.stage):
            raise HTTPException(status_code=400, detail="Geçersiz aşama numarası")
        old = order.current_stage
        order.current_stage = payload.stage
        _log_history(db, order, user, action="stage_change",
                     from_stage=old, to_stage=payload.stage, note=payload.note)

    db.commit()
    order = _resolve_order(db, order_ref, user.tenant_id)
    return _serialize_detail(order, db)


# ─── Bayraklar ──────────────────────────────────────────────

class FlagsUpdate(BaseModel):
    is_acil: bool | None = None
    is_tedarik_bekleme: bool | None = None
    is_hatali_gonderildi: bool | None = None
    barkod_kodu: str | None = None
    add_to_list: str | None = None
    remove_from_list: str | None = None


@router.patch("/{order_ref}/flags", response_model=None)
def update_flags(
    order_ref: str,
    payload: FlagsUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = _resolve_order(db, order_ref, user.tenant_id, with_rels=False)

    if payload.is_acil is not None:
        order.is_acil = payload.is_acil
        _log_history(db, order, user, action="acil" if payload.is_acil else "acil_kaldir")

    if payload.is_tedarik_bekleme is not None:
        order.is_tedarik_bekleme = payload.is_tedarik_bekleme
        _log_history(db, order, user,
                     action="tedarik_bekle" if payload.is_tedarik_bekleme else "tedarik_devam")

    if payload.is_hatali_gonderildi is not None:
        order.is_hatali_gonderildi = payload.is_hatali_gonderildi
        if payload.is_hatali_gonderildi:
            _log_history(db, order, user, action="hatali_gonderildi")

    if payload.barkod_kodu is not None:
        order.barkod_kodu = payload.barkod_kodu.strip() or None

    lists = list(order.internal_lists or [])
    if payload.add_to_list:
        if payload.add_to_list not in VALID_LISTS:
            raise HTTPException(status_code=400, detail="Geçersiz liste")
        if payload.add_to_list not in lists:
            lists.append(payload.add_to_list)
            _log_history(db, order, user, action="list_add", note=payload.add_to_list)
    if payload.remove_from_list and payload.remove_from_list in lists:
        lists.remove(payload.remove_from_list)
        _log_history(db, order, user, action="list_remove", note=payload.remove_from_list)
    order.internal_lists = lists

    db.commit()
    order = _resolve_order(db, order_ref, user.tenant_id)
    return _serialize_detail(order, db)


# ─── Line item güncelleme ───────────────────────────────────

class LineItemWorkflowPatch(BaseModel):
    tedarik_status: str | None = None
    is_hazir: bool | None = None
    is_kaliba_eklendi: bool | None = None
    device_model_override: str | None = None
    fields_to_update: list[str] = []


@router.patch("/{order_ref}/line-items/{line_item_id}", response_model=None)
def update_line_item_workflow(
    order_ref: str,
    line_item_id: uuid.UUID,
    payload: LineItemWorkflowPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = _resolve_order(db, order_ref, user.tenant_id, with_rels=False)
    li = db.scalar(
        select(LineItem).where(
            LineItem.id == line_item_id,
            LineItem.order_id == order.id,
            LineItem.tenant_id == user.tenant_id,
        )
    )
    if not li:
        raise HTTPException(status_code=404, detail="Line item bulunamadı")

    fields = set(payload.fields_to_update)
    if "tedarik_status" in fields and payload.tedarik_status is not None:
        li.tedarik_status = payload.tedarik_status
    if "is_hazir" in fields and payload.is_hazir is not None:
        li.is_hazir = payload.is_hazir
    if "is_kaliba_eklendi" in fields and payload.is_kaliba_eklendi is not None:
        li.is_kaliba_eklendi = payload.is_kaliba_eklendi
    if "device_model_override" in fields:
        li.device_model_override = (payload.device_model_override or "").strip() or None

    db.commit()
    db.refresh(li)
    return _serialize_line_item(li)


# ─── Geçmiş ─────────────────────────────────────────────────

@router.get("/{order_ref}/history", response_model=None)
def get_history(
    order_ref: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = _resolve_order(db, order_ref, user.tenant_id)
    return {
        "items": [
            {
                "id": str(h.id),
                "from_stage": h.from_stage,
                "to_stage": h.to_stage,
                "from_label": stage_info(h.from_stage)["label"] if h.from_stage else None,
                "to_label": stage_info(h.to_stage)["label"] if h.to_stage else None,
                "action": h.action,
                "note": h.note,
                "created_by": h.created_by,
                "created_at": h.created_at.isoformat() if h.created_at else None,
            }
            for h in (order.status_history or [])
        ]
    }


# ─── Sipariş kopyala ────────────────────────────────────────

@router.post("/{order_ref}/duplicate", response_model=None)
def duplicate_order(
    order_ref: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    src = _resolve_order(db, order_ref, user.tenant_id)
    new = Order(
        tenant_id=src.tenant_id,
        store_id=src.store_id,
        external_id=f"COPY-{uuid.uuid4().hex[:10]}",
        order_number=f"{src.order_number}-K",
        name=src.name,
        customer_name=src.customer_name,
        customer_email=src.customer_email,
        raw=src.raw,
        note=src.note,
        tags=src.tags,
        current_stage=1,
    )
    db.add(new)
    db.flush()
    for li in (src.line_items or []):
        db.add(LineItem(
            tenant_id=new.tenant_id,
            order_id=new.id,
            product_id=li.product_id,
            variant_id=li.variant_id,
            title=li.title,
            variant_title=li.variant_title,
            sku=li.sku,
            quantity=li.quantity,
            position=li.position,
            properties=li.properties,
            raw=li.raw,
        ))
    db.commit()
    db.refresh(new)
    return {"id": str(new.id), "order_number": new.order_number}
