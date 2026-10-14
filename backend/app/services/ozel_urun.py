"""Tasarım talebine ÖZEL ürün — yalnız linki bilen görür.

Müşteri hesabından tasarım talebi açar; mağaza tasarımı hazırlayıp panelden
yükler, fiyatı yazar. Burada:
  • baskı dosyası bir Tasarım (Design) kaydı olur → kalıp planlayıcı siparişte
    baskı dosyasını bulur (catalog_products.design_id, bkz. katalog_tasarim)
  • ürün status='ozel' doğar: vitrin listeleri, arama, koleksiyonlar, site
    haritası ve reklam katalogları YALNIZ 'active' ürünleri alır → hiçbir yerde
    çıkmaz; ürün sayfası, sepet ve ödeme ise 'ozel'i de kabul eder
  • adres tahmin edilemez (ozel-<10 onaltılık>); link defalarca kullanılabilir
  • model seçimi mağazanın varyant setinden; kargo/ücretsiz kargo/kampanya
    sepetteki her ürün gibi işler (ayrı kural yok)
  • ürün fotoğrafı: verilmediyse tasarım kılıf görseline giydirilir
"""
from __future__ import annotations

import io
import secrets
import uuid

from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    CaseTemplate, CatalogImage, CatalogProduct, Customer, Design, DesignRequest, Store, VariantSet,
)
from app.services import storage as storage_svc

OZEL = "ozel"
# Vitrinin ürün sayfası/sepet/ödeme bu durumları satılabilir sayar
SATILABILIR = ("active", OZEL)


def varsayilan_set(db: Session, store_id) -> VariantSet | None:
    """En çok üründe kullanılan model seti (kılıf ürünlerinin standardı)."""
    sayim = (select(CatalogProduct.variant_set_id, func.count().label("n"))
             .where(CatalogProduct.store_id == store_id, CatalogProduct.variant_set_id.isnot(None))
             .group_by(CatalogProduct.variant_set_id).order_by(func.count().desc()).limit(1))
    satir = db.execute(sayim).first()
    if satir:
        return db.get(VariantSet, satir[0])
    return db.scalar(select(VariantSet).where(VariantSet.store_id == store_id)
                     .order_by(VariantSet.created_at))


def raster(veri: bytes, ad: str) -> Image.Image | None:
    """Baskı dosyasının görüntüsü (PNG/JPG; PDF ise ilk sayfa). SVG → None."""
    uzanti = storage_svc.get_extension(ad)
    try:
        if uzanti == "pdf":
            import pymupdf
            sayfa = pymupdf.open("pdf", veri)[0]
            pix = sayfa.get_pixmap(dpi=150, alpha=True)
            return Image.frombytes("RGBA" if pix.alpha else "RGB", (pix.width, pix.height), pix.samples)
        if uzanti in ("png", "jpg", "jpeg", "webp"):
            g = Image.open(io.BytesIO(veri))
            g.load()
            return g
    except Exception:  # noqa: BLE001 — görüntü çıkarılamazsa ürün yine kurulur
        return None
    return None


def _jpeg(g: Image.Image, uzun_kenar: int = 1600) -> bytes:
    g = g.convert("RGBA")
    o = min(1.0, uzun_kenar / max(g.size))
    if o < 1:
        g = g.resize((round(g.width * o), round(g.height * o)), Image.LANCZOS)
    zemin = Image.new("RGB", g.size, (255, 255, 255))
    zemin.paste(g, (0, 0), g)
    buf = io.BytesIO()
    zemin.save(buf, "JPEG", quality=90)
    return buf.getvalue()


def _gorsel_ekle(db: Session, urun: CatalogProduct, veri: bytes, ad: str, sira: int) -> None:
    image_id = uuid.uuid4()
    rel = storage_svc.save_catalog_image(urun.tenant_id, image_id, veri, ad)
    db.add(CatalogImage(id=image_id, tenant_id=urun.tenant_id, product_id=urun.id,
                        file_path=rel, alt=(urun.title or "")[:200] or None, position=sira))


def _gorselleri_sil(db: Session, urun: CatalogProduct) -> None:
    for im in db.scalars(select(CatalogImage).where(CatalogImage.product_id == urun.id)).all():
        storage_svc.delete_catalog_image(im.file_path)
        db.delete(im)


def _tasarim_kaydet(db: Session, store: Store, r: DesignRequest, veri: bytes, ad: str,
                    mevcut: Design | None) -> Design:
    if not storage_svc.is_allowed_extension(ad or ""):
        raise ValueError(f"Baskı dosyası biçimi: {', '.join(sorted(storage_svc.ALLOWED_EXTENSIONS))}")
    if len(veri) > storage_svc.MAX_FILE_SIZE:
        raise ValueError("Baskı dosyası çok büyük")
    d = mevcut
    if d is None:
        d = Design(tenant_id=store.tenant_id, store_id=store.id,
                   code=f"OZEL-{secrets.token_hex(3).upper()}",
                   name=f"Tasarım talebi — {r.customer_name or r.customer_email}"[:200],
                   is_kisiye_ozel=True, file_path="", file_format="", file_size_bytes=0,
                   notes=f"Tasarım talebi {r.id}")
        db.add(d)
        db.flush()
    eski = d.file_path
    bilgi = storage_svc.save_design_file(tenant_id=store.tenant_id, design_id=d.id,
                                         file_data=veri, original_filename=ad, skip_thumbnail=True)
    d.file_path, d.file_format, d.file_size_bytes = bilgi["relative_path"], bilgi["format"], bilgi["size"]
    if eski and eski != d.file_path:
        storage_svc.delete_design_file(eski)
    return d


def urun_kur(db: Session, store: Store, r: DesignRequest, *, fiyat: float, baslik: str | None,
             baski: tuple[bytes, str] | None, gorseller: list[tuple[bytes, str]] | None,
             variant_set_id=None, template_id=None) -> CatalogProduct:
    """Talebin özel ürününü kur ya da güncelle.

    Ürünün görselleri = mağazanın YÜKLEDİĞİ görseller (sırasıyla, ilki kapak).
    Görsel yüklenmezse: yeni üründe baskı dosyası kılıfa giydirilip görsel
    yapılır; güncellemede mevcut görseller aynen kalır. Baskı dosyası isteğe
    bağlıdır (üretim dosyası; siparişte kalıp planlayıcı bunu kullanır)."""
    from app.routers.catalog import sync_set_to_product

    urun = db.get(CatalogProduct, r.product_id) if r.product_id else None
    gorseller = [g for g in (gorseller or []) if g and g[0]][:8]
    if urun is None and baski is None and not gorseller:
        raise ValueError("Ürün görselini yükleyin")
    for veri, ad in gorseller:
        if storage_svc.get_extension(ad) not in storage_svc.CATALOG_IMAGE_EXTENSIONS:
            raise ValueError(f"“{ad}” görsel değil — JPG, PNG veya WEBP yükleyin")
    ad = (r.customer_name or "").strip().split(" ")[0]
    baslik = (baslik or "").strip() or (f"Özel Tasarım Kılıf — {ad}" if ad else "Özel Tasarım Kılıf")

    if urun is None:
        vs = (db.scalar(select(VariantSet).where(VariantSet.id == variant_set_id,
                                                 VariantSet.store_id == store.id))
              if variant_set_id else None) or varsayilan_set(db, store.id)
        if vs is None:
            raise ValueError("Mağazada model seti yok — Ürünler › Varyant setleri'nden bir set oluşturun")
        urun = CatalogProduct(
            tenant_id=store.tenant_id, store_id=store.id,
            slug=f"ozel-{secrets.token_hex(5)}", title=baslik[:300], status=OZEL,
            description="Bu ürün size özel hazırlandı. Telefon modelinizi seçip sepete ekleyebilirsiniz.",
            base_price=fiyat, variant_set_id=vs.id,
            tags="ozel-tasarim",
        )
        db.add(urun)
        db.flush()
        urun.variants = []
        sync_set_to_product(db, urun, vs.items or [])
        r.product_id = urun.id
    else:
        urun.title = baslik[:300]
        urun.base_price = fiyat
        if urun.status not in SATILABILIR:      # elle arşivlenmişse yeniden açılır
            urun.status = OZEL

    if baski is not None:
        mevcut = db.get(Design, urun.design_id) if urun.design_id else None
        d = _tasarim_kaydet(db, store, r, baski[0], baski[1], mevcut)
        urun.design_id = d.id
        d.product_title = urun.title

    yeni_urun = not db.scalar(select(func.count()).select_from(CatalogImage)
                              .where(CatalogImage.product_id == urun.id))
    if gorseller:
        # Mağazanın yüklediği görseller ürünün görselleri olur (ilki kapak)
        _gorselleri_sil(db, urun)
        for sira, (veri, ad) in enumerate(gorseller):
            _gorsel_ekle(db, urun, veri, ad, sira)
    elif baski is not None and yeni_urun:
        # Görsel yüklenmedi: baskı dosyasından ürün görseli üret
        duz = raster(*baski)
        if duz is not None:
            sira = 0
            from app.services import kapak_gorseli
            tpl = _kilif(db, store, template_id)
            if tpl is not None:
                try:
                    _gorsel_ekle(db, urun, kapak_gorseli.kare_kapak(
                        kapak_gorseli.gorsel_giydir(tpl, duz)), "kapak.jpg", sira)
                    sira += 1
                except ValueError:
                    pass
            _gorsel_ekle(db, urun, _jpeg(duz), "tasarim.jpg", sira)
    r.status = "teklif" if r.status in ("acik", "incelendi") else r.status
    return urun


def _kilif(db: Session, store: Store, template_id) -> CaseTemplate | None:
    q = select(CaseTemplate).where(CaseTemplate.store_id == store.id,
                                   CaseTemplate.image_path.isnot(None))
    if template_id:
        t = db.scalar(q.where(CaseTemplate.id == template_id))
        if t:
            return t
    return db.scalar(q.where(CaseTemplate.is_active.is_(True))
                     .order_by(CaseTemplate.position, CaseTemplate.created_at))


def urun_ozeti(db: Session, store: Store, r: DesignRequest) -> dict | None:
    if not r.product_id:
        return None
    u = db.get(CatalogProduct, r.product_id)
    if not u:
        return None
    from app.services.site import site_url
    site = site_url(store)
    gorseller = sorted(u.images, key=lambda im: im.position)
    kapak = gorseller[0] if gorseller else None
    return {"id": str(u.id), "slug": u.slug, "title": u.title, "status": u.status,
            "price": float(u.base_price or 0),
            "url": f"{site}/urun/{u.slug}" if site else f"/urun/{u.slug}",
            "image_url": f"/storage/{kapak.file_path}" if kapak else None,
            "gorseller": [f"/storage/{im.file_path}" for im in gorseller],
            "baski_var": bool(u.design_id),
            "satista": u.status in SATILABILIR}


def musteri_telefonu(db: Session, store: Store, r: DesignRequest) -> str | None:
    c = db.scalar(select(Customer).where(Customer.tenant_id == store.tenant_id,
                                         Customer.email == r.customer_email))
    return (c.phone or None) if c else None


def fiyat_metni(tutar: float) -> str:
    s = f"{tutar:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return (s[:-3] if s.endswith(",00") else s) + " TL"


def whatsapp_metni(store: Store, r: DesignRequest, ozet: dict | None) -> str:
    ad = (r.customer_name or "").strip().split(" ")[0]
    satirlar = [f"Merhaba{' ' + ad if ad else ''}, {store.name} olarak tasarım talebinize dönüş yapıyoruz."]
    if ozet and ozet.get("satista"):
        satirlar.append(f"Size özel ürününüz hazır: {ozet['title']} — {fiyat_metni(ozet['price'])}")
        satirlar.append("Telefon modelinizi seçip sepete ekleyerek siparişinizi verebilirsiniz:")
        satirlar.append(ozet["url"])
    if r.admin_note:
        satirlar.append(r.admin_note)
    return "\n".join(satirlar)
