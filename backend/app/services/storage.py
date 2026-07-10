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


def generate_design_thumbnail(tenant_id, design_id) -> bool:
    """PDF tasarim icin thumbnail'i arka planda uret. Dosya zaten kayitli olmali."""
    dir_path = _tenant_design_dir(tenant_id)
    pdf_path = dir_path / f"{design_id}.pdf"
    if not pdf_path.exists():
        return False
    thumb_full = dir_path / f"{design_id}_thumb.png"
    if thumb_full.exists():
        return True
    return _generate_pdf_thumbnail(pdf_path, thumb_full)


def save_design_file(
    tenant_id,
    design_id,
    file_data: bytes,
    original_filename: str,
    skip_thumbnail: bool = False,
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

    # PDF için thumbnail üret (skip_thumbnail=True ise atla — background'da uretilecek)
    thumbnail_relative_path: str | None = None
    if ext == "pdf" and not skip_thumbnail:
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


def save_logo(tenant_id, kind: str, file_data: bytes, ext: str) -> str:
    """Logo/avatar kaydet. kind: 'brand' | 'avatar-<uuid>'. Donus: /storage/... URL."""
    import time
    rel_dir = Path("tenants") / str(tenant_id) / "branding"
    full_dir = STORAGE_ROOT / rel_dir
    full_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{kind}-{int(time.time())}.{ext}"
    rel_path = rel_dir / fname
    full_path = STORAGE_ROOT / rel_path
    with open(full_path, "wb") as f:
        f.write(file_data)
    return f"/storage/{rel_path.as_posix()}"


# ─── Vitrin (katalog) görselleri ─────────────────────────────

CATALOG_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
# Kabul sınırı — diske OPTIMIZE edilmiş küçük dosya yazılır (services/images.py)
MAX_CATALOG_IMAGE_SIZE = 25 * 1024 * 1024  # 25 MB


def save_catalog_image(tenant_id, image_id, file_data: bytes, original_filename: str) -> str:
    """Vitrin ürün görselini optimize edip kaydet (Shopify davranışı:
    büyük fotoğraf reddedilmez, küçültülür). Dönüş: relative_path."""
    ext = get_extension(original_filename)
    if ext not in CATALOG_IMAGE_EXTENSIONS:
        raise ValueError(
            f"İzin verilen görsel formatları: {', '.join(sorted(CATALOG_IMAGE_EXTENSIONS))}. "
            f"Yüklenen: .{ext}"
        )
    if len(file_data) > MAX_CATALOG_IMAGE_SIZE:
        raise ValueError(f"Görsel çok büyük (max {MAX_CATALOG_IMAGE_SIZE // 1024 // 1024} MB)")

    from app.services.images import optimize_image
    file_data, ext = optimize_image(file_data, max_px=2048)

    rel_dir = Path("tenants") / str(tenant_id) / "catalog"
    full_dir = STORAGE_ROOT / rel_dir
    full_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{image_id}.{ext}"
    with open(full_dir / fname, "wb") as f:
        f.write(file_data)
    return (rel_dir / fname).as_posix()


def delete_catalog_image(relative_path: str) -> bool:
    """Vitrin görselini diskten sil (yol storage kökü altında kalmalı)."""
    if not relative_path:
        return False
    full = (STORAGE_ROOT / relative_path).resolve()
    if not str(full).startswith(str(STORAGE_ROOT)):
        return False  # path traversal koruması
    try:
        full.unlink(missing_ok=True)
        return True
    except OSError:
        return False


# ─── Mağaza tema varlıkları (logo/favicon/hero) ──────────────

STORE_ASSET_KINDS = {"logo", "favicon", "hero", "blog"}
# SVG bilinçli olarak yok: SafeStaticFiles XSS koruması SVG'yi inline göstermez
STORE_ASSET_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "ico"}
MAX_STORE_ASSET_SIZE = 25 * 1024 * 1024  # 25 MB (kabul; diske optimize yazılır)


def save_store_asset(tenant_id, store_id, kind: str, file_data: bytes, original_filename: str) -> str:
    """Tema varlığını kaydet. Dönüş: /storage/... URL yolu."""
    if kind not in STORE_ASSET_KINDS:
        raise ValueError(f"Geçersiz varlık türü: {kind}")
    ext = get_extension(original_filename)
    if ext not in STORE_ASSET_EXTENSIONS:
        raise ValueError(
            f"İzin verilen formatlar: {', '.join(sorted(STORE_ASSET_EXTENSIONS))}")
    if len(file_data) > MAX_STORE_ASSET_SIZE:
        raise ValueError(f"Dosya çok büyük (max {MAX_STORE_ASSET_SIZE // 1024 // 1024} MB)")

    if ext != "ico":  # ico binary formatı Pillow round-trip'ine sokulmaz
        from app.services.images import optimize_image
        file_data, ext = optimize_image(
            file_data, max_px=512 if kind == "favicon" else 2560)

    import time
    rel_dir = Path("tenants") / str(tenant_id) / "store-assets" / str(store_id)
    full_dir = STORAGE_ROOT / rel_dir
    full_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{kind}-{int(time.time())}.{ext}"
    with open(full_dir / fname, "wb") as f:
        f.write(file_data)
    return f"/storage/{(rel_dir / fname).as_posix()}"
