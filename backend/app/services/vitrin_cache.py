"""Vitrin önbelleğini panelden anında düşürme.

Vitrin (Next.js) katalog verisini 60 sn önbelleğe alır — yoksa her ziyaretçi
için backend'e gidip sayfayı yavaşlatır. Ama panelde fiyat/stok/koleksiyon
değiştirildiğinde bu gecikme "değişikliğim yansımadı" hissi veriyordu.

Çözüm: panelde katalog değişince vitrine "katalog etiketini düşür" sinyali
gönderilir; vitrin bir sonraki istekte veriyi tazeler. Sinyal best-effort'tur —
vitrin kapalıysa hata yutulur, en fazla 60 sn'lik normal gecikmeye düşülür.

Tema için aynı iş store_settings._revalidate_storefront ile yapılıyor.
"""
from __future__ import annotations

import logging
import threading
import time

log = logging.getLogger("vitrin_cache")

_SON_GONDERIM = 0.0
_ARALIK_SN = 2.0        # toplu düzenlemede yüzlerce sinyal gitmesin


def katalog_degisti() -> None:
    """Ürün/varyant/koleksiyon değişti — vitrin önbelleğini düşür (arka plan)."""
    global _SON_GONDERIM
    simdi = time.monotonic()
    if simdi - _SON_GONDERIM < _ARALIK_SN:
        return
    _SON_GONDERIM = simdi
    threading.Thread(target=_gonder, daemon=True).start()


def _gonder() -> None:
    try:
        import httpx
        from sqlalchemy import select

        from app.database import SessionLocal
        from app.models import Store
        from app.services.site import site_url

        with SessionLocal() as db:
            magazalar = db.scalars(
                select(Store).where(Store.platform == "storefront")).all()
        for magaza in magazalar:
            base = site_url(magaza)
            if not base:
                continue
            try:
                httpx.post(f"{base}/api/revalidate-katalog", timeout=3)
            except Exception:  # noqa: BLE001 — vitrin kapalıysa sessizce geç
                log.debug("vitrin cache sinyali gitmedi: %s", base)
    except Exception:  # noqa: BLE001 — sinyal panelin işini bloklamaz
        log.debug("vitrin cache sinyali üretilemedi", exc_info=True)
