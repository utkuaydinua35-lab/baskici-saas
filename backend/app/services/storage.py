"""
Tasarım dosyalarının saklanması.

Storage path:
- Dev:  ./storage (backend çalışma dizini)
- Prod: env STORAGE_ROOT (örn /srv/baskici/storage)

Layout:
    storage/
      tenants/
        <tenant_id>/
          designs/
            <design_id>.<ext>
            <design_id>_thumb.png       (PDF tasarımlar için otomatik üretilir)
"""
from __future__ import annotations

import os
from pathlib import Path

ALLOWED_EXTENSIONS = {"svg", "png", "jpg", "jpeg", "pdf"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

STORAGE_ROOT = Path(os.environ.get("STORAGE_ROOT", "./storage")).resolve()


def ensure_storage_root() -> None:
    """Storage kök dizinini garanti et."""
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)


def _tenant_design_dir(tenant_id) -> Path:
    return STORAGE_ROOT / "tenants" / str(tenant_id) / "designs"


def get_extension(filename: str) -> str:
    """Dosya adından uzantı al (küçük harfle, nokta yok)."""
    return Path(filename).suffix.lower().lstrip(".")


def is_allowed_extension(filename: str) -> bool:
    return get_extension(filename) in ALLOWED_EXTENSIONS


def _generate_pdf_thumbnail(pdf_path: Path, thumb_path: Path, dpi: int = 100) -> bool:
    """
    PDF'in ilk sayfasını PNG thumbnail olarak çıkar.
    PyMuPDF (fitz) gerekli. Başarısız olursa sessizce False döner.
    """
    try:
        import pymupdf
    except ImportError:
        print("[storage] pymupdf yüklü değil — PDF thumbnail atlandı")
        return False

    try:
        doc = pymupdf.open(str(pdf_path))
        if doc.page_count == 0:
            doc.close()
            return False
        page = doc[0]
        mat = pymupdf.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        pix.save(str(thumb_path))
        doc.close()
        return True
    except Exception as e:
        print(f"[storage] PDF thumbnail hatası: {e}")
        return False


def save_design_file(
    tenant_id,
    design_id,
    file_data: bytes,
    original_filename: str,
) -> dict:
    """
    Tasarım dosyasını diske kaydet. PDF ise otomatik thumbnail üret.

    Returns: {relative_path, thumbnail_relative_path | None, full_path, size, format}
    """
    ext = get_extension(original_filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"İzin verilen formatlar: {', '.join(sorted(ALLOWED_EXTENSIONS))}. "
            f"Yüklenen: .{ext}"
        )

    if len(file_data) > MAX_FILE_SIZE:
        raise ValueError(
            f"Dosya çok büyük (max {MAX_FILE_SIZE // 1024 // 1024} MB)"
        )

    dir_path = _tenant_design_dir(tenant_id)
    dir_path.mkdir(parents=True, exist_ok=True)

    filename = f"{design_id}.{ext}"
    full_path = dir_path / filename

    with open(full_path, "wb") as f:
        f.write(file_data)

    relative_path = f"tenants/{tenant_id}/designs/{filename}"

    # PDF için thumbnail üret
    thumbnail_relative_path: str | None = None
    if ext == "pdf":
        thumb_filename = f"{design_id}_thumb.png"
        thumb_full = dir_path / thumb_filename
        if _generate_pdf_thumbnail(full_path, thumb_full):
            thumbnail_relative_path = (
                f"tenants/{tenant_id}/designs/{thumb_filename}"
            )

    return {
        "relative_path": relative_path,
        "thumbnail_relative_path": thumbnail_relative_path,
        "full_path": str(full_path),
        "size": len(file_data),
        "format": ext,
    }


def delete_design_file(relative_path: str) -> bool:
    """Tasarım dosyasını ve varsa thumbnail'ini sil."""
    if not relative_path:
        return False
    full_path = STORAGE_ROOT / relative_path
    deleted = False
    if full_path.exists() and full_path.is_file():
        try:
            full_path.unlink()
            deleted = True
        except OSError:
            pass

    # Thumbnail'i de sil (PDF için)
    if relative_path.endswith(".pdf"):
        thumb_path = STORAGE_ROOT / (relative_path[:-4] + "_thumb.png")
        if thumb_path.exists() and thumb_path.is_file():
            try:
                thumb_path.unlink()
            except OSError:
                pass

    return deleted


def get_design_url(relative_path: str | None) -> str | None:
    """Frontend'e gönderilecek public URL ('/storage/...' önekiyle)."""
    if not relative_path:
        return None
    return f"/storage/{relative_path}"


def get_thumbnail_url(file_path: str | None, file_format: str | None) -> str | None:
    """
    Tasarım için thumbnail URL'i:
    - SVG/PNG/JPG → dosyanın kendisi
    - PDF → varsa <design_id>_thumb.png, yoksa None
    """
    if not file_path:
        return None
    fmt = (file_format or "").lower()
    if fmt in ("svg", "png", "jpg", "jpeg"):
        return f"/storage/{file_path}"
    if fmt == "pdf":
        thumb_path = file_path[:-4] + "_thumb.png"
        full = STORAGE_ROOT / thumb_path
        if full.exists():
            return f"/storage/{thumb_path}"
    return None
