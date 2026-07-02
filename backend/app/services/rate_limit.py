"""
Basit in-memory IP rate limiter — public (auth'suz) endpoint'ler için.

Tek-process varsayımı (uvicorn tek worker). Cloudflare arkasında gerçek IP
CF-Connecting-IP / X-Forwarded-For'dan okunur. Kullanım:

    from app.services.rate_limit import make_rate_limiter
    rate_limit = make_rate_limiter(max_hits=10, window=60.0)

    @router.post("/x")
    def x(_rl: None = Depends(rate_limit)): ...

Her make_rate_limiter çağrısı kendi sayacını tutar (endpoint başına bağımsız kota).
"""
from __future__ import annotations

import time

from fastapi import HTTPException, Request


def client_ip(request: Request) -> str:
    cf = request.headers.get("cf-connecting-ip")
    if cf:
        return cf.strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "?"


def make_rate_limiter(max_hits: int = 10, window: float = 60.0):
    hits: dict[str, list[float]] = {}

    def rate_limit(request: Request) -> None:
        ip = client_ip(request)
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

    return rate_limit
