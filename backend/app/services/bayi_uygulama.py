"""Bayi masaüstü uygulamasının yayınlanan kurulum dosyaları.

Dosyalar sunucuda `backend/uploads/uygulama/` altında durur ve /uploads
üzerinden servis edilir. Veritabanı kaydı YOK: tek doğruluk kaynağı klasörün
kendisi — yeni sürümü oraya kopyalamak yayınlamak için yeterli, panelde ayrıca
bir şey güncellenmez.

Dosya adı kuralı (electron-builder bu adlarla üretiyor):
    BERNZ-Bayi-<surum>-arm64.dmg      → macOS (Apple Silicon)
    BERNZ-Bayi-<surum>-x64.dmg        → macOS (Intel)
    BERNZ-Bayi-Kurulum-<surum>.exe    → Windows
"""
from __future__ import annotations

import re
from datetime import UTC, datetime

from app.services.uploads import UPLOAD_ROOT, public_url

UYGULAMA_DIR = UPLOAD_ROOT / "uygulama"

_MAC = re.compile(r"^BERNZ-Bayi-(?P<surum>[\d.]+)-(?P<mimari>arm64|x64)\.dmg$", re.I)
_WIN = re.compile(r"^BERNZ-Bayi-Kurulum-(?P<surum>[\d.]+)\.exe$", re.I)

MIMARI_ETIKET = {
    "arm64": "Apple Silicon (M1/M2/M3/M4)",
    "x64": "Intel işlemcili Mac",
}


def _boyut_yaz(bayt: int) -> str:
    mb = bayt / 1024 / 1024
    return f"{mb:.0f} MB" if mb >= 10 else f"{mb:.1f} MB"


def kurulumlar() -> list[dict]:
    """Yayındaki kurulum dosyaları — yeniden eskiye."""
    if not UYGULAMA_DIR.exists():
        return []
    out = []
    for p in UYGULAMA_DIR.iterdir():
        if not p.is_file():
            continue
        m = _MAC.match(p.name)
        platform, mimari = None, None
        if m:
            platform, mimari = "mac", m.group("mimari").lower()
        else:
            m = _WIN.match(p.name)
            if m:
                platform, mimari = "windows", "x64"
        if not m:
            continue
        st = p.stat()
        out.append({
            "platform": platform,
            "mimari": mimari,
            "mimari_etiket": MIMARI_ETIKET.get(mimari) if platform == "mac" else None,
            "surum": m.group("surum"),
            "dosya": p.name,
            "url": public_url(f"uygulama/{p.name}"),
            "boyut": _boyut_yaz(st.st_size),
            "tarih": datetime.fromtimestamp(st.st_mtime, UTC).isoformat(),
        })
    out.sort(key=lambda x: (x["surum"], x["platform"], x["mimari"]), reverse=True)
    return out


def son_surum(kayitlar: list[dict] | None = None) -> str | None:
    kayitlar = kayitlar if kayitlar is not None else kurulumlar()
    surumler = {k["surum"] for k in kayitlar}
    if not surumler:
        return None
    return max(surumler, key=lambda s: [int(x) for x in s.split(".") if x.isdigit()] or [0])
