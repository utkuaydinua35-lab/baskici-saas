"""
Public sipariş takip — AUTH YOK (müşteriye açık).

siparistakip.bernzcompany.com → Caddy → bu router.
- GET  /track-page       → takip sayfası (track.html)
- GET  /                 → takip sayfası (subdomain kökü)
- POST /track            → sipariş sorgula (rate-limit, no+e-posta eşleşme şart)

Rate limit: IP başına 60 sn'de 10 istek (in-memory, tek-process). Cloudflare
arkasında olduğu için gerçek IP CF-Connecting-IP / X-Forwarded-For'dan okunur.
"""
from __future__ import annotations

import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import tracker as tk

router = APIRouter(tags=["public-tracker"])

# track.html'i bir kez oku (cache)
_HTML_PATH = Path(__file__).parent.parent / "public" / "track.html"
try:
    _TRACK_HTML = _HTML_PATH.read_text(encoding="utf-8")
except Exception:
    _TRACK_HTML = "<h1>Takip sayfası yüklenemedi</h1>"

# ── basit in-memory rate limiter ──
_hits: dict[str, list[float]] = {}
_WINDOW = 60.0
_MAX = 10


def _client_ip(request: Request) -> str:
    cf = request.headers.get("cf-connecting-ip")
    if cf:
        return cf.strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "?"


def rate_limit(request: Request):
    ip = _client_ip(request)
    now = time.time()
    arr = [t for t in _hits.get(ip, []) if now - t < _WINDOW]
    if len(arr) >= _MAX:
        raise HTTPException(429, "Çok fazla deneme. Lütfen biraz bekleyip tekrar deneyin.")
    arr.append(now)
    _hits[ip] = arr
    # ara sıra temizlik
    if len(_hits) > 5000:
        for k in [k for k, v in _hits.items() if not v or now - v[-1] > _WINDOW]:
            _hits.pop(k, None)


class TrackRequest(BaseModel):
    order_number: str
    email: EmailStr


@router.get("/track-page", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def tracking_page():
    return HTMLResponse(_TRACK_HTML)


@router.post("/track")
def track_order(
    payload: TrackRequest,
    request: Request,
    _rl: None = Depends(rate_limit),
    db: Session = Depends(get_db),
):
    store = tk.resolve_tracker_store(db)
    if not store:
        raise HTTPException(503, "Takip servisi şu an kullanılamıyor.")

    order = tk.fetch_order_for_tracking(store, payload.order_number, str(payload.email))
    if not order:
        raise HTTPException(
            404,
            "Sipariş bulunamadı. Sipariş numaranızı ve e-posta adresinizi kontrol edin.",
        )
    return tk.build_track_response(db, order)
