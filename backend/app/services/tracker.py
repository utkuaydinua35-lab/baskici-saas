"""
Sipariş Takip (public) servisi — otomatik aşama hesaplı (Paket 2).

Aşama, müşteri sorguladığı anda siparişin GERÇEK üretim durumundan hesaplanır
(yazma/scheduler yok, her zaman güncel). Elle override istenirse
tracker_order_stages tablosuna yazılan kayıt önceliklidir.

Otomatik kurallar (yüksekten düşüğe):
  teslim_edildi   ← Shopify fulfillment shipment_status = delivered
  kargoya_verildi ← fulfillment_status = fulfilled VEYA kargo takip no var
  kalite_kontrol  ← sipariş bir kalıpta ve o kalıp basıldı (Mold.current_stage >= 5)
  uv_baskida      ← sipariş bir kalıpta (henüz basılmadı)
  tasarim_hazirlaniyor (etiket: İşleme Alındı) ← kalıpta değil ama Shopify created_at'ten 12+ saat geçmiş
  siparis_alindi  ← varsayılan
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.adapters.shopify import ShopifyAdapter
from app.config import get_settings
from app.models import LineItem, Mold, MoldItem, Order, Store, TrackerOrderStage

# ── BERNZ özel aşamaları (track.html'deki COLORS/id'lerle birebir id) ──
BERNZ_STAGES = [
    {"id": "siparis_alindi", "label": "Sipariş Alındı", "description": "Siparişin başarıyla alındı.", "icon": "✓", "color": "#4ade80"},
    {"id": "tasarim_hazirlaniyor", "label": "İşleme Alındı", "description": "Ürününe özel tasarım hazırlanıyor.", "icon": "✦", "color": "#60a5fa"},
    {"id": "uv_baskida", "label": "UV Baskıda", "description": "Tasarım UV baskı makinasında işleniyor.", "icon": "◈", "color": "#f59e0b"},
    {"id": "kalite_kontrol", "label": "Kalite Kontrol", "description": "Ürün kalite kontrolden geçiyor.", "icon": "◉", "color": "#a78bfa"},
    {"id": "kargoya_verildi", "label": "Kargoya Verildi", "description": "Ürün kargoya teslim edildi.", "icon": "→", "color": "#fb923c"},
    {"id": "teslim_edildi", "label": "Teslim Edildi", "description": "Sipariş adresine ulaştı.", "icon": "★", "color": "#34d399"},
]
STAGE_IDS = [s["id"] for s in BERNZ_STAGES]
STAGE_MAP = {s["id"]: s for s in BERNZ_STAGES}

PRINTED_STAGE = 5  # Mold.current_stage == 5  → kalıp.pdf indirildi / basıldı
PROCESSING_HOURS = 12


# ─── Saf karar mantığı (test edilebilir, DB'siz) ───
def decide_stage(*, cancelled, delivered, fulfilled_or_tracking, in_mold, min_mold_stage, hours_since) -> str:
    if cancelled:
        return "siparis_alindi"
    if delivered:
        return "teslim_edildi"
    if fulfilled_or_tracking:
        return "kargoya_verildi"
    if in_mold:
        if min_mold_stage is not None and min_mold_stage >= PRINTED_STAGE:
            return "kalite_kontrol"
        return "uv_baskida"
    if hours_since is not None and hours_since >= PROCESSING_HOURS:
        return "tasarim_hazirlaniyor"
    return "siparis_alindi"


def resolve_tracker_store(db: Session) -> Store | None:
    domain = get_settings().tracker_shop_domain
    stores = db.scalars(
        select(Store).where(Store.platform == "shopify", Store.is_active.is_(True))
    ).all()
    for s in stores:
        if (s.config or {}).get("store_url") == domain:
            return s
    return stores[0] if stores else None


def fetch_order_for_tracking(store: Store, order_number: str, email: str) -> dict | None:
    adapter = ShopifyAdapter(store)
    clean = order_number.lstrip("#").strip()
    email_n = email.lower().strip()
    r = adapter.session.get(
        f"{adapter._base_url()}/orders.json",
        headers=adapter._headers(),
        params={
            "name": f"#{clean}",
            "email": email_n,
            "status": "any",
            "fields": (
                "id,name,order_number,email,created_at,updated_at,"
                "financial_status,fulfillment_status,fulfillments,"
                "line_items,shipping_address,note,cancel_reason,cancelled_at"
            ),
        },
        timeout=12,
    )
    if r.status_code != 200:
        return None
    orders = r.json().get("orders", [])
    if not orders:
        return None
    order = orders[0]
    if (order.get("email") or "").lower() != email_n:
        return None
    return order


def extract_tracking_info(order: dict) -> dict:
    fulfillments = order.get("fulfillments", []) or []
    tracking_numbers, tracking_urls, carrier = [], [], None
    for f in fulfillments:
        if f.get("tracking_number"):
            tracking_numbers.append(f["tracking_number"])
        if f.get("tracking_url"):
            tracking_urls.append(f["tracking_url"])
        if f.get("tracking_company"):
            carrier = f["tracking_company"]
    line_items = [
        {"name": it.get("name", ""), "quantity": it.get("quantity", 1), "variant_title": it.get("variant_title", "")}
        for it in order.get("line_items", []) or []
    ]
    return {
        "shopify_order_id": str(order["id"]),
        "order_name": order.get("name", ""),
        "order_number": str(order.get("order_number", "")),
        "created_at": order.get("created_at"),
        "financial_status": order.get("financial_status"),
        "fulfillment_status": order.get("fulfillment_status"),
        "cancelled_at": order.get("cancelled_at"),
        "line_items": line_items,
        "tracking_numbers": tracking_numbers,
        "tracking_urls": tracking_urls,
        "carrier": carrier,
    }


def _mold_stages_for_order(db: Session, order: Order) -> list[int]:
    """Siparişin parçalarının bulunduğu kalıpların current_stage listesi."""
    li_subq = select(LineItem.id).where(LineItem.order_id == order.id)
    rows = db.execute(
        select(Mold.current_stage)
        .join(MoldItem, MoldItem.mold_id == Mold.id)
        .where(
            or_(
                MoldItem.line_item_id.in_(li_subq),
                and_(
                    MoldItem.tenant_id == order.tenant_id,
                    MoldItem.order_number == order.order_number,
                ),
            )
        )
    ).scalars().all()
    return [s for s in rows if s is not None]


def _hours_since(dt: datetime | None) -> float | None:
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def compute_stage(db: Session, store: Store, live_order: dict, info: dict) -> str:
    """Otomatik aşama — siparişin gerçek üretim durumundan."""
    cancelled = bool(info.get("cancelled_at"))
    fulfillments = live_order.get("fulfillments", []) or []
    delivered = any((f.get("shipment_status") == "delivered") for f in fulfillments)
    fulfilled_or_tracking = (info.get("fulfillment_status") == "fulfilled") or bool(info.get("tracking_numbers"))

    in_mold = False
    min_mold_stage = None
    hours_since = _hours_since(_parse_iso(info.get("created_at")))

    o = db.scalar(
        select(Order).where(Order.store_id == store.id, Order.external_id == info["shopify_order_id"])
    )
    if o:
        if o.created_at_platform:
            hours_since = _hours_since(o.created_at_platform)
        stages = _mold_stages_for_order(db, o)
        if stages:
            in_mold = True
            min_mold_stage = min(stages)

    return decide_stage(
        cancelled=cancelled,
        delivered=delivered,
        fulfilled_or_tracking=fulfilled_or_tracking,
        in_mold=in_mold,
        min_mold_stage=min_mold_stage,
        hours_since=hours_since,
    )


def get_custom_stage(db: Session, shopify_order_id: str) -> TrackerOrderStage | None:
    return db.scalar(
        select(TrackerOrderStage).where(TrackerOrderStage.shopify_order_id == shopify_order_id)
    )


def build_track_response(db: Session, order: dict) -> dict:
    info = extract_tracking_info(order)

    custom = get_custom_stage(db, info["shopify_order_id"])
    if custom and custom.stage_id in STAGE_MAP:
        active_id = custom.stage_id
        note = custom.note
    else:
        store = resolve_tracker_store(db)
        active_id = compute_stage(db, store, order, info) if store else "siparis_alindi"
        note = None

    active_index = next((i for i, s in enumerate(BERNZ_STAGES) if s["id"] == active_id), 0)
    timeline = []
    for i, stage in enumerate(BERNZ_STAGES):
        timeline.append({
            **stage,
            "status": "completed" if i < active_index else ("active" if i == active_index else "pending"),
        })

    return {
        "order": info,
        "active_stage": STAGE_MAP[active_id],
        "stage_note": note,
        "timeline": timeline,
        "is_cancelled": bool(info.get("cancelled_at")),
    }
