"""Ürün kimliğinin GERÇEKTEN o mağazaya ait olduğunu doğrular. TEK KAYNAK.

NEDEN VAR (2026-10-13'te yandı)
-------------------------------
Aksesuar / couple / kişiye özel işaretleme ekranları ürün listesini
``/api/designs/_meta/products`` ucundan çeker. Shopify listesi dış API'den
saniyeler içinde gelir, vitrin listesi veritabanından anında. Kullanıcı mağaza
değiştirdiğinde geciken Shopify yanıtı yeni listenin üstüne biniyor; ekranda
Shopify ürünleri, seçili mağaza ise VİTRİN oluyordu. Tıklanan her satır
**Shopify kimliğini vitrin mağazasına** yazdı: kayıt "işaretli" görünüyor ama
hiçbir vitrin ürünüyle eşleşmiyor, dolayısıyla hiçbir işe yaramıyor
(aksesuar işaretlenen boş kılıf kalıp planında "tasarım eksik" demeye devam
etti). Arayüzdeki yarış düzeltildi; burası emniyet kemeri.

Vitrin (storefront) mağazasında ürün kimliği catalog_products.id UUID'sidir;
başka bir şey yazılıyorsa istek baştan yanlıştır ve reddedilir. Dış platform
mağazalarında kimlik doğrulanamaz (ürün listesi uzakta), oradaki istek
olduğu gibi kabul edilir.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import CatalogProduct, Store


def magazaya_ait_mi(db: Session, store: Store, product_id) -> bool:
    """Vitrin mağazasında kimlik o mağazanın ürünü mü? Diğer platformlarda True."""
    if (store.platform or "").lower() != "storefront":
        return True
    try:
        pid = uuid.UUID(str(product_id).strip())
    except (ValueError, AttributeError, TypeError):
        return False
    return db.scalar(
        select(CatalogProduct.id).where(
            CatalogProduct.id == pid, CatalogProduct.store_id == store.id
        )
    ) is not None


def dogrula(db: Session, store: Store, product_id) -> None:
    """Ait değilse 400 — yanlış mağazaya yazılmış işe yaramaz kayıt oluşmasın."""
    from fastapi import HTTPException

    if not magazaya_ait_mi(db, store, product_id):
        raise HTTPException(
            400,
            "Bu ürün seçili mağazaya ait değil. Mağazayı değiştirdikten sonra "
            "ürün listesinin yenilenmesini bekleyip tekrar deneyin.",
        )
