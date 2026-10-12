"""Vitrin (katalog) ürünü -> baskı tasarımı bağı. TEK KAYNAK.

NEDEN AYRI BİR BAĞ VAR
----------------------
Shopify mağazalarında bağ kendiliğinden kurulur: ``line_items.product_id`` da
``Design.product_id`` de aynı Shopify sayısal kimliğidir.

Vitrin (platform='storefront') siparişlerinde ``line_items.product_id`` bizim
``catalog_products.id`` UUID'imizdir. Yani Shopify kimliğiyle ASLA eşleşmez;
kalıp planlayıcı da bu yüzden "ürün tasarıma bağlanmamış" diyordu. Bağ bu
yüzden açıkça ``catalog_products.design_id`` sütununda tutulur.

Tasarımın kendisi BAŞKA bir mağazaya ait olabilir (ortak tasarım havuzu,
bkz. services/tasarim_kapsam.py) — BERNZ COMPANY'nin Shopify tasarımı BERNZ
vitrininde kullanılır, bu normaldir.
"""
from __future__ import annotations

import re
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CatalogProduct, Design, Store
from . import tasarim_kapsam

# Başlıkları karşılaştırırken kılık değiştiren karakterler
_ESLER = (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'), ("–", "-"), ("—", "-"))


def normalize(s: str | None) -> str:
    """Başlığı karşılaştırılabilir hale getirir (tırnak/çizgi/boşluk/büyük-küçük)."""
    s = s or ""
    for a, b in _ESLER:
        s = s.replace(a, b)
    s = re.sub(r"[\"']", "", s)
    return " ".join(s.split()).casefold()


def bag_haritasi(
    db: Session, tenant_id: uuid.UUID, store_id: uuid.UUID | None = None
) -> dict[tuple, Design]:
    """(store_id, product_id metni) -> Design. Kalıp planlayıcı toplu okur."""
    q = (
        select(CatalogProduct.store_id, CatalogProduct.id, Design)
        .join(Design, Design.id == CatalogProduct.design_id)
        .join(Store, Store.id == CatalogProduct.store_id)
        .where(Store.tenant_id == tenant_id)
    )
    if store_id:
        q = q.where(CatalogProduct.store_id == store_id)
    return {(s_id, str(p_id)): d for (s_id, p_id, d) in db.execute(q).all()}


def tasarim_bul(db: Session, store_id: uuid.UUID, product_id) -> Design | None:
    """Tek ürün için bağlı tasarım. product_id UUID değilse (Shopify) None."""
    if not product_id:
        return None
    try:
        pid = uuid.UUID(str(product_id))
    except (ValueError, AttributeError, TypeError):
        return None  # Shopify sayısal kimliği — bu bağ onun için değil
    urun = db.get(CatalogProduct, pid)
    if urun is None or urun.store_id != store_id or not urun.design_id:
        return None
    return db.get(Design, urun.design_id)


def _tasarim_havuzu(db: Session, store_id: uuid.UUID) -> dict[str, list[Design]]:
    """Normalize başlık -> tasarımlar. Hem product_title hem name taranır:
    göçle gelen tasarımların bir kısmında tam ürün başlığı name alanındadır."""
    havuz: dict[str, list[Design]] = {}
    for d in db.scalars(select(Design).where(tasarim_kapsam.kosul(db, store_id))).all():
        for alan in (d.product_title, d.name):
            k = normalize(alan)
            if len(k) > 15:  # "siyah" gibi kısa adlar yanlış eşleşir
                havuz.setdefault(k, []).append(d)
    return havuz


def oneri(db: Session, urun: CatalogProduct) -> Design | None:
    """Ürün başlığıyla BİREBİR eşleşen tek tasarım. Birden fazlaysa None
    (yanlış tasarımla üretim yapmaktansa elle seçilsin)."""
    adaylar = _tasarim_havuzu(db, urun.store_id).get(normalize(urun.title), [])
    benzersiz = {d.id: d for d in adaylar}
    return next(iter(benzersiz.values())) if len(benzersiz) == 1 else None


def toplu_eslestir(
    db: Session, store_id: uuid.UUID, *, uygula: bool = False, uzerine_yaz: bool = False
) -> dict:
    """Başlığı birebir eşleşen ürünleri tasarımına bağlar.

    uygula=False  : yalnız rapor (kuru çalışma) — hiçbir şey yazılmaz.
    uzerine_yaz=False: zaten bağlı ürüne dokunulmaz (elle verilen karar korunur).
    """
    havuz = _tasarim_havuzu(db, store_id)
    urunler = db.scalars(
        select(CatalogProduct).where(CatalogProduct.store_id == store_id)
    ).all()

    rapor = {"toplam": len(urunler), "baglandi": 0, "zaten_bagli": 0,
             "belirsiz": 0, "eslesmeyen": 0, "ornekler": [], "belirsizler": []}
    for u in urunler:
        if u.design_id and not uzerine_yaz:
            rapor["zaten_bagli"] += 1
            continue
        benzersiz = {d.id: d for d in havuz.get(normalize(u.title), [])}
        if len(benzersiz) == 1:
            d = next(iter(benzersiz.values()))
            if uygula:
                u.design_id = d.id
            rapor["baglandi"] += 1
            if len(rapor["ornekler"]) < 10:
                rapor["ornekler"].append({"urun": u.title, "tasarim": d.code})
        elif len(benzersiz) > 1:
            rapor["belirsiz"] += 1
            if len(rapor["belirsizler"]) < 20:
                rapor["belirsizler"].append({
                    "urun": u.title,
                    "tasarimlar": [d.code for d in benzersiz.values()],
                })
        else:
            rapor["eslesmeyen"] += 1
    if uygula:
        db.commit()
    return rapor
