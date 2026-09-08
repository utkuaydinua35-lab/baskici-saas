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

import io
import os
import secrets
from pathlib import Path

ALLOWED_EXTENSIONS = {"svg", "png", "jpg", "jpeg", "pdf"}
MAX_FILE_SIZE = 75 * 1024 * 1024  # 75 MB (tasarim dosyalarinin TEK sinir kaynagi)

def _storage_root() -> Path:
    """Depolama kökü. Sıra: süreç ortamı > backend/.env > ./storage

    .env DE okunmalı: os.environ tek başına yalnızca systemd'nin verdiği ortamı
    görür. Elle çalıştırılan betikler ve cron o ortamı almadığı için sessizce
    BAŞKA bir köke düşüyordu — tanı betikleri "dosya yok" diyordu, oysa dosyalar
    servisin kullandığı kökte duruyordu. Yazma yapan bir betik yanlış diske
    yazabilirdi.
    """
    v = os.environ.get("STORAGE_ROOT")
    if not v:
        env = Path(__file__).resolve().parent.parent.parent / ".env"
        if env.exists():
            for satir in env.read_text(encoding="utf-8", errors="replace").splitlines():
                satir = satir.strip()
                if satir.startswith("STORAGE_ROOT=") and not satir.startswith("#"):
                    v = satir.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    return Path(v or "./storage").resolve()


STORAGE_ROOT = _storage_root()


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
        # PNG kaydediliyor: alpha=True olmadan arkasi bos tasarimlar beyaz
        # zeminli kucuk resim uretiyordu.
        pix = page.get_pixmap(matrix=mat, alpha=True)
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


ONIZLEME_UZANTI = {"jpg", "jpeg", "png", "webp"}
MAX_ONIZLEME = 15 * 1024 * 1024


def save_onizleme(tenant_id, design_id, file_data: bytes, original_filename: str) -> str:
    """ÖNİZLEME görselini kaydet; goreli yolu doner.

    Tasarim dosyasindan AYRI klasorde durur — baski akisinin yanlislikla
    onizlemeyi almasi imkansiz olsun diye. Kalip/PDF tarafi bu klasoru hic
    okumaz.
    """
    ext = get_extension(original_filename)
    if ext not in ONIZLEME_UZANTI:
        raise ValueError(f"Önizleme için izin verilen formatlar: "
                         f"{', '.join(sorted(ONIZLEME_UZANTI)).upper()}")
    if not file_data:
        raise ValueError("Önizleme dosyası boş")
    if len(file_data) > MAX_ONIZLEME:
        raise ValueError(f"Önizleme çok büyük (max {MAX_ONIZLEME // 1024 // 1024} MB)")
    rel_dir = Path(str(tenant_id)) / "onizleme"
    (STORAGE_ROOT / rel_dir).mkdir(parents=True, exist_ok=True)
    rel = rel_dir / f"{design_id}.{ext}"
    (STORAGE_ROOT / rel).write_bytes(file_data)
    return str(rel)


def onizleme_url(relative_path: str | None) -> str | None:
    if not relative_path:
        return None
    return f"/storage/{relative_path}"


def delete_onizleme(relative_path: str | None) -> bool:
    if not relative_path:
        return False
    try:
        yol = STORAGE_ROOT / relative_path
        if yol.is_file():
            yol.unlink()
            return True
    except OSError:
        pass
    return False


def read_design_file(relative_path: str | None) -> bytes | None:
    """Kayitli tasarim dosyasinin BAYTLARI; yoksa/okunamazsa None.

    Mukerrer yukleme tespitinde hash eslesmesi TEK BASINA yeterli sayilmaz;
    aday dosya bununla bayt bayt karsilastirilir. Yanlis eslesme, musteriye
    YANLIS TASARIM basilmasi demektir.
    """
    if not relative_path:
        return None
    try:
        yol = STORAGE_ROOT / relative_path
        if not yol.is_file():
            return None
        return yol.read_bytes()
    except OSError:
        return None


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


DEKONT_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "webp"}
MAX_DEKONT_SIZE = 20 * 1024 * 1024  # 20 MB


def save_dealer_dekont(tenant_id, tx_id, file_data: bytes, original_filename: str) -> str:
    """Bayii ödeme dekontunu kaydet (PDF/görsel). Dönüş: relative_path."""
    ext = get_extension(original_filename)
    if ext not in DEKONT_EXTENSIONS:
        raise ValueError(f"İzin verilen formatlar: {', '.join(sorted(DEKONT_EXTENSIONS))}. Yüklenen: .{ext}")
    if len(file_data) > MAX_DEKONT_SIZE:
        raise ValueError(f"Dosya çok büyük (max {MAX_DEKONT_SIZE // 1024 // 1024} MB)")
    rel_dir = Path("tenants") / str(tenant_id) / "dekont"
    full_dir = STORAGE_ROOT / rel_dir
    full_dir.mkdir(parents=True, exist_ok=True)
    # Eski uzantılı kopyalar kalmasın (aynı tx yeni format)
    for e in DEKONT_EXTENSIONS:
        (full_dir / f"{tx_id}.{e}").unlink(missing_ok=True)
    fname = f"{tx_id}.{ext}"
    with open(full_dir / fname, "wb") as f:
        f.write(file_data)
    return (rel_dir / fname).as_posix()


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

STORE_ASSET_KINDS = {"logo", "favicon", "hero", "blog", "collection", "musteri", "page"}
# SVG bilinçli olarak yok: SafeStaticFiles XSS koruması SVG'yi inline göstermez
STORE_ASSET_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "ico"}
MAX_STORE_ASSET_SIZE = 25 * 1024 * 1024  # 25 MB (kabul; diske optimize yazılır)


VIDEO_EXTENSIONS = {"mp4", "webm", "mov", "m4v"}
MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100 MB


def save_store_video(tenant_id, store_id, file_data: bytes, original_filename: str) -> str:
    """Ürün videosu kaydet (optimize edilmez). Dönüş: /storage/... URL yolu."""
    ext = get_extension(original_filename)
    if ext not in VIDEO_EXTENSIONS:
        raise ValueError(f"İzin verilen video formatları: {', '.join(sorted(VIDEO_EXTENSIONS))}")
    if len(file_data) > MAX_VIDEO_SIZE:
        raise ValueError(f"Video çok büyük (max {MAX_VIDEO_SIZE // 1024 // 1024} MB)")
    import time
    rel_dir = Path("tenants") / str(tenant_id) / "store-assets" / str(store_id)
    full_dir = STORAGE_ROOT / rel_dir
    full_dir.mkdir(parents=True, exist_ok=True)
    fname = f"video-{int(time.time())}.{ext}"
    with open(full_dir / fname, "wb") as f:
        f.write(file_data)
    return f"/storage/{(rel_dir / fname).as_posix()}"


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


# ─── Tasarım stüdyosu varlıkları ─────────────────────────────
# Müşterinin yüklediği görsel BASKIYA gidecek: küçültülmez, yeniden
# sıkıştırılmaz, saydamlığı korunur. Tarayıcı için ayrıca hafif bir
# önizleme türetilir (40 MP fotoğrafı tuvalde sürüklemek imkânsızdır).

DESIGN_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "pdf", "svg"}
# Vektörel kaynaklar: baskı PDF'ine OLDUĞU GİBİ gömülür (rasterleşmez).
# Tuvalde ise sunucuda üretilen PNG önizlemesi gösterilir.
VEKTOR_TASARIM_UZANTILARI = {"pdf", "svg"}
MAX_VEKTOR_SAYFA = 1
MAX_DESIGN_SIZE = 40 * 1024 * 1024      # 40 MB — telefon fotoğrafı rahat sığar
DESIGN_PREVIEW_PX = 1400


def save_design_original(tenant_id, store_id, file_data: bytes,
                         original_filename: str) -> tuple[str, str, int, int]:
    """Tasarım görselini ORİJİNAL haliyle kaydet + web önizlemesi üret.

    Dönüş: (orijinal_url, onizleme_url, genislik, yukseklik)
    """
    import time

    from PIL import Image, ImageOps

    ext = get_extension(original_filename)
    if ext not in DESIGN_EXTENSIONS:
        raise ValueError(f"İzin verilen formatlar: {', '.join(sorted(DESIGN_EXTENSIONS))}")
    if len(file_data) > MAX_DESIGN_SIZE:
        raise ValueError(f"Dosya çok büyük (max {MAX_DESIGN_SIZE // 1024 // 1024} MB)")

    rel_dir = Path("tenants") / str(tenant_id) / "designs" / str(store_id)
    full_dir = STORAGE_ROOT / rel_dir
    full_dir.mkdir(parents=True, exist_ok=True)
    damga = f"{int(time.time() * 1000)}-{secrets.token_hex(4)}"

    # ── Vektörel dosya (PDF/SVG) ──
    # Orijinal DOKUNULMADAN saklanır; baskıda vektör olarak gömülecek.
    # Tuval için yüksek çözünürlüklü PNG önizleme üretilir.
    if ext in VEKTOR_TASARIM_UZANTILARI:
        return _vektor_tasarim_kaydet(file_data, ext, full_dir, rel_dir, damga)

    # Gerçekten görsel mi + EXIF yönü (dikey fotoğraf yan yatmasın)
    try:
        img = Image.open(io.BytesIO(file_data))
        img.load()
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"Görsel dosyası okunamadı: {e}") from e
    img = ImageOps.exif_transpose(img)
    genislik, yukseklik = img.size

    # EXIF döndürmesi uygulanmış hali yazılır — baskıda yan yatma olmasın.
    # Yeniden ÖLÇEKLEME YOK; JPEG'de kalite 100 + subsampling kapalı.
    orig_name = f"{damga}.{'png' if img.mode in ('RGBA', 'LA', 'P') else 'jpg'}"
    orig_kaydet = img
    if orig_name.endswith(".png"):
        orig_kaydet.save(full_dir / orig_name, "PNG", optimize=True)
    else:
        orig_kaydet.convert("RGB").save(
            full_dir / orig_name, "JPEG", quality=100, subsampling=0)

    onizleme = img.copy()
    onizleme.thumbnail((DESIGN_PREVIEW_PX, DESIGN_PREVIEW_PX), Image.LANCZOS)
    prev_name = f"{damga}-onizleme.png"
    onizleme.save(full_dir / prev_name, "PNG", optimize=True)

    return (
        f"/storage/{(rel_dir / orig_name).as_posix()}",
        f"/storage/{(rel_dir / prev_name).as_posix()}",
        genislik, yukseklik,
    )


def _vektor_tasarim_kaydet(veri: bytes, ext: str, full_dir: Path, rel_dir: Path,
                           damga: str) -> tuple[str, str, int, int]:
    """PDF/SVG tasarımı olduğu gibi sakla + tuval için PNG önizleme üret.

    Dönüş: (orijinal_url, onizleme_url, genislik_px, yukseklik_px)
    Genişlik/yükseklik, dosyanın nokta (pt) ölçüsünden 300 DPI karşılığıdır —
    editördeki çözünürlük uyarısı bunu kullanır.
    """
    try:
        import pymupdf
    except ImportError as e:
        raise ValueError(
            "PDF/SVG desteği için sunucuda pymupdf kurulu olmalı") from e

    try:
        belge = pymupdf.open(stream=veri, filetype=ext)
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"Dosya açılamadı ({ext.upper()}): {e}") from e

    try:
        if belge.page_count == 0:
            raise ValueError("Dosya boş görünüyor")
        if belge.page_count > MAX_VEKTOR_SAYFA:
            raise ValueError(
                f"Yalnız tek sayfalık dosya kabul ediliyor "
                f"({belge.page_count} sayfa gönderildi)")
        sayfa = belge[0]
        # 300 DPI karşılığı piksel ölçüsü (1 pt = 1/72 inch)
        genislik = max(1, round(sayfa.rect.width / 72 * 300))
        yukseklik = max(1, round(sayfa.rect.height / 72 * 300))

        orig_name = f"{damga}.{ext}"
        (full_dir / orig_name).write_bytes(veri)

        # Tuval önizlemesi — vektörden rasterleştirilir (yalnız ekran için)
        olcek = min(DESIGN_PREVIEW_PX / max(sayfa.rect.width, 1),
                    DESIGN_PREVIEW_PX / max(sayfa.rect.height, 1), 4.0)
        pix = sayfa.get_pixmap(matrix=pymupdf.Matrix(olcek, olcek), alpha=True)
        onizleme_name = f"{damga}-onizleme.png"
        pix.save(str(full_dir / onizleme_name))
    finally:
        belge.close()

    return (f"/storage/{(rel_dir / orig_name).as_posix()}",
            f"/storage/{(rel_dir / onizleme_name).as_posix()}",
            genislik, yukseklik)


def design_render_url(rel_path: str | None) -> str | None:
    """Baskı dosyası URL'i + SÜRÜM damgası.

    Dosya adı sabittir (baski.png / baski-pdf.pdf) — "yeniden üret" dosyayı
    aynı yola yazar. Adres değişmediği için tarayıcı ve Cloudflare ESKİ
    KOPYAYI veriyordu: kullanıcı yeniden üretiyor, indirdiği dosya bir önceki
    çıkıyordu. Dosyanın değiştirilme zamanı sorguya eklenerek her yeni üretim
    yeni bir adres olur, önbellek kendiliğinden atlanır.
    """
    if not rel_path:
        return None
    url = f"/storage/{rel_path}"
    try:
        return f"{url}?v={int((STORAGE_ROOT / rel_path).stat().st_mtime)}"
    except OSError:
        return url


def save_design_render(tenant_id, store_id, design_id, data: bytes, kind: str) -> str:
    """Tasarımın üretilmiş çıktısı: 'onizleme' (küçük), 'baski' (yüksek
    çözünürlük PNG) veya 'baski-pdf' (vektörel + CMYK)."""
    rel_dir = Path("tenants") / str(tenant_id) / "designs" / str(store_id) / str(design_id)
    full_dir = STORAGE_ROOT / rel_dir
    full_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{kind}.pdf" if kind.endswith("pdf") else f"{kind}.png"
    with open(full_dir / fname, "wb") as f:
        f.write(data)
    return f"/storage/{(rel_dir / fname).as_posix()}"
