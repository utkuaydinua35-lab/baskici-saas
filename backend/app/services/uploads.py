"""
Destek görsel yükleme servisi (Paket: görsel).

Görseller VPS diskinde backend/uploads/support/ altında saklanır, FastAPI
/uploads StaticFiles ile servis edilir. 14 günden eski dosyalar scheduler ile
silinir. Güvenlik: sadece jpg/png/webp, maks 5MB, magic-byte kontrolü.
"""
from __future__ import annotations

import time
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.config import get_settings

# backend/uploads/support  (app/services/uploads.py → parents[2] = backend)
UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "uploads"
SUPPORT_DIR = UPLOAD_ROOT / "support"

MAX_BYTES = 5 * 1024 * 1024  # 5MB
RETENTION_DAYS = 14
_REL_PREFIX = "support/"


def ensure_upload_root() -> None:
    SUPPORT_DIR.mkdir(parents=True, exist_ok=True)


def _sniff_ext(data: bytes) -> str | None:
    """Magic-byte ile gerçek tür (uzantıya güvenme)."""
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def save_image(file: UploadFile) -> str:
    """Yüklenen görseli doğrula + kaydet. Göreli yol döndürür (support/<uuid>.<ext>)."""
    ensure_upload_root()
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Görsel çok büyük (en fazla 5MB).")
    if not data:
        raise HTTPException(400, "Boş dosya.")
    ext = _sniff_ext(data)
    if not ext:
        raise HTTPException(415, "Yalnızca JPG, PNG veya WEBP görseller yüklenebilir.")
    fname = f"{uuid.uuid4().hex}.{ext}"
    (SUPPORT_DIR / fname).write_bytes(data)
    return f"{_REL_PREFIX}{fname}"


def public_url(rel_path: str) -> str:
    base = get_settings().support_public_base_url.rstrip("/")
    return f"{base}/uploads/{rel_path}"


def is_valid_image_url(url: str | None) -> bool:
    """Yalnızca kendi /uploads/support/ altımızdaki URL'leri kabul et (XSS/dış pixel engeli)."""
    if not url:
        return False
    base = get_settings().support_public_base_url.rstrip("/")
    return url.startswith(f"{base}/uploads/{_REL_PREFIX}")


def cleanup_old(days: int = RETENTION_DAYS) -> int:
    """days günden eski görselleri sil. Silinen dosya sayısını döndürür."""
    if not SUPPORT_DIR.exists():
        return 0
    cutoff = time.time() - days * 86400
    removed = 0
    for p in SUPPORT_DIR.iterdir():
        try:
            if p.is_file() and p.stat().st_mtime < cutoff:
                p.unlink()
                removed += 1
        except Exception:
            pass
    return removed
