"""
Public vitrin API'si — AUTH YOK (müşteriye açık).

Next.js vitrini bu endpoint'leri SUNUCUDAN SUNUCUYA çağırır (tarayıcı doğrudan
gelmez → CORS gerekmez). Ödeme sağlayıcı callback'leri de buraya gelir (PR3).

- GET /api/shop/{store_slug}/products               → aktif ürün listesi
- GET /api/shop/{store_slug}/products/{product_slug} → ürün detayı (varyant+görsel)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import CatalogProduct, CatalogVariant, Store
from app.services.rate_limit import make_rate_limiter

router = APIRouter(prefix="/api/shop", tags=["public-shop"])

# Okuma uçları için cömert limit (katalog gezinme), yazma uçları PR3'te ayrı sayaç.
read_rate_limit = make_rate_limiter(max_hits=60, window=60.0)


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
                "variation": v.variation,
                "price": _effective_price(p, v),
                "in_stock": (not v.track_stock) or v.quantity > 0,
            }
            for v in p.variants if v.is_active
        ],
    }


@router.get("/{store_slug}/products")
def list_products(
    store_slug: str,
    response: Response,
    q: str | None = Query(None, max_length=100),
    tag: str | None = Query(None, max_length=50),
    model: str | None = Query(None, max_length=120),
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
    return {
        "store": {"name": store.name},
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
