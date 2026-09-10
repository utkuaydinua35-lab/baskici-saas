"""Müşteriye gösterilecek sipariş özeti — kalemler, modeller, durumlar.

TEK KAYNAK: aynı özet hem model değişikliği sayfasında hem eksik stok
e-postasında kullanılıyor. İkisi ayrı yazılırsa müşteri aynı siparişi iki
yerde FARKLI görür ve hangisinin doğru olduğunu bilemez.

Durum adları PANEL TERİMİ DEĞİL: müşteri "kalıba eklendi" ya da "is_hazir"
gibi iç kavramları bilmiyor.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CatalogImage, CatalogProduct, LineItem, Order


def kalem_durumu(li: LineItem) -> str:
    """Müşteriye gösterilecek kalem durumu."""
    if li.is_hazir:
        return "Hazır"
    if (li.raw or {}).get("stok_bekliyor"):
        return "Stok bekleniyor"
    if li.is_kaliba_eklendi:
        return "Üretimde"
    return "Hazırlanıyor"


def kalemler(db: Session, order: Order, *, gorsel: bool = False,
             vurgu: str | None = None) -> list[dict]:
    """Siparişin kalemleri: ürün adı, telefon modeli, durum (+isteğe bağlı görsel).

    `vurgu`: bu line_item_id işaretlenir (sayfada "bu kalem" rozeti).
    """
    from app.services import mold_planner as _mp

    liste = list(db.scalars(select(LineItem).where(LineItem.order_id == order.id)).all())

    # Görsel kaynağı: kalemin kendi `product_image_url`'i çoğu kalemde BOŞ;
    # aynı başlıklı katalog ürününün görseli çok daha kapsayıcı.
    katalog_gorsel: dict[str, str] = {}
    if gorsel:
        basliklar = {(li.title or "").strip() for li in liste if li.title}
        if basliklar:
            for _p, _yol in db.execute(
                select(CatalogProduct.title, CatalogImage.file_path)
                .join(CatalogImage, CatalogImage.product_id == CatalogProduct.id)
                .where(CatalogProduct.tenant_id == order.tenant_id,
                       CatalogProduct.title.in_(basliklar))
                .order_by(CatalogImage.position)
            ).all():
                katalog_gorsel.setdefault((_p or "").strip(), f"/storage/{_yol}")

    out = []
    for li in liste:
        # Model TEK KAYNAKTAN: elle düzeltilmişse o, yoksa siparişten çözülen.
        model = (li.device_model_override or "").strip() or _mp.extract_phone_model(li) or None
        kayit = {
            "urun": (li.title or "")[:160],
            "model": model,
            "durum": kalem_durumu(li),
            "adet": getattr(li, "quantity", 1) or 1,
        }
        if gorsel:
            kayit["gorsel"] = (li.product_image_url
                               or katalog_gorsel.get((li.title or "").strip()) or None)
        if vurgu is not None:
            kayit["bu_kalem"] = str(li.id) == str(vurgu)
        out.append(kayit)
    return out
