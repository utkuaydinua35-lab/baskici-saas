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

import logging
import re
import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import (APIRouter, BackgroundTasks, Depends, HTTPException, Query,
                     Request, Response)
from fastapi.responses import PlainTextResponse, RedirectResponse
from pydantic import BaseModel, BeforeValidator, EmailStr, Field
from sqlalchemy import String, cast, func, or_, select, union_all
from sqlalchemy.orm import Session, selectinload

from app.services.site import site_url
from app.database import get_db
from app.models import CatalogProduct, CatalogVariant, CheckoutSession, DiscountCode, Store
from app.payments import get_payment_provider
from app.services import checkout as checkout_svc
from app.services import storage as storage_svc
from app.services.rate_limit import client_ip, make_rate_limiter
from starlette.concurrency import run_in_threadpool

router = APIRouter(prefix="/api/shop", tags=["public-shop"])

# Okuma uçları için cömert limit (katalog gezinme); yazma uçları ayrı, sıkı sayaç.
read_rate_limit = make_rate_limiter(max_hits=60, window=60.0)
checkout_rate_limit = make_rate_limiter(max_hits=10, window=60.0)
status_rate_limit = make_rate_limiter(max_hits=30, window=60.0)


def _studio_modules(db, store, product) -> list[dict]:
    """Ürüne bağlı kılıf şablonları (yalnız yayında ve görseli olanlar)."""
    from app.models import CaseTemplate

    anahtarlar = list(product.studio_templates or [])
    if not anahtarlar:
        return []
    rows = db.scalars(select(CaseTemplate).where(
        CaseTemplate.store_id == store.id,
        CaseTemplate.key.in_(anahtarlar),
        CaseTemplate.is_active.is_(True),
        CaseTemplate.image_path.isnot(None),
    ).order_by(CaseTemplate.position)).all()
    return [
        {"key": t.key, "label": t.label, "description": t.description,
         "image_url": f"/storage/{t.image_path}"}
        for t in rows
    ]


def _studio_overlay_moduller(db, store, product) -> list[dict]:
    """Ürüne bağlanan HAZIR TASARIM MODÜLLERİ (Spotify arayüzü, forma…).

    Kılıf şablonundan (studio_templates) farkı: bunlar hazır bir tasarım
    sunar, müşteri yalnız içindeki alanları doldurur. Ürün sayfasında ayrı
    kart olarak çıkar; karta basınca stüdyo o modül seçili açılır.
    """
    from app.models import CaseTemplate, DesignOverlay

    kimlikler = [str(x) for x in (product.studio_overlays or [])]
    if not kimlikler:
        return []
    rows = db.execute(
        select(DesignOverlay, CaseTemplate.key)
        .join(CaseTemplate, DesignOverlay.case_template_id == CaseTemplate.id,
              isouter=True)
        .where(DesignOverlay.store_id == store.id,
               DesignOverlay.id.in_(kimlikler),
               DesignOverlay.is_active.is_(True))
        .order_by(DesignOverlay.position, DesignOverlay.created_at)
    ).all()
    return [
        {
            "id": str(o.id),
            "label": o.label,
            "kategori": o.kategori or None,
            "thumb_url": f"/storage/{o.thumb_path or o.image_path}",
            # Modül belirli bir kılıfa bağlıysa stüdyo o kılıfla açılsın
            "kilif_key": key,
        }
        for o, key in rows
    ]


# Vitrin "bakımda" — kiracının aboneliği askıya düştüğünde. Vitrin bu
# kodu tanıyıp hata yerine düzgün bir bakım sayfası gösterir.
BAKIMDA_KODU = "vitrin_bakimda"


def _resolve_store(db: Session, store_slug: str) -> Store:
    """Vitrin mağazasını slug ile çöz. Yalnızca platform='storefront' + aktif.

    KİRALAMA: kiracının ödemesi 14 günden fazla gecikmişse (ya da hesap elle
    askıya alındıysa) vitrin bakıma girer — 503 + BAKIMDA_KODU.

    Bu kontrolün BURADA olması bilinçli: mevcut müşterinin işini gören uçlar
    (iyzico/PayTR ödeme dönüşü, token'la sipariş takibi, sepet geri yükleme)
    mağazayı slug ile değil token ile buluyor ve _resolve_store'dan
    GEÇMİYOR. Böylece vitrin kapansa bile ödemesi yolda olan müşterinin
    siparişi düşer, sipariş takip sayfası çalışmaya devam eder. Yalnız YENİ
    alışveriş durur.
    """
    store = db.scalar(select(Store).where(
        Store.slug == store_slug,
        Store.platform == "storefront",
        Store.is_active.is_(True),
    ))
    if not store:
        raise HTTPException(404, "Mağaza bulunamadı")

    from app.models import Tenant
    from app.services import abonelik
    if not abonelik.durum(db.get(Tenant, store.tenant_id)).vitrin_acik:
        raise HTTPException(503, BAKIMDA_KODU)
    return store


def _effective_price(product: CatalogProduct, variant: CatalogVariant) -> str:
    price = variant.price_override if variant.price_override is not None else product.base_price
    return str(price)


COK_SATAN_GUN = 90


def _cok_satan_alt(db, store):
    """Ürün başına son 90 günde satılan adet (alt sorgu: urun_id, adet).

    Katalog ile sipariş satırı arasında doğrudan bağ yok: vitrin siparişinde
    satır ürün kimliğini taşır, Shopify siparişinde Shopify'ın kimliğini.
    Bu yüzden kimlik YA DA başlık eşleşmesi sayılır — Shopify'dan taşınan
    ürünlerin satışı da "Çok Satanlar"a girer. İptal ve telafi hariç.
    """
    from datetime import datetime, timedelta, timezone

    from app.models import LineItem, Order

    sinir = datetime.now(timezone.utc) - timedelta(days=COK_SATAN_GUN)
    satis = (
        select(LineItem.product_id.label("pid"), LineItem.title.label("baslik"),
               func.sum(LineItem.quantity).label("adet"))
        .join(Order, Order.id == LineItem.order_id)
        .where(Order.tenant_id == store.tenant_id, Order.cancelled_at.is_(None),
               Order.is_telafi.is_(False), Order.created_at_platform >= sinir)
        .group_by(LineItem.product_id, LineItem.title)
    ).subquery()
    # "kimlik YA DA başlık" tek koşulda hash join'i engelliyor (500 ürün,
    # 1 yıllık satışla 268 ms). İki eşitlik birleştirmesi + UNION ALL aynı
    # sonucu 50 ms'de verir; ikinci kol kimliği eşleşeni dışarıda bırakır ki
    # satış iki kez sayılmasın.
    urun_kimlik = cast(CatalogProduct.id, String)
    eslesme = union_all(
        select(CatalogProduct.id.label("urun_id"), satis.c.adet)
        .join(satis, satis.c.pid == urun_kimlik)
        .where(CatalogProduct.store_id == store.id),
        select(CatalogProduct.id.label("urun_id"), satis.c.adet)
        .join(satis, (satis.c.baslik == CatalogProduct.title)
              & satis.c.pid.is_distinct_from(urun_kimlik))
        .where(CatalogProduct.store_id == store.id),
    ).subquery()
    return (
        select(eslesme.c.urun_id, func.sum(eslesme.c.adet).label("adet"))
        .group_by(eslesme.c.urun_id)
    ).subquery("cok_satan")


def _kart_ozetleri(db: Session, urun_idleri) -> dict:
    """Ürün kartı için varyant özeti — TEK sorguda, veritabanında.

    Eskiden liste her ürünün TÜM varyantlarını ORM nesnesi olarak yüklüyordu
    (canlıda ürün başına ~300 varyant → 24'lük sayfada ~7.400 satır) ve yalnız
    "N model için uygun" + stok rozeti için Python'da sayıyordu. Ürün listesi
    bu yüzden her istekte 1-2 sn sürüyordu. Sonuç birebir aynı:
      model_count = farklı aktif model sayısı
      total_stock = aktif varyantların HEPSİ stok takipliyse stok toplamı, değilse None
    """
    if not urun_idleri:
        return {}
    aktif = CatalogVariant.is_active.is_(True)
    satirlar = db.execute(
        select(
            CatalogVariant.product_id,
            func.count(func.distinct(CatalogVariant.model_display)).filter(aktif),
            func.count().filter(aktif),
            func.count().filter(aktif, CatalogVariant.track_stock.is_(True)),
            func.coalesce(func.sum(func.greatest(CatalogVariant.quantity, 0))
                          .filter(aktif, CatalogVariant.track_stock.is_(True)), 0),
        ).where(CatalogVariant.product_id.in_(list(urun_idleri)))
        .group_by(CatalogVariant.product_id)
    ).all()
    return {
        pid: {"model_count": int(mc or 0),
              "total_stock": int(stok) if aktif_say and takipli == aktif_say else None}
        for pid, mc, aktif_say, takipli, stok in satirlar
    }


def _serialize_product_card(p: CatalogProduct, ozet: dict | None = None) -> dict:
    """Liste kartı — minimum alan (PII yok, iç ID'ler yalnızca gerekli olanlar).

    ozet: _kart_ozetleri satırı (varyantlar YÜKLENMEDEN). Verilmezse eski yol
    (p.variants yüklü olmalı)."""
    if ozet is None:
        active_variants = [v for v in p.variants if v.is_active]
        models = {v.model_display for v in active_variants}
        # "Son N adet" rozeti: yalnızca TÜM varyantlar stok takipliyse anlamlı
        tracked = [v for v in active_variants if v.track_stock]
        ozet = {
            "model_count": len(models),
            "total_stock": (sum(max(v.quantity, 0) for v in tracked)
                            if active_variants and len(tracked) == len(active_variants) else None),
        }
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
        "model_count": ozet["model_count"],
        "total_stock": ozet["total_stock"],
    }


def _serialize_product_detail(p: CatalogProduct, db=None, store=None) -> dict:
    return {
        "slug": p.slug,
        "title": p.title,
        "custom_fields": p.custom_fields or [],
        # Tasarım stüdyosu modülleri — müşteri bu kılıflarla kendi tasarımını
        # yapabilir; ürün sayfasında "Kendi Tasarımını Yap" bölümü olarak çıkar
        "studio_overlays": [str(x) for x in (p.studio_overlays or [])],
        "studio_templates": (_studio_modules(db, store, p)
                             if db is not None and store is not None else []),
        # Ürüne bağlı HAZIR TASARIM MODÜLLERİ — kılıf şablonu seçilmemiş olsa
        # bile ürün sayfasında görünür (modül tek başına da satılabilir)
        "studio_moduller": (_studio_overlay_moduller(db, store, p)
                            if db is not None and store is not None else []),
        "models_per_item": p.models_per_item or 1,
        "model_basliklari": p.model_basliklari or [],
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
    # yeni = "Önerilen" (paneldeki elle sıra — adı tarihsel)
    sort: str = Query("yeni", pattern="^(yeni|en-yeni|cok-satan|fiyat-artan|fiyat-azalan|a-z|z-a)$"),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    page: int = Query(1, ge=1, le=1000),
    per_page: int = Query(24, ge=1, le=60),
    # Ürünler sayfasındaki arama kaydedilir ("müşteriler ne aradı" raporu);
    # yazarken öneriler (header) kaydedilmez — yarım kelimelerle dolardı
    kaydet: bool = Query(False),
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
        # Varyantlar YÜKLENMEZ — kart özeti tek sorguda (_kart_ozetleri)
        .options(selectinload(CatalogProduct.images))
    )
    if sort == "fiyat-artan":
        query = query.order_by(CatalogProduct.base_price.asc(), CatalogProduct.position)
    elif sort == "fiyat-azalan":
        query = query.order_by(CatalogProduct.base_price.desc(), CatalogProduct.position)
    elif sort == "en-yeni":
        query = query.order_by(CatalogProduct.created_at.desc())
    elif sort in ("a-z", "z-a"):
        # Türkçe kural: Ç/Ş/Ö/Ü/İ doğru yere düşsün (ICU, PG16'da mevcut)
        ad = CatalogProduct.title.collate("tr-TR-x-icu")
        query = query.order_by(ad.asc() if sort == "a-z" else ad.desc())
    elif sort == "cok-satan":
        satis = _cok_satan_alt(db, store)
        query = query.outerjoin(satis, satis.c.urun_id == CatalogProduct.id).order_by(
            func.coalesce(satis.c.adet, 0).desc(), CatalogProduct.position)
    else:
        query = query.order_by(CatalogProduct.position, CatalogProduct.created_at.desc())
    arama_sirasi: list | None = None
    if q and q.strip():
        # Türkçe harf + yazım hatası toleranslı, alakaya göre sıralı arama
        # (services/arama.py). Diğer süzgeçler (koleksiyon, marka, fiyat)
        # bu kümenin üstüne SQL'de uygulanır.
        from app.services import arama
        arama_sirasi = arama.ara(db, store, q)
        query = query.where(CatalogProduct.id.in_(arama_sirasi or [uuid.uuid4()]))
        if sort == "yeni" and arama_sirasi:
            # Varsayılan sıralamada en alakalı ürün önce
            from sqlalchemy import bindparam
            from sqlalchemy.dialects.postgresql import ARRAY, UUID as PG_UUID
            sira = bindparam("arama_sirasi", arama_sirasi, type_=ARRAY(PG_UUID(as_uuid=True)))
            query = query.order_by(None).order_by(func.array_position(sira, CatalogProduct.id))
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

    # Model filtresi SQL'de: "Galaxy S24 Plus" varyantı olan ürünler.
    # (Python'da süzülürse mağazadaki BÜTÜN ürünler + varyantları belleğe
    # çekilirdi — vitrinin ve destek botu linklerinin yavaşlama sebebi buydu.)
    if model:
        query = query.where(
            select(CatalogVariant.id).where(
                CatalogVariant.product_id == CatalogProduct.id,
                CatalogVariant.is_active.is_(True),
                CatalogVariant.model_display.ilike(f"%{model}%"),
            ).exists()
        )

    if slugs:
        # Verilen sırada dönen küçük liste (en fazla 24) — sayfalama uygulanmaz
        wanted = [x.strip() for x in slugs.split(",") if x.strip()][:24]
        rows = db.scalars(query.where(CatalogProduct.slug.in_(wanted))).all()
        by_slug = {p_.slug: p_ for p_ in rows}
        items = [by_slug[w] for w in wanted if w in by_slug]
        total = len(items)
    else:
        # Sayım ve sayfalama VERİTABANINDA — sabit maliyet, katalog büyüdükçe
        # yavaşlamaz. order_by sayımda gereksiz, alt sorgudan çıkarılır.
        total = db.scalar(
            select(func.count()).select_from(query.order_by(None).subquery())
        ) or 0
        start = (page - 1) * per_page
        items = db.scalars(query.limit(per_page).offset(start)).all()

    # Filtre yüzeyleri: mağazadaki aktif markalar (mevcut filtrelerden bağımsız)
    # ÖNBELLEKLİ: bu sorgu her istekte mağazanın TÜM varyantlarını tarıyordu
    # (canlıda 191 bin satır, 103 ms, iki paralel işçi) ve veritabanının en
    # çok satır okuyan sorgusuydu. Marka listesi katalog değişmedikçe
    # değişmez; vitrin_cache katalog sinyaliyle + TTL ile tazeliyor.
    from app.services import vitrin_cache

    def _markalari_oku():
        return sorted(b for (b,) in db.execute(
            select(CatalogVariant.brand).distinct()
            .join(CatalogProduct, CatalogVariant.product_id == CatalogProduct.id)
            .where(
                CatalogProduct.store_id == store.id,
                CatalogProduct.status == "active",
                CatalogVariant.is_active.is_(True),
                CatalogVariant.brand.isnot(None),
            )
        ).all() if b)

    brands = vitrin_cache.markalar(db, store.id, _markalari_oku)
    if kaydet and q and page == 1 and arama_sirasi is not None:
        _aramayi_kaydet(db, store, q, total)
    ozetler = _kart_ozetleri(db, [p_.id for p_ in items])
    bos_ozet = {"model_count": 0, "total_stock": None}

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
        "items": [_serialize_product_card(p, ozetler.get(p.id, bos_ozet)) for p in items],
        "facets": {"brands": brands},
    }


def _aramayi_kaydet(db: Session, store, q: str, sonuc: int) -> None:
    """Analitik — asla aramayı bozmaz. 90 günden eskiler ara sıra budanır."""
    from app.models import AramaKaydi
    from app.services import arama
    sorgu = arama.normalize(q)[:100]
    if len(sorgu) < 2:
        return
    try:
        db.add(AramaKaydi(store_id=store.id, sorgu=sorgu, sonuc=int(sonuc)))
        import random
        if random.random() < 0.01:
            from sqlalchemy import text
            db.execute(text("DELETE FROM arama_kayitlari WHERE created_at < now() - interval '90 days'"))
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()


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

    detail = _serialize_product_detail(product, db, store)

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
    ).options(selectinload(CatalogProduct.images))
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
    rel_ozet = _kart_ozetleri(db, [r.id for r in related])
    detail["related"] = [_serialize_product_card(r, rel_ozet.get(r.id, {"model_count": 0, "total_stock": None}))
                         for r in related]

    response.headers["Cache-Control"] = "public, max-age=60"
    return detail


# ─── Checkout + Ödeme ────────────────────────────────────────

def _kirp(sinir: int):
    """Uzun değeri REDDETME, KIRP.

    Ödeme akışında zorunlu olmayan alanlar (reklam eşleşme sinyalleri, sipariş
    notu) uzun geldi diye istek 422 alırsa müşteri ödeme yapamaz — üstelik
    ekranda sebebi görünmez. Gerçek vaka: Facebook/Instagram reklamından gelen
    ziyaretçinin `_fbc` çerezi 200 karakteri aşıyor ve REKLAMDAN GELEN HER
    MÜŞTERİNİN ödemesi düşüyordu. Bu alanlar teslimat için gerekli değil;
    fazlası atılır, sipariş devam eder.
    """
    def kirp(v):
        if v is None:
            return None
        s = str(v).strip()
        return s[:sinir] or None
    return kirp


# Reklam eşleşme sinyali (_fbp/_fbc çerezleri) — uzunluğu Facebook'un elinde
Sinyal = Annotated[str | None, BeforeValidator(_kirp(400))]
# Müşterinin serbest metni — kırpılır, ödeme durmaz
SiparisNotu = Annotated[str | None, BeforeValidator(_kirp(500))]


class CheckoutItemIn(BaseModel):
    variant_id: uuid.UUID
    quantity: int = Field(..., ge=1, le=20)
    # Couple ürünler: ikinci kılıfın modeli (aynı ürünün varyantı olmalı)
    second_variant_id: uuid.UUID | None = None
    # Kişiye özel alanlar: {key: value} — üründeki tanıma göre doğrulanır
    custom: dict | None = None
    # Tasarım stüdyosunda hazırlanan tasarım (varsa) — sunucuda doğrulanır
    design_id: uuid.UUID | None = None


class CheckoutCustomerIn(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: str = Field(..., min_length=7, max_length=20)
    address1: str = Field(..., min_length=5, max_length=300)
    city: str = Field(..., min_length=2, max_length=60)
    province: str | None = Field(None, max_length=60)
    zip: str | None = Field(None, max_length=20)
    note: SiparisNotu = None
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
    fbp: Sinyal = None
    fbc: Sinyal = None
    vid: Sinyal = None   # birinci taraf ziyaretçi kimliği (bz_vid) — CAPI external_id


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
    shipping = checkout_svc.kargo_ucreti(store, items_total, plan)
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
    shipping = checkout_svc.kargo_ucreti(store, items_total, plan)
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
                # Stüdyo tasarımı — checkout.create_session bunu okuyup baskı
                # dosyasını siparişe bağlar. Aktarılmadığı için müşterinin
                # tasarımı siparişe HİÇ düşmüyordu.
                "design_id": str(i.design_id) if i.design_id else None,
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
                    "vid": body.vid,
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


# ── Ürün feed'i ortak parçaları (Meta + Google aynı g: şemasını kullanır) ──

TELEFON_KILIFI_KATEGORI = (
    "Electronics &gt; Communications &gt; Telephony &gt; "
    "Mobile Phone Accessories &gt; Mobile Phone Cases"
)


def _kargo_xml(config: dict) -> str:
    """<g:shipping> — reklamda kargo ücreti görünsün.

    Feed şemasında "şu tutarın üstünde bedava" diye bir alan YOK; eşik
    Merchant Center / Commerce Manager tarafında tanımlanır. Buraya sabit
    ücret yazılır — siparişlerin çoğu eşiğin altında olduğu için doğru olan
    da budur. Ücret tanımsızsa etiket hiç basılmaz (0 yazmak "bedava" demek
    olurdu ve yanıltırdı).
    """
    from xml.sax.saxutils import escape
    ham = str(config.get("shipping_fee") or "").strip()
    if not ham:
        return ""
    try:
        ucret = Decimal(ham)
    except ArithmeticError:
        return ""
    return ("<g:shipping><g:country>TR</g:country>"
            f"<g:service>Standart</g:service>"
            f"<g:price>{escape(f'{ucret} TRY')}</g:price></g:shipping>")


def _urun_tipi(p) -> str:
    """<g:product_type> — mağazanın KENDİ kategorisi (koleksiyon adı).

    google_product_category standart taksonomidir ve hepsi aynı değeri alır;
    reklam tarafında ürünleri birbirinden ayıran şey budur.
    """
    from xml.sax.saxutils import escape
    adlar = [c.title for c in (p.collections or []) if c.title][:2]
    if not adlar:
        return ""
    return f"<g:product_type>{escape(' &gt; '.join(adlar)[:250])}</g:product_type>"


def _fiyat_bandi(fiyat) -> str:
    """<g:custom_label_0> — fiyat bandı.

    Advantage+ katalog kampanyasında ürünleri marja göre ayırıp farklı
    teklif vermeyi sağlar. Meta bu etiketin ANLAMINI bilmez, yalnız
    gruplamak için kullanır.
    """
    try:
        f = Decimal(str(fiyat))
    except ArithmeticError:
        return ""
    band = "0-300" if f < 300 else "300-600" if f < 600 else "600+"
    return f"<g:custom_label_0>{band}</g:custom_label_0>"


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
    site = site_url(config)

    products = db.scalars(
        select(CatalogProduct)
        .where(CatalogProduct.store_id == store.id, CatalogProduct.status == "active")
        .options(selectinload(CatalogProduct.variants),
                 selectinload(CatalogProduct.images),
                 selectinload(CatalogProduct.collections))
        .order_by(CatalogProduct.position)
    ).all()

    kargo = _kargo_xml(config)
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
            f"<g:google_product_category>{TELEFON_KILIFI_KATEGORI}</g:google_product_category>"
            + _urun_tipi(p)
            + _fiyat_bandi(p.base_price)
            + kargo
            + "</item>"
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
    site = site_url(config)

    products = db.scalars(
        select(CatalogProduct)
        .where(CatalogProduct.store_id == store.id, CatalogProduct.status == "active")
        .options(selectinload(CatalogProduct.variants),
                 selectinload(CatalogProduct.images),
                 selectinload(CatalogProduct.collections))
        .order_by(CatalogProduct.position)
    ).all()

    kargo = _kargo_xml(config)
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
                # Merchant Center kategori olmadan ürünü "eksik veri" sayıyordu
                + f"<g:google_product_category>{TELEFON_KILIFI_KATEGORI}</g:google_product_category>"
                + _urun_tipi(p)
                + _fiyat_bandi(price)
                + kargo
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
    tema = resolve_theme(config)
    # Eski ham kampanya kodu (çark / "Gitmeden önce") vitrine gitmez: kapatınca
    # tekrar tekrar açılıyordu. Tema aracı kapalıysa eski koddaki ayarlarla
    # yeni araç açılır (kayıtlı veri değişmez — bkz. eski_kampanya_kodu).
    from app.services import eski_kampanya_kodu
    from app.services.theme import _cark_temizle, _cikis_temizle
    ozel_kod, eski_cark, eski_cikis = eski_kampanya_kodu.ayikla(config.get("custom_code") or None)
    if eski_cark and not tema["cark"]["enabled"]:
        tema["cark"] = _cark_temizle({**tema["cark"], **eski_cark})
    if eski_cikis and not tema["cikis"]["enabled"]:
        tema["cikis"] = _cikis_temizle({**tema["cikis"], **eski_cikis})
    return {
        "store_name": store.name,
        "theme": tema,
        "settings": {
            "shipping_fee": config.get("shipping_fee"),
            "free_shipping_over": config.get("free_shipping_over"),
            "min_order_amount": config.get("min_order_amount"),
            "gift_wrap_enabled": bool(config.get("gift_wrap_enabled")),
            # Güven rozeti aktif sağlayıcıyı göstersin (iyzico VEYA PayTR)
            "payment_provider": config.get("payment_provider") or "iyzico",
            # Tasarım stüdyosu ürünü — fiyat ve telefon modelleri buradan gelir
            "studio_product_slug": config.get("studio_product_slug") or None,
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
        "custom_code": ozel_kod,
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
        # İşletme bilgileri: BOŞ gelirse vitrin o cümleyi HİÇ yazmaz. Yeni bir
        # mağazaya başka bir işletmenin taahhüdünü (teslim süresi, iade
        # istisnası) miras bırakmaktansa susmak doğru olan.
        "isletme": {
            "urun_turu": (config.get("isletme_urun_turu") or "").strip() or None,
            "tanitim": (config.get("isletme_tanitim") or "").strip() or None,
            "teslim_suresi": (config.get("isletme_teslim_suresi") or "").strip() or None,
            "kisiye_ozel": bool(config.get("isletme_kisiye_ozel")),
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

    # Mağazaya haber ver — soru yanıtlanana kadar vitrinde görünmez, bu yüzden
    # bildirim gelmezse müşteri cevapsız kalır
    baslik = f"❓ Yeni ürün sorusu — {product.title[:40]}"
    ozet = body.question.strip()[:200]
    try:
        from app.models import Notification
        from app.services import push

        db.add(Notification(
            tenant_id=store.tenant_id, store_id=store.id,
            kind="info", title=baslik, body=ozet, link="/yorumlar",
        ))
        db.commit()
        push.send_to_tenant(db, store.tenant_id, baslik, ozet[:120],
                            url="/yorumlar", tag="urun-sorusu")
    except Exception:  # noqa: BLE001 — bildirim gitmese de soru kaydedildi
        logging.getLogger("public_shop").warning("Soru bildirimi gönderilemedi", exc_info=True)
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
        url = await run_in_threadpool(
            storage_svc.save_store_asset,
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
    # Oturum raporu (services/oturum): yalnız oturumun İLK ping'inde kullanılır
    ref: str | None = Field(None, max_length=300)       # document.referrer
    utm: str | None = Field(None, max_length=60)        # utm_source
    tik: str | None = Field(None, pattern="^(fbclid|gclid|ttclid)$")  # reklam tıklama kimliği türü
    mobil: bool | None = None


presence_rate_limit = make_rate_limiter(max_hits=12, window=60.0)

# Cloudflare ülkeyi bilmediğinde ya da Tor çıkışında bu kodları döner —
# gerçek ülke değiller, konum listesinde "Bilinmiyor" sayılsınlar
_ULKE_YOK = {"XX", "T1", "", "ZZ"}


def _ulke_kodu(request: Request) -> str | None:
    """Vitrin proxy'sinin ilettiği ülke kodu (Cloudflare kaynaklı)."""
    ham = (request.headers.get("x-visitor-country") or "").strip().upper()[:2]
    if ham in _ULKE_YOK or not ham.isalpha():
        return None
    return ham


@router.post("/{store_slug}/presence")
def presence_ping(
    store_slug: str,
    body: PresenceIn,
    request: Request,
    _rl: None = Depends(presence_rate_limit),
    db: Session = Depends(get_db),
):
    """Ziyaretçi ping'i (~20 sn'de bir) — panel Canlı Görünüm'ünü besler.

    Kişisel veri yok: istemcinin ürettiği rastgele oturum anahtarı ve
    Cloudflare'in bildirdiği ÜLKE KODU. IP adresi saklanmaz."""
    from datetime import datetime, timezone

    from app.models import StorefrontPresence

    store = _resolve_store(db, store_slug)
    now = datetime.now(timezone.utc)
    key = body.key.strip()[:64]
    # Aynı ziyaretçinin eşzamanlı ping'leri sıraya girer (işlem sonunda bırakılır):
    # yoksa ikisi birden "oturum yok" görüp İKİ oturum açar, sayım şişer.
    db.execute(select(func.pg_advisory_xact_lock(func.hashtext(f"{store.id}:{key}"))))
    row = db.scalar(select(StorefrontPresence).where(
        StorefrontPresence.store_id == store.id,
        StorefrontPresence.session_key == key,
    ))
    if row is None:
        row = StorefrontPresence(
            tenant_id=store.tenant_id, store_id=store.id,
            session_key=key, first_seen=now, last_seen=now,
        )
        db.add(row)
        # İlk iki ping aynı anda gelebilir (sayfa açılışı + sepet sayımı):
        # ikisi de "satır yok" görüp eklemeye çalışıyor, biri benzersizlik
        # kısıtına takılıp 500 veriyordu (canlı günlükte, 2026-10). Satırı
        # hemen yaz; çakışırsa diğer isteğin yazdığını oku.
        from sqlalchemy.exc import IntegrityError
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            row = db.scalar(select(StorefrontPresence).where(
                StorefrontPresence.store_id == store.id,
                StorefrontPresence.session_key == key,
            ))
            if row is None:      # çakışma değil, başka bir kısıt: gizleme
                raise
    row.last_seen = now
    row.last_path = (body.path or "")[:300] or None
    row.cart_items = body.cart_items
    # Ülke bir kez yazılır; sonraki ping'lerde değişmez (aynı oturum)
    if not row.country:
        row.country = _ulke_kodu(request)
    # Ulaşılan en ileri huni aşaması — "nerede vazgeçti" analizi
    from app.services import funnel
    new_stage = funnel.merge_stage(
        row.stage, funnel.stage_from_path(body.path, body.cart_items))
    if new_stage != row.stage:
        row.stage = new_stage
        row.stage_at = now
    # Oturum (Shopify "Oturumlar") — panel ana sayfası ve dönüşüm oranı
    from app.services import oturum
    oturum.kaydet(
        db, store, ziyaretci=key, yol=body.path, sepet=body.cart_items, now=now,
        ulke=row.country, ref=body.ref, utm=body.utm, tik=body.tik, mobil=body.mobil,
        kendi_host=(request.headers.get("x-vitrin-host") or "").split(":")[0].lower() or None)
    db.commit()
    return {"ok": True}


# ─── Meta piksel beacon'u ────────────────────────────────────
#
# Sepet TARAYICIDA tutulduğu için AddToCart/ViewContent sunucuya hiç
# uğramıyordu ve yalnız facebook.net üzerinden gidiyordu — reklam
# engelleyicilerin ve iOS izleme kısıtının kestiği tam olarak o yol.
# İstek BİZİM alan adımıza geldiğinde kesilmiyor; üstelik sunucu gerçek
# IP ve User-Agent'ı ekleyebiliyor. Tarayıcı aynı olayı aynı event_id ile
# gönderdiği için Meta ikisini tekilleştirir, çift sayım olmaz.

class PikselOlayi(BaseModel):
    olay: str = Field(..., max_length=40)
    event_id: str = Field(..., min_length=6, max_length=100)
    url: str | None = Field(None, max_length=500)
    deger: float | None = Field(None, ge=0, le=1_000_000)
    para: str | None = Field(None, max_length=8)
    icerik: list[str] = Field(default_factory=list, max_length=50)
    adet: int | None = Field(None, ge=1, le=1000)
    fbp: str | None = Field(None, max_length=120)
    fbc: str | None = Field(None, max_length=400)
    eposta: str | None = Field(None, max_length=200)
    vid: str | None = Field(None, max_length=64)   # birinci taraf ziyaretçi kimliği


piksel_rate_limit = make_rate_limiter(max_hits=40, window=60.0)


@router.post("/{store_slug}/piksel")
def piksel_olayi(
    store_slug: str,
    body: PikselOlayi,
    request: Request,
    _rl: None = Depends(piksel_rate_limit),
    db: Session = Depends(get_db),
):
    """Tarayıcıdan gelen olayı sunucu tarafından Meta'ya ilet.

    Uç herkese açık olduğu için sıkı tutulur: olay adı BEYAZ LİSTEDEN,
    tutar ve içerik sayısı sınırlı, IP ve User-Agent GÖVDEDEN DEĞİL
    istekten alınır (istemci kendi IP'sini uyduramasın).
    """
    from app.services import meta_capi

    if body.olay not in meta_capi.BEACON_OLAYLARI:
        return {"ok": False, "sebep": "bilinmeyen olay"}

    store = _resolve_store(db, store_slug)
    ip = (request.headers.get("cf-connecting-ip")
          or (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
          or (request.client.host if request.client else None))

    user_data = {
        "client_ip_address": ip,
        "client_user_agent": request.headers.get("user-agent"),
        "fbp": body.fbp,
        "fbc": body.fbc,
        "em": meta_capi._h(body.eposta) if body.eposta else None,
        "external_id": [x for x in (meta_capi.ziyaretci_kimligi(body.vid),
                                    meta_capi._h(body.eposta) if body.eposta else None) if x] or None,
    }
    custom: dict = {"content_type": "product"}
    if body.olay == "PageView":
        custom = {}
    if body.icerik:
        custom["content_ids"] = [i[:100] for i in body.icerik[:50]]
    if body.deger is not None:
        custom["value"] = body.deger
        custom["currency"] = (body.para or "TRY")[:8]
    if body.adet:
        custom["num_items"] = body.adet

    gonderildi = meta_capi.send_event(
        store, event_name=body.olay, event_id=body.event_id,
        user_data=user_data, custom_data=custom, source_url=body.url)
    return {"ok": gonderildi}


# ─── BERNZ Support — kurallı 7/24 asistan uçları ─────────────
# AI değildir: sistem verisiyle (sipariş, katalog, ayarlar) çalışan kurallı
# yanıtlar. Vitrindeki sohbet balonu bu uçları çağırır.

class SupportOrderStatusIn(BaseModel):
    email: str = Field(..., min_length=5, max_length=200)
    order_no: str | None = Field(None, max_length=40)


def _takip_postasi_gonder(store_id, tenant_id, email: str,
                          siparisler: list[tuple[str, str]]) -> None:
    """Takip bağlantılarını müşterinin KAYITLI adresine yolla (arka planda).

    siparisler: [(görünen_ad, lookup_token), ...]
    """
    if not siparisler:
        return
    from app.database import SessionLocal
    from app.models import Store, Tenant
    from app.services import email_service

    db = SessionLocal()
    try:
        store = db.get(Store, store_id)
        marka = email_service.store_brand_kwargs(store)
        if not marka:
            marka = email_service.brand_kwargs(db.get(Tenant, tenant_id))
        site = site_url((store.config or {}) if store else {})

        satirlar = "".join(
            f'<p style="margin:6px 0"><a href="{site}/siparis/{tok}">{ad}</a></p>'
            for ad, tok in siparisler
        )
        ilk = siparisler[0][1]
        html = email_service.render_email(
            title="Sipariş takip bağlantın",
            body_html=(
                "<p>Sipariş durumunu görmek için aşağıdaki bağlantıyı kullanabilirsin. "
                "Bu bağlantı siparişine özeldir, paylaşma.</p>" + satirlar
            ),
            button_text="Siparişimi gör",
            button_url=f"{site}/siparis/{ilk}",
            preheader="Sipariş takip bağlantın",
            footer="Bu e-postayı sen istemediysen dikkate alma.",
            **marka,
        )
        email_service.send_email(email, "Sipariş takip bağlantın", html)
    except Exception:  # noqa: BLE001
        logging.getLogger("public_shop").warning(
            "[support] takip postası gönderilemedi", exc_info=True)
    finally:
        db.close()


@router.post("/{store_slug}/support/order-status")
def support_order_status(
    store_slug: str,
    body: SupportOrderStatusIn,
    arka: BackgroundTasks,
    request: Request,
    _rl: None = Depends(status_rate_limit),
    db: Session = Depends(get_db),
):
    """Sipariş takip bağlantısını KAYITLI e-posta adresine gönderir.

    ⚠ GÜVENLİK — bu uç eskiden yalnızca e-posta ile son 3 siparişin durumunu
    VE `lookup_token`'ını döndürüyordu. E-posta adresi gizli bir bilgi değil;
    token ise sipariş detayını açıyor ve o sipariş üzerinde iade/değişim
    talebi açmaya yetiyor (`POST /orders/{lookup_token}/request`). Yani bir
    müşterinin adresini bilen herkes siparişlerini okuyup adına talep
    açabiliyordu.

    Ayrıca `order_no` verildiğinde eşleşme yoksa TÜM siparişlere düşülüyordu
    (`matched or orders`) — yanlış numara vermek hiçbir kısıtlama getirmiyordu.

    Şimdi: uç hiçbir sipariş verisi döndürmez, bağlantı e-posta kutusuna
    gider. Adresi BİLMEK değil, ERİŞMEK gerekir. Yanıt kayıt olsun olmasın
    aynıdır ve gönderim arka planda yapılır — yanıt süresi de ayırt etmez.
    """
    from sqlalchemy import func as sql_func

    from app.models import Order

    store = _resolve_store(db, store_slug)
    email = body.email.strip().lower()
    q = select(Order).where(
        Order.store_id == store.id,
        sql_func.lower(Order.customer_email) == email,
    )
    if body.order_no:
        # Numara VERİLDİYSE eşleşme şart — eşleşmiyorsa hiçbir şey gönderme.
        # Süzme SORGUDA: eskiden son 3 sipariş alınıp sonra süzülüyordu,
        # 4. ve daha eski bir sipariş numarasıyla sorgu hiç bulamıyordu.
        num = body.order_no.strip().lstrip("#")
        q = q.where(or_(Order.order_number == num, Order.name == f"#{num}"))
    orders = db.scalars(
        q.order_by(Order.created_at_platform.desc().nulls_last()).limit(3)).all()

    sessions = db.execute(
        select(CheckoutSession.order_id, CheckoutSession.lookup_token).where(
            CheckoutSession.order_id.in_([o.id for o in orders] or [uuid.uuid4()]))
    ).all()
    token_map = {r[0]: r[1] for r in sessions}

    baglantilar = [
        (o.name or (f"#{o.order_number}" if o.order_number else "Siparişin"),
         token_map[o.id])
        for o in orders if token_map.get(o.id)
    ]
    arka.add_task(_takip_postasi_gonder, store.id, store.tenant_id, email, baglantilar)

    # Kayıt olsun olmasın AYNI yanıt — hesap sayımı (enumeration) yapılamaz.
    return {"sent": True,
            "mesaj": "Sipariş takip bağlantısını e-posta adresine gönderdim. "
                     "Gelen kutunu (ve spam klasörünü) kontrol et."}


# "s24 plus var mı" gibi cümlelerde modele ait olmayan dolgu kelimeleri
_MODEL_STOPWORDS = {
    "var", "mı", "mi", "mu", "mü", "midir", "kılıf", "kilif", "kılıfı", "kilifi",
    "case", "uyumlu", "için", "icin", "telefon", "telefonum", "telefonuma",
    "model", "modeli", "acaba", "merhaba", "selam", "ve", "ile", "bir",
}


# Müşterinin kullandığı marka adı ile katalogdaki marka/model adı çoğu zaman
# tutmuyor ("samsung s24" ↔ "Galaxy S24"). Marka başına eş anlamlı token'lar.
_MARKA_ESANLAM: dict[str, list[str]] = {
    "samsung": ["galaxy", "samsung"],
    "apple": ["iphone", "apple"],
    "xiaomi": ["xiaomi", "mi", "redmi", "poco"],
    "huawei": ["huawei", "nova", "mate"],
    "honor": ["honor"],
    "oppo": ["oppo", "reno"],
    "vivo": ["vivo"],
    "realme": ["realme"],
    "tecno": ["tecno"],
    "infinix": ["infinix"],
    "reeder": ["reeder"],
    "general mobile": ["general", "mobile", "gm"],
    "google": ["google", "pixel"],
    "oneplus": ["oneplus"],
}


def _norm_model(s: str) -> list[str]:
    """Model adını karşılaştırma token'larına indirger: küçük harf,
    +→plus, noktalama temizliği ('S24+' ile 's24 plus' eşleşir)."""
    s = s.lower().replace("+", " plus ")
    s = "".join(ch if ch.isalnum() else " " for ch in s)
    return [t for t in s.split() if t and t not in _MODEL_STOPWORDS]


def _model_tokenlari(model_display: str, marka: str | None) -> list[str]:
    """Bir modelin eşleşebileceği tüm token'lar: model adı + marka + markanın
    eş anlamlıları. Marka alanı boş olsa da model adından çıkarılır
    ('Galaxy S24' → samsung), böylece 'samsung s24 plus' da bulur."""
    tokenlar = _norm_model(model_display) + _norm_model(marka or "")
    genis = list(tokenlar)
    for anahtar, esler in _MARKA_ESANLAM.items():
        if anahtar in tokenlar or any(e in tokenlar for e in esler):
            genis += esler
    return genis


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
    # MODEL BAŞINA tek satır: sayım ve örnek ürün veritabanında hesaplanır.
    # (Eskiden mağazadaki tüm varyant satırları Python'a çekiliyordu —
    # on binlerce satırda destek botu saniyelerce bekletiyordu.)
    rows = db.execute(
        select(
            CatalogVariant.model_display,
            func.min(CatalogVariant.brand).label("brand"),
            func.count(func.distinct(CatalogProduct.id)).label("urun_sayisi"),
            func.min(CatalogProduct.title).label("ornek_baslik"),
            func.min(CatalogProduct.slug).label("ornek_slug"),
        )
        .join(CatalogProduct, CatalogVariant.product_id == CatalogProduct.id)
        .where(
            CatalogProduct.store_id == store.id,
            CatalogProduct.status == "active",
            CatalogVariant.is_active.is_(True),
            # Sorgunun en uzun kelimesi model veya marka adında geçmeli —
            # token kontrolüne kalan aday sayısını SQL'de daraltır
            or_(
                CatalogVariant.model_display.ilike(f"%{max(q_tokens, key=len)}%"),
                CatalogVariant.brand.ilike(f"%{max(q_tokens, key=len)}%"),
            ),
        )
        .group_by(CatalogVariant.model_display)
    ).all()

    bulunan: list[dict] = []
    for model_display, marka, urun_sayisi, ornek_baslik, ornek_slug in rows:
        # Eşleşme havuzuna MARKA da girer: müşteri "samsung s24 plus" yazınca
        # model adı "Galaxy S24 Plus" olsa da bulunur (marka Samsung).
        m_tokens = _model_tokenlari(model_display, marka)
        if not all(t in m_tokens for t in q_tokens):
            continue
        bulunan.append({
            "model": model_display,
            "product_count": urun_sayisi,      # VARYANT değil, benzersiz ürün
            "sample_title": ornek_baslik,
            "sample_slug": ornek_slug,
            # Az token farkı = daha isabetli eşleşme, üste gelsin
            "_extra": len(_norm_model(model_display)) - len(q_tokens),
        })
    ranked = sorted(bulunan, key=lambda m: m["_extra"])[:10]
    for m in ranked:
        m.pop("_extra", None)
    return {"models": ranked}


# ═════════════════════════════════════════════════════════════
# TASARIM STÜDYOSU (vitrin) — müşteri kendi kılıfını tasarlar
# ═════════════════════════════════════════════════════════════
# Şablon listesi herkese açık (tasarlamaya başlamak için hesap gerekmez);
# KAYDETMEK için hesap gerekir — böylece müşteri kaldığı yerden devam eder.

@router.get("/{store_slug}/studio/overlays")
def studio_overlays(store_slug: str, response: Response,
                    urun: str | None = Query(None, max_length=200),
                    db: Session = Depends(get_db)):
    """Hazır tasarım modülleri — müşterinin tasarımına eklenen şablonlar.

    Görünürlük iki kademeli:
      • MODÜL (sadece_urunde=True): yalnız ürün detayında kendisine atanan
        ürünlerin stüdyosunda çıkar. Spotify arayüzü gibi ürüne özel
        tasarımlar her ürünün listesini şişirmesin diye.
      • GENEL şablon (sadece_urunde=False): her üründe görünür.
    Ayrıca case_template_id doluysa yalnız o kılıf tipinde listelenir.
    """
    from app.models import CaseTemplate, CatalogProduct, DesignOverlay

    store = _resolve_store(db, store_slug)
    # Ürün verildiyse o ürüne atanmış modüllerin kimlikleri
    urun_modulleri: set[str] = set()
    if urun:
        p = db.scalar(select(CatalogProduct).where(
            CatalogProduct.store_id == store.id, CatalogProduct.slug == urun))
        if p:
            urun_modulleri = {str(x) for x in (p.studio_overlays or [])}
    rows = db.execute(
        select(DesignOverlay, CaseTemplate.key)
        .join(CaseTemplate, DesignOverlay.case_template_id == CaseTemplate.id,
              isouter=True)
        .where(DesignOverlay.store_id == store.id,
               DesignOverlay.is_active.is_(True))
        .order_by(DesignOverlay.position, DesignOverlay.created_at)
    ).all()
    response.headers["Cache-Control"] = "public, max-age=120"
    from app.services import kisitli_sablon

    return [
        {
            "id": str(o.id),
            "label": o.label,
            "template_key": key,          # null → tüm kılıflarda geçerli
            "image_url": f"/storage/{o.image_path}",
            "thumb_url": f"/storage/{o.thumb_path or o.image_path}",
            # "kisitli" ise editör form moduna geçer: müşteri yalnız bu
            # alanları doldurur, serbest görsel/yazı ekleyemez.
            "mod": o.mod,
            "kategori": o.kategori or "Diğer",
            "alanlar": kisitli_sablon.alan_ozeti(o) if o.mod == "kisitli" else [],
        }
        for o, key in rows
        # Ürüne özel modül: yalnız atandığı üründe. Genel şablon: her üründe.
        if (str(o.id) in urun_modulleri) or not o.sadece_urunde
    ]


@router.get("/{store_slug}/studio/templates")
def studio_templates(store_slug: str, response: Response, db: Session = Depends(get_db)):
    """Boş kılıf seçenekleri + baskı alanı (editörün zemini)."""
    from app.models import CaseTemplate

    store = _resolve_store(db, store_slug)
    rows = db.scalars(select(CaseTemplate).where(
        CaseTemplate.store_id == store.id,
        CaseTemplate.is_active.is_(True),
        CaseTemplate.image_path.isnot(None),
    ).order_by(CaseTemplate.position, CaseTemplate.created_at)).all()
    response.headers["Cache-Control"] = "public, max-age=120"
    return [
        {
            "key": t.key,
            "label": t.label,
            "description": t.description,
            "image_url": f"/storage/{t.image_path}",
            "area": {"x": float(t.area_x), "y": float(t.area_y),
                     "w": float(t.area_w), "h": float(t.area_h),
                     "radius": float(t.area_radius or 0)},
            # Basılamayan bölgeler — editör bunların üstünü maskeler
            "cutouts": t.cutouts or [],
            "print": {"width_mm": t.print_width_mm, "height_mm": t.print_height_mm,
                      "dpi": t.print_dpi},
        }
        for t in rows
    ]


design_upload_rate_limit = make_rate_limiter(max_hits=30, window=300.0)
MAX_DESIGN_LAYERS = 40


def _ser_design(d, store) -> dict:
    return {
        "id": str(d.id),
        "name": d.name,
        "template_key": d.template_key,
        "variant_id": str(d.variant_id) if d.variant_id else None,
        "layers": d.layers or [],
        "preview_url": f"/storage/{d.preview_path}" if d.preview_path else None,
        "status": d.status,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
    }


@router.get("/account/designs")
def list_designs(request: Request, db: Session = Depends(get_db)):
    """Müşterinin kayıtlı tasarımları — en son düzenlenen üstte."""
    from app.models import CustomerDesign

    customer, store = _get_customer_from_token(request, db)
    rows = db.scalars(select(CustomerDesign).where(
        CustomerDesign.customer_id == customer.id,
        CustomerDesign.store_id == store.id,
    ).order_by(CustomerDesign.updated_at.desc()).limit(60)).all()
    return [_ser_design(d, store) for d in rows]


class DesignSave(BaseModel):
    id: uuid.UUID | None = None
    name: str = Field("Tasarımım", max_length=120)
    template_key: str | None = Field(None, max_length=40)
    variant_id: uuid.UUID | None = None
    layers: list[dict] = Field(default_factory=list, max_length=MAX_DESIGN_LAYERS)
    status: str = Field("draft", pattern="^(draft|ready)$")
    # Kısıtlı şablon kullanılıyorsa: hangi şablon + müşterinin girdiği alan
    # değerleri. Katmanlar bunlardan SUNUCUDA üretilir; gövdedeki layers yok
    # sayılır — böylece müşteri şablonun dışına çıkan bir şey bastıramaz.
    overlay_id: uuid.UUID | None = None
    alan_degerleri: dict[str, str | bool | None] | None = None
    # Tuvalden alınan küçük önizleme (data URL) — liste ve panelde gösterilir
    preview_data_url: str | None = Field(None, max_length=4_000_000)


@router.post("/account/designs")
def save_design(request: Request, body: DesignSave, db: Session = Depends(get_db)):
    """Tasarımı kaydet/güncelle. id verilirse günceller (otomatik kayıt bunu kullanır).

    Katman sayısı ve gövde boyutu sınırlıdır; tuval içeriği sunucuda saklanır
    ki müşteri başka cihazdan girince de kaldığı yerden devam etsin.
    """
    from app.models import CustomerDesign

    customer, store = _get_customer_from_token(request, db)

    if body.id:
        design = db.scalar(select(CustomerDesign).where(
            CustomerDesign.id == body.id,
            CustomerDesign.customer_id == customer.id,   # başkasının tasarımı düzenlenemez
            CustomerDesign.store_id == store.id,
        ))
        if not design:
            raise HTTPException(404, "Tasarım bulunamadı")
        if design.status == "ordered":
            raise HTTPException(422, "Sipariş edilmiş tasarım değiştirilemez — kopyasını oluşturun")
    else:
        adet = db.scalar(select(func.count()).select_from(CustomerDesign).where(
            CustomerDesign.customer_id == customer.id,
            CustomerDesign.store_id == store.id)) or 0
        if adet >= 60:
            raise HTTPException(422, "En fazla 60 tasarım saklanabilir — eskilerini silin")
        design = CustomerDesign(tenant_id=store.tenant_id, store_id=store.id,
                                customer_id=customer.id)
        db.add(design)

    design.name = (body.name or "Tasarımım").strip()[:120]
    design.template_key = body.template_key
    design.variant_id = body.variant_id
    design.status = body.status

    if body.overlay_id:
        # KISITLI ŞABLON — katmanları şablon tanımından biz üretiriz
        from app.models import DesignOverlay
        from app.services import kisitli_sablon

        ov = db.scalar(select(DesignOverlay).where(
            DesignOverlay.id == body.overlay_id,
            DesignOverlay.store_id == store.id,
            DesignOverlay.is_active.is_(True),
        ))
        if not ov:
            raise HTTPException(404, "Şablon bulunamadı")
        if ov.mod != "kisitli":
            raise HTTPException(422, "Bu şablon serbest modda — alan değeri gönderilemez")
        # Baskı alanının en/boy oranı — müşteri fotoğrafının çerçeveye
        # oranı bozmadan oturması (kapla) bu orana göre hesaplanır
        from app.models import CaseTemplate as _CT
        _tpl = db.scalar(select(_CT).where(
            _CT.store_id == store.id, _CT.key == body.template_key))
        _oran = 1.0
        if _tpl and _tpl.area_h:
            _oran = (float(_tpl.area_w) * _tpl.print_width_mm) / (
                float(_tpl.area_h) * _tpl.print_height_mm)
        design.layers = kisitli_sablon.layers_uret(
            ov, body.alan_degerleri, db=db, alan_oran=_oran)
    else:
        design.layers = body.layers

    if body.preview_data_url and body.preview_data_url.startswith("data:image/"):
        try:
            import base64
            b64 = body.preview_data_url.split(",", 1)[1]
            ham = base64.b64decode(b64)
            if len(ham) <= 3 * 1024 * 1024:
                db.flush()   # design.id gerekli
                design.preview_path = storage_svc.save_design_render(
                    store.tenant_id, store.id, design.id, ham, "onizleme"
                ).removeprefix("/storage/")
        except Exception:  # noqa: BLE001 — önizleme kaydı tasarımı bloklamaz
            pass

    db.commit()
    db.refresh(design)
    return _ser_design(design, store)


@router.delete("/account/designs/{design_id}", status_code=204)
def delete_design(design_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    from app.models import CustomerDesign

    customer, store = _get_customer_from_token(request, db)
    design = db.scalar(select(CustomerDesign).where(
        CustomerDesign.id == design_id,
        CustomerDesign.customer_id == customer.id,
        CustomerDesign.store_id == store.id,
    ))
    if not design:
        raise HTTPException(404, "Tasarım bulunamadı")
    if design.status == "ordered":
        raise HTTPException(422, "Sipariş edilmiş tasarım silinemez")
    db.delete(design)
    db.commit()


@router.post("/{store_slug}/studio/assets")
async def upload_design_asset(
    store_slug: str,
    request: Request,
    _rl: None = Depends(design_upload_rate_limit),
    db: Session = Depends(get_db),
):
    """Stüdyoya görsel yükle. ORİJİNAL saklanır (baskı bundan üretilecek),
    tuvale hafif önizleme döner."""
    from app.models import DesignAsset

    store = _resolve_store(db, store_slug)
    # Girişliyse varlık müşteriye bağlanır (hesabında kalır); değilse serbest
    musteri = None
    try:
        musteri, _ = _get_customer_from_token(request, db)
    except HTTPException:
        pass

    form = await request.form()
    file = form.get("file")
    if file is None or not hasattr(file, "read"):
        raise HTTPException(422, "Dosya gerekli")
    data = await file.read()
    try:
        orijinal, onizleme, gen, yuk = await run_in_threadpool(
            storage_svc.save_design_original,
            store.tenant_id, store.id, data,
            getattr(file, "filename", None) or "tasarim.png")
    except ValueError as e:
        raise HTTPException(422, str(e))

    asset = DesignAsset(
        tenant_id=store.tenant_id, store_id=store.id,
        customer_id=musteri.id if musteri else None,
        original_path=orijinal.removeprefix("/storage/"),
        preview_path=onizleme.removeprefix("/storage/"),
        width=gen, height=yuk, bytes_size=len(data),
        filename=(getattr(file, "filename", None) or "")[:300] or None,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return {
        "asset_id": str(asset.id),
        "preview_url": onizleme,   # tuvalde bu kullanılır
        "width": gen, "height": yuk,
        # Baskı kalitesi uyarısı: 300 DPI'da kaç cm'e kadar net basılır
        "print_cm": round(min(gen, yuk) / 300 * 2.54, 1),
    }
