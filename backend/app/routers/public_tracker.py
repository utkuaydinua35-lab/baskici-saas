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

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import tracker as tk
from app.services.rate_limit import make_rate_limiter

router = APIRouter(tags=["public-tracker"])

# track.html'i bir kez oku (cache)
_HTML_PATH = Path(__file__).parent.parent / "public" / "track.html"
try:
    _TRACK_HTML = _HTML_PATH.read_text(encoding="utf-8")
except Exception:
    _TRACK_HTML = "<h1>Takip sayfası yüklenemedi</h1>"

rate_limit = make_rate_limiter(max_hits=10, window=60.0)


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

    order = tk.fetch_order_for_tracking(db, store, payload.order_number, str(payload.email))
    if not order:
        raise HTTPException(
            404,
            "Sipariş bulunamadı. Sipariş numaranızı ve e-posta adresinizi kontrol edin.",
        )
    return tk.build_track_response(db, order)
