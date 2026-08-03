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

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import case, desc, func as sql_func, or_ as sa_or, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.adapters import get_adapter
from app.auth.dependencies import get_current_user, require_any_permission, require_permission
from app.database import get_db
from app.services import activity
from app.models import LineItem, Mold, MoldItem, Order, OrderStatusHistory, Store, User
from app.stages import is_valid_stage

router = APIRouter(prefix="/api/orders", tags=["orders"],
    dependencies=[Depends(require_any_permission("siparisler", "bayii", "stok"))],
)

# Acil eşik: kaç gün geçince "Acil" sayılır — TEK KAYNAK order_counts'ta
# (dashboard/özet/worklist ile birebir aynı olsun diye buraya import edilir).
from app.services.order_counts import ACIL_THRESHOLD_DAYS  # noqa: E402

TAB_KEYS = ["tumu", "acil", "barkod", "tedarik", "kaliplanmis", "kalip_bekliyor", "gonderilmeyen", "tamamlandi"]


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
    internal_lists: list = []   # iç etiketler (arsiv dahil) — panel filtreler


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


# Uygulamaya ait (Shopify'dan GELMEYEN) LineItem alanlari — elle secim, atama,
# uretim akisi. Sync artik kalemleri silip yeniden yaratmiyor, external_id ile
# eslesen kalemi YERINDE guncelliyor; bu yuzden bu alanlara hic dokunulmuyor.
# Liste belge olarak duruyor: sync'in yazdigi Shopify alanlariyla karismasin.
_LI_APP_FIELDS = (
    "assigned_design_id", "assigned_design_id_2",
    "device_model_override", "device_model_override_2",
    "kilif_varyasyon", "kilif_varyasyon_2",
    "birincil_renk", "ikincil_renk", "ucuncu_renk",
    "tedarik_status", "is_hazir", "is_hazir_2", "is_kaliba_eklendi",
    "is_kisiye_ozel", "product_image_url",
)


def _upsert_order(db: Session, *, tenant_id, store_id, raw: dict) -> tuple[Order, bool, bool]:
    """Raw order dict'ten Order kaydı oluştur veya güncelle."""
    external_id = str(raw.get("id", ""))
    if not external_id:
        raise ValueError("raw order'da id yok")

    # Kargo sözü hesabı için mağaza config (db.get identity-map ile cache'lenir)
    _store = db.get(Store, store_id)
    _sla_days = _store_sla_days(_store)

    # include_deleted: çöpe atılmış (soft-delete) sipariş de bulunmalı — yoksa sync onu
    # göremeyip aynı (mağaza, external_id) ile INSERT deneyip UniqueViolation ile patlıyor.
    existing = db.scalar(
        select(Order).where(
            Order.store_id == store_id,
            Order.external_id == external_id,
        ).execution_options(include_deleted=True)
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
        "closed_at": _parse_iso(raw.get("closed_at")),   # Shopify "Arşivle" -> kapandı
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
        # ★ KALEMLER ARTIK SILINIP YENIDEN YARATILMIYOR ★
        # Eskiden her sync'te line_items.clear() yapiliyordu; kalemler YENI UUID
        # aliyordu. Sonuclari: kalip slotu bagi kopuyor, acik panel sayfalarindaki
        # kimlikler gecersizlesiyor ("Line item bulunamadi"), uygulamaya ait alanlar
        # tek tek geri yazilmak zorunda kaliyordu. Artik external_id ile eslesen
        # kalem YERINDE guncellenir; kimligi sabit kalir.
        _mevcut_li = {
            (_li.external_id or ""): _li for _li in order.line_items if _li.external_id
        }
        _gelen_ext: set[str] = set()
    else:
        is_new = True
        was_updated = False
        order = Order(**order_data)
        if _deadline is not None:
            order.kargo_deadline = _deadline
        db.add(order)
        db.flush()

    # Shopify'da iptal edilen siparisi otomatik 'iptal' isaretle -> hazirlik/plan/notlardan
    # cikar. (is_iptal aksi halde yalnizca elle set ediliyordu.) Elle is_iptal'i geri ALMA.
    if order_data["cancelled_at"] is not None and not order.is_iptal:
        order.is_iptal = True
        was_updated = True

    # Shopify fulfillment takip no'sunu otomatik kargo_info'ya cek (musteri Shopify'da
    # dogrudan kargolarsa webhook gelmez; sync penceresindeki siparisler icin takip burada
    # icer alinir). App ici kargo akisiyla yazilan mevcut takip_no'yu ASLA ezme.
    _ff = raw.get("fulfillments")
    if _ff:
        try:
            from app.services import tracker as _tracker
            _ti = _tracker.extract_tracking_info(raw)
            _tnos = _ti.get("tracking_numbers") or []
            _ki = dict(order.kargo_info or {})
            if _tnos and not _ki.get("takip_no"):
                _ki["takip_no"] = _tnos[0]
                if _ti.get("tracking_urls"):
                    _ki["takip_url"] = _ti["tracking_urls"][0]
                if _ti.get("carrier"):
                    _ki["handler_name"] = _ti["carrier"]
                _ki.setdefault("status", "kargoya_verildi")
                _ki["kaynak"] = "shopify_sync"
                order.kargo_info = _ki
                was_updated = True
        except Exception:
            pass

    _mevcut_li = locals().get("_mevcut_li", {})
    _gelen_ext = locals().get("_gelen_ext", set())
    # Shopify'dan gelen alanlar — YALNIZCA bunlar guncellenir; uygulamaya ait
    # alanlara (_LI_APP_FIELDS) DOKUNULMAZ, zaten kalemin uzerinde duruyorlar.
    for pos, li_raw in enumerate(raw.get("line_items", [])):
        _ext = str(li_raw.get("id", "")) if li_raw.get("id") else None
        _alanlar = {
            "product_id": str(li_raw.get("product_id", "")) if li_raw.get("product_id") else None,
            "variant_id": str(li_raw.get("variant_id", "")) if li_raw.get("variant_id") else None,
            "title": li_raw.get("title", ""),
            "variant_title": li_raw.get("variant_title"),
            "sku": li_raw.get("sku"),
            "quantity": li_raw.get("quantity", 1),
            "position": pos,
            "properties": li_raw.get("properties") or [],
            "raw": li_raw,
        }
        li = _mevcut_li.get(_ext) if _ext else None
        if li is not None:
            # YERINDE guncelle — kimlik (id) korunur
            for _f, _v in _alanlar.items():
                if getattr(li, _f, None) != _v:
                    setattr(li, _f, _v)
        else:
            li = LineItem(tenant_id=tenant_id, order_id=order.id,
                          external_id=_ext, **_alanlar)
            db.add(li)
        if _ext:
            _gelen_ext.add(_ext)

    # Shopify'dan ARTIK GELMEYEN kalemler (siparis duzenlenmis, kalem silinmis) —
    # bunlari kaldir. Kalip slotlari FK ondelete=SET NULL ile bagsiz kalir.
    for _ext, _eski in _mevcut_li.items():
        if _ext not in _gelen_ext:
            db.delete(_eski)
    db.flush()

    # Müşteri CRM kaydını güncelle — hata sync'i asla düşürmesin
    try:
        from app.services.customers import upsert_from_order
        upsert_from_order(db, order)
    except Exception as _crm_err:  # noqa: BLE001
        print(f"[crm] musteri upsert hatasi (order {order.order_number}): {_crm_err}")

    return order, is_new, was_updated


# ─── Tab filtreleri (Paket 18) ───────────────────────────────
def _build_tab_filter(q, tab: str, tenant_id=None):
    """Order üzerinde base query'ye tab filtresini ekle."""
    if tab == "acil":
        # order_counts ile birebir: gerçek açık + 5 gün eski + (bayii/kargoda/takipli hariç)
        from app.services import order_counts as _oc
        q = q.where(
            *_oc.open_conds(), *_oc.acil_extra_conds(tenant_id),
            Order.created_at_platform < _oc.acil_threshold_dt(),
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
    elif tab == "gonderilmeyen":
        # Henüz SEVK EDİLMEMİŞ siparişler: gerçek açık + kargoda/teslim (stage>=8)
        # değil + takip no'su yok. Bayii 'teslim' siparişleri stage 8/9 olduğundan
        # artık burada görünmez.
        from app.services import order_counts as _oc
        q = q.where(*_oc.open_conds(), *_oc.acil_extra_conds())
    elif tab == "tamamlandi":
        q = q.where(
            (Order.fulfillment_status == "fulfilled")
            | (Order.cancelled_at.is_not(None))
            | (Order.closed_at.is_not(None))   # Shopify'da arşivlenmiş de tamamlandı
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
    # Telafiler ayrı panelde — liste sorgusu da hariç tutuyor; badge sayıları tutsun.
    base = select(Order.id).where(
        Order.tenant_id == user.tenant_id,
        Order.is_telafi == False,  # noqa: E712
    )
    if store_id:
        base = base.where(Order.store_id == store_id)

    counts = {}
    for tab in TAB_KEYS:
        q = _build_tab_filter(base, tab, user.tenant_id)
        c = db.scalar(select(sql_func.count()).select_from(q.subquery())) or 0
        counts[tab] = c
    return counts


@router.get("/export/orders.csv")
def export_orders_csv(
    store_id: uuid.UUID = Query(...),
    start: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Mağaza siparişlerini CSV indir (muhasebe/e-fatura aktarımı).

    Tarih aralığı platform sipariş tarihine göre (dahil); boşsa tümü.
    """
    import csv
    import io
    from datetime import datetime, timedelta, timezone as _tz

    from fastapi.responses import StreamingResponse
    from sqlalchemy.orm import selectinload as _sel

    q = (
        select(Order)
        .where(Order.tenant_id == user.tenant_id, Order.store_id == store_id)
        .options(_sel(Order.line_items))
        .order_by(Order.created_at_platform.desc().nulls_last())
    )
    if start:
        q = q.where(Order.created_at_platform >= datetime.fromisoformat(start).replace(tzinfo=_tz.utc))
    if end:
        q = q.where(Order.created_at_platform
                    < datetime.fromisoformat(end).replace(tzinfo=_tz.utc) + timedelta(days=1))

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["siparis_no", "tarih", "musteri", "eposta", "tutar", "para_birimi",
                "odeme_durumu", "kalem_sayisi", "urunler", "kargo_takip_no", "iptal"])
    for o in db.scalars(q).all():
        raw = o.raw or {}
        w.writerow([
            o.name or f"#{o.order_number}",
            o.created_at_platform.isoformat() if o.created_at_platform else "",
            o.customer_name or "",
            o.customer_email or "",
            raw.get("total_price") or "",
            raw.get("currency") or "TRY",
            o.financial_status or "",
            sum(li.quantity for li in o.line_items),
            " | ".join(f"{li.title} ({li.variant_title or '-'}) x{li.quantity}"
                       for li in o.line_items),
            (o.kargo_info or {}).get("takip_no") or "",
            "evet" if o.cancelled_at else "",
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=siparisler.csv"},
    )


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
        q = _build_tab_filter(q, tab, user.tenant_id)
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
            # En YENİ kalıp önce (son eklendiği kalıp ilk gösterilsin)
            for onum, mid, kod, _cr in db.execute(
                select(MoldItem.order_number, Mold.id, Mold.kod, Mold.created_at)
                .join(Mold, Mold.id == MoldItem.mold_id)
                .where(Mold.tenant_id == user.tenant_id, MoldItem.order_number.in_(onums))
                .order_by(Mold.created_at.desc())
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
        item["total_price"] = (o.raw or {}).get("total_price")
        item["kalipta_count"] = sum(
            1 for li in o.line_items if getattr(li, "is_kaliba_eklendi", False)
        )
        # En yeni kalıp ilk (query created_at desc sıralı) — 'son eklendiği kalıp' önde
        _links = mold_links_by_onum.get(str(o.order_number), [])
        item["molds"] = _links
        item["mold_kodlari"] = [m["kod"] for m in _links]
        _ki = o.kargo_info or {}
        item["kargo_status"] = _ki.get("status")
        item["kargo_takip"] = _ki.get("takip_no")
        item["kargo_firma"] = _ki.get("handler_name")
        _ki = o.kargo_info or {}
        item["is_acil"] = bool(
            o.cancelled_at is None
            and o.closed_at is None
            and not getattr(o, "is_iptal", False)
            and (o.fulfillment_status != "fulfilled")
            and (o.financial_status != "refunded")
            and (o.current_stage or 0) < 8                  # kargoda(8)/teslim(9) değil
            and not (_ki.get("takip_no"))                   # takip no yoksa
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


@router.get("/live-view", response_model=dict)
def live_view(
    store_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Panel Canlı Görünüm (Shopify live view) — anlık ziyaretçi/sepet/ödeme.

    Vitrin presence ping'leri + checkout oturumlarından türetilir; kart
    ~10 sn'de bir yeniler."""
    from datetime import datetime, timedelta, timezone
    from zoneinfo import ZoneInfo

    from sqlalchemy import func as sql_func

    from app.models import CheckoutSession, Store as _Store, StorefrontPresence

    store = db.scalar(select(_Store).where(
        _Store.id == store_id, _Store.tenant_id == user.tenant_id,
        _Store.platform == "storefront"))
    if not store:
        raise HTTPException(404, "Vitrin mağazası bulunamadı")

    now = datetime.now(timezone.utc)
    # "Bugün" Türkiye günüdür — gece yarısı TR'de sıfırlanır
    tr_now = now.astimezone(ZoneInfo("Europe/Istanbul"))
    day_start = tr_now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)

    def _count(*conds) -> int:
        return db.scalar(select(sql_func.count()).select_from(StorefrontPresence).where(
            StorefrontPresence.store_id == store.id, *conds)) or 0

    paid_q = (CheckoutSession.store_id == store.id,
              CheckoutSession.status == "paid")
    today_orders = db.scalar(select(sql_func.count()).select_from(CheckoutSession).where(
        *paid_q, CheckoutSession.paid_at >= day_start)) or 0
    today_revenue = db.scalar(select(sql_func.coalesce(sql_func.sum(CheckoutSession.amount), 0))
        .where(*paid_q, CheckoutSession.paid_at >= day_start)) or 0

    # Bakım: 7 günden eski presence satırlarını buda (uç seyrek çağrılır)
    db.query(StorefrontPresence).filter(
        StorefrontPresence.store_id == store.id,
        StorefrontPresence.last_seen < now - timedelta(days=7),
    ).delete(synchronize_session=False)
    db.commit()

    return {
        "current_visitors": _count(StorefrontPresence.last_seen > now - timedelta(minutes=5)),
        "today_sessions": _count(StorefrontPresence.first_seen >= day_start),
        "active_carts": _count(
            StorefrontPresence.cart_items > 0,
            StorefrontPresence.last_seen > now - timedelta(minutes=30)),
        "checking_out": db.scalar(select(sql_func.count()).select_from(CheckoutSession).where(
            CheckoutSession.store_id == store.id,
            CheckoutSession.status == "pending",
            CheckoutSession.created_at > now - timedelta(minutes=30))) or 0,
        "purchased_recent": db.scalar(select(sql_func.count()).select_from(CheckoutSession).where(
            *paid_q, CheckoutSession.paid_at > now - timedelta(minutes=15))) or 0,
        "today_orders": today_orders,
        "today_revenue": str(today_revenue),
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
_BULK_VALID_LISTS = {"isaretlenenler", "bugun", "sonra", "kontrol", "export", "baski", "arsiv"}

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

    # ÜRÜN (siparis) + KARGO borcunu birlikte geri al — kargo iptalde takılı kalmasın.
    # (kargo TRY, urun bayi para biriminde; tx.currency ile dogru bakiyeye islenir.)
    txs = db.scalars(
        select(_DTx).where(_DTx.ref_order_id == order.id, _DTx.kind.in_(["siparis", "kargo"]))
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


@router.post("/_refresh-stale", response_model=dict)
def refresh_stale_open(
    days: int = Query(0, ge=0),   # 0 = tüm açık siparişler; >0 = sadece N günden eski açıklar
    user: User = Depends(require_permission("siparisler")),
    db: Session = Depends(get_db),
):
    """Açık görünen (fulfilled değil) siparişlerin GÜNCEL durumunu Shopify'dan
    tek tek çekip tazeler. Amaç: eski sync penceresinin dışında kaldığı için
    'unfulfilled' olarak DONMUŞ (ama gerçekte kargolanmış) siparişleri kapatmak —
    böylece hayalet 'açık'/'acil' sayıları düzelir. Yalnızca Shopify mağazaları;
    bayii/manuel siparişler atlanır (onlar panelden yönetilir)."""
    from app.services import order_counts as _oc

    conds = [Order.tenant_id == user.tenant_id, Order.is_telafi == False, *_oc.open_conds()]  # noqa: E712
    if days > 0:
        conds.append(Order.created_at_platform < datetime.now(UTC) - timedelta(days=days))
    orders = db.scalars(
        select(Order).where(*conds).order_by(Order.created_at_platform.asc()).limit(500)
    ).all()

    # Mağaza + adapter cache
    store_cache: dict = {}
    checked = closed = errors = skipped = 0
    for o in orders:
        store = store_cache.get(o.store_id)
        if store is None:
            store = db.get(Store, o.store_id)
            store_cache[o.store_id] = store
        if not store or store.platform != "shopify":
            skipped += 1
            continue
        oid = o.external_id or str((o.raw or {}).get("id") or "")
        if not oid:
            skipped += 1
            continue
        try:
            adapter = get_adapter(store)
            raw = adapter.get_order_by_id(oid)
            checked += 1
            if raw is None:
                continue  # Shopify'da yok (silinmiş) — dokunma
            _upsert_order(db, tenant_id=user.tenant_id, store_id=store.id, raw=raw)
            # Güncelleme sonrası artık açık değilse "kapandı" say
            # (fulfilled / iptal / Shopify'da arşivlenmiş=closed_at)
            if (raw.get("fulfillment_status") == "fulfilled") or raw.get("cancelled_at") or raw.get("closed_at"):
                closed += 1
        except Exception:  # noqa: BLE001
            errors += 1
    db.commit()
    return {
        "ok": True, "checked": checked, "closed": closed,
        "errors": errors, "skipped": skipped, "candidates": len(orders),
    }


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
    # En YENİ kalıp önce: bir kalem birden fazla kez kalıba eklendiyse (eskiden
    # çıkarılıp yeniden eklendi) SON eklendiği kalıp gösterilsin.
    rows = db.execute(
        select(MoldItem, Mold.id, Mold.kod)
        .join(Mold, Mold.id == MoldItem.mold_id)
        .where(Mold.tenant_id == tenant_id, MoldItem.order_number == onum)
        .order_by(Mold.created_at.desc(), MoldItem.id.desc())
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
        # rows en yeniden eskiye sıralı: kaleme yalnızca EN SON kalıbı ata
        if target.id not in out:
            out[target.id] = [{"id": str(mid), "kod": kod}]
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
            # Slot kilidi acikken kalanlar YERINDE kalir (kalip detayindaki anahtar).
            if items and not getattr(mo, "slot_kilitli", False):
                placed = mold_planner.pr.assign_slots(
                    [{"kod": x.kalip_kodu, "model": x.model, "_ref": x} for x in items])
                for d in placed:
                    d["_ref"].slot_index = d["slot_index"]
    li.is_kaliba_eklendi = False
    db.commit()
    return {"ok": True, "removed": len(targets)}


# ⚠ SIRA ÖNEMLİ: bu uçlar '/{order_id}' rotasından ÖNCE tanımlanmalı.
# FastAPI rotaları tanım sırasına göre eşler; sonra tanımlanırsa
# '/api/orders/_takip-bekleyen' isteği '/{order_id}' ile eşleşip
# '_takip-bekleyen' UUID olarak ayrıştırılmaya çalışılıyor ve hata veriyor.
# ─── Toplu kargo takip no içe aktarma ────────────────────────
# Kendi kargo anlaşmasıyla çalışırken takip numaraları sisteme otomatik düşmüyor.
# Firma panelinden alınan Excel/CSV listesi buraya YAPIŞTIRILIR; sipariş numarası
# ve takip numarası satır satır eşlenir. Önce ÖNİZLEME, sonra uygulama.

class TopluTakipIn(BaseModel):
    metin: str = ""                 # Excel'den yapıştırılan ham metin
    kargo_firma: str = ""
    mail_gonder: bool = True
    uygula: bool = False            # False -> yalnızca önizleme
    mevcudun_uzerine_yaz: bool = False


_TAKIP_MIN_UZUNLUK = 6


def _satir_parcala(satir: str) -> list[str]:
    """Satırı sütunlara ayır — Excel yapıştırması sekmeli, CSV virgüllü/noktalı virgüllü."""
    import re as _re
    return [p.strip().strip('"').strip() for p in _re.split(r"[\t;,|]+|\s{2,}", satir) if p.strip()]


@router.post("/_toplu-takip", response_model=None)
def toplu_takip_no(
    body: TopluTakipIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Yapıştırılan listeden sipariş↔takip no eşle. uygula=False ise sadece rapor.

    Sütun sırası ÖNEMSİZ: her satırdaki parçalardan hangisi gerçek bir sipariş
    numarasıysa o seçilir, kalanların en uzun/rakam içereni takip numarası sayılır.
    Böylece kargo firmasının export düzeni ne olursa olsun çalışır.
    """
    satirlar = [s for s in (body.metin or "").splitlines() if s.strip()]
    if not satirlar:
        return {"ok": False, "message": "Liste boş — Excel'den kopyalayıp yapıştır."}

    # Tüm satırlardaki aday sipariş numaralarını tek seferde çöz
    _adaylar: set[str] = set()
    _parcali: list[tuple[str, list[str]]] = []
    for s in satirlar:
        p = _satir_parcala(s)
        _parcali.append((s, p))
        for x in p:
            _adaylar.add(x.lstrip("#").strip())

    _bulunan: dict[str, list[Order]] = {}
    if _adaylar:
        for o in db.scalars(
            select(Order).where(
                Order.tenant_id == user.tenant_id,
                Order.order_number.in_(list(_adaylar)),
            ).options(selectinload(Order.line_items))
        ).all():
            _bulunan.setdefault(str(o.order_number), []).append(o)

    from app.services import shipments as _sh

    rapor = []
    uygulanan = 0
    for ham, parcalar in _parcali:
        _sip_no = None
        for x in parcalar:
            if x.lstrip("#").strip() in _bulunan:
                _sip_no = x.lstrip("#").strip()
                break
        if not _sip_no:
            rapor.append({"satir": ham[:120], "durum": "siparis_bulunamadi",
                          "aciklama": "Bu satırda tanınan sipariş numarası yok"})
            continue
        # Takip no: sipariş numarası DIŞINDAki, rakam içeren en uzun parça
        _kalan = [x for x in parcalar if x.lstrip("#").strip() != _sip_no]
        _takip = ""
        for x in sorted(_kalan, key=len, reverse=True):
            if len(x) >= _TAKIP_MIN_UZUNLUK and any(c.isdigit() for c in x):
                _takip = x
                break
        if not _takip:
            rapor.append({"satir": ham[:120], "siparis_no": _sip_no, "durum": "takip_yok",
                          "aciklama": "Takip numarası okunamadı"})
            continue

        _eslesme = _bulunan[_sip_no]
        if len(_eslesme) > 1:
            rapor.append({"satir": ham[:120], "siparis_no": _sip_no, "takip_no": _takip,
                          "durum": "belirsiz",
                          "aciklama": f"{len(_eslesme)} mağazada aynı numara — elle gir"})
            continue
        o = _eslesme[0]
        _mevcut = (o.kargo_info or {}).get("takip_no")
        if _mevcut and not body.mevcudun_uzerine_yaz:
            rapor.append({"satir": ham[:120], "siparis_no": _sip_no, "takip_no": _takip,
                          "durum": "zaten_var",
                          "aciklama": f"Zaten takip no var: {_mevcut}"})
            continue
        _kalanlar = _sh.remaining_counts(o)
        _items = [{"line_item_id": k, "quantity": v} for k, v in _kalanlar.items() if v > 0]
        if not _items:
            rapor.append({"satir": ham[:120], "siparis_no": _sip_no, "takip_no": _takip,
                          "durum": "tamamen_gonderilmis",
                          "aciklama": "Siparişin tüm kalemleri zaten gönderilmiş"})
            continue

        if not body.uygula:
            rapor.append({"satir": ham[:120], "siparis_no": _sip_no, "takip_no": _takip,
                          "durum": "hazir",
                          "aciklama": f"{sum(i['quantity'] for i in _items)} ürün kargolanacak"})
            continue
        try:
            _sh.create_shipment(
                db, o, items=_items, takip_no=_takip,
                kargo_firma=(body.kargo_firma or "").strip() or None,
                note="Toplu takip no içe aktarma",
                user_label=user.email, send_email=body.mail_gonder,
            )
            uygulanan += 1
            rapor.append({"satir": ham[:120], "siparis_no": _sip_no, "takip_no": _takip,
                          "durum": "uygulandi", "aciklama": "Kargolandı olarak işlendi"})
        except Exception as e:  # noqa: BLE001
            rapor.append({"satir": ham[:120], "siparis_no": _sip_no, "takip_no": _takip,
                          "durum": "hata", "aciklama": str(e)[:160]})

    if body.uygula:
        db.commit()
    _sayac: dict = {}
    for r in rapor:
        _sayac[r["durum"]] = _sayac.get(r["durum"], 0) + 1
    return {
        "ok": True,
        "uygulandi": body.uygula,
        "toplam_satir": len(rapor),
        "uygulanan": uygulanan,
        "sayac": _sayac,
        "rapor": rapor,
    }


# ─── Takip no bekleyen gönderiler + xlsx eşleştirme ──────────
# Kendi kargo anlaşmasında barkod firmanın sisteminde basılıyor; takip numarası
# günün sonunda Excel ile geliyor. "Kargoya Ver"e basılan sipariş takip numarası
# gelene kadar burada bekler.

def _bekleyen_gonderiler(db: Session, tenant_id) -> list[dict]:
    """Kargoya verilmiş ama TAKİP NUMARASI olmayan siparişler.

    Kaynak sipariş bazındadır, gönderi kaydı bazında DEĞİL: Basit Kargo akışı
    order.kargo_info + aşama yazıyor ama OrderShipment kaydı oluşturmuyor.
    Yalnızca gönderi kayıtlarına bakmak listeyi boş bırakıyordu.

    Ölçüt: iptal değil · (aşama >= Kargoda VEYA gönderi kaydı var) ·
    hiçbir yerde takip no yok · kargo ücreti alınmayan bayii değil.
    """
    from app.models import Dealer, OrderShipment

    _muaf = {
        str(_id) for (_id,) in db.execute(
            select(Dealer.id).where(Dealer.tenant_id == tenant_id,
                                    sql_func.coalesce(Dealer.shipping_fee, 0) == 0)
        ).all()
    }

    # Sipariş -> gönderi kayıtları (varsa)
    _gonderiler: dict = {}
    for sh in db.scalars(
        select(OrderShipment).where(OrderShipment.tenant_id == tenant_id)
    ).all():
        _gonderiler.setdefault(sh.order_id, []).append(sh)

    # Çıkış tarihi: "kargoya verildi" geçmiş kaydı en doğrusu
    _cikis: dict = {}
    for _oid, _t in db.execute(
        select(OrderStatusHistory.order_id, sql_func.max(OrderStatusHistory.created_at))
        .where(OrderStatusHistory.tenant_id == tenant_id,
               OrderStatusHistory.action == "kargoya_verildi")
        .group_by(OrderStatusHistory.order_id)
    ).all():
        _cikis[_oid] = _t

    _adaylar = db.scalars(
        select(Order).where(
            Order.tenant_id == tenant_id,
            Order.is_iptal == False,  # noqa: E712
            sa_or(Order.current_stage >= 8, Order.id.in_(list(_gonderiler.keys()) or [None])),
        ).order_by(desc(Order.created_at))
    ).all()

    _magazalar = {str(s.id): s.name for s in db.scalars(
        select(Store).where(Store.tenant_id == tenant_id)).all()}
    _bayiler = {str(d.id): d.name for d in db.scalars(
        select(Dealer).where(Dealer.tenant_id == tenant_id)).all()}

    out = []
    for o in _adaylar:
        _shs = _gonderiler.get(o.id, [])
        # Takip no HERHANGİ bir yerde varsa bekleyen değildir.
        # AMA: Basit Kargo gerçek kargo takip kodunu (handlerShipmentCode) dönmezse
        # kendi BARKODUNU takip no olarak yazıyoruz. Müşteri onunla takip yapamaz —
        # gerçek numara kargo firmasının Excel'inden gelecek, yani hâlâ BEKLİYOR.
        _ki = o.kargo_info or {}
        _tn = (_ki.get("takip_no") or "").strip()
        if _tn and _tn != (_ki.get("barcode") or "").strip():
            continue
        if any((sh.takip_no or "").strip() for sh in _shs):
            continue
        _raw = o.raw or {}
        _did = str(_raw.get("dealer_id") or "") or None
        if _did and _did in _muaf:
            continue        # kargo ücreti almadığımız bayii
        _sa = _raw.get("shipping_address") or {}
        _bos = next((sh for sh in _shs if not (sh.takip_no or "").strip()), None)
        out.append({
            # gönderi kaydı yoksa None — uygulama aşamasında oluşturulur
            "shipment_id": str(_bos.id) if _bos else None,
            "order_id": str(o.id),
            "order_number": o.order_number,
            "ad": (_sa.get("name") or o.customer_name or "").strip(),
            "adres": " ".join(x for x in [(_sa.get("address1") or ""),
                                          (_sa.get("address2") or "")] if x).strip(),
            "il": (_sa.get("province") or _sa.get("city") or "").strip(),
            "ilce": (_sa.get("city") or "").strip(),
            "cikis_tarihi": (_zaman.isoformat() if (_zaman := (
                _cikis.get(o.id) or (_bos.created_at if _bos else None)
                or o.created_at)) else None),
            "kaynak": (_bayiler.get(_did) if _did
                       else _magazalar.get(str(o.store_id or ""))) or "—",
            "kaynak_tipi": "bayii" if _did else "magaza",
            "kargo_firma": (_bos.kargo_firma if _bos
                            else (o.kargo_info or {}).get("handler_name")),
        })
    return out


@router.get("/_takip-bekleyen", response_model=None)
def takip_bekleyen(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Takip numarası bekleyen gönderiler — isim · çıkış tarihi · mağaza/bayii."""
    items = _bekleyen_gonderiler(db, user.tenant_id)
    return {"toplam": len(items), "items": items}


@router.post("/_takip-xlsx", response_model=None)
async def takip_xlsx(
    dosya: UploadFile = File(...),
    uygula: bool = Query(False),
    mail_gonder: bool = Query(True),
    onaylananlar: str = Query("", description="Şüpheli eşleşmelerden onaylananların shipment_id'leri"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Kargo firmasının .xlsx listesini yükle; isim+adres ile bekleyenlere eşle.

    uygula=False -> yalnızca ÖNİZLEME (hiçbir şey yazılmaz).
    Kesin eşleşmeler (skor ≥ 0.80) uygulanır; şüpheliler (0.60–0.80) yalnızca
    'onaylananlar' listesinde varsa uygulanır. Belirsizlikte tahmin yürütülmez.
    """
    from app.models import OrderShipment
    from app.services import kargo_eslestir, shipments as _sh
    from app.services.xlsx_reader import XlsxError, read_rows, sutun_bul

    ham = await dosya.read()
    if len(ham) > 10 * 1024 * 1024:
        raise HTTPException(413, "Dosya çok büyük (en fazla 10 MB).")
    try:
        satirlar = read_rows(ham)
    except XlsxError as e:
        raise HTTPException(400, str(e))
    if not satirlar:
        return {"ok": False, "message": "Dosyada veri satırı yok."}

    kargolar = []
    for r in satirlar:
        _takip = sutun_bul(r, "TakipNo", "Takip No", "Takip Numarasi", "Barkod")
        _ad = sutun_bul(r, "Alici", "Alıcı", "Alici Adi", "Alıcı Adı", "AliciUnvan")
        if not _takip or not _ad:
            continue
        kargolar.append({
            "takip_no": _takip,
            "ad": _ad,
            "adres": sutun_bul(r, "AliciAdres", "Alıcı Adres", "Adres", "Teslimat Adresi"),
            "il": sutun_bul(r, "Varışİl", "Varis Il", "Il", "Şehir"),
            "ilce": sutun_bul(r, "Varışİlçe", "Varis Ilce", "Ilce"),
            "tarih": sutun_bul(r, "Fatura Tarihi", "Kayit Tarihi", "Islem Tarihi"),
        })
    if not kargolar:
        return {"ok": False,
                "message": "Dosyada takip no + alıcı adı sütunları bulunamadı."}

    bekleyenler = _bekleyen_gonderiler(db, user.tenant_id)
    if not bekleyenler:
        return {"ok": False, "message": "Takip numarası bekleyen gönderi yok."}

    _onay = {x.strip() for x in (onaylananlar or "").split(",") if x.strip()}
    sonuclar = kargo_eslestir.eslestir(bekleyenler, kargolar)

    rapor, uygulanan = [], 0
    for r in sonuclar:
        k, s = r["kargo"], r["siparis"]
        satir = {
            "takip_no": k["takip_no"], "kargo_ad": k["ad"],
            "kargo_il": k.get("il"), "durum": r["durum"],
            "skor": r["skor"], "detay": r["detay"],
            "siparis": None if not s else {
                "shipment_id": s["shipment_id"], "order_id": s["order_id"],
                "order_number": s["order_number"], "ad": s["ad"],
                "kaynak": s["kaynak"], "cikis_tarihi": s["cikis_tarihi"],
            },
        }
        if not uygula or not s:
            rapor.append(satir)
            continue
        if r["durum"] == "supheli" and s["shipment_id"] not in _onay:
            satir["aciklama"] = "Şüpheli — onaylanmadı, atlandı"
            rapor.append(satir)
            continue
        o = db.scalar(select(Order).where(Order.id == uuid.UUID(s["order_id"])))
        if not o:
            satir["aciklama"] = "Sipariş bulunamadı (bu arada değişmiş)"
            rapor.append(satir)
            continue
        sh = None
        if s.get("shipment_id"):
            sh = db.scalar(select(OrderShipment).where(
                OrderShipment.id == uuid.UUID(s["shipment_id"]),
                OrderShipment.tenant_id == user.tenant_id))
        if sh is None:
            # Basit Kargo akışı gönderi kaydı oluşturmuyor; takip no gelince
            # burada açılır — kalemler, aşama ve müşteri maili tek yerden yönetilsin.
            _kalan = _sh.remaining_counts(o)
            _items = [{"line_item_id": _k, "quantity": _v}
                      for _k, _v in _kalan.items() if _v > 0]
            if not _items:
                satir["aciklama"] = "Siparişin tüm kalemleri zaten gönderilmiş"
                rapor.append(satir)
                continue
            try:
                sh = _sh.create_shipment(
                    db, o, items=_items, takip_no=None,
                    kargo_firma=(o.kargo_info or {}).get("handler_name"),
                    note="Toplu takip no içe aktarma", user_label=user.email,
                    send_email=False,
                )
            except _sh.ShipmentError as e:
                satir["aciklama"] = f"Gönderi açılamadı: {str(e)[:100]}"
                rapor.append(satir)
                continue
        _mail = _sh.set_tracking(db, o, sh, takip_no=k["takip_no"],
                                 kargo_firma=sh.kargo_firma, send_email=mail_gonder)
        uygulanan += 1
        satir["durum"] = "uygulandi"
        satir["aciklama"] = "Takip no yazıldı" + (" · müşteriye mail gitti" if _mail else "")
        rapor.append(satir)

    if uygula:
        db.commit()
    _sayac: dict = {}
    for r in rapor:
        _sayac[r["durum"]] = _sayac.get(r["durum"], 0) + 1
    return {
        "ok": True, "uygulandi": uygula, "uygulanan": uygulanan,
        "dosya_satir": len(kargolar), "bekleyen": len(bekleyenler),
        "sayac": _sayac, "rapor": rapor,
    }


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
    _ki = order.kargo_info or {}
    data["is_acil"] = bool(
        order.cancelled_at is None
        and order.closed_at is None
        and not getattr(order, "is_iptal", False)
        and order.fulfillment_status != "fulfilled"
        and order.financial_status != "refunded"
        and (order.current_stage or 0) < 8
        and not _ki.get("takip_no")
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


# ─── Para iadesi (vitrin siparişleri — iyzico/PayTR API) ─────

class RefundRequest(BaseModel):
    amount: float
    reason: str | None = None


def _require_admin(user: User) -> None:
    """Para hareketi geniş 'siparisler' iznine binmez — yalnızca yönetici."""
    from app.auth.permissions import is_admin
    if not is_admin(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Para iadesi için yönetici yetkisi gerekli")


def _refund_context(db: Session, user: User, order_id: uuid.UUID):
    """Sipariş + ödeme oturumu + önceki başarılı iadeler toplamı."""
    from decimal import Decimal
    from app.models import CheckoutSession, Refund

    order = db.scalar(select(Order).where(
        Order.id == order_id, Order.tenant_id == user.tenant_id))
    if not order:
        raise HTTPException(404, "Sipariş bulunamadı")
    session = db.scalar(select(CheckoutSession).where(
        CheckoutSession.order_id == order.id, CheckoutSession.status == "paid"))
    if not session:
        raise HTTPException(404, "Bu sipariş panel üzerinden iade edilemez "
                                 "(yalnızca vitrin ödemeleri)")
    refunded = db.scalar(
        select(sql_func.coalesce(sql_func.sum(Refund.amount), 0)).where(
            Refund.order_id == order.id, Refund.status == "succeeded")
    ) or 0
    return order, session, Decimal(str(refunded))


@router.get("/{order_id}/requests", response_model=dict)
def list_order_requests(
    order_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Siparişin müşteri talepleri (iade/değişim/sorun) — sipariş detayı kartı."""
    from app.models import CustomerRequest
    order = db.scalar(select(Order).where(
        Order.id == order_id, Order.tenant_id == user.tenant_id))
    if not order:
        raise HTTPException(status_code=404, detail="Sipariş bulunamadı")
    rows = db.scalars(
        select(CustomerRequest).where(CustomerRequest.order_id == order.id)
        .order_by(CustomerRequest.created_at.desc())
    ).all()
    return {"requests": [
        {
            "id": str(r.id),
            "request_type": r.request_type,
            "message": r.message,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
        } for r in rows
    ]}


@router.post("/requests/{request_id}/resolve", response_model=dict)
def resolve_order_request(
    request_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from datetime import datetime, timezone
    from app.models import CustomerRequest
    req = db.scalar(select(CustomerRequest).where(
        CustomerRequest.id == request_id, CustomerRequest.tenant_id == user.tenant_id))
    if not req:
        raise HTTPException(status_code=404, detail="Talep bulunamadı")
    req.status = "cozuldu"
    req.resolved_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


@router.get("/{order_id}/refunds", response_model=dict)
def list_refunds(
    order_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(user)
    from app.models import Refund
    order, session, refunded = _refund_context(db, user, order_id)
    rows = db.scalars(select(Refund).where(Refund.order_id == order.id)
                      .order_by(Refund.created_at.desc())).all()
    return {
        "paid_amount": str(session.amount),
        "refunded_total": str(refunded),
        "refundable": str(session.amount - refunded),
        "provider": session.provider,
        "refunds": [
            {
                "id": str(r.id),
                "amount": str(r.amount),
                "status": r.status,
                "reason": r.reason,
                "error": r.error,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.post("/{order_id}/refund", response_model=dict)
def create_refund(
    order_id: uuid.UUID,
    body: RefundRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(user)
    from decimal import Decimal, InvalidOperation
    from app.models import Refund, Store as _Store
    from app.payments import get_payment_provider

    order, session, refunded = _refund_context(db, user, order_id)
    try:
        amount = Decimal(str(body.amount)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        raise HTTPException(422, "Geçersiz tutar")
    remaining = Decimal(str(session.amount)) - refunded
    if amount <= 0 or amount > remaining:
        raise HTTPException(422, f"Tutar 0 ile {remaining} TL arasında olmalı")

    store = db.get(_Store, session.store_id)
    provider = get_payment_provider(store)
    result = provider.refund(session, amount)

    refund = Refund(
        tenant_id=user.tenant_id,
        order_id=order.id,
        checkout_session_id=session.id,
        amount=amount,
        status=result.status,
        provider=session.provider,
        provider_ref=result.provider_ref,
        reason=(body.reason or "")[:500] or None,
        error=(result.error or "")[:500] or None,
        raw=result.raw or None,
        created_by=user.id,
    )
    db.add(refund)

    if result.status == "succeeded":
        new_total = refunded + amount
        full = new_total >= Decimal(str(session.amount))
        order.financial_status = "refunded" if full else "partially_refunded"
        db.add(OrderStatusHistory(
            tenant_id=order.tenant_id, order_id=order.id,
            action="iade",
            note=f"{amount} TL iade ({'tam' if full else 'kısmi'})"
                 + (f" — {body.reason}" if body.reason else ""),
            created_by=user.full_name or user.email,
        ))
        activity.record(db, user, "iade", store_id=order.store_id, entity_type="siparis",
                        entity_id=order.id, entity_label=order.name or order.order_number,
                        detail={"tutar": str(amount), "tam": full,
                                "sebep": (body.reason or "")[:120] or None})
    db.commit()

    if result.status != "succeeded":
        raise HTTPException(502, f"İade başarısız: {result.error or 'sağlayıcı hatası'}")
    return {
        "status": "succeeded",
        "amount": str(amount),
        "financial_status": order.financial_status,
        "refunded_total": str(refunded + amount),
    }
