"""
IP hız sınırlayıcı — public (auth'suz) endpoint'ler için.

⚠ SAYAÇ VERİTABANINDA (tablo: hiz_siniri_vuruslari), SÜREÇ BELLEĞİNDE DEĞİL.
Eskiden sayaç her sürecin kendi sözlüğündeydi: tek uvicorn worker'ında doğru,
ama ikinci worker açıldığı gün her worker kendi sayacını tutacak ve IP başına
hak worker sayısı kadar KATLANACAKTI (giriş kodu 5/5 dk → 10/5 dk).

Veritabanına ulaşılamazsa süreç-içi sayaca DÜŞÜLÜR (açık kalır): hız sınırı
yüzünden gerçek müşteriyi kapıda bırakmak, sınırın bir süre gevşemesinden kötü.

Cloudflare arkasında gerçek IP CF-Connecting-IP / X-Forwarded-For'dan okunur.

    from app.services.rate_limit import make_rate_limiter
    rate_limit = make_rate_limiter(max_hits=10, window=60.0)

    @router.post("/x")
    def x(_rl: None = Depends(rate_limit)): ...

Her make_rate_limiter çağrısı kendi kotasını tutar. Kimlik ÇAĞRILDIĞI YERDEN
(modül:satır) türetilir — tüm worker'larda aynı olsun diye sayaç sırasına
değil koda bağlı.
"""
from __future__ import annotations

import logging
import random
import sys
import time

from fastapi import HTTPException, Request
from sqlalchemy import text

logger = logging.getLogger("rate_limit")


def client_ip(request: Request) -> str:
    cf = request.headers.get("cf-connecting-ip")
    if cf:
        return cf.strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "?"


def _ortak_sayac(anahtar: str, max_hits: int, window: float) -> bool | None:
    """Veritabanındaki ortak sayaçla karar ver. True=izin, False=sınır, None=DB yok."""
    try:
        from app.database import SessionLocal
        with SessionLocal() as db:
            n = db.execute(text(
                "SELECT count(*) FROM hiz_siniri_vuruslari "
                "WHERE anahtar = :a AND zaman > now() - make_interval(secs => :w)"),
                {"a": anahtar, "w": float(window)}).scalar() or 0
            if n >= max_hits:
                return False
            db.execute(text("INSERT INTO hiz_siniri_vuruslari (anahtar) VALUES (:a)"),
                       {"a": anahtar})
            # Ara sıra budama: tablo büyümesin (en uzun pencere 5 dk; 1 gün bol pay).
            if random.random() < 0.01:
                db.execute(text("DELETE FROM hiz_siniri_vuruslari "
                                "WHERE zaman < now() - interval '1 day'"))
            db.commit()
            return True
    except Exception as e:  # noqa: BLE001 — sınırlayıcı isteği DÜŞÜRMEZ
        logger.warning(f"[rate_limit] ortak sayaç kullanılamadı, bellek sayacına düşüldü: {e}")
        return None


def make_rate_limiter(max_hits: int = 10, window: float = 60.0, ad: str | None = None):
    _cagiran = sys._getframe(1)
    kimlik = ad or f"{_cagiran.f_globals.get('__name__', '?')}:{_cagiran.f_lineno}"
    hits: dict[str, list[float]] = {}   # YEDEK: yalnız veritabanına ulaşılamazsa

    def rate_limit(request: Request) -> None:
        ip = client_ip(request)
        karar = _ortak_sayac(f"{kimlik}|{ip}"[:300], max_hits, window)
        if karar is False:
            raise HTTPException(429, "Çok fazla deneme. Lütfen biraz bekleyip tekrar deneyin.")
        if karar is True:
            return

        now = time.time()
        arr = [t for t in hits.get(ip, []) if now - t < window]
        if len(arr) >= max_hits:
            raise HTTPException(429, "Çok fazla deneme. Lütfen biraz bekleyip tekrar deneyin.")
        arr.append(now)
        hits[ip] = arr
        # ara sıra temizlik (bellek büyümesin)
        if len(hits) > 5000:
            for k in [k for k, v in hits.items() if not v or now - v[-1] > window]:
                hits.pop(k, None)

    rate_limit.kimlik = kimlik   # testler ve teşhis için
    return rate_limit
