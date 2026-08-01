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

import re
import uuid
from decimal import Decimal

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
        # Kart hover'ı: 2. görsel varsa o, yoksa video oynar
        "hover_image": f"/storage/{p.images[1].file_path}" if len(p.images) > 1 else None,
        "video_url": p.video_url,
        "tags": p.tags,
        "model_count": len(models),
        "total_stock": total_stock,
    }


def _serialize_product_detail(p: CatalogProduct) -> dict:
    return {
        "slug": p.slug,
        "title": p.title,
        "custom_fields": p.custom_fields or [],
        "models_per_item": p.models_per_item or 1,
        "video_url": p.video_url,
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
        {"slug": c.slug, "title": c.title, "description": c.description,
         "image_url": f"/storage/{c.image_path}" if c.image_path else None}
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
        # Başlık VEYA varyant modeli eşleşsin — müşteri "iPhone 13" yazınca
        # o modele sahip tüm ürünler listelenir (başlıkta geçmese bile)
        variant_match = select(CatalogVariant.id).where(
            CatalogVariant.product_id == CatalogProduct.id,
            CatalogVariant.is_active.is_(True),
            CatalogVariant.model_display.ilike(f"%{q}%"),
        ).exists()
        query = query.where(
            CatalogProduct.title.ilike(f"%{q}%") | variant_match)
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
    # Couple ürünler: ikinci kılıfın modeli (aynı ürünün varyantı olmalı)
    second_variant_id: uuid.UUID | None = None
    # Kişiye özel alanlar: {key: value} — üründeki tanıma göre doğrulanır
    custom: dict | None = None


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
    # Meta CAPI eşleşme sinyalleri (ops.) — _fbp/_fbc çerezleri; sunucu
    # taraflı Purchase'ın müşteriyle eşleşme kalitesini yükseltir
    fbp: str | None = Field(None, max_length=100)
    fbc: str | None = Field(None, max_length=200)


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
    """Kupon kodunu ödeme öncesi doğrula (hiçbir kayıt yaratmaz — UX için).

    Kupon 'birleşebilir' işaretliyse uygun otomatik indirim de eklenir; yanıt
    ödemede tahsil edilecek tutarın AYNISINI gösterir (fiyat sunucuda)."""
    from decimal import Decimal

    store = _resolve_store(db, store_slug)
    items_count = sum(i.quantity for i in body.items)
    try:
        _snapshot, items_total = checkout_svc.validate_and_snapshot(
            db, store,
            [{"variant_id": str(i.variant_id), "quantity": i.quantity} for i in body.items])
        base_shipping = checkout_svc._shipping_fee(store, items_total)
        plan = checkout_svc.resolve_discounts(
            db, store, body.code, items_total, body.email,
            base_shipping, items_count, _snapshot)
    except checkout_svc.CheckoutError as e:
        return {"valid": False, "message": str(e)}

    dc = plan.primary
    discount = plan.total
    shipping = Decimal("0") if plan.free_shipping else base_shipping
    extra = [r for r in plan.breakdown() if r["code"] != (body.code or "").strip().upper()]
    return {
        "valid": True,
        "code": dc.code if dc else body.code,
        "kind": dc.kind if dc else None,
        "discount_amount": str(discount),
        "free_shipping": plan.free_shipping,
        "new_total": str(items_total - discount + shipping),
        "applied": plan.breakdown(),
        "message": (
            "Kupon uygulandı — " + " + ".join(r["label"] for r in extra) + " ile birleşti"
            if extra else "Kupon uygulandı"
        ),
    }


class QuoteRequest(BaseModel):
    items: list[CheckoutItemIn] = Field(..., min_length=1, max_length=30)
    email: str | None = Field(None, max_length=200)


@router.post("/{store_slug}/checkout/quote")
def checkout_quote(
    store_slug: str,
    body: QuoteRequest,
    request: Request,
    _rl: None = Depends(status_rate_limit),
    db: Session = Depends(get_db),
):
    """Sepet özeti teklifi — OTOMATİK indirim dahil (kayıt yaratmaz).

    Sepet ve ödeme sayfaları gerçek tahsilat tutarını göstersin diye;
    yoksa '3 al 2 öde uygulanıyor' yazar ama müşteri indirimi göremez."""
    from decimal import Decimal

    store = _resolve_store(db, store_slug)
    try:
        snapshot, items_total = checkout_svc.validate_and_snapshot(
            db, store,
            [i.model_dump(exclude_none=True) for i in body.items])
    except checkout_svc.CheckoutError as e:
        return {"valid": False, "message": str(e)}

    shipping = checkout_svc._shipping_fee(store, items_total)
    plan = checkout_svc.resolve_discounts(
        db, store, None, items_total, body.email, shipping,
        sum(i.quantity for i in body.items), snapshot)
    discount = plan.total
    dc = plan.primary
    if plan.free_shipping:
        shipping = Decimal("0")
    return {
        "valid": True,
        "items_total": str(items_total),
        "discount_amount": str(discount),
        "discount_code": dc.code if dc else None,
        "free_shipping": plan.free_shipping,
        "applied": plan.breakdown(),
        "shipping": str(shipping),
        "total": str(items_total - discount + shipping),
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
            items=[{
                "variant_id": str(i.variant_id), "quantity": i.quantity,
                "second_variant_id": str(i.second_variant_id) if i.second_variant_id else None,
                "custom": i.custom or None,
            } for i in body.items],
            customer={
                **body.customer.model_dump(),
                # CAPI eşleşme sinyalleri — KVKK sweep'i customer'ı sildiğinde
                # bunlar da birlikte temizlenir
                "_meta": {
                    "ip": client_ip(request),
                    "ua": (request.headers.get("x-client-user-agent")
                           or request.headers.get("user-agent") or "")[:300],
                    "fbp": body.fbp,
                    "fbc": body.fbc,
                },
            },
            client_ip=client_ip(request),
            discount_code=body.discount_code,
        )
    except checkout_svc.CheckoutError as e:
        raise HTTPException(422, str(e))
    except ValueError as e:
        # Sağlayıcı config/başlatma hatası — müşteriye genel mesaj, log'a detay.
        # DİKKAT: 502/503/504 KULLANMA — Cloudflare bu kodlarda origin gövdesini
        # kendi HTML hata sayfasıyla ezer, müşteri "Unexpected token <!DOCTYPE"
        # görür; 500 ise JSON detail'iyle aynen iletilir.
        print(f"[checkout] baslatma hatasi store={store.slug}: {e}")
        raise HTTPException(
            500, "Ödeme sistemi şu an hizmet veremiyor. Lütfen daha sonra tekrar deneyin "
                 "ya da WhatsApp üzerinden bize ulaşın.")

    # Müşteri formu doldurdu ve sağlayıcıya yönlendi — buradan sonra
    # dönmezse sebep genelde kart/3D/POS kaynaklıdır (terk analizi)
    from datetime import datetime as _dt, timezone as _tz
    session.last_stage = "provider_redirect"
    session.last_stage_at = _dt.now(_tz.utc)
    db.commit()

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
        # Piksel Purchase olayı katalog eşleşmesi için satın alınan ürünler
        # (id = ürün slug'ı — Meta feed'indeki g:id ile aynı anahtar)
        snap = session.cart_snapshot or []
        slug_map: dict[str, str] = {}
        missing = [i["product_id"] for i in snap
                   if not i.get("product_slug") and i.get("product_id")]
        if missing:
            rows = db.execute(select(CatalogProduct.id, CatalogProduct.slug)
                              .where(CatalogProduct.id.in_(missing))).all()
            slug_map = {str(r[0]): r[1] for r in rows}
        out["items"] = [
            {
                "id": i.get("product_slug") or slug_map.get(str(i.get("product_id")), ""),
                "name": i.get("title"),
                "quantity": i.get("quantity", 1),
                "price": i.get("unit_price"),
            }
            for i in snap
        ]
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
        # Kısmi kargolama: sipariş parça parça gönderildiyse her gönderi ayrı
        # (müşteri "hangi ürünüm nerede" sorusunu buradan yanıtlar)
        "gonderiler": [
            {
                "takip_no": s.takip_no,
                "takip_url": s.takip_url,
                "firma": s.kargo_firma,
                "tarih": s.created_at.isoformat() if s.created_at else None,
                "urunler": [
                    {"title": i.get("title"), "variant_title": i.get("variant_title"),
                     "quantity": i.get("quantity")}
                    for i in (s.items or [])
                ],
            }
            for s in (order.shipments or [])
        ],
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
            # Couple + kişiye özel alanlar da geri yüklensin
            "second_variant_id": i.get("second_variant_id"),
            "second_model_display": i.get("second_model_display"),
            "custom": i.get("custom"),
        })
    return {"items": items}


def _eligible_automatics(db: Session, store: Store) -> list[DiscountCode]:
    """Zaman penceresi + limit koşulunu sağlayan otomatik indirimler."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    out = []
    for dc in db.scalars(select(DiscountCode).where(
        DiscountCode.store_id == store.id,
        DiscountCode.is_automatic.is_(True),
        DiscountCode.is_active.is_(True),
    )).all():
        if dc.starts_at and now < dc.starts_at:
            continue
        if dc.ends_at and now > dc.ends_at:
            continue
        if dc.usage_limit is not None and dc.usage_count >= dc.usage_limit:
            continue
        out.append(dc)
    return out


def _promo_dict(dc: DiscountCode) -> dict:
    from decimal import Decimal

    if dc.kind == "percent":
        label = f"%{Decimal(str(dc.value)):.0f} indirim"
    elif dc.kind == "amount":
        label = f"{Decimal(str(dc.value)):.0f} TL indirim"
    elif dc.kind == "bxgy":
        label = f"{dc.buy_x} Al {dc.pay_y} Öde"
    else:
        label = "Ücretsiz kargo"
    if dc.min_subtotal:
        label = f"{Decimal(str(dc.min_subtotal)):.0f} TL üzeri {label}"
    if dc.min_quantity:
        label = f"{dc.min_quantity}+ ürüne {label}"
    return {
        # Panelde özel mesaj yazıldıysa o gösterilir; boşsa kuraldan üretilen
        "label": dc.promo_message or f"{label} — sepette otomatik uygulanır",
        "kind": dc.kind,
        "min_subtotal": str(dc.min_subtotal) if dc.min_subtotal is not None else None,
        "buy_x": dc.buy_x,
        "pay_y": dc.pay_y,
    }


def _active_promotions(db: Session, store: Store) -> list[dict]:
    """Vitrine gösterilecek TÜM otomatik kampanyalar — sepet aynı anda birden
    çok hedefe yönlendirebilsin (2 üründe 3al2'ye, 4 üründe 5al3'e…)."""
    return [_promo_dict(dc) for dc in _eligible_automatics(db, store)]


def _active_promotion(db: Session, store: Store) -> dict | None:
    """Duyuru şeridi için tek etiket (en cömert otomatik) — geriye uyum."""
    from decimal import Decimal

    best = None
    best_rank = Decimal("-1")
    for dc in _eligible_automatics(db, store):
        rank = (Decimal(str((dc.buy_x or 0) - (dc.pay_y or 0))) * 100
                if dc.kind == "bxgy" else Decimal(str(dc.value or 0)))
        if rank > best_rank:
            best, best_rank = dc, rank
    if not best:
        return None

    return _promo_dict(best)


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


@router.get("/{store_slug}/feed/meta.xml")
def meta_catalog_feed(
    store_slug: str,
    _rl: None = Depends(read_rate_limit),
    db: Session = Depends(get_db),
):
    """Meta (Facebook/Instagram) katalog feed'i — ÜRÜN bazlı tek item.

    g:id = ürün slug'ı: pikselin ViewContent/AddToCart/Purchase content_ids'i
    ile birebir aynı anahtar → dynamic ads (Advantage+ catalog) eşleşmesi.
    Google feed'i varyant bazlıdır (233 model = 233 satır) — Meta reklamında
    aynı ürünün yüzlerce kopyası anlamsız olacağından ayrı uç gerekir.
    Commerce Manager → Veri Kaynakları → Veri Akışı'na bu URL verilir.
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
        active = [v for v in p.variants if v.is_active]
        in_stock = any((not v.track_stock) or v.quantity > 0 for v in active) if active else False
        desc = re.sub(r"<[^>]*>", " ", p.seo_description or p.description or p.title or "")
        desc = re.sub(r"\s+", " ", desc).strip()[:5000] or p.title
        image = f"{site}/storage/{p.images[0].file_path}" if p.images else ""
        extra_images = [f"{site}/storage/{im.file_path}" for im in p.images[1:11]]
        sale = (p.compare_at_price is not None
                and Decimal(str(p.compare_at_price)) > Decimal(str(p.base_price)))
        items_xml.append(
            "<item>"
            f"<g:id>{escape(p.slug[:100])}</g:id>"
            f"<title>{escape((p.title or '')[:150])}</title>"
            f"<description>{escape(desc)}</description>"
            f"<link>{escape(f'{site}/urun/{p.slug}')}</link>"
            + (f"<g:image_link>{escape(image)}</g:image_link>" if image else "")
            + "".join(f"<g:additional_image_link>{escape(u)}</g:additional_image_link>"
                      for u in extra_images)
            # İndirimliyse: price = üstü çizili, sale_price = gerçek satış fiyatı
            + (f"<g:price>{p.compare_at_price} TRY</g:price>"
               f"<g:sale_price>{p.base_price} TRY</g:sale_price>" if sale
               else f"<g:price>{p.base_price} TRY</g:price>")
            + f"<g:availability>{'in stock' if in_stock else 'out of stock'}</g:availability>"
            "<g:condition>new</g:condition>"
            f"<g:brand>{escape(store.name)}</g:brand>"
            "<g:google_product_category>Electronics &gt; Communications &gt; "
            "Telephony &gt; Mobile Phone Accessories &gt; Mobile Phone Cases</g:google_product_category>"
            "</item>"
        )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">'
        f"<channel><title>{escape(store.name)}</title>"
        f"<link>{escape(site)}</link>"
        f"<description>{escape(store.name)} Meta katalog feed'i</description>"
        + "".join(items_xml)
        + "</channel></rss>"
    )
    return Response(content=xml, media_type="application/xml",
                    headers={"Cache-Control": "public, max-age=900"})


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
        # Zengin metin açıklamadan etiketleri ayıkla (feed düz metin ister)
        desc = re.sub(r"<[^>]*>", " ", p.seo_description or p.description or p.title or "")
        desc = re.sub(r"\s+", " ", desc).strip()[:5000]
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
    preview: bool = Query(False),
    _rl: None = Depends(read_rate_limit),
    db: Session = Depends(get_db),
):
    """Vitrin teması + mağaza ayarları + yasal metin override'ları (tek istek).

    preview=1: panel canlı editörünün taslağı (config.theme_preview) döner —
    önbelleksiz; taslak yoksa canlı temaya düşer.
    """
    from app.services.theme import resolve_theme

    store = _resolve_store(db, store_slug)
    config = store.config or {}
    if preview and config.get("theme_preview"):
        response.headers["Cache-Control"] = "no-store"
        preview_config = dict(config)
        preview_config["theme"] = config["theme_preview"]
        config = preview_config
    else:
        response.headers["Cache-Control"] = "public, max-age=60"
    return {
        "store_name": store.name,
        "theme": resolve_theme(config),
        "settings": {
            "shipping_fee": config.get("shipping_fee"),
            "free_shipping_over": config.get("free_shipping_over"),
            "min_order_amount": config.get("min_order_amount"),
            "gift_wrap_enabled": bool(config.get("gift_wrap_enabled")),
            # Güven rozeti aktif sağlayıcıyı göstersin (iyzico VEYA PayTR)
            "payment_provider": config.get("payment_provider") or "iyzico",
        },
        # BERNZ Support sohbet balonu — kurallı asistan ayarları
        "support": {
            "enabled": config.get("support_chat_enabled", True),
            "faq": [
                {"q": str(f.get("q") or "")[:200], "a": str(f.get("a") or "")[:2000]}
                for f in (config.get("support_faq") or [])[:12]
                if isinstance(f, dict) and f.get("q") and f.get("a")
            ],
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
        "active_promotions": _active_promotions(db, store),
        # Yayin oncesi kilit (Shopify password page) — sifrenin kendisi ASLA donmez
        "password_protected": bool((config.get("storefront_password") or "").strip()),
        "has_blog": _has_blog(db, store),
        "legal": {
            "kvkk": config.get("kvkk_text") or None,
            "mesafeli_satis": config.get("mesafeli_satis_text") or None,
            "iade": config.get("iade_text") or None,
        },
    }


@router.get("/_il-ilce")
def il_ilce_public(response: Response):
    """TR il→ilçe listesi — adres formlarındaki dropdown'lar için (statik)."""
    from app.services.tr_iller import IL_ILCE
    response.headers["Cache-Control"] = "public, max-age=86400"
    return IL_ILCE


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
        ProductReview.product_id == product.id, ProductReview.status == "approved",
        ProductReview.kind == "review")
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


class QuestionIn(BaseModel):
    product_slug: str = Field(..., max_length=200)
    author_name: str = Field(..., min_length=2, max_length=60)
    question: str = Field(..., min_length=5, max_length=1000)


@router.get("/{store_slug}/products/{product_slug}/questions")
def list_questions(
    store_slug: str,
    product_slug: str,
    response: Response,
    _rl: None = Depends(read_rate_limit),
    db: Session = Depends(get_db),
):
    """Ürün soru-cevapları — YALNIZCA yanıtlanmış ve onaylanmış olanlar."""
    from app.models import ProductReview

    store = _resolve_store(db, store_slug)
    product = db.scalar(select(CatalogProduct).where(
        CatalogProduct.store_id == store.id, CatalogProduct.slug == product_slug))
    if not product:
        raise HTTPException(404, "Ürün bulunamadı")

    rows = db.scalars(
        select(ProductReview).where(
            ProductReview.product_id == product.id,
            ProductReview.kind == "question",
            ProductReview.status == "approved",
            ProductReview.answer.isnot(None),
        ).order_by(ProductReview.answered_at.desc()).limit(20)
    ).all()
    response.headers["Cache-Control"] = "public, max-age=120"
    return {"items": [
        {
            "author": _mask_author(r.author_name),
            "question": r.comment,
            "answer": r.answer,
            "answered_at": r.answered_at.date().isoformat() if r.answered_at else None,
        }
        for r in rows
    ]}


@router.post("/{store_slug}/questions", status_code=201)
def create_question(
    store_slug: str,
    body: QuestionIn,
    request: Request,
    _rl: None = Depends(status_rate_limit),
    db: Session = Depends(get_db),
):
    """Ürün sorusu — satın alma şartı YOK (yorumdan farkı bu), ama yanıt
    verilene ve onaylanana kadar vitrinde görünmez (spam koruması)."""
    from app.models import ProductReview

    store = _resolve_store(db, store_slug)
    product = db.scalar(select(CatalogProduct).where(
        CatalogProduct.store_id == store.id, CatalogProduct.slug == body.product_slug))
    if not product:
        raise HTTPException(404, "Ürün bulunamadı")

    db.add(ProductReview(
        tenant_id=store.tenant_id,
        product_id=product.id,
        kind="question",
        author_name=body.author_name.strip()[:60],
        comment=body.question.strip()[:1000],
        rating=None,
        status="pending",
    ))
    db.commit()
    return {"ok": True,
            "message": "Sorunuz iletildi — yanıtladığımızda ürün sayfasında görünecek"}


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
contact_rate_limit = make_rate_limiter(max_hits=5, window=300.0)
upload_rate_limit = make_rate_limiter(max_hits=10, window=300.0)


@router.post("/{store_slug}/upload")
async def customer_upload(
    store_slug: str,
    request: Request,
    _rl: None = Depends(upload_rate_limit),
    db: Session = Depends(get_db),
):
    """Kişiye özel ürün fotoğrafı yükleme (checkout öncesi) — optimize edilir,
    /storage URL'i döner; siparişin özel alanında saklanır."""
    from fastapi import UploadFile
    from app.services import storage as storage_svc

    store = _resolve_store(db, store_slug)
    form = await request.form()
    file = form.get("file")
    if file is None or not hasattr(file, "read"):
        raise HTTPException(422, "Dosya gerekli")
    data = await file.read()
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(413, "Dosya 25MB'ı aşamaz")
    try:
        url = storage_svc.save_store_asset(
            store.tenant_id, store.id, "musteri",
            data, getattr(file, "filename", None) or "musteri.jpg")
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"url": url}



class ContactRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    message: str = Field(..., min_length=10, max_length=3000)


@router.post("/{store_slug}/contact")
def contact_message(
    store_slug: str,
    body: ContactRequest,
    _rl: None = Depends(contact_rate_limit),
    db: Session = Depends(get_db),
):
    """İletişim formu — mesajı mağazanın iletişim e-postasına iletir."""
    from xml.sax.saxutils import escape
    from app.services import email_service

    store = _resolve_store(db, store_slug)
    to = ((store.config or {}).get("contact_email") or "").strip()
    if not to:
        # 502/503 değil — Cloudflare o kodlarda gövdeyi kendi HTML'iyle ezer
        raise HTTPException(500, "İletişim formu şu an kullanılamıyor")

    tenant = getattr(store, "tenant", None)
    brand = email_service.brand_kwargs(tenant) if tenant else {}
    html = email_service.render_email(
        title="Vitrinden yeni mesaj",
        body_html=(
            f"<p><b>{escape(body.name.strip())}</b> "
            f"(<a href='mailto:{escape(str(body.email))}'>{escape(str(body.email))}</a>) yazdı:</p>"
            f"<p style='white-space:pre-line'>{escape(body.message.strip())}</p>"
        ),
        preheader=f"{body.name.strip()} iletişim formunu doldurdu",
        emoji="✉️",
        **brand,
    )
    ok = email_service.send_email(to, f"Vitrin iletişim: {body.name.strip()}", html)
    if not ok:
        raise HTTPException(500, "Mesaj gönderilemedi — lütfen daha sonra tekrar deneyin")
    return {"ok": True, "message": "Mesajınız iletildi — en kısa sürede dönüş yapacağız"}



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
    fresh = not customer.accepts_marketing
    if fresh:
        customer.accepts_marketing = True
        customer.marketing_opted_at = datetime.now(timezone.utc)
    db.commit()
    # Kampanya listesine de yaz — yoksa vitrinden abone olan müşteri hiçbir
    # e-posta kampanyasını almaz (iki liste ayrı tablolarda tutuluyor)
    from app.services import marketing as marketing_svc
    marketing_svc.sync_from_customer(
        db, store.tenant_id, email, customer.name, True,
        ip=None, source="vitrin_bulten")
    # Yeni aboneye hoş geldin + indirim kodu (tek sefer, best-effort)
    if fresh:
        try:
            from app.services.email_flows import send_welcome
            send_welcome(db, store, customer)
        except Exception as e:  # noqa: BLE001 — kayıt başarılı sayılır
            print(f"[flows] hoş geldin gönderilemedi: {e}")
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

    # Mağazanın kendi markası (isim/logo/renk) — generic BERNZ yerine
    _accent, _logo = "#111827", ""
    try:
        from app.services.theme import resolve_theme
        _th = resolve_theme(store.config or {})
        _accent = (_th.get("colors") or {}).get("primary") or _accent
        _logo = _th.get("logo_url") or ""
    except Exception:  # noqa: BLE001
        pass

    _code_box = (
        "<div style=\"margin:24px 0;text-align:center;\">"
        "<div style=\"display:inline-block;background:#f3f4f6;border:1px solid #e5e7eb;"
        "border-radius:14px;padding:18px 32px;\">"
        f"<span style=\"font-size:34px;font-weight:800;letter-spacing:10px;color:#111827;"
        f"font-family:'SFMono-Regular',Menlo,Consolas,monospace;\">{code}</span>"
        "</div></div>"
    )
    html = email_service.render_email(
        title="Giriş Kodunuz",
        body_html=(
            f"<p>Merhaba,</p><p><b>{store.name}</b> hesabınıza giriş için tek kullanımlık kodunuz:</p>"
            f"{_code_box}"
            "<p style='color:#6b7280;font-size:13px;text-align:center;margin-top:4px'>Kod <b>10 dakika</b> geçerlidir.</p>"
            "<p style='color:#9ca3af;font-size:12px'>Bu isteği siz yapmadıysanız bu e-postayı yok sayabilirsiniz.</p>"
        ),
        preheader=f"{store.name} giriş kodunuz: {code}",
        emoji="🔑",
        brand=store.name,
        accent=_accent,
        logo_url=_logo,
        footer=f"{store.name} · Bu otomatik bir e-postadır.",
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


@router.get("/account/favorites")
def account_favorites(request: Request, db: Session = Depends(get_db)):
    customer, _store = _get_customer_from_token(request, db)
    return {"favorites": customer.favorites or []}


@router.put("/account/favorites")
def account_favorites_put(
    request: Request,
    body: dict,
    db: Session = Depends(get_db),
):
    """Favori slug listesini kaydet (cihazlar arası senkron; max 100)."""
    customer, _store = _get_customer_from_token(request, db)
    raw = body.get("favorites")
    if not isinstance(raw, list):
        raise HTTPException(422, "favorites listesi gerekli")
    customer.favorites = [str(x)[:200] for x in raw[:100] if x]
    db.commit()
    return {"ok": True, "favorites": customer.favorites}


class DesignRequestIn(BaseModel):
    image_url: str = Field(..., min_length=5, max_length=500)
    message: str | None = Field(None, max_length=2000)
    phone_model: str | None = Field(None, max_length=120)


@router.get("/account/design-requests")
def account_design_requests(request: Request, db: Session = Depends(get_db)):
    """Müşterinin tasarım talepleri (son 20)."""
    from app.models import DesignRequest
    customer, store = _get_customer_from_token(request, db)
    rows = db.scalars(
        select(DesignRequest).where(
            DesignRequest.store_id == store.id,
            DesignRequest.customer_email == customer.email,
        ).order_by(DesignRequest.created_at.desc()).limit(20)
    ).all()
    STATUS_TR = {"acik": "İnceleme bekliyor", "incelendi": "İncelendi",
                 "teklif": "Teklif hazırlandı", "tamam": "Tamamlandı", "red": "Uygun değil"}
    return {"requests": [
        {"id": str(r.id), "image_url": r.image_url, "message": r.message,
         "phone_model": r.phone_model, "status": r.status,
         "status_label": STATUS_TR.get(r.status, r.status),
         "admin_note": r.admin_note,
         "created_at": r.created_at.isoformat() if r.created_at else None}
        for r in rows
    ]}


@router.post("/account/design-requests")
def account_design_request_create(
    request: Request,
    body: DesignRequestIn,
    db: Session = Depends(get_db),
):
    """Kendi tasarımını yükle + talep oluştur (hesap gerektirir)."""
    from app.models import DesignRequest
    customer, store = _get_customer_from_token(request, db)
    open_count = db.scalar(select(func.count(DesignRequest.id)).where(
        DesignRequest.store_id == store.id,
        DesignRequest.customer_email == customer.email,
        DesignRequest.status == "acik",
    ))
    if (open_count or 0) >= 5:
        raise HTTPException(429, "En fazla 5 açık talebiniz olabilir — "
                                 "mevcut taleplerinize dönüş bekleyin")
    if not body.image_url.startswith("/storage/"):
        raise HTTPException(422, "Geçersiz görsel — lütfen tasarımınızı yükleyin")
    db.add(DesignRequest(
        tenant_id=store.tenant_id, store_id=store.id,
        customer_email=customer.email, customer_name=customer.name,
        image_url=body.image_url, message=(body.message or "").strip() or None,
        phone_model=(body.phone_model or "").strip() or None,
    ))
    db.commit()

    # Mağazaya bildirim — başarısızlık talebi düşürmez (panelde zaten görünür)
    to = ((store.config or {}).get("contact_email") or "").strip()
    if to:
        try:
            from xml.sax.saxutils import escape
            from app.services import email_service

            tenant = getattr(store, "tenant", None)
            brand = email_service.brand_kwargs(tenant) if tenant else {}
            who = escape(customer.name or customer.email)
            detay = ""
            if body.phone_model:
                detay += f"<p>📱 Model: <b>{escape(body.phone_model.strip())}</b></p>"
            if body.message:
                detay += (f"<p style='white-space:pre-line'>"
                          f"{escape(body.message.strip())}</p>")
            html = email_service.render_email(
                title="Yeni tasarım talebi 🎨",
                body_html=(
                    f"<p><b>{who}</b> "
                    f"(<a href='mailto:{escape(customer.email)}'>{escape(customer.email)}</a>) "
                    f"kendi tasarımıyla talep açtı.</p>{detay}"
                    "<p>Görseli ve talebi panelden inceleyebilirsiniz: "
                    "<b>Tasarım Talepleri</b> sayfası.</p>"
                ),
                preheader=f"{customer.name or customer.email} tasarım talebi açtı",
                emoji="🎨",
                **brand,
            )
            email_service.send_email(to, "Yeni tasarım talebi", html)
        except Exception:  # noqa: BLE001 — bildirim best-effort
            pass
    return {"ok": True, "message": "Tasarım talebiniz alındı — inceleyip döneceğiz 🎨"}


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
    from app.services import marketing as marketing_svc
    marketing_svc.sync_from_customer(
        db, customer.tenant_id, customer.email, customer.name, subscribed,
        source="vitrin_hesap")
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


@router.get("/{store_slug}/cart-suggestions")
def cart_suggestions(
    store_slug: str,
    slugs: str = Query("", max_length=2000),   # sepetteki ürün slug'ları (virgüllü)
    limit: int = Query(3, ge=1, le=6),
    _rl: None = Depends(read_rate_limit),
    db: Session = Depends(get_db),
):
    """Sepette 'bunu da ekleyin' önerileri (cross-sell).

    Sıralama: (1) panelden ürüne özel seçilen öneriler, (2) BİRLİKTE SATILAN
    ürünler (geçmiş siparişlerden öğrenilir), (3) aynı koleksiyondan çok
    satanlar. Sepettekiler ve stoksuzlar elenir."""
    from collections import Counter

    from app.models import CatalogCollection, LineItem, Order

    store = _resolve_store(db, store_slug)
    in_cart = {s.strip() for s in slugs.split(",") if s.strip()}

    picked: list[str] = []

    def _add(slug_list) -> None:
        for s in slug_list:
            if s and s not in in_cart and s not in picked:
                picked.append(s)

    products = {
        p.slug: p for p in db.scalars(
            select(CatalogProduct).where(
                CatalogProduct.store_id == store.id,
                CatalogProduct.status == "active",
            ).options(selectinload(CatalogProduct.images), selectinload(CatalogProduct.variants))
        ).all()
    }

    # 1) Panelden elle seçilen öneriler (ürün.cross_sell_slugs)
    for slug in in_cart:
        p = products.get(slug)
        if p:
            _add(p.cross_sell_slugs or [])

    # 2) Birlikte satılanlar — aynı siparişte geçmiş ürünler
    if in_cart and len(picked) < limit:
        cart_ids = [str(products[s].id) for s in in_cart if s in products]
        if cart_ids:
            order_ids = db.scalars(
                select(LineItem.order_id).join(Order, LineItem.order_id == Order.id)
                .where(Order.store_id == store.id,
                       LineItem.product_id.in_(cart_ids)).limit(500)
            ).all()
            if order_ids:
                together = db.scalars(
                    select(LineItem.product_id).where(
                        LineItem.order_id.in_(order_ids),
                        LineItem.product_id.isnot(None),
                        LineItem.product_id.notin_(cart_ids),
                    ).limit(2000)
                ).all()
                by_id = {str(p.id): p.slug for p in products.values()}
                _add([by_id.get(str(pid)) for pid, _ in Counter(together).most_common(20)])

    # 3) Aynı koleksiyondan tamamlayıcılar, yoksa en yeni ürünler
    if len(picked) < limit:
        coll_slugs: list[str] = []
        for slug in in_cart:
            p = products.get(slug)
            if p:
                coll_slugs += [c.slug for c in (p.collections or [])]
        if coll_slugs:
            same = db.scalars(
                select(CatalogProduct).join(CatalogProduct.collections)
                .where(CatalogProduct.store_id == store.id,
                       CatalogProduct.status == "active",
                       CatalogCollection.slug.in_(coll_slugs))
                .order_by(CatalogProduct.position).limit(30)
            ).all()
            _add([p.slug for p in same])
        _add(sorted(products, key=lambda s: products[s].position)[:20])

    out = []
    for slug in picked[:limit]:
        p = products.get(slug)
        if not p:
            continue
        if p.variants and not any(
                (not v.track_stock) or v.quantity > 0 for v in p.variants if v.is_active):
            continue   # tamamen stoksuz ürünü önerme
        out.append({
            "slug": p.slug,
            "title": p.title,
            "price": str(p.base_price),
            "compare_at_price": str(p.compare_at_price) if p.compare_at_price else None,
            "currency": "TRY",
            "cover_image": f"/storage/{p.images[0].file_path}" if p.images else None,
        })
    return {"items": out}


# ─── Canlı görünüm (live view) presence ping'i ───────────────

class PresenceIn(BaseModel):
    key: str = Field(..., min_length=8, max_length=64)
    path: str | None = Field(None, max_length=300)
    cart_items: int = Field(0, ge=0, le=200)


presence_rate_limit = make_rate_limiter(max_hits=12, window=60.0)


@router.post("/{store_slug}/presence")
def presence_ping(
    store_slug: str,
    body: PresenceIn,
    request: Request,
    _rl: None = Depends(presence_rate_limit),
    db: Session = Depends(get_db),
):
    """Ziyaretçi ping'i (~20 sn'de bir) — panel Canlı Görünüm kartını besler.

    Kişisel veri yok: yalnız istemcinin ürettiği rastgele oturum anahtarı."""
    from datetime import datetime, timezone

    from app.models import StorefrontPresence

    store = _resolve_store(db, store_slug)
    now = datetime.now(timezone.utc)
    key = body.key.strip()[:64]
    row = db.scalar(select(StorefrontPresence).where(
        StorefrontPresence.store_id == store.id,
        StorefrontPresence.session_key == key,
    ))
    if row is None:
        row = StorefrontPresence(
            tenant_id=store.tenant_id, store_id=store.id,
            session_key=key, first_seen=now,
        )
        db.add(row)
    row.last_seen = now
    row.last_path = (body.path or "")[:300] or None
    row.cart_items = body.cart_items
    # Ulaşılan en ileri huni aşaması — "nerede vazgeçti" analizi
    from app.services import funnel
    new_stage = funnel.merge_stage(
        row.stage, funnel.stage_from_path(body.path, body.cart_items))
    if new_stage != row.stage:
        row.stage = new_stage
        row.stage_at = now
    db.commit()
    return {"ok": True}


# ─── BERNZ Support — kurallı 7/24 asistan uçları ─────────────
# AI değildir: sistem verisiyle (sipariş, katalog, ayarlar) çalışan kurallı
# yanıtlar. Vitrindeki sohbet balonu bu uçları çağırır.

class SupportOrderStatusIn(BaseModel):
    email: str = Field(..., min_length=5, max_length=200)
    order_no: str | None = Field(None, max_length=40)


@router.post("/{store_slug}/support/order-status")
def support_order_status(
    store_slug: str,
    body: SupportOrderStatusIn,
    request: Request,
    _rl: None = Depends(status_rate_limit),
    db: Session = Depends(get_db),
):
    """E-postayla son siparişlerin durumu (en çok 3). Enumeration koruması:
    e-posta kayıtlı olmasa da 200 + boş liste döner."""
    from sqlalchemy import func as sql_func

    from app.models import Order
    from app.stages import stage_label

    store = _resolve_store(db, store_slug)
    email = body.email.strip().lower()
    orders = db.scalars(
        select(Order).where(
            Order.store_id == store.id,
            sql_func.lower(Order.customer_email) == email,
        ).order_by(Order.created_at_platform.desc().nulls_last()).limit(3)
    ).all()
    if body.order_no:
        num = body.order_no.strip().lstrip("#")
        matched = [o for o in orders
                   if str(o.order_number or "") == num or (o.name or "").lstrip("#") == num]
        orders = matched or orders

    sessions = db.execute(
        select(CheckoutSession.order_id, CheckoutSession.lookup_token).where(
            CheckoutSession.order_id.in_([o.id for o in orders] or [uuid.uuid4()]))
    ).all()
    token_map = {r[0]: r[1] for r in sessions}

    out = []
    for o in orders:
        kargo = o.kargo_info or {}
        out.append({
            "name": o.name or (f"#{o.order_number}" if o.order_number else "Sipariş"),
            "created_at": o.created_at_platform.isoformat() if o.created_at_platform else None,
            "durum": "İptal" if o.is_iptal else stage_label(o.current_stage or 1),
            "kargo_firma": kargo.get("handler_name"),
            "takip_no": kargo.get("takip_no"),
            "takip_url": kargo.get("takip_url"),
            "lookup_token": token_map.get(o.id),
        })
    return {"orders": out}


# "s24 plus var mı" gibi cümlelerde modele ait olmayan dolgu kelimeleri
_MODEL_STOPWORDS = {
    "var", "mı", "mi", "mu", "mü", "midir", "kılıf", "kilif", "kılıfı", "kilifi",
    "case", "uyumlu", "için", "icin", "telefon", "telefonum", "telefonuma",
    "model", "modeli", "acaba", "merhaba", "selam", "ve", "ile", "bir",
}


def _norm_model(s: str) -> list[str]:
    """Model adını karşılaştırma token'larına indirger: küçük harf,
    +→plus, noktalama temizliği ('S24+' ile 's24 plus' eşleşir)."""
    s = s.lower().replace("+", " plus ")
    s = "".join(ch if ch.isalnum() else " " for ch in s)
    return [t for t in s.split() if t and t not in _MODEL_STOPWORDS]


@router.get("/{store_slug}/support/model-check")
def support_model_check(
    store_slug: str,
    q: str = "",
    _rl: None = Depends(read_rate_limit),
    db: Session = Depends(get_db),
):
    """'Telefonuma uygun kılıf var mı?' — model adına göre aktif varyant arar.

    Tam alt dize yerine token bazlı eşleşme: sorgudaki her anlamlı kelime
    model adında geçmeli ("s24 plus var mı" → "Galaxy S24 Plus")."""
    store = _resolve_store(db, store_slug)
    q_tokens = _norm_model(q or "")
    if not q_tokens:
        return {"models": []}
    rows = db.execute(
        select(CatalogVariant.model_display, CatalogProduct.title, CatalogProduct.slug)
        .join(CatalogProduct, CatalogVariant.product_id == CatalogProduct.id)
        .where(
            CatalogProduct.store_id == store.id,
            CatalogProduct.status == "active",
            CatalogVariant.is_active.is_(True),
        )
    ).all()
    models: dict[str, dict] = {}
    for model_display, p_title, p_slug in rows:
        m_tokens = _norm_model(model_display)
        if not all(t in m_tokens for t in q_tokens):
            continue
        m = models.setdefault(model_display, {
            "model": model_display, "product_count": 0,
            "sample_title": p_title, "sample_slug": p_slug,
            # Az token farkı = daha isabetli eşleşme, üste gelsin
            "_extra": len(m_tokens) - len(q_tokens),
        })
        m["product_count"] += 1
    ranked = sorted(models.values(), key=lambda m: m["_extra"])[:10]
    for m in ranked:
        m.pop("_extra", None)
    return {"models": ranked}
