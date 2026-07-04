"""
Public vitrin API'si — AUTH YOK (müşteriye açık).

Next.js vitrini bu endpoint'leri SUNUCUDAN SUNUCUYA çağırır (tarayıcı doğrudan
gelmez → CORS gerekmez). Ödeme sağlayıcı callback'leri de buraya gelir.

- GET  /api/shop/{store_slug}/products                → aktif ürün listesi
- GET  /api/shop/{store_slug}/products/{product_slug} → ürün detayı
- POST /api/shop/{store_slug}/checkout                → ödeme oturumu başlat
- GET  /api/shop/checkout/{token}/status              → sonuç sayfası poll'u
- POST /api/shop/payments/iyzico/callback/{token}     → iyzico dönüşü (doğrula+redirect)
- POST /api/shop/payments/paytr/webhook               → PayTR bildirimi (hash+OK)
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse, RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import CatalogProduct, CatalogVariant, CheckoutSession, Store
from app.payments import get_payment_provider
from app.services import checkout as checkout_svc
from app.services.rate_limit import client_ip, make_rate_limiter

router = APIRouter(prefix="/api/shop", tags=["public-shop"])

# Okuma uçları için cömert limit (katalog gezinme); yazma uçları ayrı, sıkı sayaç.
read_rate_limit = make_rate_limiter(max_hits=60, window=60.0)
checkout_rate_limit = make_rate_limiter(max_hits=10, window=60.0)
status_rate_limit = make_rate_limiter(max_hits=30, window=60.0)


def _resolve_store(db: Session, store_slug: str) -> Store:
    """Vitrin mağazasını slug ile çöz. Yalnızca platform='storefront' + aktif."""
    store = db.scalar(select(Store).where(
        Store.slug == store_slug,
        Store.platform == "storefront",
        Store.is_active.is_(True),
    ))
    if not store:
        raise HTTPException(404, "Mağaza bulunamadı")
    return store


def _effective_price(product: CatalogProduct, variant: CatalogVariant) -> str:
    price = variant.price_override if variant.price_override is not None else product.base_price
    return str(price)


def _serialize_product_card(p: CatalogProduct) -> dict:
    """Liste kartı — minimum alan (PII yok, iç ID'ler yalnızca gerekli olanlar)."""
    active_variants = [v for v in p.variants if v.is_active]
    models = sorted({v.model_display for v in active_variants})
    return {
        "slug": p.slug,
        "title": p.title,
        "price": str(p.base_price),
        "compare_at_price": str(p.compare_at_price) if p.compare_at_price is not None else None,
        "currency": p.currency,
        "cover_image": f"/storage/{p.images[0].file_path}" if p.images else None,
        "tags": p.tags,
        "model_count": len(models),
    }


def _serialize_product_detail(p: CatalogProduct) -> dict:
    return {
        "slug": p.slug,
        "title": p.title,
        "description": p.description,
        "seo_title": p.seo_title,
        "seo_description": p.seo_description,
        "price": str(p.base_price),
        "compare_at_price": str(p.compare_at_price) if p.compare_at_price is not None else None,
        "currency": p.currency,
        "tags": p.tags,
        "images": [
            {"url": f"/storage/{im.file_path}", "alt": im.alt,
             "variant_id": str(im.variant_id) if im.variant_id else None}
            for im in p.images
        ],
        "variants": [
            {
                "id": str(v.id),
                "model_key": v.model_key,
                "model_display": v.model_display,
                "brand": v.brand,
                "variation": v.variation,
                "price": _effective_price(p, v),
                "in_stock": (not v.track_stock) or v.quantity > 0,
            }
            for v in p.variants if v.is_active
        ],
    }


@router.get("/{store_slug}/collections")
def list_collections(
    store_slug: str,
    response: Response,
    _rl: None = Depends(read_rate_limit),
    db: Session = Depends(get_db),
):
    from app.models import CatalogCollection

    store = _resolve_store(db, store_slug)
    collections = db.scalars(
        select(CatalogCollection).where(
            CatalogCollection.store_id == store.id,
            CatalogCollection.is_active.is_(True),
        ).order_by(CatalogCollection.position, CatalogCollection.created_at)
    ).all()
    response.headers["Cache-Control"] = "public, max-age=60"
    return [
        {"slug": c.slug, "title": c.title, "description": c.description}
        for c in collections
    ]


@router.get("/{store_slug}/products")
def list_products(
    store_slug: str,
    response: Response,
    q: str | None = Query(None, max_length=100),
    tag: str | None = Query(None, max_length=50),
    model: str | None = Query(None, max_length=120),
    collection: str | None = Query(None, max_length=200),
    page: int = Query(1, ge=1, le=1000),
    per_page: int = Query(24, ge=1, le=60),
    _rl: None = Depends(read_rate_limit),
    db: Session = Depends(get_db),
):
    store = _resolve_store(db, store_slug)

    query = (
        select(CatalogProduct)
        .where(
            CatalogProduct.store_id == store.id,
            CatalogProduct.status == "active",
        )
        .options(selectinload(CatalogProduct.variants), selectinload(CatalogProduct.images))
        .order_by(CatalogProduct.position, CatalogProduct.created_at.desc())
    )
    if q:
        query = query.where(CatalogProduct.title.ilike(f"%{q}%"))
    if tag:
        query = query.where(CatalogProduct.tags.ilike(f"%{tag}%"))
    if collection:
        from app.models import CatalogCollection, catalog_product_collections
        query = query.join(
            catalog_product_collections,
            catalog_product_collections.c.product_id == CatalogProduct.id,
        ).join(
            CatalogCollection,
            CatalogCollection.id == catalog_product_collections.c.collection_id,
        ).where(
            CatalogCollection.slug == collection,
            CatalogCollection.is_active.is_(True),
        )

    products = db.scalars(query).all()
    if model:
        m = model.lower()
        products = [
            p for p in products
            if any(m in v.model_display.lower() for v in p.variants if v.is_active)
        ]

    total = len(products)
    start = (page - 1) * per_page
    items = products[start:start + per_page]

    response.headers["Cache-Control"] = "public, max-age=60"
    config = store.config or {}
    return {
        "store": {
            "name": store.name,
            "settings": {
                "shipping_fee": config.get("shipping_fee"),
                "free_shipping_over": config.get("free_shipping_over"),
                "min_order_amount": config.get("min_order_amount"),
            },
        },
        "total": total,
        "page": page,
        "per_page": per_page,
        "items": [_serialize_product_card(p) for p in items],
    }


@router.get("/{store_slug}/products/{product_slug}")
def get_product(
    store_slug: str,
    product_slug: str,
    response: Response,
    _rl: None = Depends(read_rate_limit),
    db: Session = Depends(get_db),
):
    store = _resolve_store(db, store_slug)
    product = db.scalar(
        select(CatalogProduct)
        .where(
            CatalogProduct.store_id == store.id,
            CatalogProduct.slug == product_slug,
            CatalogProduct.status == "active",
        )
        .options(selectinload(CatalogProduct.variants), selectinload(CatalogProduct.images))
    )
    if not product:
        raise HTTPException(404, "Ürün bulunamadı")

    response.headers["Cache-Control"] = "public, max-age=60"
    return _serialize_product_detail(product)


# ─── Checkout + Ödeme ────────────────────────────────────────

class CheckoutItemIn(BaseModel):
    variant_id: uuid.UUID
    quantity: int = Field(..., ge=1, le=20)


class CheckoutCustomerIn(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: str = Field(..., min_length=7, max_length=20)
    address1: str = Field(..., min_length=5, max_length=300)
    city: str = Field(..., min_length=2, max_length=60)
    province: str | None = Field(None, max_length=60)
    zip: str | None = Field(None, max_length=20)
    note: str | None = Field(None, max_length=500)


class CheckoutRequest(BaseModel):
    items: list[CheckoutItemIn] = Field(..., min_length=1, max_length=30)
    customer: CheckoutCustomerIn
    kvkk_accept: bool
    discount_code: str | None = Field(None, max_length=40)


class ValidateCodeRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=40)
    items: list[CheckoutItemIn] = Field(..., min_length=1, max_length=30)
    email: str | None = Field(None, max_length=200)


@router.post("/{store_slug}/checkout/validate-code")
def validate_discount_code(
    store_slug: str,
    body: ValidateCodeRequest,
    request: Request,
    _rl: None = Depends(status_rate_limit),
    db: Session = Depends(get_db),
):
    """Kupon kodunu ödeme öncesi doğrula (hiçbir kayıt yaratmaz — UX için)."""
    from decimal import Decimal

    store = _resolve_store(db, store_slug)
    try:
        _snapshot, items_total = checkout_svc.validate_and_snapshot(
            db, store,
            [{"variant_id": str(i.variant_id), "quantity": i.quantity} for i in body.items])
        dc, discount, free_shipping = checkout_svc.apply_discount(
            db, store, body.code, items_total, body.email)
    except checkout_svc.CheckoutError as e:
        return {"valid": False, "message": str(e)}

    shipping = Decimal("0") if free_shipping else checkout_svc._shipping_fee(store, items_total)
    return {
        "valid": True,
        "code": dc.code,
        "kind": dc.kind,
        "discount_amount": str(discount),
        "free_shipping": free_shipping,
        "new_total": str(items_total - discount + shipping),
        "message": "Kupon uygulandı",
    }


@router.post("/{store_slug}/checkout")
def create_checkout(
    store_slug: str,
    body: CheckoutRequest,
    request: Request,
    _rl: None = Depends(checkout_rate_limit),
    db: Session = Depends(get_db),
):
    if not body.kvkk_accept:
        raise HTTPException(422, "Devam etmek için KVKK aydınlatma metnini onaylamalısınız")

    store = _resolve_store(db, store_slug)
    try:
        session, init = checkout_svc.create_session(
            db,
            store,
            items=[{"variant_id": str(i.variant_id), "quantity": i.quantity} for i in body.items],
            customer=body.customer.model_dump(),
            client_ip=client_ip(request),
            discount_code=body.discount_code,
        )
    except checkout_svc.CheckoutError as e:
        raise HTTPException(422, str(e))
    except ValueError as e:
        # Sağlayıcı config/başlatma hatası — müşteriye genel mesaj, log'a detay
        print(f"[checkout] baslatma hatasi store={store.slug}: {e}")
        raise HTTPException(502, "Ödeme başlatılamadı. Lütfen daha sonra tekrar deneyin.")

    return {
        "token": session.token,
        "mode": init.mode,          # redirect | iframe
        "url": init.url,
        "amount": str(session.amount),
        "shipping_amount": str(session.shipping_amount),
        "discount_amount": str(session.discount_amount or 0),
    }


@router.get("/checkout/{token}/status")
def checkout_status(
    token: str,
    request: Request,
    _rl: None = Depends(status_rate_limit),
    db: Session = Depends(get_db),
):
    session = checkout_svc.get_session_by_token(db, token)
    if not session:
        raise HTTPException(404, "Ödeme oturumu bulunamadı")
    out: dict = {"status": session.status}
    if session.status == "paid":
        out["lookup_token"] = session.lookup_token
        out["amount"] = str(session.amount)
        if session.order_id:
            from app.models import Order
            order = db.get(Order, session.order_id)
            if order:
                out["order_number"] = order.order_number
    return out


@router.post("/payments/iyzico/callback/{token}")
async def iyzico_callback(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """iyzico tarayıcı dönüşü. Form'daki token'a GÜVENİLMEZ — sunucudan
    sunucuya retrieve ile doğrulanır; sonra müşteri vitrine yönlendirilir."""
    session = checkout_svc.get_session_by_token(db, token, for_update=True)
    if not session or session.provider != "iyzico":
        raise HTTPException(404)

    form = dict(await request.form())
    store = db.get(Store, session.store_id)
    provider = get_payment_provider(store)
    result = provider.handle_callback(form, session)
    checkout_svc.process_payment_result(db, session, result)

    return RedirectResponse(
        checkout_svc.storefront_result_url(store, session), status_code=303
    )


@router.post("/payments/paytr/webhook")
async def paytr_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """PayTR sunucudan sunucuya bildirim. Hash doğrulanır; yanıt HER ZAMAN
    düz metin 'OK' olmalı (aksi halde PayTR tekrar dener)."""
    form = dict(await request.form())
    merchant_oid = str(form.get("merchant_oid") or "")
    try:
        session_id = uuid.UUID(hex=merchant_oid)
    except ValueError:
        raise HTTPException(404)

    session = db.scalar(
        select(CheckoutSession)
        .where(CheckoutSession.id == session_id, CheckoutSession.provider == "paytr")
        .with_for_update()
    )
    if not session:
        raise HTTPException(404)

    store = db.get(Store, session.store_id)
    provider = get_payment_provider(store)
    result = provider.handle_callback(form, session)
    if result.status == "failed" and result.error == "hash doğrulanamadı":
        # imzasız/bozuk istek — OK dönme ki saldırgan "işlendi" sanmasın
        raise HTTPException(400, "hash gecersiz")

    checkout_svc.process_payment_result(db, session, result)
    return PlainTextResponse("OK")


# ─── Müşteri sipariş takibi (lookup_token ile) ───────────────

@router.get("/orders/{lookup_token}")
def order_lookup(
    lookup_token: str,
    request: Request,
    _rl: None = Depends(status_rate_limit),
    db: Session = Depends(get_db),
):
    """Sipariş durumu — tahmin edilemez lookup_token ile. Minimum veri döner
    (tam adres/telefon asla yankılanmaz)."""
    from app.models import Order
    from app.stages import progress_percent, stage_label

    session = db.scalar(select(CheckoutSession).where(
        CheckoutSession.lookup_token == lookup_token,
        CheckoutSession.status == "paid",
    ))
    if not session or not session.order_id:
        raise HTTPException(404, "Sipariş bulunamadı")
    order = db.get(Order, session.order_id)
    if not order:
        raise HTTPException(404, "Sipariş bulunamadı")

    kargo = order.kargo_info or {}
    stage_no = order.current_stage or 1
    if order.is_iptal:
        durum = {"key": "iptal", "label": "İptal Edildi", "progress": 0}
    else:
        durum = {
            "key": str(stage_no),
            "label": stage_label(stage_no),
            "progress": progress_percent(stage_no),
        }

    return {
        "order_number": order.order_number,
        "created_at": order.created_at_platform.isoformat() if order.created_at_platform else None,
        "durum": durum,
        "kargo": {
            "takip_no": kargo.get("takip_no"),
            "takip_url": kargo.get("takip_url"),
            "firma": kargo.get("handler_name"),
        } if kargo.get("takip_no") else None,
        "items": [
            {
                "title": li.title,
                "variant_title": li.variant_title,
                "quantity": li.quantity,
            }
            for li in order.line_items
        ],
        "amount": str(session.amount),
        "shipping_amount": str(session.shipping_amount),
        "currency": session.currency,
    }


@router.get("/checkout/{lookup_token}/cart")
def restore_cart(
    lookup_token: str,
    request: Request,
    _rl: None = Depends(status_rate_limit),
    db: Session = Depends(get_db),
):
    """Terk edilmiş sepeti geri yükleme — kalem + ürün gösterim bilgisi döner
    (müşteri PII'si ASLA dönmez; fiyat yine ödeme anında sunucuda hesaplanır)."""
    session = db.scalar(select(CheckoutSession).where(
        CheckoutSession.lookup_token == lookup_token,
        CheckoutSession.order_id.is_(None),
    ))
    if not session:
        raise HTTPException(404, "Sepet bulunamadı")

    items = []
    for i in (session.cart_snapshot or []):
        product = db.get(CatalogProduct, i.get("product_id")) if i.get("product_id") else None
        if not product or product.status != "active":
            continue  # artık satışta olmayan kalemler geri yüklenmez
        items.append({
            "variant_id": i.get("variant_id"),
            "quantity": int(i.get("quantity", 1)),
            "title": i.get("title"),
            "model_display": i.get("model_display"),
            "variation": i.get("variation"),
            "unit_price": i.get("unit_price"),
            "product_slug": product.slug,
            "image": f"/storage/{product.images[0].file_path}" if product.images else None,
        })
    return {"items": items}


@router.get("/{store_slug}/theme")
def get_store_theme(
    store_slug: str,
    response: Response,
    _rl: None = Depends(read_rate_limit),
    db: Session = Depends(get_db),
):
    """Vitrin teması + mağaza ayarları + yasal metin override'ları (tek istek)."""
    from app.services.theme import resolve_theme

    store = _resolve_store(db, store_slug)
    config = store.config or {}
    response.headers["Cache-Control"] = "public, max-age=60"
    return {
        "store_name": store.name,
        "theme": resolve_theme(config),
        "settings": {
            "shipping_fee": config.get("shipping_fee"),
            "free_shipping_over": config.get("free_shipping_over"),
            "min_order_amount": config.get("min_order_amount"),
        },
        "contact": {
            "email": config.get("contact_email"),
            "phone": config.get("contact_phone"),
            "instagram": config.get("contact_instagram"),
        },
        "pixels": {
            "meta": config.get("meta_pixel_id"),
            "ga4": config.get("ga4_id"),
            "tiktok": config.get("tiktok_pixel_id"),
        },
        "legal": {
            "kvkk": config.get("kvkk_text") or None,
            "mesafeli_satis": config.get("mesafeli_satis_text") or None,
            "iade": config.get("iade_text") or None,
        },
    }


@router.get("/_resolve")
def resolve_host(
    host: str = Query(..., max_length=253),
    response: Response = None,
    db: Session = Depends(get_db),
):
    """Host → mağaza slug çözümlemesi (özel domain'ler için; vitrin SSR kullanır)."""
    normalized = host.strip().lower().split(":")[0]
    if not normalized:
        raise HTTPException(404)
    store = db.scalar(select(Store).where(
        Store.platform == "storefront",
        Store.is_active.is_(True),
        (Store.config["custom_domain"].astext == normalized)
        | (Store.config["shop_domain"].astext == normalized),
    ))
    if not store:
        raise HTTPException(404, "Bu alan adına bağlı mağaza yok")
    if response is not None:
        response.headers["Cache-Control"] = "public, max-age=300"
    return {"slug": store.slug}
