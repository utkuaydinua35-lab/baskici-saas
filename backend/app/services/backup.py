"""Zamanlanmış veritabanı yedeği — pg_dump + gzip + rotasyon.

Yedekler STORAGE_ROOT DIŞINDA tutulur (STORAGE_ROOT /storage'tan public servis
edilir; yedekler tüm veriyi içerir, asla web'e açılmamalı). Sadece platform
admin endpoint'i (auth) ile listelenir/indirilir.

BACKUP_DIR env ile override edilebilir. pg_dump PATH'te olmalı (postgresql-client).
"""
from __future__ import annotations

import gzip
import logging
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.services.storage import STORAGE_ROOT

logger = logging.getLogger("backup")
_TR = ZoneInfo("Europe/Istanbul")

# STORAGE_ROOT'un YANINDA (içinde değil) — web'e açık /storage'a düşmesin
BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", str(STORAGE_ROOT.parent / "backups")))
KEEP = int(os.environ.get("BACKUP_KEEP", "7"))
_NAME_RE = re.compile(r"^baskici-\d{8}-\d{6}\.sql\.gz$")


class BackupError(Exception):
    pass


def _pg_url() -> str:
    """SQLAlchemy URL'inden pg_dump için saf postgresql:// URI."""
    return get_settings().database_url.replace("+psycopg2", "").replace("+psycopg", "")


def _rotate() -> None:
    files = sorted(
        (p for p in BACKUP_DIR.glob("baskici-*.sql.gz") if p.is_file()),
        key=lambda p: p.stat().st_mtime, reverse=True,
    )
    for old in files[KEEP:]:
        try:
            old.unlink()
        except OSError:
            pass


def run_backup() -> dict:
    """pg_dump | gzip -> BACKUP_DIR/baskici-<ts>.sql.gz, rotasyon. Dosya bilgisi döner."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(_TR).strftime("%Y%m%d-%H%M%S")
    out = BACKUP_DIR / f"baskici-{ts}.sql.gz"
    url = _pg_url()
    try:
        with gzip.open(out, "wb") as gz:
            proc = subprocess.Popen(
                ["pg_dump", "--dbname", url, "--no-owner", "--no-privileges"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            shutil.copyfileobj(proc.stdout, gz)
            proc.stdout.close()
            rc = proc.wait()
            err = (proc.stderr.read() or b"").decode(errors="replace")
    except FileNotFoundError as e:
        out.unlink(missing_ok=True)
        raise BackupError("pg_dump bulunamadı. VPS'te 'postgresql-client' kurulu olmalı.") from e
    except Exception as e:  # noqa: BLE001
        out.unlink(missing_ok=True)
        raise BackupError(f"Yedek alınamadı: {e}") from e

    if rc != 0 or not out.exists() or out.stat().st_size == 0:
        out.unlink(missing_ok=True)
        raise BackupError(f"pg_dump hata (kod {rc}): {err[:200]}")

    _rotate()
    size = out.stat().st_size
    logger.info(f"[backup] alındı: {out.name} ({size} bayt)")
    return {"name": out.name, "size": size}


def list_backups() -> list[dict]:
    if not BACKUP_DIR.exists():
        return []
    rows = []
    for p in BACKUP_DIR.glob("baskici-*.sql.gz"):
        if not p.is_file():
            continue
        st = p.stat()
        rows.append({
            "name": p.name,
            "size": st.st_size,
            "created_at": datetime.fromtimestamp(st.st_mtime, _TR).isoformat(),
        })
    rows.sort(key=lambda r: r["created_at"], reverse=True)
    return rows


def backup_path(name: str) -> Path | None:
    """Güvenli dosya yolu (path traversal'a karşı isim doğrulanır)."""
    if not _NAME_RE.match(name or ""):
        return None
    p = (BACKUP_DIR / name).resolve()
    if p.parent != BACKUP_DIR.resolve() or not p.is_file():
        return None
    return p
