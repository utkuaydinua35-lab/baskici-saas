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
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
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
from app.services import smart_collections
from app.services import storage as storage_svc
from app.services.sanitize import sanitize_rich_text

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
    publish_at: datetime | None = None   # draft üründe zamanlanmış yayın
    custom_fields: list[dict] | None = None   # kişiye özel alanlar (aşağıda temizlenir)
    # Sepette 'bunu da ekleyin' önerileri — ürün slug listesi (en fazla 6)
    cross_sell_slugs: list[str] | None = None
    models_per_item: int | None = Field(None, ge=1, le=2)
    video_url: str | None = Field(None, max_length=500)


class VariantCreate(BaseModel):
    model_key: str = Field(..., min_length=1, max_length=60)
    model_display: str = Field(..., min_length=1, max_length=120)
    brand: str | None = Field(None, max_length=40)
    variation: str | None = Field(None, max_length=30)
    sku: str | None = Field(None, max_length=100)
    price_override: Decimal | None = Field(None, ge=0)
    quantity: int = Field(0, ge=0)
    track_stock: bool = True
    stock_item_id: uuid.UUID | None = None
    position: int = 0


class VariantUpdate(BaseModel):
    brand: str | None = Field(None, max_length=40)
    model_display: str | None = Field(None, min_length=1, max_length=120)
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


def _clean_custom_fields(raw) -> list[dict]:
    """Kişiye özel alan tanımlarını temizle (max 6; type: text|image|color)."""
    out = []
    for f in (raw or [])[:6]:
        if not isinstance(f, dict):
            continue
        label = str(f.get("label") or "").strip()[:80]
        if not label:
            continue
        ftype = f.get("type") if f.get("type") in ("text", "image", "color") else "text"
        entry = {
            "key": slugify(label)[:40] or "alan",
            "label": label,
            "type": ftype,
            "required": bool(f.get("required")),
        }
        if ftype == "color":
            entry["options"] = [str(o).strip()[:30]
                                for o in (f.get("options") or [])[:12] if str(o).strip()]
        out.append(entry)
    return out


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
        "brand": v.brand,
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
        "variant_set_id": str(p.variant_set_id) if p.variant_set_id else None,
        "custom_fields": p.custom_fields or [],
        "cross_sell_slugs": p.cross_sell_slugs or [],
        "models_per_item": p.models_per_item or 1,
        "video_url": p.video_url,
        "publish_at": p.publish_at.isoformat() if p.publish_at else None,
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
        description=sanitize_rich_text(body.description),
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
    smart_collections.sync_product(db, product)   # kurala uyan akıllı koleksiyonlara gir
    db.commit()
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
    if "description" in updates:
        updates["description"] = sanitize_rich_text(updates["description"])
    if "custom_fields" in updates:
        updates["custom_fields"] = _clean_custom_fields(updates["custom_fields"])
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
    smart_collections.sync_product(db, product)   # fiyat/etiket değişmiş olabilir
    db.commit()
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
    payload = body.model_dump()
    if not payload.get("brand"):
        from app.services.brands import infer_brand
        payload["brand"] = infer_brand(payload.get("model_display"))
    variant = CatalogVariant(tenant_id=user.tenant_id, product_id=product.id, **payload)
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
    if not by_key:
        raise HTTPException(422, "Telefon modeli listesi boş — bu buton Baskıcı'daki "
                                 "Telefon Modelleri tablosundan üretir. Alternatif: "
                                 "Ürünler sayfasındaki 🧩 Varyant Setleri'ni kullanın.")

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
            from app.services.brands import infer_brand
            db.add(CatalogVariant(
                tenant_id=user.tenant_id,
                product_id=product.id,
                model_key=pm.spec_key,
                model_display=pm.display_name,
                brand=pm.brand or infer_brand(pm.display_name),
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
    was_out = variant.track_stock and variant.quantity <= 0
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(variant, k, v)
    # Stok 0'dan yukarı çıktıysa 'gelince haber ver' bildirimleri
    if was_out and (not variant.track_stock or variant.quantity > 0):
        from app.services.stock_alerts import notify_variant
        notify_variant(db, variant)
    db.commit()
    db.refresh(variant)
    return _serialize_variant(variant)


class BrandRename(BaseModel):
    old: str = Field(..., min_length=1, max_length=40)
    new: str = Field(..., min_length=1, max_length=40)


@router.post("/products/{product_id}/variants/rename-brand", response_model=dict)
def rename_brand(
    product_id: uuid.UUID,
    body: BrandRename,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Üründeki bir markanın (ana varyant başlığı) adını toplu değiştirir."""
    product = db.scalar(select(CatalogProduct).where(
        CatalogProduct.id == product_id, CatalogProduct.tenant_id == user.tenant_id,
    ))
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ürün bulunamadı")
    count = 0
    for v in product.variants:
        if (v.brand or "") == body.old:
            v.brand = body.new.strip()
            count += 1
    db.commit()
    return {"updated": count}


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
async def upload_images(
    product_id: uuid.UUID,
    files: list[UploadFile] = File(...),
    alt: str | None = Form(None),
    variant_id: uuid.UUID | None = Form(None),
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Çoklu görsel yükleme (max 10/istek) — büyük fotoğraflar sunucuda
    otomatik optimize edilir (25MB'a kadar kabul)."""
    product = _get_product(db, user.tenant_id, product_id, eager=True)
    if len(files) > 10:
        raise HTTPException(422, "Tek seferde en fazla 10 görsel yüklenebilir")

    next_pos = max([im.position for im in product.images], default=-1) + 1
    uploaded, errors = [], []
    for n, file in enumerate(files):
        data = await file.read()
        image_id = uuid.uuid4()
        try:
            rel_path = storage_svc.save_catalog_image(
                user.tenant_id, image_id, data, file.filename or "gorsel.jpg")
        except ValueError as e:
            errors.append({"dosya": file.filename, "mesaj": str(e)})
            continue
        image = CatalogImage(
            id=image_id,
            tenant_id=user.tenant_id,
            product_id=product.id,
            variant_id=variant_id,
            file_path=rel_path,
            alt=(alt or "")[:200] or None,
            position=next_pos + n,
        )
        db.add(image)
        db.flush()
        uploaded.append(_serialize_image(image))
    if not uploaded and errors:
        raise HTTPException(422, errors[0]["mesaj"])
    db.commit()
    return {"images": uploaded, "errors": errors}


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

class SmartRule(BaseModel):
    field: str = Field(..., max_length=20)
    op: str = Field(..., max_length=20)
    value: str | None = Field(None, max_length=200)

    @field_validator("field")
    @classmethod
    def _field_ok(cls, v: str) -> str:
        if v not in smart_collections.FIELDS:
            raise ValueError(f"Bilinmeyen kural alanı: {v}")
        return v

    @field_validator("op")
    @classmethod
    def _op_ok(cls, v: str) -> str:
        if v not in smart_collections.OPS:
            raise ValueError(f"Bilinmeyen kural işleci: {v}")
        return v


class CollectionCreate(BaseModel):
    store_id: uuid.UUID
    title: str = Field(..., min_length=1, max_length=200)
    slug: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=2000)
    position: int = 0
    is_smart: bool = False
    rules: list[SmartRule] = Field(default_factory=list, max_length=smart_collections.MAX_RULES)
    rules_match: str = "all"


class CollectionUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)
    image_path: str | None = Field(None, max_length=500)  # /storage/... URL'inden path
    position: int | None = None
    is_active: bool | None = None
    is_smart: bool | None = None
    rules: list[SmartRule] | None = Field(None, max_length=smart_collections.MAX_RULES)
    rules_match: str | None = None


class SmartPreviewRequest(BaseModel):
    store_id: uuid.UUID
    rules: list[SmartRule] = Field(default_factory=list, max_length=smart_collections.MAX_RULES)
    rules_match: str = "all"


class ProductCollectionsUpdate(BaseModel):
    collection_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)


def _serialize_collection(c, product_count: int | None = None) -> dict:
    data = {
        "id": str(c.id),
        "store_id": str(c.store_id),
        "slug": c.slug,
        "title": c.title,
        "description": c.description,
        "image_url": f"/storage/{c.image_path}" if c.image_path else None,
        "position": c.position,
        "is_active": c.is_active,
        "is_smart": c.is_smart,
        "rules": c.rules or [],
        "rules_match": c.rules_match or "all",
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
        is_smart=body.is_smart,
        rules=[r.model_dump() for r in body.rules] if body.is_smart else None,
        rules_match="any" if body.rules_match == "any" else "all",
    )
    db.add(collection)
    db.commit()
    db.refresh(collection)
    sayi = smart_collections.sync_collection(db, collection) if collection.is_smart else 0
    db.commit()
    return _serialize_collection(collection, sayi)


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
    updates = body.model_dump(exclude_unset=True)
    if updates.get("image_path"):
        updates["image_path"] = updates["image_path"].removeprefix("/storage/")
    if "rules_match" in updates:
        updates["rules_match"] = "any" if updates["rules_match"] == "any" else "all"
    for k, v in updates.items():
        setattr(collection, k, v)
    db.commit()
    # Kural/tür değiştiyse üyelik baştan kurulur. Akıllıdan normale dönerse
    # o anki üyelik dondurulur (elle düzenlenebilir hale gelir).
    sayi = None
    if collection.is_smart:
        sayi = smart_collections.sync_collection(db, collection)
        db.commit()
    db.refresh(collection)
    return _serialize_collection(collection, sayi)


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


@router.post("/collections/preview", response_model=dict)
def preview_smart_collection(
    body: SmartPreviewRequest,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Kaydetmeden önce kaç ürünün eşleştiğini göster (panel önizlemesi)."""
    _get_storefront_store(db, user.tenant_id, body.store_id)
    return smart_collections.preview(
        db, body.store_id, [r.model_dump() for r in body.rules],
        "any" if body.rules_match == "any" else "all",
    )


@router.post("/collections/{collection_id}/sync", response_model=dict)
def sync_smart_collection(
    collection_id: uuid.UUID,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Akıllı koleksiyonu şimdi yeniden hesapla (ürünler dışarıdan değişmişse)."""
    from app.models import CatalogCollection

    collection = db.scalar(select(CatalogCollection).where(
        CatalogCollection.id == collection_id, CatalogCollection.tenant_id == user.tenant_id))
    if not collection:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Koleksiyon bulunamadı")
    if not collection.is_smart:
        raise HTTPException(422, "Bu koleksiyon kural bazlı değil")
    sayi = smart_collections.sync_collection(db, collection)
    db.commit()
    return {"product_count": sayi}


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
        CatalogCollection.is_smart.is_(False),   # akıllı üyelik elle değişmez
    )).all() if body.collection_ids else []
    # Akıllı koleksiyon üyelikleri kuralın sonucudur — burada korunur
    akilli = [c for c in product.collections if c.is_smart]
    product.collections = list(collections) + akilli
    db.commit()
    return {"product_id": str(product.id),
            "collection_ids": [str(c.id) for c in product.collections]}


# ─── Zengin ürün editörü (görsel sırası, çoğaltma, toplu durum) ──

class ImageOrderRequest(BaseModel):
    image_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=50)


class BulkStatusRequest(BaseModel):
    ids: list[uuid.UUID] = Field(..., min_length=1, max_length=200)
    status: str = Field(..., pattern="^(draft|active|archived)$")


@router.put("/products/{product_id}/images/order", response_model=dict)
def reorder_images(
    product_id: uuid.UUID,
    body: ImageOrderRequest,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Görsel sırası — verilen id listesi yeni pozisyon sırasıdır (ilk = kapak)."""
    product = _get_product(db, user.tenant_id, product_id, eager=True)
    by_id = {im.id: im for im in product.images}
    if set(body.image_ids) != set(by_id.keys()):
        raise HTTPException(422, "Görsel listesi ürünün görselleriyle eşleşmiyor")
    for pos, image_id in enumerate(body.image_ids):
        by_id[image_id].position = pos
    db.commit()
    return {"ok": True, "order": [str(i) for i in body.image_ids]}


@router.post("/products/{product_id}/duplicate", response_model=dict,
             status_code=status.HTTP_201_CREATED)
def duplicate_product(
    product_id: uuid.UUID,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Ürünü varyant + koleksiyon bağlarıyla kopyala (taslak; görseller hariç)."""
    src = _get_product(db, user.tenant_id, product_id, eager=True)

    slug = f"{src.slug}-kopya"
    if db.scalar(select(CatalogProduct).where(
            CatalogProduct.store_id == src.store_id, CatalogProduct.slug == slug)):
        slug = f"{src.slug}-kopya-{uuid.uuid4().hex[:6]}"

    copy = CatalogProduct(
        tenant_id=src.tenant_id, store_id=src.store_id,
        slug=slug, title=f"{src.title} (Kopya)",
        description=src.description, status="draft",
        seo_title=src.seo_title, seo_description=src.seo_description,
        base_price=src.base_price, compare_at_price=src.compare_at_price,
        tags=src.tags, position=src.position,
        variant_set_id=src.variant_set_id,
        custom_fields=src.custom_fields,
        models_per_item=src.models_per_item,
    )
    db.add(copy)
    db.flush()
    for v in src.variants:
        db.add(CatalogVariant(
            tenant_id=v.tenant_id, product_id=copy.id,
            model_key=v.model_key, model_display=v.model_display,
            brand=v.brand,
            variation=v.variation, sku=None,  # SKU tekil kalsın — kopyalanmaz
            price_override=v.price_override, quantity=v.quantity,
            track_stock=v.track_stock, stock_item_id=v.stock_item_id,
            is_active=v.is_active, position=v.position,
        ))
    copy.collections = list(src.collections)
    db.commit()
    db.refresh(copy)
    return _serialize_product(copy, full=True)


@router.post("/products/bulk-status", response_model=dict)
def bulk_status(
    body: BulkStatusRequest,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    from sqlalchemy import update as sa_update
    result = db.execute(
        sa_update(CatalogProduct)
        .where(CatalogProduct.id.in_(body.ids),
               CatalogProduct.tenant_id == user.tenant_id)
        .values(status=body.status)
    )
    db.commit()
    return {"updated": result.rowcount, "status": body.status}


class BulkEditRequest(BaseModel):
    """Toplu düzenleme (Shopify bulk editor) — tek istekte bir işlem."""
    ids: list[uuid.UUID] = Field(..., min_length=1, max_length=200)
    # Fiyat: percent (+%10 = 10, -%15 = -15) | set (sabit TL) — base_price'a uygulanır
    price_mode: str | None = Field(None, pattern="^(percent|set)$")
    price_value: Decimal | None = None
    compare_at_from_old: bool = False   # eski fiyatı "indirim öncesi"ne taşı
    add_collection_id: uuid.UUID | None = None
    add_tags: str | None = Field(None, max_length=300)   # virgüllü


@router.post("/products/bulk-edit", response_model=dict)
def bulk_edit(
    body: BulkEditRequest,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Seçili ürünlere toplu işlem: fiyat / koleksiyon / etiket."""
    products = db.scalars(
        select(CatalogProduct).where(
            CatalogProduct.id.in_(body.ids),
            CatalogProduct.tenant_id == user.tenant_id,
        )
    ).all()
    if not products:
        raise HTTPException(404, "Ürün bulunamadı")

    collection = None
    if body.add_collection_id:
        from app.models import CatalogCollection
        collection = db.scalar(select(CatalogCollection).where(
            CatalogCollection.id == body.add_collection_id,
            CatalogCollection.tenant_id == user.tenant_id,
        ))
        if not collection:
            raise HTTPException(404, "Koleksiyon bulunamadı")

    if body.price_mode and body.price_value is None:
        raise HTTPException(422, "Fiyat değeri gerekli")
    if body.price_mode == "set" and body.price_value is not None and body.price_value <= 0:
        raise HTTPException(422, "Sabit fiyat 0'dan büyük olmalı")

    updated = 0
    for p in products:
        if body.price_mode:
            old_price = Decimal(str(p.base_price))
            if body.price_mode == "percent":
                new_price = (old_price * (1 + Decimal(str(body.price_value)) / 100)
                             ).quantize(Decimal("0.01"))
                if new_price <= 0:
                    continue  # anlamsız sonuç — ürünü atla
            else:
                new_price = Decimal(str(body.price_value))
            if body.compare_at_from_old and new_price < old_price:
                p.compare_at_price = old_price  # indirim rozeti otomatik doğar
            p.base_price = new_price
        if collection and collection.is_smart:
            raise HTTPException(422, "Akıllı koleksiyona ürün elle eklenemez — kuralı düzenleyin")
        if collection and collection not in p.collections:
            p.collections.append(collection)
        if body.add_tags:
            existing = [t.strip() for t in (p.tags or "").split(",") if t.strip()]
            for t in body.add_tags.split(","):
                t = t.strip()
                if t and t not in existing:
                    existing.append(t)
            p.tags = ", ".join(existing)
        updated += 1
    db.commit()
    # Fiyat/etiket değişti — akıllı koleksiyon üyelikleri tazelenir
    for p in products:
        smart_collections.sync_product(db, p)
    db.commit()
    return {"updated": updated}


# ─── CSV Export / Import ─────────────────────────────────────

CSV_COLUMNS = [
    "urun_slug", "urun_adi", "durum", "fiyat", "indirim_oncesi", "aciklama",
    "etiketler", "koleksiyonlar", "seo_baslik", "seo_aciklama",
    "model_key", "model_adi", "renk", "sku", "varyant_fiyat", "stok", "varyant_aktif",
]
IMPORT_ROW_LIMIT = 5000


def _shopify_to_native_rows(reader) -> list[dict]:
    """Shopify ürün export'unu bizim CSV satır formatımıza çevir.

    Shopify yapısı: Handle başına ilk satır ürünü taşır (Title/Body/Tags…);
    sonraki satırlar ya ek varyant (Option1 Value) ya da yalnız ek görseldir.
    'Default Title' gerçek varyant değildir — ürün satırına katlanır.
    Görseller (CDN URL'leri) aktarılmaz.
    """
    out: list[dict] = []
    seen_product: set[str] = set()
    for row in reader:
        handle = (row.get("Handle") or "").strip()
        if not handle:
            continue
        title = (row.get("Title") or "").strip()
        opt1 = (row.get("Option1 Value") or "").strip()
        is_variant = opt1 and opt1.lower() != "default title"

        native: dict = {"urun_slug": handle}
        if title and handle not in seen_product:
            seen_product.add(handle)
            status = (row.get("Status") or "").strip().lower()
            if status not in ("active", "draft", "archived"):
                status = "active" if (row.get("Published") or "").strip().lower() == "true" else "draft"
            native.update({
                "urun_adi": title,
                "durum": status,
                "fiyat": (row.get("Variant Price") or "").strip(),
                "indirim_oncesi": (row.get("Variant Compare At Price") or "").strip(),
                "aciklama": (row.get("Body (HTML)") or "").strip(),
                "etiketler": (row.get("Tags") or "").strip(),
                "seo_baslik": (row.get("SEO Title") or "").strip(),
                "seo_aciklama": (row.get("SEO Description") or "").strip(),
            })
        elif not is_variant:
            continue  # yalnız ek görsel satırı — aktarılmıyor

        if is_variant:
            native.update({
                "model_adi": opt1,
                "model_key": slugify(opt1),
                "renk": (row.get("Option2 Value") or "").strip() or "",
                "sku": (row.get("Variant SKU") or "").strip(),
                "varyant_fiyat": (row.get("Variant Price") or "").strip(),
                "stok": (row.get("Variant Inventory Qty") or "").strip(),
                "varyant_aktif": "1",
            })
        out.append(native)
    return out


def publish_due_products(db: Session) -> int:
    """Yayın zamanı gelmiş taslakları aktifleştir (scheduler 10 dk'da bir çağırır)."""
    from datetime import datetime, timezone
    from sqlalchemy import update as sa_update
    result = db.execute(
        sa_update(CatalogProduct)
        .where(
            CatalogProduct.status == "draft",
            CatalogProduct.publish_at.isnot(None),
            CatalogProduct.publish_at <= datetime.now(timezone.utc),
        )
        .values(status="active", publish_at=None)
    )
    db.commit()
    return result.rowcount


@router.post("/products/{product_id}/video", response_model=dict)
async def upload_product_video(
    product_id: uuid.UUID,
    file: UploadFile = File(...),
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Ürün videosu yükle (mp4/webm/mov, max 100MB) — galeride ▶ karesi olur."""
    product = _get_product(db, user.tenant_id, product_id)
    data = await file.read()
    try:
        url = storage_svc.save_store_video(
            user.tenant_id, product.store_id, data, file.filename or "video.mp4")
    except ValueError as e:
        raise HTTPException(422, str(e))
    product.video_url = url
    db.commit()
    return {"video_url": url}


@router.delete("/products/{product_id}/video", status_code=status.HTTP_204_NO_CONTENT)
def delete_product_video(
    product_id: uuid.UUID,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    product = _get_product(db, user.tenant_id, product_id)
    product.video_url = None
    db.commit()


# ─── Varyant Setleri (hazır varyantlar — tek yerden yönetim) ──

class VariantSetItem(BaseModel):
    model_key: str = Field(..., min_length=1, max_length=60)
    model_display: str = Field(..., min_length=1, max_length=120)
    brand: str | None = Field(None, max_length=60)
    variation: str | None = Field(None, max_length=80)
    price_override: Decimal | None = Field(None, ge=0)


class VariantSetCreate(BaseModel):
    store_id: uuid.UUID
    name: str = Field(..., min_length=2, max_length=120)
    items: list[VariantSetItem] = Field(default_factory=list, max_length=500)


class VariantSetUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=120)
    items: list[VariantSetItem] | None = Field(None, max_length=500)


def _serialize_variant_set(vs, product_count: int | None = None) -> dict:
    data = {
        "id": str(vs.id),
        "name": vs.name,
        "items": vs.items or [],
        "updated_at": vs.updated_at.isoformat() if vs.updated_at else None,
    }
    if product_count is not None:
        data["product_count"] = product_count
    return data


def sync_set_to_product(db: Session, product: CatalogProduct, items: list[dict]) -> dict:
    """Set kalemlerini ürünün varyantlarına uygula (upsert by model_key+variation).

    Mevcut varyantın STOK ve stok-takibi KORUNUR; görünen ad/marka/fiyat setten
    gelir. Sette olmayan varyantlar silinir (set = tek doğruluk kaynağı).
    """
    from app.services.brands import infer_brand

    keyof = lambda mk, var: (str(mk), str(var or ""))  # noqa: E731
    wanted = {keyof(i["model_key"], i.get("variation")): i for i in items}
    existing = {keyof(v.model_key, v.variation): v for v in product.variants}

    created = updated = deleted = 0
    for key, item in wanted.items():
        brand = item.get("brand") or infer_brand(item["model_display"])
        price = item.get("price_override")
        if key in existing:
            v = existing[key]
            v.model_display = item["model_display"]
            v.brand = brand
            v.price_override = price
            updated += 1
        else:
            db.add(CatalogVariant(
                tenant_id=product.tenant_id,
                product_id=product.id,
                model_key=item["model_key"],
                model_display=item["model_display"],
                brand=brand,
                variation=item.get("variation"),
                price_override=price,
                track_stock=False,  # setten gelen varyant sınırsız doğar
                position=len(existing) + created,
            ))
            created += 1
    for key, v in existing.items():
        if key not in wanted:
            db.delete(v)
            deleted += 1
    return {"created": created, "updated": updated, "deleted": deleted}


@router.get("/variant-sets", response_model=list[dict])
def list_variant_sets(
    store_id: uuid.UUID = Query(...),
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    from app.models import VariantSet
    _get_storefront_store(db, user.tenant_id, store_id)
    sets = db.scalars(select(VariantSet).where(VariantSet.store_id == store_id)
                      .order_by(VariantSet.name)).all()
    counts = dict(db.execute(
        select(CatalogProduct.variant_set_id, func.count(CatalogProduct.id))
        .where(CatalogProduct.store_id == store_id,
               CatalogProduct.variant_set_id.isnot(None))
        .group_by(CatalogProduct.variant_set_id)
    ).all())
    return [_serialize_variant_set(vs, counts.get(vs.id, 0)) for vs in sets]


@router.post("/variant-sets", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_variant_set(
    body: VariantSetCreate,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    from app.models import VariantSet
    _get_storefront_store(db, user.tenant_id, body.store_id)
    if db.scalar(select(VariantSet).where(
            VariantSet.store_id == body.store_id, VariantSet.name == body.name.strip())):
        raise HTTPException(409, "Bu adla bir set zaten var")
    vs = VariantSet(
        tenant_id=user.tenant_id, store_id=body.store_id,
        name=body.name.strip(),
        items=[i.model_dump(mode="json") for i in body.items],
    )
    db.add(vs)
    db.commit()
    db.refresh(vs)
    return _serialize_variant_set(vs, 0)


@router.patch("/variant-sets/{set_id}", response_model=dict)
def update_variant_set(
    set_id: uuid.UUID,
    body: VariantSetUpdate,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Seti güncelle — bağlı TÜM ürünlerin varyantları senkronlanır."""
    from sqlalchemy.orm.attributes import flag_modified
    from app.models import VariantSet
    vs = db.scalar(select(VariantSet).where(
        VariantSet.id == set_id, VariantSet.tenant_id == user.tenant_id))
    if not vs:
        raise HTTPException(404, "Set bulunamadı")

    if body.name:
        vs.name = body.name.strip()
    synced = 0
    if body.items is not None:
        vs.items = [i.model_dump(mode="json") for i in body.items]
        flag_modified(vs, "items")
        products = db.scalars(
            select(CatalogProduct)
            .where(CatalogProduct.variant_set_id == vs.id)
            .options(selectinload(CatalogProduct.variants))
        ).all()
        for p in products:
            sync_set_to_product(db, p, vs.items)
            synced += 1
    db.commit()
    db.refresh(vs)
    out = _serialize_variant_set(vs)
    out["synced_products"] = synced
    return out


@router.delete("/variant-sets/{set_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_variant_set(
    set_id: uuid.UUID,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Seti sil — ürünlerin varyantları YERİNDE KALIR, yalnızca bağ kopar."""
    from app.models import VariantSet
    vs = db.scalar(select(VariantSet).where(
        VariantSet.id == set_id, VariantSet.tenant_id == user.tenant_id))
    if not vs:
        raise HTTPException(404, "Set bulunamadı")
    db.delete(vs)
    db.commit()


@router.post("/products/{product_id}/apply-variant-set", response_model=dict)
def apply_variant_set(
    product_id: uuid.UUID,
    body: dict,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Ürüne set bağla (varyantlar hemen senkronlanır) ya da bağı kopar."""
    from app.models import VariantSet
    product = _get_product(db, user.tenant_id, product_id, eager=True)
    set_id = body.get("variant_set_id")
    if not set_id:
        product.variant_set_id = None  # varyantlar olduğu gibi kalır
        db.commit()
        return {"detached": True}
    vs = db.scalar(select(VariantSet).where(
        VariantSet.id == set_id, VariantSet.tenant_id == user.tenant_id,
        VariantSet.store_id == product.store_id))
    if not vs:
        raise HTTPException(404, "Set bulunamadı")
    product.variant_set_id = vs.id
    stats = sync_set_to_product(db, product, vs.items or [])
    db.commit()
    return {"applied": vs.name, **stats}


class BulkApplySetRequest(BaseModel):
    # ids boş + only_without_variants=true → mağazadaki TÜM varyantsız ürünler
    ids: list[uuid.UUID] = Field(default_factory=list, max_length=500)
    variant_set_id: uuid.UUID
    only_without_variants: bool = False


@router.post("/products/bulk-apply-variant-set", response_model=dict)
def bulk_apply_variant_set(
    body: BulkApplySetRequest,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Seçili ürünlerin HEPSİNE varyant seti bağla (toplu varyant ekleme).

    Her ürün için set senkronu çalışır: eksik modeller eklenir, mevcutların
    stok bilgisi korunur, sette olmayan varyantlar silinir."""
    from app.models import VariantSet

    vs = db.scalar(select(VariantSet).where(
        VariantSet.id == body.variant_set_id, VariantSet.tenant_id == user.tenant_id))
    if not vs:
        raise HTTPException(404, "Set bulunamadı")

    q = select(CatalogProduct).where(
        CatalogProduct.tenant_id == user.tenant_id,
        CatalogProduct.store_id == vs.store_id,
    )
    if body.only_without_variants:
        # Varyantı hiç olmayan ürünler — müşteri model seçemediği için
        # bunlar SATIN ALINAMAZ; sayfa sayfa seçmeye gerek kalmasın
        has_variant = select(CatalogVariant.id).where(
            CatalogVariant.product_id == CatalogProduct.id).exists()
        q = q.where(~has_variant)
    else:
        if not body.ids:
            raise HTTPException(422, "Ürün seçilmedi")
        q = q.where(CatalogProduct.id.in_(body.ids))

    products = db.scalars(q).all()
    if not products:
        raise HTTPException(404, "Ürün bulunamadı")

    total = {"created": 0, "updated": 0, "deleted": 0}
    for product in products:
        product.variant_set_id = vs.id
        stats = sync_set_to_product(db, product, vs.items or [])
        for k in total:
            total[k] += stats.get(k, 0)
    db.commit()
    return {"applied": vs.name, "products": len(products), **total}


# ─── Envanter (Shopify Inventory ekranı) ─────────────────────

@router.get("/inventory", response_model=dict)
def list_inventory(
    store_id: uuid.UUID = Query(...),
    filter_: str = Query("all", alias="filter", pattern="^(all|low|out|untracked)$"),
    q: str | None = Query(None, max_length=100),
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Mağazadaki tüm varyantlar tek listede — hızlı stok düzenleme için."""
    _get_storefront_store(db, user.tenant_id, store_id)
    rows = db.execute(
        select(CatalogVariant, CatalogProduct.title, CatalogProduct.status)
        .join(CatalogProduct, CatalogVariant.product_id == CatalogProduct.id)
        .where(CatalogProduct.store_id == store_id)
        .order_by(CatalogProduct.title, CatalogVariant.position)
    ).all()

    items = []
    for v, title, p_status in rows:
        if q and q.lower() not in f"{title} {v.model_display} {v.variation or ''} {v.sku or ''}".lower():
            continue
        if filter_ == "low" and not (v.track_stock and 0 < v.quantity < 5):
            continue
        if filter_ == "out" and not (v.track_stock and v.quantity <= 0):
            continue
        if filter_ == "untracked" and v.track_stock:
            continue
        items.append({
            "variant_id": str(v.id),
            "product_id": str(v.product_id),
            "product_title": title,
            "product_status": p_status,
            "model_display": v.model_display,
            "variation": v.variation,
            "sku": v.sku,
            "quantity": v.quantity,
            "track_stock": v.track_stock,
            "is_active": v.is_active,
        })
    tracked = [i for i in items if i["track_stock"]]
    return {
        "total": len(items),
        "out_of_stock": sum(1 for i in tracked if i["quantity"] <= 0),
        "low_stock": sum(1 for i in tracked if 0 < i["quantity"] < 5),
        "items": items,
    }


class InventoryUpdate(BaseModel):
    variant_id: uuid.UUID
    quantity: int | None = Field(None, ge=0, le=1_000_000)
    track_stock: bool | None = None


class InventoryBulkRequest(BaseModel):
    updates: list[InventoryUpdate] = Field(..., min_length=1, max_length=500)


@router.post("/inventory/bulk", response_model=dict)
def bulk_inventory(
    body: InventoryBulkRequest,
    store_id: uuid.UUID = Query(...),
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Toplu stok güncelleme — envanter ekranındaki kaydet çubuğu."""
    _get_storefront_store(db, user.tenant_id, store_id)
    ids = [u.variant_id for u in body.updates]
    variants = {
        v.id: v for v in db.scalars(
            select(CatalogVariant)
            .join(CatalogProduct, CatalogVariant.product_id == CatalogProduct.id)
            .where(CatalogVariant.id.in_(ids), CatalogProduct.store_id == store_id)
        ).all()
    }
    from app.services.stock_alerts import notify_variant
    updated = 0
    for u in body.updates:
        v = variants.get(u.variant_id)
        if not v:
            continue  # başka mağazanın varyantı sessizce atlanır
        was_out = v.track_stock and v.quantity <= 0
        if u.quantity is not None:
            v.quantity = u.quantity
        if u.track_stock is not None:
            v.track_stock = u.track_stock
        if was_out and (not v.track_stock or v.quantity > 0):
            notify_variant(db, v)
        updated += 1
    db.commit()
    return {"updated": updated}


@router.get("/export")
def export_csv(
    store_id: uuid.UUID,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Katalog CSV'si — satır = varyant (varyantsız ürün tek satır).
    UTF-8 BOM: Excel Türkçe karakterleri doğru açsın."""
    import csv
    import io

    from fastapi.responses import StreamingResponse

    _get_storefront_store(db, user.tenant_id, store_id)
    products = db.scalars(
        select(CatalogProduct)
        .where(CatalogProduct.store_id == store_id)
        .options(selectinload(CatalogProduct.variants),
                 selectinload(CatalogProduct.collections))
        .order_by(CatalogProduct.position, CatalogProduct.created_at)
    ).all()

    buf = io.StringIO()
    buf.write("﻿")  # BOM
    writer = csv.writer(buf)
    writer.writerow(CSV_COLUMNS)
    for p in products:
        base = [
            p.slug, p.title, p.status, str(p.base_price),
            str(p.compare_at_price) if p.compare_at_price is not None else "",
            p.description or "", p.tags or "",
            ", ".join(c.title for c in p.collections),
            p.seo_title or "", p.seo_description or "",
        ]
        if p.variants:
            for v in p.variants:
                writer.writerow(base + [
                    v.model_key, v.model_display, v.variation or "",
                    v.sku or "",
                    str(v.price_override) if v.price_override is not None else "",
                    str(v.quantity), "1" if v.is_active else "0",
                ])
        else:
            writer.writerow(base + [""] * 7)

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="urunler.csv"'},
    )


@router.post("/import", response_model=dict)
async def import_csv(
    store_id: uuid.UUID,
    file: UploadFile = File(...),
    dry_run: bool = Query(True),
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """CSV içe aktarma — upsert: ürün=urun_slug, varyant=(model_key, renk).

    dry_run=true: hiçbir şey yazılmaz, yalnızca ne olacağı raporlanır.
    Hatalı satırlar atlanır ve raporlanır; sağlam satırlar işlenir.
    """
    import csv
    import io
    from decimal import Decimal, InvalidOperation

    from app.models import CatalogCollection

    _get_storefront_store(db, user.tenant_id, store_id)

    raw = (await file.read()).decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(raw))
    shopify_note = None
    if reader.fieldnames and "Handle" in reader.fieldnames and "Title" in reader.fieldnames:
        # SHOPIFY ürün export'u algılandı — kendi formatımıza çevirip aynı
        # upsert hattından geçir (görseller aktarılmaz; not düşülür).
        reader = iter(_shopify_to_native_rows(reader))
        shopify_note = ("Shopify formatı algılandı ve dönüştürüldü. Görseller "
                        "aktarılmaz — ürün görsellerini panelden yükleyin.")
    elif not reader.fieldnames or "urun_slug" not in reader.fieldnames:
        raise HTTPException(422, "Geçersiz CSV — başlık satırında 'urun_slug' bulunamadı "
                                 "(şablon için Dışa Aktar'ı kullanın; Shopify ürün "
                                 "export'u da desteklenir)")

    stats = {"products_created": 0, "products_updated": 0,
             "variants_created": 0, "variants_updated": 0, "errors": []}
    products_cache: dict[str, CatalogProduct] = {}
    collections_cache: dict[str, CatalogCollection] = {
        c.title.strip().lower(): c
        for c in db.scalars(select(CatalogCollection).where(
            CatalogCollection.store_id == store_id)).all()
    }

    def _dec(val, satir, alan):
        if val in (None, ""):
            return None
        try:
            return Decimal(str(val).replace(",", ".").strip())
        except InvalidOperation:
            raise ValueError(f"{alan} geçersiz sayı: {val}")

    for n, row in enumerate(reader, start=2):  # 1 = başlık
        if n - 1 > IMPORT_ROW_LIMIT:
            stats["errors"].append({"satir": n, "mesaj": f"Satır limiti ({IMPORT_ROW_LIMIT}) aşıldı — kalanlar atlandı"})
            break
        try:
            raw_slug = (row.get("urun_slug") or "").strip()
            if not raw_slug:
                raise ValueError("urun_slug boş")
            slug = slugify(raw_slug)

            product = products_cache.get(slug) or db.scalar(
                select(CatalogProduct).where(
                    CatalogProduct.store_id == store_id, CatalogProduct.slug == slug)
                .options(selectinload(CatalogProduct.variants)))

            fiyat = _dec(row.get("fiyat"), n, "fiyat")
            if product is None:
                if not (row.get("urun_adi") or "").strip():
                    raise ValueError("yeni ürün için urun_adi zorunlu")
                if fiyat is None:
                    raise ValueError("yeni ürün için fiyat zorunlu")
                product = CatalogProduct(
                    tenant_id=user.tenant_id, store_id=store_id, slug=slug,
                    title=row["urun_adi"].strip()[:300], base_price=fiyat,
                    status="draft",
                )
                db.add(product)
                db.flush()
                products_cache[slug] = product
                stats["products_created"] += 1
            elif slug not in products_cache:
                products_cache[slug] = product
                stats["products_updated"] += 1

            # Ürün alanları (doluysa güncelle)
            if (row.get("urun_adi") or "").strip():
                product.title = row["urun_adi"].strip()[:300]
            if fiyat is not None:
                product.base_price = fiyat
            durum = (row.get("durum") or "").strip()
            if durum in ("draft", "active", "archived"):
                product.status = durum
            cmp_ = _dec(row.get("indirim_oncesi"), n, "indirim_oncesi")
            if cmp_ is not None:
                product.compare_at_price = cmp_
            for csv_key, attr, maxlen in (
                ("aciklama", "description", 20000), ("etiketler", "tags", 500),
                ("seo_baslik", "seo_title", 200), ("seo_aciklama", "seo_description", 400),
            ):
                val = (row.get(csv_key) or "").strip()
                if val:
                    if attr == "description":
                        val = sanitize_rich_text(val) or ""
                    setattr(product, attr, val[:maxlen])

            # Koleksiyonlar (ad ile; yoksa oluştur)
            col_names = [c.strip() for c in (row.get("koleksiyonlar") or "").split(",") if c.strip()]
            if col_names:
                cols = []
                for name in col_names:
                    key = name.lower()
                    col = collections_cache.get(key)
                    if not col:
                        col = CatalogCollection(
                            tenant_id=user.tenant_id, store_id=store_id,
                            slug=slugify(name), title=name[:200])
                        db.add(col)
                        db.flush()
                        collections_cache[key] = col
                    cols.append(col)
                product.collections = cols

            # Varyant satırı
            model_key = (row.get("model_key") or "").strip()
            if model_key:
                renk = (row.get("renk") or "").strip().upper() or None
                variant = next(
                    (v for v in product.variants
                     if v.model_key == model_key and v.variation == renk), None)
                if variant is None:
                    model_adi = (row.get("model_adi") or "").strip()
                    if not model_adi:
                        raise ValueError("yeni varyant için model_adi zorunlu")
                    from app.services.brands import infer_brand
                    variant = CatalogVariant(
                        tenant_id=user.tenant_id, product_id=product.id,
                        model_key=model_key[:60], model_display=model_adi[:120],
                        brand=infer_brand(model_adi), variation=renk)
                    db.add(variant)
                    product.variants.append(variant)
                    stats["variants_created"] += 1
                else:
                    stats["variants_updated"] += 1
                if (row.get("model_adi") or "").strip():
                    variant.model_display = row["model_adi"].strip()[:120]
                if (row.get("sku") or "").strip():
                    variant.sku = row["sku"].strip()[:100]
                vfiyat = _dec(row.get("varyant_fiyat"), n, "varyant_fiyat")
                if vfiyat is not None:
                    variant.price_override = vfiyat
                stok = (row.get("stok") or "").strip()
                if stok:
                    variant.quantity = max(0, int(float(stok)))
                aktif = (row.get("varyant_aktif") or "").strip()
                if aktif in ("0", "1"):
                    variant.is_active = aktif == "1"
        except (ValueError, KeyError) as e:
            stats["errors"].append({"satir": n, "mesaj": str(e)[:200]})

    if dry_run:
        db.rollback()
        stats["dry_run"] = True
    else:
        db.commit()
        stats["dry_run"] = False
        # İçe aktarılan ürünler akıllı koleksiyon kurallarına göre yerleşsin
        for c in db.scalars(select(CatalogCollection).where(
                CatalogCollection.store_id == store_id,
                CatalogCollection.is_smart.is_(True))).all():
            smart_collections.sync_collection(db, c)
        db.commit()
    if shopify_note:
        stats["note"] = shopify_note
    return stats


# ── Shopify görselleri — CDN'den arka planda indirip ürünlere bağlar ──
# (Ürün import'unun eksik yarısı: Image Src sütunları CDN URL'idir.)

_IMG_JOBS: dict[str, dict] = {}   # store_id -> ilerleme
MAX_IMAGES_PER_PRODUCT = 5


@router.post("/import/shopify-images", response_model=dict)
async def import_shopify_images(
    store_id: uuid.UUID,
    file: UploadFile = File(...),
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Shopify export CSV'sindeki görselleri indirip ürünlere bağla.

    Arka planda çalışır (714 ürün dakikalar sürer) — ilerleme:
    GET /import/shopify-images/status. Görseli OLAN ürünler atlanır
    (tekrar çalıştırmak güvenli)."""
    import csv
    import io
    import threading

    _get_storefront_store(db, user.tenant_id, store_id)
    key = str(store_id)
    if _IMG_JOBS.get(key, {}).get("running"):
        raise HTTPException(409, "Görsel aktarımı zaten sürüyor — durumunu bekleyin")

    raw = (await file.read()).decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames or "Handle" not in reader.fieldnames \
            or "Image Src" not in reader.fieldnames:
        raise HTTPException(422, "Bu dosya Shopify ürün export'u değil "
                                 "(Handle/Image Src sütunları yok)")

    images: dict[str, list] = {}
    for row in reader:
        handle = (row.get("Handle") or "").strip()
        src = (row.get("Image Src") or "").strip()
        if not handle or not src.startswith("http"):
            continue
        try:
            pos = int(row.get("Image Position") or 999)
        except ValueError:
            pos = 999
        images.setdefault(handle, []).append((pos, src))

    if not images:
        raise HTTPException(422, "CSV'de indirilecek görsel bulunamadı")

    _IMG_JOBS[key] = {"running": True, "total": len(images), "done": 0,
                      "added": 0, "skipped": 0, "errors": []}
    threading.Thread(
        target=_run_image_import,
        args=(key, str(user.tenant_id), images),
        daemon=True,
    ).start()
    return {"ok": True, "products": len(images),
            "message": "Görsel aktarımı arka planda başladı"}


def _run_image_import(store_key: str, tenant_id: str, images: dict[str, list]) -> None:
    import httpx

    from app.database import SessionLocal

    job = _IMG_JOBS[store_key]
    db = SessionLocal()
    client = httpx.Client(timeout=25, follow_redirects=True)
    try:
        for handle, urls in images.items():
            slug = slugify(handle)
            try:
                product = db.scalar(
                    select(CatalogProduct)
                    .where(CatalogProduct.store_id == uuid.UUID(store_key),
                           CatalogProduct.slug == slug)
                    .options(selectinload(CatalogProduct.images)))
                if not product:
                    job["skipped"] += 1
                    continue
                if product.images:
                    job["skipped"] += 1   # görseli var — idempotent atla
                    continue
                added_here = 0
                for idx, (_pos, url) in enumerate(sorted(urls)[:MAX_IMAGES_PER_PRODUCT]):
                    try:
                        r = client.get(url)
                        r.raise_for_status()
                        fname = url.split("?")[0].rsplit("/", 1)[-1] or "gorsel.jpg"
                        if "." not in fname:
                            fname += ".jpg"
                        image_id = uuid.uuid4()
                        rel_path = storage_svc.save_catalog_image(
                            uuid.UUID(tenant_id), image_id, r.content, fname)
                        db.add(CatalogImage(
                            id=image_id, tenant_id=uuid.UUID(tenant_id),
                            product_id=product.id, file_path=rel_path,
                            alt=None, position=idx,
                        ))
                        added_here += 1
                    except Exception as e:  # noqa: BLE001 — tek görsel hatası ürünü durdurmaz
                        if len(job["errors"]) < 30:
                            job["errors"].append(
                                {"urun": slug, "mesaj": f"{type(e).__name__}: {e}"[:200]})
                db.commit()   # ürün başına commit — kısmi ilerleme korunur
                job["added"] += added_here
            except Exception as e:  # noqa: BLE001
                db.rollback()
                if len(job["errors"]) < 30:
                    job["errors"].append({"urun": slug, "mesaj": str(e)[:200]})
            finally:
                job["done"] += 1
    finally:
        client.close()
        db.close()
        job["running"] = False


@router.get("/import/shopify-images/status", response_model=dict)
def shopify_images_status(
    store_id: uuid.UUID,
    user: User = Depends(require_permission("vitrin")),
):
    return _IMG_JOBS.get(str(store_id)) or {"running": False, "total": 0, "done": 0,
                                            "added": 0, "skipped": 0, "errors": []}


# ─── Yorum moderasyonu ───────────────────────────────────────

@router.get("/reviews", response_model=dict)
def list_all_reviews(
    store_id: uuid.UUID,
    status_f: str = Query("pending", alias="status"),
    kind: str = Query("review", pattern="^(review|question)$"),
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    from app.models import ProductReview

    _get_storefront_store(db, user.tenant_id, store_id)
    rows = db.execute(
        select(ProductReview, CatalogProduct.title, CatalogProduct.slug)
        .join(CatalogProduct, CatalogProduct.id == ProductReview.product_id)
        .where(CatalogProduct.store_id == store_id,
               ProductReview.status == status_f,
               ProductReview.kind == kind)
        .order_by(ProductReview.created_at.desc()).limit(200)
    ).all()
    return {"items": [
        {
            "id": str(r.ProductReview.id),
            "product_title": r.title,
            "product_slug": r.slug,
            "author_name": r.ProductReview.author_name,
            "rating": r.ProductReview.rating,
            "comment": r.ProductReview.comment,
            "kind": r.ProductReview.kind,
            "answer": r.ProductReview.answer,
            "status": r.ProductReview.status,
            "verified": r.ProductReview.checkout_session_id is not None,
            "created_at": r.ProductReview.created_at.isoformat()
                if r.ProductReview.created_at else None,
        }
        for r in rows
    ]}


@router.post("/reviews/{review_id}/moderate", response_model=dict)
def moderate_review(
    review_id: uuid.UUID,
    body: dict,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    from app.models import ProductReview

    action = (body or {}).get("action")
    if action not in ("approve", "reject", "answer"):
        raise HTTPException(422, "action approve|reject|answer olmalı")
    review = db.scalar(select(ProductReview).where(
        ProductReview.id == review_id, ProductReview.tenant_id == user.tenant_id))
    if not review:
        raise HTTPException(404, "Kayıt bulunamadı")

    if action == "answer":
        # Soruyu yanıtla — yanıtlanan soru otomatik yayına girer
        text_ = str((body or {}).get("answer") or "").strip()[:2000]
        if not text_:
            raise HTTPException(422, "Yanıt boş olamaz")
        review.answer = text_
        review.answered_at = datetime.now(timezone.utc)
        review.status = "approved"
    else:
        review.status = "approved" if action == "approve" else "rejected"
    db.commit()
    return {"id": str(review.id), "status": review.status, "answer": review.answer}
