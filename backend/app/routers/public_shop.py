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
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import CatalogProduct, CatalogVariant, CheckoutSession, DiscountCode, Store
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
    # "Son N adet" rozeti: yalnızca TÜM varyantlar stok takipliyse anlamlı
    tracked = [v for v in active_variants if v.track_stock]
    total_stock = (
        sum(max(v.quantity, 0) for v in tracked)
        if active_variants and len(tracked) == len(active_variants) else None
    )
    return {
        "slug": p.slug,
        "title": p.title,
        "price": str(p.base_price),
        "compare_at_price": str(p.compare_at_price) if p.compare_at_price is not None else None,
        "currency": p.currency,
        "cover_image": f"/storage/{p.images[0].file_path}" if p.images else None,
        "tags": p.tags,
        "model_count": len(models),
        "total_stock": total_stock,
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
                # Aciliyet: takipli ve 5'ten az stok varsa kalan adet (yoksa null)
                "low_stock_left": (
                    v.quantity if v.track_stock and 0 < v.quantity < 5 else None
                ),
                # Sepette adet üst sınırı (takipsizse null = servis limiti geçerli)
                "max_qty": v.quantity if v.track_stock else None,
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
    brand: str | None = Query(None, max_length=60),
    collection: str | None = Query(None, max_length=200),
    slugs: str | None = Query(None, max_length=2500),  # virgüllü, verilen sırada döner
    sort: str = Query("yeni", pattern="^(yeni|fiyat-artan|fiyat-azalan)$"),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
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
    )
    if sort == "fiyat-artan":
        query = query.order_by(CatalogProduct.base_price.asc(), CatalogProduct.position)
    elif sort == "fiyat-azalan":
        query = query.order_by(CatalogProduct.base_price.desc(), CatalogProduct.position)
    else:
        query = query.order_by(CatalogProduct.position, CatalogProduct.created_at.desc())
    if q:
        query = query.where(CatalogProduct.title.ilike(f"%{q}%"))
    if min_price is not None:
        query = query.where(CatalogProduct.base_price >= min_price)
    if max_price is not None:
        query = query.where(CatalogProduct.base_price <= max_price)
    if brand:
        query = query.where(
            select(CatalogVariant.id).where(
                CatalogVariant.product_id == CatalogProduct.id,
                CatalogVariant.is_active.is_(True),
                CatalogVariant.brand.ilike(brand),
            ).exists()
        )
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
    if slugs:
        wanted = [x.strip() for x in slugs.split(",") if x.strip()][:24]
        by_slug = {p_.slug: p_ for p_ in products}
        products = [by_slug[w] for w in wanted if w in by_slug]
    if model:
        m = model.lower()
        products = [
            p for p in products
            if any(m in v.model_display.lower() for v in p.variants if v.is_active)
        ]

    total = len(products)
    start = (page - 1) * per_page
    items = products[start:start + per_page]

    # Filtre yüzeyleri: mağazadaki aktif markalar (mevcut filtrelerden bağımsız)
    brands = sorted(b for (b,) in db.execute(
        select(CatalogVariant.brand).distinct()
        .join(CatalogProduct, CatalogVariant.product_id == CatalogProduct.id)
        .where(
            CatalogProduct.store_id == store.id,
            CatalogProduct.status == "active",
            CatalogVariant.is_active.is_(True),
            CatalogVariant.brand.isnot(None),
        )
    ).all() if b)

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
        "facets": {"brands": brands},
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

    detail = _serialize_product_detail(product)

    # Onaylı yorum özeti (yıldız ortalaması + sayı)
    from sqlalchemy import func as sql_func
    from app.models import ProductReview
    row = db.execute(
        select(sql_func.avg(ProductReview.rating), sql_func.count(ProductReview.id))
        .where(ProductReview.product_id == product.id, ProductReview.status == "approved")
    ).one()
    detail["rating_avg"] = round(float(row[0]), 1) if row[0] is not None else None
    detail["rating_count"] = int(row[1] or 0)

    # Benzer ürünler: aynı koleksiyondan (kendisi hariç); yoksa son eklenenler
    related_q = select(CatalogProduct).where(
        CatalogProduct.store_id == store.id,
        CatalogProduct.status == "active",
        CatalogProduct.id != product.id,
    ).options(selectinload(CatalogProduct.variants), selectinload(CatalogProduct.images))
    col_ids = [c.id for c in product.collections]
    if col_ids:
        from app.models import catalog_product_collections
        related_q = related_q.join(
            catalog_product_collections,
            catalog_product_collections.c.product_id == CatalogProduct.id,
        ).where(catalog_product_collections.c.collection_id.in_(col_ids)).distinct()
    related = db.scalars(
        related_q.order_by(CatalogProduct.position, CatalogProduct.created_at.desc()).limit(4)
    ).all()
    detail["related"] = [_serialize_product_card(r) for r in related]

    response.headers["Cache-Control"] = "public, max-age=60"
    return detail


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
    # Kurumsal fatura (opsiyonel) — e-fatura/e-arşiv için
    invoice_company: str | None = Field(None, max_length=200)
    invoice_tax_office: str | None = Field(None, max_length=100)
    invoice_tax_no: str | None = Field(None, max_length=20)


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
            db, store, body.code, items_total, body.email,
            sum(i.quantity for i in body.items), _snapshot)
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

    # Yorum linki için line item -> katalog slug haritası
    _pids = [li.product_id for li in order.line_items if li.product_id]
    _product_slug_map: dict = {}
    if _pids:
        try:
            _uuids = [uuid.UUID(p_) for p_ in _pids]
            for cp in db.scalars(select(CatalogProduct).where(
                    CatalogProduct.id.in_(_uuids))).all():
                _product_slug_map[str(cp.id)] = cp.slug
        except ValueError:
            pass  # vitrin dışı id formatı

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
                # Yorum formu için: vitrin ürün slug'ı (varsa)
                "product_slug": _product_slug_map.get(str(li.product_id)),
            }
            for li in order.line_items
        ],
        "amount": str(session.amount),
        "shipping_amount": str(session.shipping_amount),
        "currency": session.currency,
    }


class OrderRequestBody(BaseModel):
    request_type: str = Field(..., pattern="^(iade|degisim|sorun)$")
    message: str = Field(..., min_length=10, max_length=2000)


@router.post("/orders/{lookup_token}/request")
def create_order_request(
    lookup_token: str,
    body: OrderRequestBody,
    _rl: None = Depends(status_rate_limit),
    db: Session = Depends(get_db),
):
    """Müşteri self-servis talebi (iade/değişim/sorun) — token'lı sipariş
    sayfasından. Panelde 'Müşteri Talepleri' olarak görünür."""
    from app.models import CustomerRequest, Order

    session = db.scalar(select(CheckoutSession).where(
        CheckoutSession.lookup_token == lookup_token,
        CheckoutSession.order_id.isnot(None),
    ))
    if not session:
        raise HTTPException(404, "Sipariş bulunamadı")
    order = db.get(Order, session.order_id)
    if not order:
        raise HTTPException(404, "Sipariş bulunamadı")

    open_count = db.scalar(
        select(func.count(CustomerRequest.id)).where(
            CustomerRequest.order_id == order.id,
            CustomerRequest.status == "acik",
        )
    )
    if open_count >= 3:
        raise HTTPException(429, "Bu sipariş için açık talepleriniz zaten iletildi — "
                                 "en kısa sürede dönüş yapacağız")

    db.add(CustomerRequest(
        tenant_id=order.tenant_id,
        order_id=order.id,
        request_type=body.request_type,
        message=body.message.strip(),
    ))
    db.commit()
    return {"ok": True, "message": "Talebiniz alındı — e-posta ile dönüş yapacağız"}


@router.get("/checkout/{lookup_token}/cart")
def restore_cart(
    lookup_token: str,
    request: Request,
    _rl: None = Depends(status_rate_limit),
    db: Session = Depends(get_db),
):
    """Sepeti geri yükleme — terk edilen sepet, taslak sipariş VE "tekrar sipariş
    ver" (ödenmiş sipariş) için ortak uç. Kalem + ürün gösterim bilgisi döner
    (müşteri PII'si ASLA dönmez; fiyat yine ödeme anında sunucuda hesaplanır)."""
    session = db.scalar(select(CheckoutSession).where(
        CheckoutSession.lookup_token == lookup_token,
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


def _active_promotion(db: Session, store: Store) -> dict | None:
    """Vitrine gösterilecek otomatik indirim etiketi (koşulsuz en cömerti).

    Sepet tutarı bilinmediğinden yalnızca zaman penceresi + limit denetlenir;
    kesin uygulama checkout'ta best_automatic_discount ile yapılır.
    """
    from datetime import datetime, timezone
    from decimal import Decimal

    now = datetime.now(timezone.utc)
    candidates = db.scalars(select(DiscountCode).where(
        DiscountCode.store_id == store.id,
        DiscountCode.is_automatic.is_(True),
        DiscountCode.is_active.is_(True),
    )).all()
    best = None
    best_rank = Decimal("-1")
    for dc in candidates:
        if dc.starts_at and now < dc.starts_at:
            continue
        if dc.ends_at and now > dc.ends_at:
            continue
        if dc.usage_limit is not None and dc.usage_count >= dc.usage_limit:
            continue
        rank = Decimal(str(dc.value or 0))
        if rank > best_rank:
            best, best_rank = dc, rank
    if not best:
        return None

    if best.kind == "percent":
        label = f"%{Decimal(str(best.value)):.0f} indirim"
    elif best.kind == "amount":
        label = f"{Decimal(str(best.value)):.0f} TL indirim"
    else:
        label = "Ücretsiz kargo"
    if best.min_subtotal:
        label = f"{Decimal(str(best.min_subtotal)):.0f} TL üzeri {label}"
    if best.min_quantity:
        label = f"{best.min_quantity}+ ürüne {label}"
    return {
        "label": f"{label} — sepette otomatik uygulanır",
        "kind": best.kind,
        "min_subtotal": str(best.min_subtotal) if best.min_subtotal is not None else None,
    }


@router.get("/{store_slug}/blog")
def list_blog_posts(
    store_slug: str,
    response: Response,
    _rl: None = Depends(read_rate_limit),
    db: Session = Depends(get_db),
):
    """Yayında olan blog yazıları (liste — içerik hariç)."""
    from app.models import BlogPost

    store = _resolve_store(db, store_slug)
    rows = db.scalars(
        select(BlogPost).where(
            BlogPost.store_id == store.id, BlogPost.is_published.is_(True))
        .order_by(BlogPost.published_at.desc().nulls_last())
    ).all()
    response.headers["Cache-Control"] = "public, max-age=300"
    return {"posts": [
        {
            "slug": p_.slug,
            "title": p_.title,
            "excerpt": p_.excerpt,
            "cover_url": p_.cover_url,
            "published_at": p_.published_at.isoformat() if p_.published_at else None,
        } for p_ in rows
    ]}


@router.get("/{store_slug}/blog/{post_slug}")
def get_blog_post(
    store_slug: str,
    post_slug: str,
    response: Response,
    _rl: None = Depends(read_rate_limit),
    db: Session = Depends(get_db),
):
    from app.models import BlogPost

    store = _resolve_store(db, store_slug)
    post = db.scalar(select(BlogPost).where(
        BlogPost.store_id == store.id,
        BlogPost.slug == post_slug,
        BlogPost.is_published.is_(True),
    ))
    if not post:
        raise HTTPException(404, "Yazı bulunamadı")
    response.headers["Cache-Control"] = "public, max-age=300"
    return {
        "slug": post.slug,
        "title": post.title,
        "excerpt": post.excerpt,
        "content": post.content,
        "cover_url": post.cover_url,
        "seo_title": post.seo_title,
        "seo_description": post.seo_description,
        "published_at": post.published_at.isoformat() if post.published_at else None,
    }


@router.get("/{store_slug}/feed/google.xml")
def google_shopping_feed(
    store_slug: str,
    _rl: None = Depends(read_rate_limit),
    db: Session = Depends(get_db),
):
    """Google Merchant Center ürün feed'i (RSS 2.0 + g: namespace).

    Varyant bazlı: her model ayrı item (item_group_id = ürün). Merchant
    Center'a bu URL doğrudan 'scheduled fetch' olarak verilir.
    """
    from xml.sax.saxutils import escape

    store = _resolve_store(db, store_slug)
    config = store.config or {}
    site = (config.get("storefront_url")
            or f"https://{config.get('shop_domain', '')}").rstrip("/")

    products = db.scalars(
        select(CatalogProduct)
        .where(CatalogProduct.store_id == store.id, CatalogProduct.status == "active")
        .options(selectinload(CatalogProduct.variants), selectinload(CatalogProduct.images))
        .order_by(CatalogProduct.position)
    ).all()

    items_xml = []
    for p in products:
        link = f"{site}/urun/{p.slug}"
        image = f"{site}/storage/{p.images[0].file_path}" if p.images else ""
        desc = (p.seo_description or p.description or p.title or "")[:5000]
        for v in p.variants:
            if not v.is_active:
                continue
            price = v.price_override if v.price_override is not None else p.base_price
            in_stock = (not v.track_stock) or v.quantity > 0
            title = f"{p.title} — {v.model_display}" + (f" ({v.variation})" if v.variation else "")
            items_xml.append(
                "<item>"
                f"<g:id>{escape(str(v.id))}</g:id>"
                f"<g:item_group_id>{escape(str(p.id))}</g:item_group_id>"
                f"<title>{escape(title[:150])}</title>"
                f"<description>{escape(desc)}</description>"
                f"<link>{escape(link)}</link>"
                + (f"<g:image_link>{escape(image)}</g:image_link>" if image else "")
                + f"<g:price>{price} TRY</g:price>"
                f"<g:availability>{'in_stock' if in_stock else 'out_of_stock'}</g:availability>"
                f"<g:condition>new</g:condition>"
                f"<g:brand>{escape(store.name)}</g:brand>"
                + (f"<g:mpn>{escape(v.sku)}</g:mpn>" if v.sku else "")
                + "</item>"
            )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">'
        f"<channel><title>{escape(store.name)}</title>"
        f"<link>{escape(site)}</link>"
        f"<description>{escape(store.name)} ürün feed'i</description>"
        + "".join(items_xml)
        + "</channel></rss>"
    )
    return Response(
        content=xml,
        media_type="application/xml; charset=utf-8",
        headers={"Cache-Control": "public, max-age=1800"},
    )


def _has_blog(db: Session, store: Store) -> bool:
    from app.models import BlogPost
    return bool(db.scalar(
        select(func.count()).select_from(BlogPost).where(
            BlogPost.store_id == store.id, BlogPost.is_published.is_(True))
    ))


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
            "gift_wrap_enabled": bool(config.get("gift_wrap_enabled")),
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
        "pages": [
            {"slug": p_["slug"], "title": p_["title"]}
            for p_ in (config.get("pages") or [])
        ],
        "custom_code": config.get("custom_code") or None,
        "active_promotion": _active_promotion(db, store),
        # Yayin oncesi kilit (Shopify password page) — sifrenin kendisi ASLA donmez
        "password_protected": bool((config.get("storefront_password") or "").strip()),
        "has_blog": _has_blog(db, store),
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


@router.get("/{store_slug}/pages/{page_slug}")
def get_page(
    store_slug: str,
    page_slug: str,
    response: Response,
    _rl: None = Depends(read_rate_limit),
    db: Session = Depends(get_db),
):
    """Özel sayfa içeriği — düz metin (vitrin whitespace-pre-line render eder)."""
    store = _resolve_store(db, store_slug)
    for page in ((store.config or {}).get("pages") or []):
        if page.get("slug") == page_slug:
            response.headers["Cache-Control"] = "public, max-age=60"
            return page
    raise HTTPException(404, "Sayfa bulunamadı")


# ─── Ürün yorumları + benzer ürünler ─────────────────────────

class ReviewIn(BaseModel):
    lookup_token: str = Field(..., min_length=20, max_length=80)
    product_slug: str = Field(..., min_length=1, max_length=200)
    rating: int = Field(..., ge=1, le=5)
    author_name: str = Field(..., min_length=2, max_length=60)
    comment: str | None = Field(None, max_length=2000)


def _mask_author(name: str) -> str:
    parts = (name or "").strip().split()
    if not parts:
        return "Müşteri"
    return f"{parts[0]} {' '.join(p[0] + '.' for p in parts[1:] if p)}".strip()


@router.get("/{store_slug}/products/{product_slug}/reviews")
def list_reviews(
    store_slug: str,
    product_slug: str,
    response: Response,
    page: int = Query(1, ge=1, le=100),
    _rl: None = Depends(read_rate_limit),
    db: Session = Depends(get_db),
):
    from sqlalchemy import func as sql_func
    from app.models import ProductReview

    store = _resolve_store(db, store_slug)
    product = db.scalar(select(CatalogProduct).where(
        CatalogProduct.store_id == store.id, CatalogProduct.slug == product_slug))
    if not product:
        raise HTTPException(404, "Ürün bulunamadı")

    base = select(ProductReview).where(
        ProductReview.product_id == product.id, ProductReview.status == "approved")
    total = db.scalar(select(sql_func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(ProductReview.created_at.desc())
                      .offset((page - 1) * 10).limit(10)).all()

    response.headers["Cache-Control"] = "public, max-age=60"
    return {
        "total": total,
        "page": page,
        "items": [
            {
                "author": _mask_author(r.author_name),
                "rating": r.rating,
                "comment": r.comment,
                "created_at": r.created_at.date().isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.post("/{store_slug}/reviews", status_code=201)
def create_review(
    store_slug: str,
    body: ReviewIn,
    request: Request,
    _rl: None = Depends(checkout_rate_limit),
    db: Session = Depends(get_db),
):
    """Yorum bırak — YALNIZCA o ürünü satın almış müşteri (lookup_token doğrulaması)."""
    from sqlalchemy.exc import IntegrityError
    from app.models import ProductReview

    store = _resolve_store(db, store_slug)
    session = db.scalar(select(CheckoutSession).where(
        CheckoutSession.lookup_token == body.lookup_token,
        CheckoutSession.store_id == store.id,
        CheckoutSession.status == "paid",
    ))
    if not session:
        raise HTTPException(403, "Yorum bırakmak için geçerli bir sipariş bağlantısı gerekli")

    product = db.scalar(select(CatalogProduct).where(
        CatalogProduct.store_id == store.id, CatalogProduct.slug == body.product_slug))
    if not product:
        raise HTTPException(404, "Ürün bulunamadı")
    # Doğrulanmış alıcı: ürün bu siparişin sepetinde olmalı
    in_cart = any(str(i.get("product_id")) == str(product.id)
                  for i in (session.cart_snapshot or []))
    if not in_cart:
        raise HTTPException(403, "Bu siparişte bu ürün bulunmuyor")

    review = ProductReview(
        tenant_id=store.tenant_id,
        product_id=product.id,
        checkout_session_id=session.id,
        author_name=body.author_name.strip(),
        rating=body.rating,
        comment=(body.comment or "").strip()[:2000] or None,
    )
    db.add(review)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bu ürün için zaten yorum bıraktınız")
    return {"status": "pending", "message": "Yorumunuz alındı — onaylandıktan sonra yayınlanır"}


# ─── Müşteri hesabı (şifresiz giriş) ─────────────────────────

class LoginRequestIn(BaseModel):
    email: EmailStr


class VerifyIn(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)


class AddressIn(BaseModel):
    first_name: str = Field("", max_length=100)
    last_name: str = Field("", max_length=100)
    phone: str = Field("", max_length=20)
    address1: str = Field("", max_length=300)
    city: str = Field("", max_length=60)
    province: str = Field("", max_length=60)
    zip: str = Field("", max_length=20)


login_rate_limit = make_rate_limiter(max_hits=5, window=300.0)  # 5 kod/5 dk/IP
newsletter_rate_limit = make_rate_limiter(max_hits=5, window=300.0)
unlock_rate_limit = make_rate_limiter(max_hits=10, window=300.0)


class UnlockRequest(BaseModel):
    password: str = Field(..., min_length=1, max_length=100)


@router.post("/{store_slug}/unlock")
def unlock_store(
    store_slug: str,
    body: UnlockRequest,
    _rl: None = Depends(unlock_rate_limit),
    db: Session = Depends(get_db),
):
    """Yayın öncesi vitrin kilidini aç (Shopify password page karşılığı)."""
    import hmac

    store = _resolve_store(db, store_slug)
    expected = ((store.config or {}).get("storefront_password") or "").strip()
    if not expected:
        return {"ok": True}  # koruma kapalı
    if not hmac.compare_digest(body.password.strip(), expected):
        raise HTTPException(403, "Şifre hatalı")
    return {"ok": True}

stock_alert_rate_limit = make_rate_limiter(max_hits=10, window=300.0)


class StockAlertRequest(BaseModel):
    variant_id: uuid.UUID
    email: EmailStr


@router.post("/{store_slug}/stock-alert")
def create_stock_alert(
    store_slug: str,
    body: StockAlertRequest,
    _rl: None = Depends(stock_alert_rate_limit),
    db: Session = Depends(get_db),
):
    """'Gelince haber ver' — stoksuz varyanta e-posta bırak; stok girilince
    tek seferlik bildirim gider. Aynı e-posta+varyant tekrar kaydolamaz."""
    from app.models import StockAlert

    store = _resolve_store(db, store_slug)
    variant = db.scalar(
        select(CatalogVariant)
        .join(CatalogProduct, CatalogVariant.product_id == CatalogProduct.id)
        .where(
            CatalogVariant.id == body.variant_id,
            CatalogProduct.store_id == store.id,
            CatalogProduct.status == "active",
            CatalogVariant.is_active.is_(True),
        )
    )
    if not variant:
        raise HTTPException(404, "Ürün bulunamadı")
    if not variant.track_stock or variant.quantity > 0:
        raise HTTPException(409, "Bu ürün zaten stokta")

    email = str(body.email).lower().strip()
    exists = db.scalar(select(StockAlert).where(
        StockAlert.variant_id == variant.id, StockAlert.email == email))
    if not exists:
        db.add(StockAlert(
            tenant_id=store.tenant_id, store_id=store.id,
            variant_id=variant.id, email=email,
        ))
        db.commit()
    return {"ok": True, "message": "Stok gelince e-posta göndereceğiz 🔔"}



class NewsletterRequest(BaseModel):
    email: EmailStr
    kvkk_accept: bool = Field(...)


@router.post("/{store_slug}/newsletter")
def newsletter_subscribe(
    store_slug: str,
    body: NewsletterRequest,
    _rl: None = Depends(newsletter_rate_limit),
    db: Session = Depends(get_db),
):
    """Bülten aboneliği — KVKK açık rızasıyla e-posta kaydı.

    Enumeration koruması: e-posta zaten kayıtlı olsa da aynı yanıt döner.
    """
    if not body.kvkk_accept:
        raise HTTPException(422, "Bülten kaydı için onay gerekli")
    store = _resolve_store(db, store_slug)

    from datetime import datetime, timezone
    from app.models import Customer
    email = str(body.email).lower().strip()
    customer = db.scalar(select(Customer).where(
        Customer.tenant_id == store.tenant_id, Customer.email == email))
    if not customer:
        customer = Customer(tenant_id=store.tenant_id, email=email)
        db.add(customer)
    if not customer.accepts_marketing:
        customer.accepts_marketing = True
        customer.marketing_opted_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True, "message": "Aboneliğiniz alındı 🎉"}



def _get_customer_from_token(request: Request, db: Session):
    """Authorization: Bearer <customer_token> → (Customer, Store). Yoksa 401."""
    from app.models import Customer
    from app.services.customer_auth import decode_customer_token

    auth = request.headers.get("authorization") or ""
    token = auth[7:] if auth.lower().startswith("bearer ") else None
    payload = decode_customer_token(token) if token else None
    if not payload:
        raise HTTPException(401, "Oturum geçersiz veya süresi dolmuş")
    store = db.get(Store, uuid.UUID(payload["store_id"]))
    if not store or not store.is_active:
        raise HTTPException(401, "Mağaza bulunamadı")
    customer = db.scalar(select(Customer).where(
        Customer.tenant_id == store.tenant_id,
        Customer.email == payload["email"],
    ))
    if not customer:
        raise HTTPException(401, "Hesap bulunamadı")
    return customer, store


@router.post("/{store_slug}/account/login-request")
def account_login_request(
    store_slug: str,
    body: LoginRequestIn,
    request: Request,
    _rl: None = Depends(login_rate_limit),
    db: Session = Depends(get_db),
):
    """Giriş kodu iste — e-posta kayıtlı olmasa da AYNI yanıt (enumeration yok)."""
    from app.services import email_service
    from app.services.customer_auth import generate_login_code

    store = _resolve_store(db, store_slug)
    customer, code = generate_login_code(db, store, str(body.email))

    html = email_service.render_email(
        title="Giriş Kodunuz",
        body_html=(
            f"<p>Merhaba,</p><p><b>{store.name}</b> hesabınıza giriş kodunuz:</p>"
            f"<p style='font-size:32px;font-weight:800;letter-spacing:8px;"
            f"text-align:center;margin:16px 0'>{code}</p>"
            f"<p style='color:#6b7280;font-size:13px'>Kod 10 dakika geçerlidir. "
            f"Bu isteği siz yapmadıysanız bu e-postayı yok sayabilirsiniz.</p>"
        ),
        preheader="Tek kullanımlık giriş kodunuz",
        emoji="🔑",
    )
    sent = email_service.send_email(customer.email, f"{store.name} giriş kodunuz: {code}", html)
    if not sent:
        # Dev ortamı: SMTP yoksa kod log'a düşer (canlıda SMTP zorunlu)
        print(f"[hesap] SMTP yok — giriş kodu ({customer.email}): {code}")
    return {"sent": True, "message": "Kod e-posta adresinize gönderildi"}


@router.post("/{store_slug}/account/verify")
def account_verify(
    store_slug: str,
    body: VerifyIn,
    request: Request,
    _rl: None = Depends(status_rate_limit),
    db: Session = Depends(get_db),
):
    from app.services.customer_auth import create_customer_token, verify_login_code

    store = _resolve_store(db, store_slug)
    customer = verify_login_code(db, store, str(body.email), body.code)
    if not customer:
        raise HTTPException(401, "Kod hatalı veya süresi dolmuş — yeni kod isteyin")
    return {
        "token": create_customer_token(customer, store),
        "email": customer.email,
        "name": customer.name,
    }


@router.get("/account/me")
def account_me(request: Request, db: Session = Depends(get_db)):
    customer, _store = _get_customer_from_token(request, db)
    return {
        "email": customer.email,
        "name": customer.name,
        "phone": customer.phone,
        "orders_count": customer.orders_count,
        "default_address": customer.default_address,
        # Eski tek-adres kayıtları listeye dönüştürerek göster
        "addresses": customer.addresses
            if customer.addresses is not None
            else ([customer.default_address] if customer.default_address else []),
        "accepts_marketing": customer.accepts_marketing,
    }


@router.get("/account/orders")
def account_orders(request: Request, db: Session = Depends(get_db)):
    """Müşterinin bu mağazadaki siparişleri (son 50) + takip linki token'ı."""
    from sqlalchemy import func as sql_func
    from app.models import Order

    customer, store = _get_customer_from_token(request, db)
    orders = db.scalars(
        select(Order).where(
            Order.store_id == store.id,
            sql_func.lower(Order.customer_email) == customer.email,
        ).order_by(Order.created_at_platform.desc().nulls_last()).limit(50)
    ).all()

    # lookup_token eşlemesi (sipariş takip sayfası linki için)
    sessions = db.execute(
        select(CheckoutSession.order_id, CheckoutSession.lookup_token).where(
            CheckoutSession.order_id.in_([o.id for o in orders] or [uuid.uuid4()]))
    ).all()
    token_map = {r[0]: r[1] for r in sessions}

    from app.stages import stage_label
    return {"orders": [
        {
            "order_number": o.order_number,
            "name": o.name,
            "created_at": o.created_at_platform.isoformat() if o.created_at_platform else None,
            "total_price": (o.raw or {}).get("total_price"),
            "durum": "İptal" if o.is_iptal else stage_label(o.current_stage or 1),
            "lookup_token": token_map.get(o.id),
        }
        for o in orders
    ]}


_ADDR_KEYS = ("label", "first_name", "last_name", "phone", "address1",
              "city", "province", "zip")


@router.put("/account/addresses")
def account_addresses(
    request: Request,
    body: dict,
    db: Session = Depends(get_db),
):
    """Adres defterini güncelle (Shopify address book) — ilk adres varsayılandır,
    checkout prefill için default_address'e de yazılır. En fazla 5 adres."""
    customer, _store = _get_customer_from_token(request, db)
    raw = body.get("addresses")
    if not isinstance(raw, list):
        raise HTTPException(422, "addresses listesi gerekli")
    cleaned = []
    for a in raw[:5]:
        if not isinstance(a, dict):
            continue
        entry = {k: str(a.get(k) or "").strip()[:300] for k in _ADDR_KEYS}
        if entry.get("address1") or entry.get("city"):
            cleaned.append(entry)
    customer.addresses = cleaned
    customer.default_address = cleaned[0] if cleaned else None
    db.commit()
    return {"ok": True, "addresses": cleaned}


@router.put("/account/marketing")
def account_marketing(
    request: Request,
    body: dict,
    db: Session = Depends(get_db),
):
    """Bülten aboneliğini aç/kapa — KVKK: rıza her an geri çekilebilir."""
    from datetime import datetime, timezone

    customer, _store = _get_customer_from_token(request, db)
    subscribed = bool(body.get("subscribed"))
    customer.accepts_marketing = subscribed
    customer.marketing_opted_at = datetime.now(timezone.utc) if subscribed else None
    db.commit()
    return {"ok": True, "accepts_marketing": subscribed}


@router.put("/account/address")
def account_address(
    body: AddressIn,
    request: Request,
    db: Session = Depends(get_db),
):
    customer, _store = _get_customer_from_token(request, db)
    customer.default_address = body.model_dump()
    if body.first_name or body.last_name:
        customer.name = f"{body.first_name} {body.last_name}".strip() or customer.name
    if body.phone:
        customer.phone = body.phone
    db.commit()
    return {"default_address": customer.default_address}
