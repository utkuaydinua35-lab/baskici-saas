"""
Vitrin siparişi oluşturma — ödemesi DOĞRULANMIŞ CheckoutSession → Order.

Shopify-şekilli raw payload üretip mevcut _upsert_order()'a verir; böylece
kalıp planlama, üretim hattı, kargo ve admin paneli sıfır değişiklikle çalışır.
LineItem'lara device_model_override + kilif_varyasyon yazılır (mold_planner
extract_phone_model önceliği).
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import text as sa_text, update
from sqlalchemy.orm import Session

from app.models import CatalogVariant, CheckoutSession, Order, StockItem, Store
from app.services import email_service


def _next_order_number(db: Session) -> int:
    return int(db.execute(sa_text("SELECT nextval('storefront_order_number_seq')")).scalar())


def _build_raw(session: CheckoutSession, order_number: int) -> dict:
    """adapters/base.py'de belgelenen Shopify dict şemasına normalize et."""
    cust = session.customer or {}
    full_name = f"{cust.get('first_name', '')} {cust.get('last_name', '')}".strip()
    line_items = []
    for n, item in enumerate(session.cart_snapshot or []):
        line_items.append({
            "id": f"sfli_{session.id.hex}_{n}",
            "product_id": item.get("product_id"),
            "variant_id": item.get("variant_id"),
            "title": item.get("title", ""),
            "variant_title": " / ".join(
                x for x in (item.get("model_display"), item.get("variation")) if x
            ),
            "sku": item.get("sku"),
            "quantity": int(item.get("quantity", 1)),
            "price": item.get("unit_price"),
            "properties": [
                {"name": "Telefon Modeli", "value": item.get("model_display") or ""},
            ] + ([{"name": "Renk", "value": item["variation"]}] if item.get("variation") else []),
        })

    return {
        "id": f"sf_{session.id.hex}",
        "order_number": order_number,
        "name": f"#{order_number}",
        "created_at": (session.paid_at or datetime.now(timezone.utc)).isoformat(),
        "financial_status": "paid",
        "fulfillment_status": None,  # → hat başından girer (stage 1)
        "customer": {
            "first_name": cust.get("first_name", ""),
            "last_name": cust.get("last_name", ""),
            "email": cust.get("email", ""),
        },
        "email": cust.get("email", ""),
        "shipping_address": {
            "name": full_name,
            "address1": cust.get("address1", ""),
            "city": cust.get("province", ""),      # ilçe
            "province": cust.get("city", ""),      # il (Shopify: province=il)
            "zip": cust.get("zip", ""),
            "phone": cust.get("phone", ""),
            "country": "Turkey",
        },
        "line_items": line_items,
        "note": cust.get("note") or None,
        "tags": "storefront",
        # Ek anahtarlar raw JSONB'de zararsız — denetim için ödeme özeti
        "payment": {
            "provider": session.provider,
            "provider_ref": session.provider_ref,
            "amount": str(session.amount),
            "shipping_amount": str(session.shipping_amount),
            "currency": session.currency,
        },
    }


def _decrement_stock(db: Session, session: CheckoutSession, order: Order) -> None:
    """Varyant stoğunu atomik düş; yarış kaybedilirse siparişi REDDETME —
    kalemi tedarik-bekliyor işaretle (ödemesi alınmış müşteri mağdur olmaz)."""
    from app.services import stock as stock_svc

    for item in (session.cart_snapshot or []):
        qty = int(item.get("quantity", 1))
        vid = item.get("variant_id")
        res = db.execute(
            update(CatalogVariant)
            .where(
                CatalogVariant.id == vid,
                CatalogVariant.track_stock.is_(True),
                CatalogVariant.quantity >= qty,
            )
            .values(quantity=CatalogVariant.quantity - qty)
        )
        variant = db.get(CatalogVariant, vid)
        track = bool(variant and variant.track_stock)
        if track and res.rowcount == 0:
            # checkout ile ödeme arasında stok tükendi — tedarik bekleme akışına al
            for li in order.line_items:
                if li.variant_id == str(vid):
                    li.tedarik_status = "bekliyor"
        # Fiziksel stok bağı varsa hareket kaydı yaz (denetim izi)
        sid = item.get("stock_item_id")
        if sid:
            stock_item = db.get(StockItem, sid)
            if stock_item:
                try:
                    stock_svc._move(
                        db, stock_item, -qty, "vitrin_satis",
                        ref_order_id=order.id, note=f"Vitrin #{order.order_number}",
                    )
                except Exception as e:  # stok kaydı düşmese de sipariş yaşar
                    print(f"[vitrin] stok hareketi yazılamadı: {e}")


def _send_confirmation_email(db: Session, session: CheckoutSession, order: Order, store: Store) -> None:
    cust = session.customer or {}
    email = cust.get("email")
    if not email:
        return

    tenant = getattr(store, "tenant", None)
    brand = email_service.brand_kwargs(tenant) if tenant else {}

    rows = "".join(
        f"<tr><td style='padding:6px 0;color:#374151;font-size:14px'>"
        f"{i.get('title', '')} — {i.get('model_display', '')}"
        f"{(' / ' + i['variation']) if i.get('variation') else ''} × {i.get('quantity', 1)}</td>"
        f"<td align='right' style='padding:6px 0;color:#111827;font-size:14px;white-space:nowrap'>"
        f"{Decimal(str(i.get('unit_price', '0'))) * int(i.get('quantity', 1)):.2f} ₺</td></tr>"
        for i in (session.cart_snapshot or [])
    )
    shipping_row = ""
    if session.shipping_amount and Decimal(str(session.shipping_amount)) > 0:
        shipping_row = (
            f"<tr><td style='padding:6px 0;color:#374151;font-size:14px'>Kargo</td>"
            f"<td align='right' style='padding:6px 0;font-size:14px'>{session.shipping_amount} ₺</td></tr>"
        )

    config = store.config or {}
    site = (config.get("storefront_url") or f"https://{config.get('shop_domain', '')}").rstrip("/")
    track_url = f"{site}/siparis/{session.lookup_token}"

    body = (
        f"<p>Merhaba {cust.get('first_name', '')},</p>"
        f"<p>Siparişiniz alındı ve üretim sırasına eklendi. "
        f"Sipariş numaranız: <b>#{order.order_number}</b></p>"
        f"<table width='100%' style='border-collapse:collapse;margin:10px 0'>{rows}{shipping_row}"
        f"<tr><td style='padding:10px 0 0;font-weight:700'>Toplam</td>"
        f"<td align='right' style='padding:10px 0 0;font-weight:700'>{session.amount} ₺</td></tr></table>"
        f"<p style='color:#6b7280;font-size:13px'>Siparişiniz kişiye özel üretilir ve "
        f"1–3 iş günü içinde kargoya verilir.</p>"
    )
    html = email_service.render_email(
        title="Siparişiniz Alındı",
        body_html=body,
        button_text="Siparişimi Takip Et",
        button_url=track_url,
        preheader=f"#{order.order_number} numaralı siparişiniz alındı",
        emoji="🛍️",
        **brand,
    )
    email_service.send_email(email, f"Siparişiniz alındı — #{order.order_number}", html)


def create_order_from_session(db: Session, session: CheckoutSession) -> Order:
    """Ödemesi doğrulanmış session'dan Order üret (idempotent değil —
    çağıran process_payment_result idempotency'yi garanti eder)."""
    from app.routers.orders import _upsert_order  # sync_service ile aynı desen

    store = db.get(Store, session.store_id)
    order_number = _next_order_number(db)
    raw = _build_raw(session, order_number)

    order, _, _ = _upsert_order(
        db, tenant_id=session.tenant_id, store_id=session.store_id, raw=raw,
    )
    db.flush()

    # Kalıp planlayıcı doğrudan çalışsın: model + varyasyon alanlarını doldur
    by_ext = {f"sfli_{session.id.hex}_{n}": item
              for n, item in enumerate(session.cart_snapshot or [])}
    for li in order.line_items:
        item = by_ext.get(li.external_id or "")
        if item:
            li.device_model_override = item.get("model_display")
            li.kilif_varyasyon = item.get("variation")

    _decrement_stock(db, session, order)
    session.order_id = order.id

    try:
        _send_confirmation_email(db, session, order, store)
    except Exception as e:  # e-posta hatası siparişi geri almaz
        print(f"[vitrin] onay e-postası gönderilemedi: {e}")

    return order
