"""
Sipariş Takip (public) servisi — bernz-order-tracker'dan baskıcı'ya port.

MongoDB yerine Postgres (TrackerOrderStage). Shopify sorgusu mevcut BERNZ
ShopifyAdapter'ı (postgres'teki token) ile yapılır — ayrı token gerekmez.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.shopify import ShopifyAdapter
from app.config import get_settings
from app.models import Store, TrackerOrderStage

# ── BERNZ özel aşamaları (track.html'deki COLORS/id'lerle birebir) ──
BERNZ_STAGES = [
    {"id": "siparis_alindi", "label": "Sipariş Alındı", "description": "Siparişin başarıyla alındı.", "icon": "✓", "color": "#4ade80"},
    {"id": "tasarim_hazirlaniyor", "label": "Tasarım Hazırlanıyor", "description": "Ürününe özel tasarım hazırlanıyor.", "icon": "✦", "color": "#60a5fa"},
    {"id": "uv_baskida", "label": "UV Baskıda", "description": "Tasarım UV baskı makinasında işleniyor.", "icon": "◈", "color": "#f59e0b"},
    {"id": "kalite_kontrol", "label": "Kalite Kontrol", "description": "Ürün kalite kontrolden geçiyor.", "icon": "◉", "color": "#a78bfa"},
    {"id": "kargoya_verildi", "label": "Kargoya Verildi", "description": "Ürün kargoya teslim edildi.", "icon": "→", "color": "#fb923c"},
    {"id": "teslim_edildi", "label": "Teslim Edildi", "description": "Sipariş adresine ulaştı.", "icon": "★", "color": "#34d399"},
]
STAGE_IDS = [s["id"] for s in BERNZ_STAGES]
STAGE_MAP = {s["id"]: s for s in BERNZ_STAGES}


def shopify_status_to_stage(fulfillment_status, cancelled_at) -> str:
    if cancelled_at:
        return "siparis_alindi"
    if fulfillment_status == "fulfilled":
        return "kargoya_verildi"
    return "siparis_alindi"


def resolve_tracker_store(db: Session) -> Store | None:
    """TRACKER_SHOP_DOMAIN ile eşleşen aktif Shopify mağazasını bul (BERNZ)."""
    domain = get_settings().tracker_shop_domain
    stores = db.scalars(
        select(Store).where(Store.platform == "shopify", Store.is_active.is_(True))
    ).all()
    for s in stores:
        if (s.config or {}).get("store_url") == domain:
            return s
    # fallback: domain boş/eşleşmediyse ilk shopify mağaza
    return stores[0] if stores else None


def fetch_order_for_tracking(store: Store, order_number: str, email: str) -> dict | None:
    """Sipariş no + e-posta ile Shopify'dan sorgula (e-posta EŞLEŞMESİ şart)."""
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
    # Shopify email eşleşmesi bazen gevşek — kesin kontrol
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
        {
            "name": it.get("name", ""),
            "quantity": it.get("quantity", 1),
            "variant_title": it.get("variant_title", ""),
        }
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
        active_id = shopify_status_to_stage(info["fulfillment_status"], info["cancelled_at"])
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
