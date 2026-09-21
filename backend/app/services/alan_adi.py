"""Vitrin alan adı — tek biçim, tek sahip.

Vitrin, gelen isteğin Host'unu `shop_domain` / `custom_domain` ile BİREBİR
karşılaştırarak mağazayı buluyor (public_shop._resolve). Bu yüzden:
  • "https://Magaza.Site.com/" gibi yazılan değer kaydedilirken temizlenmeli,
    yoksa vitrin mağazayı hiç bulamaz (sessizce 404).
  • Aynı alan adı iki mağazada olamaz: çözümleme ilk bulduğunu döner, yani
    ikinci mağaza birincinin vitrinini ele geçirir ya da hiç görünmez.
"""
from __future__ import annotations

import re
import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Store

_ETIKET = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
_ALAN_ADI = re.compile(rf"^(?:{_ETIKET}\.)+[a-z]{{2,63}}$")


def normalize(deger: str | None) -> str:
    """'https://Magaza.Site.com:443/urun?x=1' → 'magaza.site.com'. Boş → ''."""
    s = (deger or "").strip().lower()
    s = re.sub(r"^[a-z]+://", "", s)
    s = re.split(r"[/?#]", s, maxsplit=1)[0]
    s = s.split(":", 1)[0].rstrip(".")
    return s


def gecerli_mi(alan: str) -> bool:
    return len(alan) <= 253 and bool(_ALAN_ADI.match(alan))


def kullanan_magaza(db: Session, alan: str, haric: uuid.UUID | None = None) -> Store | None:
    """Bu alan adını kullanan BAŞKA bir vitrin mağazası (tüm atölyeler dahil)."""
    q = select(Store).where(
        Store.platform == "storefront",
        or_(Store.config["shop_domain"].astext == alan,
            Store.config["custom_domain"].astext == alan),
    )
    if haric is not None:
        q = q.where(Store.id != haric)
    return db.scalar(q.limit(1))


def dogrula(db: Session, deger: str | None, haric: uuid.UUID | None = None) -> str:
    """Temizlenmiş alan adını döner; geçersiz/çakışan ise ValueError (Türkçe mesaj)."""
    alan = normalize(deger)
    if not alan:
        return ""
    if not gecerli_mi(alan):
        raise ValueError(f"Geçersiz alan adı: {deger!s} — örnek: magaza.alanadiniz.com")
    if kullanan_magaza(db, alan, haric) is not None:
        raise ValueError(f"{alan} başka bir mağazaya bağlı")
    return alan
