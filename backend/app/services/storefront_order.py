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

from app.models import CatalogVariant, CheckoutSession, DiscountCode, Order, StockItem, Store
from app.services import email_service


def _next_order_number(db: Session) -> int:
    return int(db.execute(sa_text("SELECT nextval('storefront_order_number_seq')")).scalar())


# TR standardı: vitrin fiyatları KDV DAHİL. Fatura/muhasebe için tutarın
# içindeki vergi ayrıştırılır. Oran mağaza ayarından (varsayılan %20).
DEFAULT_TAX_RATE = Decimal("20")


def _tax_rate(store: Store | None) -> Decimal:
    try:
        raw = ((store.config or {}).get("tax_rate") if store else None)
        return Decimal(str(raw)) if raw not in (None, "") else DEFAULT_TAX_RATE
    except Exception:  # noqa: BLE001 — bozuk ayar varsayılana düşsün
        return DEFAULT_TAX_RATE


def _tax_included(session: CheckoutSession, store: Store | None) -> Decimal:
    """Toplam tutarın İÇİNDEKİ KDV: tutar - (tutar / (1 + oran/100))."""
    rate = _tax_rate(store)
    if rate <= 0:
        return Decimal("0.00")
    total = Decimal(str(session.amount or 0))
    net = (total / (Decimal("1") + rate / Decimal("100")))
    return (total - net).quantize(Decimal("0.01"))


def _build_raw(session: CheckoutSession, order_number: int,
               store: Store | None = None) -> dict:
    """adapters/base.py'de belgelenen Shopify dict şemasına normalize et."""
    cust = session.customer or {}
    full_name = f"{cust.get('first_name', '')} {cust.get('last_name', '')}".strip()
    line_items = []
    for n, item in enumerate(session.cart_snapshot or []):
        # Kişiye özel alanlar → Shopify tarzı properties (panelde/üretimde görünür)
        custom_props = []
        labels = item.get("custom_labels") or {}
        for key, val in (item.get("custom") or {}).items():
            custom_props.append({"name": labels.get(key, key), "value": val})

        props = [
            {"name": "Telefon Modeli", "value": item.get("model_display") or ""},
        ] + ([{"name": "Renk", "value": item["variation"]}] if item.get("variation") else []) \
          + ([{"name": "2. Kılıf Modeli", "value": item["second_model_display"]}]
             if item.get("second_model_display") else []) \
          + custom_props

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
            "properties": props,
        })

        # Couple ürün: 2. kılıf ÜRETİM için ayrı kalem (fiyatı 0 — tutar ilk
        # kalemde; kalıp planlayıcı her iki modeli de görür)
        if item.get("second_model_display"):
            line_items.append({
                "id": f"sfli_{session.id.hex}_{n}b",
                "product_id": item.get("product_id"),
                "variant_id": item.get("second_variant_id"),
                "title": f"{item.get('title', '')} — 2. kılıf (set)",
                "variant_title": " / ".join(
                    x for x in (item.get("second_model_display"), item.get("variation")) if x
                ),
                "sku": item.get("sku"),
                "quantity": int(item.get("quantity", 1)),
                "price": "0.00",
                "properties": [
                    {"name": "Telefon Modeli", "value": item["second_model_display"]},
                    {"name": "Set", "value": "Çift kılıf setinin 2. parçası"},
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
        # Dashboard/analitik ciroyu raw.total_price'tan okur — Shopify şemasıyla aynı
        "total_price": str(session.amount),
        "subtotal_price": str(
            Decimal(str(session.amount)) - Decimal(str(session.shipping_amount or 0))
        ),
        "total_discounts": str(session.discount_amount or 0),
        # KDV — TR'de vitrin fiyatları KDV DAHİL gösterilir; fatura için
        # tutarın içindeki vergi ayrıştırılır: kdv = tutar - (tutar / (1+oran))
        "total_tax": str(_tax_included(session, store)),
        "taxes_included": True,
        # Ek anahtarlar raw JSONB'de zararsız — denetim için ödeme özeti
        "payment": {
            "provider": session.provider,
            "provider_ref": session.provider_ref,
            "amount": str(session.amount),
            "shipping_amount": str(session.shipping_amount),
            "currency": session.currency,
        },
        **({"discount": {"code": session.discount_code,
                         "amount": str(session.discount_amount)}}
           if session.discount_code else {}),
        # Kurumsal fatura bilgisi (checkout'ta opsiyonel) — panel detayda gösterilir
        **({"invoice": {
            "company": cust.get("invoice_company"),
            "tax_office": cust.get("invoice_tax_office"),
            "tax_no": cust.get("invoice_tax_no"),
        }} if cust.get("invoice_company") or cust.get("invoice_tax_no") else {}),
    }


def _decrement_stock(db: Session, session: CheckoutSession, order: Order) -> None:
    """Varyant stoğunu atomik düş; yarış kaybedilirse siparişi REDDETME —
    kalemi tedarik-bekliyor işaretle (ödemesi alınmış müşteri mağdur olmaz)."""
    from app.services import stock as stock_svc

    # Couple setlerde ikinci varyantın stoğu da düşer
    stock_entries = []
    for item in (session.cart_snapshot or []):
        stock_entries.append((item, item.get("variant_id")))
        if item.get("second_variant_id"):
            stock_entries.append((item, item.get("second_variant_id")))

    for item, vid in stock_entries:
        qty = int(item.get("quantity", 1))
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
    discount_row = ""
    if session.discount_code and Decimal(str(session.discount_amount or 0)) > 0:
        discount_row = (
            f"<tr><td style='padding:6px 0;color:#059669;font-size:14px'>"
            f"İndirim ({session.discount_code})</td>"
            f"<td align='right' style='padding:6px 0;color:#059669;font-size:14px'>"
            f"−{session.discount_amount} ₺</td></tr>"
        )

    config = store.config or {}
    site = (config.get("storefront_url") or f"https://{config.get('shop_domain', '')}").rstrip("/")
    track_url = f"{site}/siparis/{session.lookup_token}"

    subj_over, intro_over = email_service.store_email_text(store, "siparis_onay")
    body = (
        f"<p>Merhaba {cust.get('first_name', '')},</p>"
        + (intro_over or "")
        + f"<p>Siparişiniz alındı ve üretim sırasına eklendi. "
        f"Sipariş numaranız: <b>#{order.order_number}</b></p>"
        f"<table width='100%' style='border-collapse:collapse;margin:10px 0'>{rows}{discount_row}{shipping_row}"
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
    email_service.send_email(
        email, subj_over or f"Siparişiniz alındı — #{order.order_number}", html)


def create_order_from_session(db: Session, session: CheckoutSession) -> Order:
    """Ödemesi doğrulanmış session'dan Order üret (idempotent değil —
    çağıran process_payment_result idempotency'yi garanti eder)."""
    from app.routers.orders import _upsert_order  # sync_service ile aynı desen

    store = db.get(Store, session.store_id)
    order_number = _next_order_number(db)
    raw = _build_raw(session, order_number, store)

    order, _, _ = _upsert_order(
        db, tenant_id=session.tenant_id, store_id=session.store_id, raw=raw,
    )
    db.flush()

    # Kalıp planlayıcı doğrudan çalışsın: model + varyasyon alanlarını doldur
    # (couple setin 2. kalemi "_{n}b" ekiyle gelir — ikinci modeli alır)
    by_ext: dict[str, tuple[dict, bool]] = {}
    for n, item in enumerate(session.cart_snapshot or []):
        by_ext[f"sfli_{session.id.hex}_{n}"] = (item, False)
        if item.get("second_model_display"):
            by_ext[f"sfli_{session.id.hex}_{n}b"] = (item, True)
    for li in order.line_items:
        hit = by_ext.get(li.external_id or "")
        if hit:
            item, is_second = hit
            li.device_model_override = (
                item.get("second_model_display") if is_second else item.get("model_display"))
            li.kilif_varyasyon = item.get("variation")

    _decrement_stock(db, session, order)
    session.order_id = order.id

    # Kupon kullanım sayacı YALNIZCA burada (doğrulanmış ödeme) artar — atomik
    if session.discount_code_id:
        db.execute(
            update(DiscountCode)
            .where(DiscountCode.id == session.discount_code_id)
            .values(usage_count=DiscountCode.usage_count + 1)
        )

    try:
        _send_confirmation_email(db, session, order, store)
    except Exception as e:  # e-posta hatası siparişi geri almaz
        print(f"[vitrin] onay e-postası gönderilemedi: {e}")

    return order
