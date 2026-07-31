"""Akıllı koleksiyonlar — kural bazlı otomatik ürün üyeliği.

Shopify "automated collection" karşılığı. Kurallar koleksiyonda saklanır;
üyelik AYNI M2M tablosunda MADDİLEŞTİRİLİR (catalog_product_collections).
Böylece vitrin sayfaları, filtreler, koleksiyona özel kuponlar ve Google
feed'i hiç değişmeden çalışır — hepsi aynı tabloyu okur.

Yeniden hesaplama:
- Koleksiyon kaydedilince (kurallar değişmiş olabilir) → sync_collection
- Ürün kaydedilince/silinince → sync_product (yalnız o ürünün satırları)
- Panelden "Şimdi yenile" düğmesi → sync_collection

Kurallar: [{"field": "...", "op": "...", "value": "..."}], match = all|any
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from app.models import CatalogCollection, CatalogProduct, catalog_product_collections

# Panelin gösterdiği seçenekler — backend doğrulaması da buradan
FIELDS = {
    "title": "Ürün adı",
    "tag": "Etiket",
    "price": "Fiyat",
    "discounted": "İndirimli (üstü çizili fiyat var)",
    "stock": "Stok",
    "created_days": "Eklenme (son N gün)",
}
OPS = {
    "contains": "içeriyor",
    "not_contains": "içermiyor",
    "starts_with": "ile başlıyor",
    "gt": "büyüktür",
    "lt": "küçüktür",
    "eq": "eşittir",
    "is_true": "evet",
    "is_false": "hayır",
    "within": "içinde",
}
MAX_RULES = 10


def _dec(value) -> Decimal | None:
    try:
        return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ArithmeticError, TypeError):
        return None


def _stock_of(product: CatalogProduct) -> int:
    """Takip edilen varyantların toplam stoğu. Takip yoksa sınırsız kabul (1)."""
    total = 0
    for v in product.variants:
        if not v.is_active:
            continue
        if not v.track_stock:
            return 1
        total += int(v.quantity or 0)
    return total


def rule_matches(product: CatalogProduct, rule: dict) -> bool:
    field = (rule.get("field") or "").strip()
    op = (rule.get("op") or "").strip()
    raw = rule.get("value")
    value = str(raw or "").strip()

    if field == "title":
        haystack = (product.title or "").casefold()
        needle = value.casefold()
        if not needle:
            return False
        if op == "contains":
            return needle in haystack
        if op == "not_contains":
            return needle not in haystack
        if op == "starts_with":
            return haystack.startswith(needle)
        return False

    if field == "tag":
        tags = [t.strip().casefold() for t in (product.tags or "").split(",") if t.strip()]
        needle = value.casefold()
        if not needle:
            return False
        if op == "contains":
            return needle in tags
        if op == "not_contains":
            return needle not in tags
        return False

    if field == "price":
        target = _dec(value)
        price = _dec(product.base_price)
        if target is None or price is None:
            return False
        if op == "gt":
            return price > target
        if op == "lt":
            return price < target
        if op == "eq":
            return price == target
        return False

    if field == "discounted":
        cmp_at = _dec(product.compare_at_price)
        price = _dec(product.base_price)
        indirimli = bool(cmp_at and price is not None and cmp_at > price)
        return indirimli if op == "is_true" else (not indirimli if op == "is_false" else False)

    if field == "stock":
        var = _stock_of(product) > 0
        return var if op == "is_true" else (not var if op == "is_false" else False)

    if field == "created_days":
        gun = _dec(value)
        if gun is None or not product.created_at:
            return False
        created = product.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return created >= datetime.now(timezone.utc) - timedelta(days=int(gun))

    return False


def product_matches(product: CatalogProduct, rules: list[dict], match: str) -> bool:
    """Kural listesi ürüne uyuyor mu? match='all' (ve) | 'any' (veya).

    Kural yoksa hiçbir ürün eşleşmez — boş kuralla tüm katalog bir koleksiyona
    dolmasın (kaza koruması)."""
    usable = [r for r in (rules or []) if r.get("field")]
    if not usable:
        return False
    results = (rule_matches(product, r) for r in usable)
    return all(results) if match != "any" else any(results)


def _store_products(db: Session, store_id) -> list[CatalogProduct]:
    return list(db.scalars(
        select(CatalogProduct).where(CatalogProduct.store_id == store_id)))


def sync_collection(db: Session, collection: CatalogCollection) -> int:
    """Koleksiyonun üyeliğini kurallara göre yeniden kur. Uyan ürün sayısını döndürür.

    Akıllı olmayan koleksiyona dokunmaz (elle seçilen ürünler korunur)."""
    if not collection.is_smart:
        return 0

    rules = collection.rules or []
    match = collection.rules_match or "all"
    eslesenler = [
        p.id for p in _store_products(db, collection.store_id)
        if product_matches(p, rules, match)
    ]

    db.execute(delete(catalog_product_collections).where(
        catalog_product_collections.c.collection_id == collection.id))
    if eslesenler:
        db.execute(insert(catalog_product_collections), [
            {"product_id": pid, "collection_id": collection.id} for pid in eslesenler
        ])
    return len(eslesenler)


def sync_product(db: Session, product: CatalogProduct) -> None:
    """Tek ürünün akıllı koleksiyon üyeliklerini tazele (ürün kaydedilince).

    Yalnız akıllı koleksiyonların satırlarına dokunur; elle kurulan üyelikler
    olduğu gibi kalır."""
    smarts = db.scalars(select(CatalogCollection).where(
        CatalogCollection.store_id == product.store_id,
        CatalogCollection.is_smart.is_(True),
    )).all()
    if not smarts:
        return

    mevcut = {
        row[0] for row in db.execute(
            select(catalog_product_collections.c.collection_id).where(
                catalog_product_collections.c.product_id == product.id,
                catalog_product_collections.c.collection_id.in_([c.id for c in smarts]),
            )).all()
    }
    for c in smarts:
        uyuyor = product_matches(product, c.rules or [], c.rules_match or "all")
        if uyuyor and c.id not in mevcut:
            db.execute(insert(catalog_product_collections).values(
                product_id=product.id, collection_id=c.id))
        elif not uyuyor and c.id in mevcut:
            db.execute(delete(catalog_product_collections).where(
                catalog_product_collections.c.product_id == product.id,
                catalog_product_collections.c.collection_id == c.id))


def preview(db: Session, store_id, rules: list[dict], match: str, limit: int = 12) -> dict:
    """Kaydetmeden önce "kaç ürün eşleşiyor" önizlemesi (panel)."""
    urunler = [p for p in _store_products(db, store_id)
               if product_matches(p, rules, match)]
    return {
        "count": len(urunler),
        "samples": [{"id": str(p.id), "title": p.title, "slug": p.slug}
                    for p in urunler[:limit]],
    }
