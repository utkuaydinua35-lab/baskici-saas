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
from sqlalchemy.orm.attributes import flag_modified

from app.auth.dependencies import get_current_user, require_any_permission
from app.database import get_db
from app.adapters.shopify import ShopifyAdapter
from app.models import Design, KisiyeOzelProduct, LineItem, Mold, MoldItem, Order, OrderStatusHistory, User
from app.services import storage
from app.stages import all_stages_payload, is_valid_stage, progress_percent, stage_info

router = APIRouter(prefix="/api/orders", tags=["order_detail"],
    dependencies=[Depends(require_any_permission("siparisler", "stok"))],
)

VALID_LISTS = {
    "isaretlenenler", "bugun", "sonra", "kontrol", "export", "baski",
    "arsiv",   # Shopify 'archive' karşılığı — vitrin paneli kullanır
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


def _address_editable(order, raw: dict | None = None) -> bool:
    """Shopify'dan senkron gerçek sipariş DIŞINDAki her sipariş (bayii, manuel,
    telafi, shopify olmayan mağaza) adresi elle güncellenebilir."""
    raw = raw if raw is not None else (order.raw or {})
    try:
        plat = ((order.store.platform if order.store else "") or "").lower()
    except Exception:  # noqa: BLE001
        plat = ""
    return (
        bool(getattr(order, "is_telafi", False))
        or raw.get("source") == "bayii"
        or bool(raw.get("manual"))
        or plat != "shopify"
    )


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


def _nk_model(s: str | None) -> str:
    try:
        from app.services import phone_models as _pm
        return _pm.normalize_key(s or "")
    except Exception:  # noqa: BLE001
        return (s or "").strip().lower()


def _molds_by_line_item(db, order) -> dict:
    """{line_item_id: [{id, kod}]}. Sipariş senkronu line_item_id'yi NULL'a düşürdüğü
    için kademeli eşleşme: line_item_id > (order_number+design_code) > (order_number+model).
    MoldItem.order_number stabil olduğundan aday kayıtlar onunla çekilir."""
    if db is None:
        return {}
    from app.services.mold_planner import extract_phone_model
    line_items = order.line_items or []
    onum = str(order.order_number) if order.order_number is not None else None
    li_ids = [li.id for li in line_items]
    if onum:
        where_clause = MoldItem.order_number == onum
    elif li_ids:
        where_clause = MoldItem.line_item_id.in_(li_ids)
    else:
        return {}
    rows = db.execute(
        select(MoldItem, Mold.id, Mold.kod)
        .join(Mold, Mold.id == MoldItem.mold_id)
        .where(Mold.tenant_id == order.tenant_id, where_clause)
    ).all()
    if not rows:
        return {}
    li_by_id = {li.id: li for li in line_items}
    li_by_code: dict = {}
    li_by_model: dict = {}
    for li in line_items:
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
    # Vitrin (kendi mağaza) ürünü: katalog görselinden bul
    if not image_url and db is not None and li.product_id:
        try:
            from app.models import CatalogProduct
            _cp = db.get(CatalogProduct, uuid.UUID(str(li.product_id)))
            if _cp and _cp.images:
                image_url = f"/storage/{_cp.images[0].file_path}"
        except (ValueError, TypeError):
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
        "price": (li.raw or {}).get("price"),
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
    if shipping is None:  # vitrin siparişi: kargo raw.payment altında
        shipping = _money_from_raw(raw.get("payment") or {}, "shipping_amount")
    currency = raw.get("currency") or raw.get("presentment_currency") or "TRY"

    payment_method = None
    gateway_names = raw.get("payment_gateway_names") or []
    if gateway_names:
        payment_method = ", ".join(str(g) for g in gateway_names)

    si = stage_info(order.current_stage)

    _molds_map = _molds_by_line_item(db, order)
    _li_list = []
    for li in (order.line_items or []):
        _d = _serialize_line_item(li, db, adapter)
        _d["molds"] = sorted(_molds_map.get(li.id, []), key=lambda m: m["kod"] or "")
        _li_list.append(_d)

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
        "kargo_deadline": order.kargo_deadline.isoformat() if order.kargo_deadline else None,
        "note": order.note,
        "tags": order.tags,

        "current_stage": order.current_stage,
        "current_stage_info": si,
        "progress_percent": progress_percent(order.current_stage),
        # Müşteri onayı (en güncel) — header rozeti için
        "approval_status": (order.approvals[0].status if getattr(order, "approvals", None) else None),
        # Telafi bilgisi: bu siparis bir telafi mi + ona bagli telafiler
        "is_telafi": bool(getattr(order, "is_telafi", False)),
        "telafi_sebep": getattr(order, "telafi_sebep", None),
        "telafiler": [
            {
                "id": str(t.id),
                "order_number": t.order_number,
                "telafi_sebep": t.telafi_sebep,
                "current_stage": t.current_stage,
                "current_stage_label": stage_info(t.current_stage)["label"],
                "progress_percent": progress_percent(t.current_stage),
                "item_count": len(t.line_items or []),
            }
            for t in (getattr(order, "telafiler", None) or [])
        ],
        "is_acil": order.is_acil,
        "is_tedarik_bekleme": order.is_tedarik_bekleme,
        "is_hatali_gonderildi": order.is_hatali_gonderildi,
        "is_iptal": order.is_iptal,
        "internal_lists": order.internal_lists or [],
        "barkod_kodu": order.barkod_kodu,

        "shipping_address": raw.get("shipping_address"),
        "billing_address": raw.get("billing_address"),
        # Adres düzenlenebilir mi: Shopify'dan senkron GERÇEK sipariş hariç hepsi
        # (bayii, manuel, telafi, shopify olmayan mağaza) elle güncellenebilir.
        "address_editable": _address_editable(order, raw),

        # Bayii siparişi ise: geri-navigasyon + tutar dökümü (ürün + kargo)
        "dealer_id": raw.get("dealer_id"),
        "is_bayii": (raw.get("source") == "bayii"),
        "bayii_tutar": ({
            "product_total": raw.get("total_price"),
            "shipping_fee": raw.get("shipping_fee"),
            "currency": raw.get("currency", "TRY"),
        } if raw.get("source") == "bayii" else None),

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

        # Kurumsal fatura bilgisi (vitrin checkout'unda opsiyonel alan)
        "invoice": raw.get("invoice") or None,

        "line_items": _li_list,
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
    # Kargo sözü elle override: "YYYY-MM-DD" set eder, "" temizler, None dokunmaz
    kargo_deadline: str | None = None


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

    if payload.kargo_deadline is not None:
        s = payload.kargo_deadline.strip()
        if not s:
            order.kargo_deadline = None
        else:
            try:
                from datetime import datetime as _dt
                from zoneinfo import ZoneInfo as _ZI
                order.kargo_deadline = _dt.strptime(s, "%Y-%m-%d").replace(tzinfo=_ZI("Europe/Istanbul"))
            except ValueError:
                raise HTTPException(status_code=400, detail="Geçersiz tarih (YYYY-MM-DD)")

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


# ─── Zaman akışı yorumu + etiketler (Shopify order detail paritesi) ──

class CommentIn(BaseModel):
    message: str


class AddressIn(BaseModel):
    name: str | None = None
    phone: str | None = None
    address1: str | None = None
    city: str | None = None
    province: str | None = None
    zip: str | None = None


@router.patch("/{order_ref}/address", response_model=None)
def update_address(
    order_ref: str,
    body: AddressIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Shopify harici siparişlerde (bayii / manuel / telafi) müşteri kargo adresini güncelle."""
    order = _resolve_order(db, order_ref, user.tenant_id)
    if not _address_editable(order):
        raise HTTPException(400, "Shopify siparişlerinin adresi Shopify tarafından düzenlenmeli.")
    raw = dict(order.raw or {})
    addr = dict(raw.get("shipping_address") or {})
    for k in ("name", "phone", "address1", "city", "province", "zip"):
        v = getattr(body, k)
        if v is not None:
            addr[k] = v.strip()
    raw["shipping_address"] = addr
    # İsim/telefon kolon + raw ile senkron (liste/kart bunları kullanıyor)
    if body.name is not None and body.name.strip():
        order.customer_name = body.name.strip()
    if body.phone is not None:
        raw["customer_phone"] = body.phone.strip()
    order.raw = raw
    flag_modified(order, "raw")
    _log_history(db, order, user, "address_update", note="Kargo adresi güncellendi")
    db.commit()
    db.refresh(order)
    return _serialize_detail(order, db)


@router.post("/{order_ref}/comment", response_model=None)
def add_comment(
    order_ref: str,
    payload: CommentIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Zaman akışına personel yorumu — yalnızca panelde görünür, müşteriye gitmez."""
    msg = (payload.message or "").strip()[:2000]
    if not msg:
        raise HTTPException(status_code=422, detail="Yorum boş olamaz")
    order = _resolve_order(db, order_ref, user.tenant_id, with_rels=False)
    _log_history(db, order, user, action="not", note=msg)
    db.commit()
    order = _resolve_order(db, order_ref, user.tenant_id)
    return _serialize_detail(order, db)


class TagsIn(BaseModel):
    tags: list[str]


@router.put("/{order_ref}/tags", response_model=None)
def update_tags(
    order_ref: str,
    payload: TagsIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sipariş etiketleri — virgüllü saklanır, filtre/arama için."""
    order = _resolve_order(db, order_ref, user.tenant_id, with_rels=False)
    clean: list[str] = []
    for t in (payload.tags or [])[:20]:
        t = str(t).strip()[:40]
        if t and t.lower() not in [c.lower() for c in clean]:
            clean.append(t)
    order.tags = ", ".join(clean) or None
    db.commit()
    return {"ok": True, "tags": order.tags}


# ─── Müşteriye şablonlu e-posta ─────────────────────────────

class CustomerEmailIn(BaseModel):
    subject: str
    body_html: str = ""
    title: str | None = None


@router.post("/{order_ref}/send-email", response_model=dict)
def send_customer_email(
    order_ref: str,
    req: CustomerEmailIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sipariş müşterisine şablonlu (markalı) e-posta gönder."""
    order = _resolve_order(db, order_ref, user.tenant_id, with_rels=False)
    to = (order.customer_email or "").strip()
    if not to:
        raise HTTPException(400, "Bu siparişte müşteri e-postası yok")
    from app.services import email_service
    if not email_service.is_configured():
        raise HTTPException(400, "E-posta ayarlı değil (.env SMTP_*)")
    from app.models import Tenant
    tenant = db.get(Tenant, user.tenant_id)
    bk = email_service.brand_kwargs(tenant)
    html = email_service.render_email(
        title=(req.title or req.subject),
        body_html=req.body_html or "",
        footer=f"Sipariş #{order.order_number} · Bu e-posta siparişinizle ilgilidir.",
        **bk,
    )
    ok = email_service.send_email(to, req.subject, html)
    if not ok:
        raise HTTPException(502, "E-posta gönderilemedi (SMTP)")
    _log_history(db, order, user, action="musteri_email", note=(req.subject or "")[:80])
    db.commit()
    return {"ok": True, "to": to}


# ─── Müşteri tasarım onayı ──────────────────────────────────

class ApprovalCreate(BaseModel):
    note: str | None = None


@router.post("/{order_ref}/approval", response_model=dict)
def create_design_approval(
    order_ref: str,
    payload: ApprovalCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Müşteri onay isteği oluştur (yeni versiyon). Link + hazır mesaj + telefon döner."""
    order = _resolve_order(db, order_ref, user.tenant_id)
    from app.services import approvals as ap_svc
    try:
        ap = ap_svc.create_approval(db, order, user, note=payload.note)
    except ap_svc.NoApprovalItems as e:
        raise HTTPException(status_code=422, detail=str(e))
    _log_history(db, order, user, action="onay_gonderildi", note=f"v{ap.version}")
    db.commit()
    db.refresh(ap)
    data = ap_svc.serialize(ap, with_secrets=True)
    data["message"] = ap_svc.build_message(order, data["link"])
    data["phone"] = ap_svc.resolve_phone(order)
    data["customer_name"] = order.customer_name
    return data


@router.get("/{order_ref}/approvals", response_model=dict)
def list_design_approvals(
    order_ref: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Siparişin tüm onay istekleri (en yeni önce) + müşteri telefonu/mesajı."""
    order = _resolve_order(db, order_ref, user.tenant_id)
    from app.services import approvals as ap_svc
    items = []
    for a in (order.approvals or []):
        d = ap_svc.serialize(a, with_secrets=True)
        d["message"] = ap_svc.build_message(order, d["link"])
        items.append(d)
    return {
        "items": items,
        "phone": ap_svc.resolve_phone(order),
        "customer_name": order.customer_name,
    }


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
        _new = (payload.device_model_override or "").strip() or None
        if _new != li.device_model_override:
            _log_history(
                db, order, user, action="kalem_model_degisti",
                note=f"{(li.title or 'Ürün')[:48]}: {li.device_model_override or '—'} → {_new or '—'}",
            )
        li.device_model_override = _new

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
