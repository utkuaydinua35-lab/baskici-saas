"""
Vitrin Kataloğu (admin) — /api/catalog/*

Kendi mağazamızın (platform='storefront') ürün yönetimi. Public vitrin
endpoint'leri routers/public_shop.py'de; burası yalnızca yetkili panel.

- GET    /api/catalog/products                 → liste (mağaza + durum filtre)
- POST   /api/catalog/products                 → ürün ekle
- GET    /api/catalog/products/{id}            → detay (varyant + görsel)
- PATCH  /api/catalog/products/{id}            → güncelle
- DELETE /api/catalog/products/{id}            → sil
- POST   /api/catalog/products/{id}/variants   → varyant ekle
- POST   /api/catalog/products/{id}/variants/bulk → telefon modellerinden toplu üret
- PATCH  /api/catalog/variants/{id}            → varyant güncelle
- DELETE /api/catalog/variants/{id}            → varyant sil
- POST   /api/catalog/products/{id}/images     → görsel yükle (multipart)
- DELETE /api/catalog/images/{id}              → görsel sil
"""
from __future__ import annotations

import re
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth.dependencies import require_permission
from app.database import get_db
from app.models import (
    CatalogImage,
    CatalogProduct,
    CatalogVariant,
    PhoneModel,
    Store,
    User,
)
from app.services import storage as storage_svc

router = APIRouter(
    prefix="/api/catalog", tags=["catalog"],
    dependencies=[Depends(require_permission("vitrin"))],
)


# ─── Schemas ─────────────────────────────────────────────────

class ProductCreate(BaseModel):
    store_id: uuid.UUID
    title: str = Field(..., min_length=1, max_length=300)
    slug: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=20000)
    status: str = Field("draft", pattern="^(draft|active|archived)$")
    seo_title: str | None = Field(None, max_length=200)
    seo_description: str | None = Field(None, max_length=400)
    base_price: Decimal = Field(..., ge=0)
    compare_at_price: Decimal | None = Field(None, ge=0)
    tags: str | None = Field(None, max_length=500)
    position: int = 0


class ProductUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=300)
    slug: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=20000)
    status: str | None = Field(None, pattern="^(draft|active|archived)$")
    seo_title: str | None = Field(None, max_length=200)
    seo_description: str | None = Field(None, max_length=400)
    base_price: Decimal | None = Field(None, ge=0)
    compare_at_price: Decimal | None = Field(None, ge=0)
    tags: str | None = Field(None, max_length=500)
    position: int | None = None


class VariantCreate(BaseModel):
    model_key: str = Field(..., min_length=1, max_length=60)
    model_display: str = Field(..., min_length=1, max_length=120)
    variation: str | None = Field(None, max_length=30)
    sku: str | None = Field(None, max_length=100)
    price_override: Decimal | None = Field(None, ge=0)
    quantity: int = Field(0, ge=0)
    track_stock: bool = True
    stock_item_id: uuid.UUID | None = None
    position: int = 0


class VariantUpdate(BaseModel):
    variation: str | None = Field(None, max_length=30)
    sku: str | None = Field(None, max_length=100)
    price_override: Decimal | None = Field(None, ge=0)
    quantity: int | None = Field(None, ge=0)
    track_stock: bool | None = None
    stock_item_id: uuid.UUID | None = None
    is_active: bool | None = None
    position: int | None = None


class BulkVariantRequest(BaseModel):
    """Aktif telefon modellerinden varyant üret (model × variations kartezyeni)."""
    variations: list[str] = Field(default_factory=list, max_length=20)  # boş → tek varyant (renksiz)
    brands: list[str] | None = None  # None → tüm markalar
    quantity: int = Field(0, ge=0)


# ─── Helpers ─────────────────────────────────────────────────

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_TR_MAP = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosucgiosu")


def slugify(text_: str) -> str:
    s = (text_ or "").translate(_TR_MAP).lower()
    s = _SLUG_RE.sub("-", s).strip("-")
    return s[:200] or uuid.uuid4().hex[:8]


def _get_storefront_store(db: Session, tenant_id, store_id) -> Store:
    store = db.scalar(select(Store).where(
        Store.id == store_id, Store.tenant_id == tenant_id, Store.platform == "storefront",
    ))
    if not store:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vitrin mağazası bulunamadı")
    return store


def _get_product(db: Session, tenant_id, product_id, *, eager: bool = False) -> CatalogProduct:
    q = select(CatalogProduct).where(
        CatalogProduct.id == product_id, CatalogProduct.tenant_id == tenant_id,
    )
    if eager:
        q = q.options(selectinload(CatalogProduct.variants), selectinload(CatalogProduct.images))
    product = db.scalar(q)
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ürün bulunamadı")
    return product


def _serialize_variant(v: CatalogVariant) -> dict:
    return {
        "id": str(v.id),
        "model_key": v.model_key,
        "model_display": v.model_display,
        "variation": v.variation,
        "sku": v.sku,
        "price_override": str(v.price_override) if v.price_override is not None else None,
        "quantity": v.quantity,
        "track_stock": v.track_stock,
        "stock_item_id": str(v.stock_item_id) if v.stock_item_id else None,
        "is_active": v.is_active,
        "position": v.position,
    }


def _serialize_image(im: CatalogImage) -> dict:
    return {
        "id": str(im.id),
        "url": f"/storage/{im.file_path}",
        "variant_id": str(im.variant_id) if im.variant_id else None,
        "alt": im.alt,
        "position": im.position,
    }


def _serialize_product(p: CatalogProduct, *, full: bool = False) -> dict:
    data = {
        "id": str(p.id),
        "store_id": str(p.store_id),
        "slug": p.slug,
        "title": p.title,
        "status": p.status,
        "base_price": str(p.base_price),
        "compare_at_price": str(p.compare_at_price) if p.compare_at_price is not None else None,
        "currency": p.currency,
        "tags": p.tags,
        "position": p.position,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }
    if full:
        data.update({
            "description": p.description,
            "seo_title": p.seo_title,
            "seo_description": p.seo_description,
            "variants": [_serialize_variant(v) for v in p.variants],
            "images": [_serialize_image(im) for im in p.images],
            "collection_ids": [str(c.id) for c in p.collections],
        })
    else:
        data["variant_count"] = len(p.variants)
        data["cover_image"] = f"/storage/{p.images[0].file_path}" if p.images else None
    return data


# ─── Ürün CRUD ───────────────────────────────────────────────

@router.get("/products", response_model=list[dict])
def list_products(
    store_id: uuid.UUID | None = Query(None),
    status_f: str | None = Query(None, alias="status"),
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    q = (
        select(CatalogProduct)
        .where(CatalogProduct.tenant_id == user.tenant_id)
        .options(selectinload(CatalogProduct.variants), selectinload(CatalogProduct.images))
        .order_by(CatalogProduct.position, CatalogProduct.created_at.desc())
    )
    if store_id:
        q = q.where(CatalogProduct.store_id == store_id)
    if status_f:
        q = q.where(CatalogProduct.status == status_f)
    return [_serialize_product(p) for p in db.scalars(q).all()]


@router.post("/products", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_product(
    body: ProductCreate,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    _get_storefront_store(db, user.tenant_id, body.store_id)

    slug = body.slug or slugify(body.title)
    exists = db.scalar(select(CatalogProduct).where(
        CatalogProduct.store_id == body.store_id, CatalogProduct.slug == slug,
    ))
    if exists:
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"

    product = CatalogProduct(
        tenant_id=user.tenant_id,
        store_id=body.store_id,
        slug=slug,
        title=body.title,
        description=body.description,
        status=body.status,
        seo_title=body.seo_title,
        seo_description=body.seo_description,
        base_price=body.base_price,
        compare_at_price=body.compare_at_price,
        tags=body.tags,
        position=body.position,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return _serialize_product(product, full=True)


@router.get("/products/{product_id}", response_model=dict)
def get_product(
    product_id: uuid.UUID,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    return _serialize_product(_get_product(db, user.tenant_id, product_id, eager=True), full=True)


@router.patch("/products/{product_id}", response_model=dict)
def update_product(
    product_id: uuid.UUID,
    body: ProductUpdate,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    product = _get_product(db, user.tenant_id, product_id, eager=True)
    updates = body.model_dump(exclude_unset=True)
    if "slug" in updates and updates["slug"]:
        updates["slug"] = slugify(updates["slug"])
        clash = db.scalar(select(CatalogProduct).where(
            CatalogProduct.store_id == product.store_id,
            CatalogProduct.slug == updates["slug"],
            CatalogProduct.id != product.id,
        ))
        if clash:
            raise HTTPException(status.HTTP_409_CONFLICT, "Bu slug zaten kullanılıyor")
    for k, v in updates.items():
        setattr(product, k, v)
    db.commit()
    db.refresh(product)
    return _serialize_product(product, full=True)


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: uuid.UUID,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    product = _get_product(db, user.tenant_id, product_id, eager=True)
    for im in product.images:
        storage_svc.delete_catalog_image(im.file_path)
    db.delete(product)
    db.commit()


# ─── Varyantlar ──────────────────────────────────────────────

@router.post("/products/{product_id}/variants", response_model=dict,
             status_code=status.HTTP_201_CREATED)
def create_variant(
    product_id: uuid.UUID,
    body: VariantCreate,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    product = _get_product(db, user.tenant_id, product_id)
    exists = db.scalar(select(CatalogVariant).where(
        CatalogVariant.product_id == product.id,
        CatalogVariant.model_key == body.model_key,
        CatalogVariant.variation == body.variation,
    ))
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "Bu model+varyasyon zaten mevcut")
    variant = CatalogVariant(tenant_id=user.tenant_id, product_id=product.id,
                             **body.model_dump())
    db.add(variant)
    db.commit()
    db.refresh(variant)
    return _serialize_variant(variant)


@router.post("/products/{product_id}/variants/bulk", response_model=dict)
def bulk_create_variants(
    product_id: uuid.UUID,
    body: BulkVariantRequest,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Aktif telefon modellerinden (global + tenant overlay) varyantları toplu üret."""
    product = _get_product(db, user.tenant_id, product_id)

    models_q = select(PhoneModel).where(
        PhoneModel.is_active.is_(True),
        (PhoneModel.tenant_id == user.tenant_id) | (PhoneModel.tenant_id.is_(None)),
    ).order_by(PhoneModel.brand, PhoneModel.display_name)
    phone_models = db.scalars(models_q).all()
    # Tenant overlay global'i ezer (aynı spec_key)
    by_key: dict[str, PhoneModel] = {}
    for pm in phone_models:
        if pm.spec_key not in by_key or pm.tenant_id is not None:
            by_key[pm.spec_key] = pm
    if body.brands:
        wanted = {b.lower() for b in body.brands}
        by_key = {k: v for k, v in by_key.items() if (v.brand or "").lower() in wanted}

    existing = {
        (v.model_key, v.variation)
        for v in db.scalars(select(CatalogVariant).where(
            CatalogVariant.product_id == product.id)).all()
    }
    variations: list[str | None] = list(body.variations) or [None]

    created = 0
    for pos, pm in enumerate(by_key.values()):
        for var in variations:
            if (pm.spec_key, var) in existing:
                continue
            db.add(CatalogVariant(
                tenant_id=user.tenant_id,
                product_id=product.id,
                model_key=pm.spec_key,
                model_display=pm.display_name,
                variation=var,
                quantity=body.quantity,
                position=pos,
            ))
            created += 1
    db.commit()
    return {"created": created, "skipped_existing": len(existing)}


@router.patch("/variants/{variant_id}", response_model=dict)
def update_variant(
    variant_id: uuid.UUID,
    body: VariantUpdate,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    variant = db.scalar(select(CatalogVariant).where(
        CatalogVariant.id == variant_id, CatalogVariant.tenant_id == user.tenant_id,
    ))
    if not variant:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Varyant bulunamadı")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(variant, k, v)
    db.commit()
    db.refresh(variant)
    return _serialize_variant(variant)


@router.delete("/variants/{variant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_variant(
    variant_id: uuid.UUID,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    variant = db.scalar(select(CatalogVariant).where(
        CatalogVariant.id == variant_id, CatalogVariant.tenant_id == user.tenant_id,
    ))
    if not variant:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Varyant bulunamadı")
    db.delete(variant)
    db.commit()


# ─── Görseller ───────────────────────────────────────────────

@router.post("/products/{product_id}/images", response_model=dict,
             status_code=status.HTTP_201_CREATED)
async def upload_image(
    product_id: uuid.UUID,
    file: UploadFile = File(...),
    alt: str | None = Form(None),
    variant_id: uuid.UUID | None = Form(None),
    position: int = Form(0),
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    product = _get_product(db, user.tenant_id, product_id)
    data = await file.read()
    image_id = uuid.uuid4()
    try:
        rel_path = storage_svc.save_catalog_image(
            user.tenant_id, image_id, data, file.filename or "gorsel.png")
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))

    image = CatalogImage(
        id=image_id,
        tenant_id=user.tenant_id,
        product_id=product.id,
        variant_id=variant_id,
        file_path=rel_path,
        alt=(alt or "")[:200] or None,
        position=position,
    )
    db.add(image)
    db.commit()
    db.refresh(image)
    return _serialize_image(image)


@router.delete("/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_image(
    image_id: uuid.UUID,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    image = db.scalar(select(CatalogImage).where(
        CatalogImage.id == image_id, CatalogImage.tenant_id == user.tenant_id,
    ))
    if not image:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Görsel bulunamadı")
    storage_svc.delete_catalog_image(image.file_path)
    db.delete(image)
    db.commit()


# ─── Koleksiyonlar ───────────────────────────────────────────

class CollectionCreate(BaseModel):
    store_id: uuid.UUID
    title: str = Field(..., min_length=1, max_length=200)
    slug: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=2000)
    position: int = 0


class CollectionUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)
    position: int | None = None
    is_active: bool | None = None


class ProductCollectionsUpdate(BaseModel):
    collection_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)


def _serialize_collection(c, product_count: int | None = None) -> dict:
    data = {
        "id": str(c.id),
        "store_id": str(c.store_id),
        "slug": c.slug,
        "title": c.title,
        "description": c.description,
        "position": c.position,
        "is_active": c.is_active,
    }
    if product_count is not None:
        data["product_count"] = product_count
    return data


@router.get("/collections", response_model=list[dict])
def list_collections(
    store_id: uuid.UUID | None = Query(None),
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    from app.models import CatalogCollection, catalog_product_collections
    from sqlalchemy import func as sql_func

    q = select(CatalogCollection).where(CatalogCollection.tenant_id == user.tenant_id) \
        .order_by(CatalogCollection.position, CatalogCollection.created_at)
    if store_id:
        q = q.where(CatalogCollection.store_id == store_id)
    collections = db.scalars(q).all()

    counts = dict(db.execute(
        select(catalog_product_collections.c.collection_id,
               sql_func.count(catalog_product_collections.c.product_id))
        .group_by(catalog_product_collections.c.collection_id)
    ).all())
    return [_serialize_collection(c, counts.get(c.id, 0)) for c in collections]


@router.post("/collections", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_collection(
    body: CollectionCreate,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    from app.models import CatalogCollection

    _get_storefront_store(db, user.tenant_id, body.store_id)
    slug = slugify(body.slug or body.title)
    exists = db.scalar(select(CatalogCollection).where(
        CatalogCollection.store_id == body.store_id, CatalogCollection.slug == slug))
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "Bu slug'a sahip koleksiyon zaten var")

    collection = CatalogCollection(
        tenant_id=user.tenant_id, store_id=body.store_id, slug=slug,
        title=body.title, description=body.description, position=body.position,
    )
    db.add(collection)
    db.commit()
    db.refresh(collection)
    return _serialize_collection(collection, 0)


@router.patch("/collections/{collection_id}", response_model=dict)
def update_collection(
    collection_id: uuid.UUID,
    body: CollectionUpdate,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    from app.models import CatalogCollection

    collection = db.scalar(select(CatalogCollection).where(
        CatalogCollection.id == collection_id, CatalogCollection.tenant_id == user.tenant_id))
    if not collection:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Koleksiyon bulunamadı")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(collection, k, v)
    db.commit()
    db.refresh(collection)
    return _serialize_collection(collection)


@router.delete("/collections/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_collection(
    collection_id: uuid.UUID,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    from app.models import CatalogCollection

    collection = db.scalar(select(CatalogCollection).where(
        CatalogCollection.id == collection_id, CatalogCollection.tenant_id == user.tenant_id))
    if not collection:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Koleksiyon bulunamadı")
    db.delete(collection)
    db.commit()


@router.put("/products/{product_id}/collections", response_model=dict)
def set_product_collections(
    product_id: uuid.UUID,
    body: ProductCollectionsUpdate,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    from app.models import CatalogCollection

    product = _get_product(db, user.tenant_id, product_id)
    collections = db.scalars(select(CatalogCollection).where(
        CatalogCollection.id.in_(body.collection_ids),
        CatalogCollection.tenant_id == user.tenant_id,
        CatalogCollection.store_id == product.store_id,
    )).all() if body.collection_ids else []
    product.collections = list(collections)
    db.commit()
    return {"product_id": str(product.id),
            "collection_ids": [str(c.id) for c in product.collections]}
