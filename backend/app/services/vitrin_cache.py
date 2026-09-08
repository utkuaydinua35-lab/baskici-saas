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

# ─── Marka süzgeci önbelleği ─────────────────────────────────
# Ürün listesi ucu, marka filtresi kutusunu doldurmak için HER İSTEKTE
# mağazanın tüm varyantlarını ürünlerle birleştiriyordu. Canlıda ölçüldü:
# 191 bin varyant satırı taranıyor, 103 ms sürüyor ve Postgres iki paralel
# işçi açıyor — veritabanının en çok satır okuyan sorgusu buydu
# (pg_stat: catalog_variants 383 milyon satır).
#
# Marka listesi katalog değişmedikçe değişmez. Önbellek iki yoldan tazelenir:
# katalog değişince katalog_degisti() düşürür, ayrıca TTL güvenlik ağı vardır
# (çok işçili kurulumda sinyal yalnız değişikliği yapan işçiye ulaşır).
_MARKA_TTL_SN = 300
_marka_onbellek: dict[str, tuple[float, list[str]]] = {}
_marka_kilit = threading.Lock()


def markalari_dusur() -> None:
    """Katalog değişti — marka süzgeci yeniden hesaplansın."""
    with _marka_kilit:
        _marka_onbellek.clear()


def markalar(db, store_id, oku) -> list[str]:
    """Mağazanın marka listesi; yoksa `oku()` ile hesaplanıp saklanır.

    `oku` çağrılabiliri sorguyu yapar — bu modül SQL bilmesin diye dışarıdan
    geçiliyor (public_shop kendi sorgusunu tutuyor).
    """
    anahtar = str(store_id)
    simdi = time.monotonic()
    with _marka_kilit:
        kayit = _marka_onbellek.get(anahtar)
        if kayit and simdi - kayit[0] < _MARKA_TTL_SN:
            return kayit[1]
    # Sorgu KİLİT DIŞINDA: yavaş sorgu diğer istekleri bloklamasın.
    deger = list(oku())
    with _marka_kilit:
        _marka_onbellek[anahtar] = (simdi, deger)
    return deger


def katalog_degisti() -> None:
    """Ürün/varyant/koleksiyon değişti — vitrin önbelleğini düşür (arka plan)."""
    global _SON_GONDERIM
    markalari_dusur()
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
