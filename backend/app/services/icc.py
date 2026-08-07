"""Mağazanın CMYK ICC profili.

Baskı makinesinin (ya da matbaanın) profili panelden yüklenir; RGB fotoğraflar
baskı PDF'ine çevrilirken bu profil kullanılır. Profil yoksa Pillow'un basit
dönüşümü devreye girer — çalışır ama renkler makinenin gerçek gamutuna göre
ayarlanmaz, bu yüzden panelde uyarı gösterilir.
"""
from __future__ import annotations

import logging
from pathlib import Path

from app.services.storage import STORAGE_ROOT

log = logging.getLogger("icc")


def magaza_icc(db, store_id) -> bytes | None:
    """Mağazanın yüklü CMYK profili (bayt) — yoksa None."""
    from sqlalchemy import select

    from app.models import Store

    try:
        store = db.scalar(select(Store).where(Store.id == store_id))
    except Exception:  # noqa: BLE001
        return None
    yol = ((store.config or {}).get("cmyk_icc_path") or "") if store else ""
    if not yol:
        return None
    dosya = STORAGE_ROOT / yol
    if not dosya.exists():
        log.warning("ICC profili bulunamadı: %s", dosya)
        return None
    try:
        return dosya.read_bytes()
    except OSError:
        return None
