"""Baskıya hazır PDF — vektörel yazı + CMYK renk.

PNG çıktısı (design_render.py) ekranla birebir aynı görüntüyü verir ama her şey
rasterdir ve renkler RGB'dir. Matbaa/RIP tarafında istenen dosya ise:
  • yazılar ve şekiller VEKTÖR (punto ne olursa olsun kenarlar keskin),
  • renkler CMYK (RIP'in tahmin yürütmesine gerek kalmaz),
  • sayfa GERÇEK fiziksel ölçüde (70×145 mm gibi).

Bu modül aynı katman listesinden PDF üretir. Fotoğraflar vektöre çevrilemez
(fizik) — onlar CMYK rastere dönüştürülüp gömülür; müşteri PDF/SVG yüklediyse
o dosya OLDUĞU GİBİ (vektörel) gömülür, yeniden çizilmez.

PyMuPDF tek başına üçünü de yapar: font gömme, CMYK renk (4 elemanlı renk
demeti) ve PDF-içine-PDF yerleştirme.
"""
from __future__ import annotations

import io
import logging
from pathlib import Path

from PIL import Image

from app.services.design_render import FONT_DIR, FONT_FILES, _basilabilir_renk
from app.services.storage import STORAGE_ROOT

log = logging.getLogger("design_pdf")

MM = 72 / 25.4          # 1 mm kaç punto
VEKTOR_UZANTILARI = {".pdf", ".svg", ".eps", ".ai"}


def hex_to_cmyk(hex_renk: str | None) -> tuple[float, float, float, float]:
    """#rrggbb → (c, m, y, k) 0-1. Basılabilir beyaz kuralı burada da geçerli:
    saf beyaz baskıda 'mürekkep yok' demek olduğu için K=%5'e çekilir."""
    s = _basilabilir_renk(hex_renk).lstrip("#")
    r, g, b = (int(s[i:i + 2], 16) / 255 for i in (0, 2, 4))
    k = 1 - max(r, g, b)
    if k >= 1:
        return (0.0, 0.0, 0.0, 1.0)
    return ((1 - r - k) / (1 - k), (1 - g - k) / (1 - k), (1 - b - k) / (1 - k), k)


def _cmyk_jpeg(img: Image.Image, icc: bytes | None) -> bytes:
    """Raster görseli CMYK JPEG'e çevir. ICC profili varsa onunla (doğru
    dönüşüm), yoksa Pillow'un basit dönüşümüyle (kaba ama çalışır)."""
    if img.mode in ("RGBA", "LA", "P"):
        zemin = Image.new("RGB", img.size, (255, 255, 255))
        img = img.convert("RGBA")
        zemin.paste(img, mask=img.split()[-1])
        img = zemin
    elif img.mode != "RGB":
        img = img.convert("RGB")

    if icc:
        try:
            from PIL import ImageCms
            kaynak = ImageCms.createProfile("sRGB")
            hedef = ImageCms.ImageCmsProfile(io.BytesIO(icc))
            img = ImageCms.profileToProfile(img, kaynak, hedef, outputMode="CMYK")
        except Exception:  # noqa: BLE001 — bozuk profil baskıyı durdurmasın
            log.warning("ICC profili uygulanamadı — basit dönüşüme düşülüyor",
                        exc_info=True)
            img = img.convert("CMYK")
    else:
        img = img.convert("CMYK")

    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=95, subsampling=0)
    return buf.getvalue()


def _asset_yolu(db, asset_id: str) -> Path | None:
    from sqlalchemy import select

    from app.models import DesignAsset

    try:
        a = db.scalar(select(DesignAsset).where(DesignAsset.id == asset_id))
    except Exception:  # noqa: BLE001
        return None
    if not a:
        return None
    p = STORAGE_ROOT / a.original_path
    return p if p.exists() else None


def render_print_pdf(db, design, template, icc: bytes | None = None) -> bytes:
    """Tasarımdan baskıya hazır PDF üret (gerçek mm ölçüsünde, CMYK)."""
    import pymupdf

    W = template.print_width_mm * MM
    H = template.print_height_mm * MM

    belge = pymupdf.open()
    sayfa = belge.new_page(width=W, height=H)

    for katman in (design.layers or []):
        tip = katman.get("type")
        try:
            if tip == "text":
                _yazi(sayfa, katman, W, H)
            elif tip == "sekil":
                _sekil(sayfa, katman, W, H)
            elif tip == "image":
                _gorsel(db, sayfa, katman, W, H, icc)
            elif tip == "overlay":
                _overlay(db, sayfa, katman, W, H, icc)
        except Exception:  # noqa: BLE001 — tek katman tüm dosyayı bozmasın
            log.exception("PDF katmanı çizilemedi (design=%s, tip=%s)", design.id, tip)

    çıktı = belge.tobytes(garbage=3, deflate=True)
    belge.close()
    return çıktı


def _yazi(sayfa, k: dict, W: float, H: float) -> None:
    """VEKTÖREL metin — font PDF'e gömülür, punto ne olursa olsun keskin."""
    import pymupdf

    metin = (k.get("text") or "").strip()
    if not metin:
        return
    dosya = FONT_FILES.get(str(k.get("font") or "poppins")) or FONT_FILES["poppins"]
    yol = FONT_DIR / dosya
    boy = float(k.get("size", 0.1)) * H
    renk = hex_to_cmyk(k.get("color"))
    kutu_gen = float(k.get("w", 0.8)) * W
    sol = float(k.get("x", 0)) * W
    ust = float(k.get("y", 0)) * H
    hiza = {"left": 0, "center": 1, "right": 2}.get(k.get("align") or "left", 0)

    # Metin kutusu: PNG çıktısındaki satır sarma davranışının karşılığı
    kutu = pymupdf.Rect(sol, ust, sol + kutu_gen, H)
    sayfa.insert_textbox(
        kutu, metin, fontsize=boy, fontfile=str(yol), fontname=yol.stem,
        color=renk, align=hiza, lineheight=1.15,
    )


def _sekil(sayfa, k: dict, W: float, H: float) -> None:
    """Vektör şekil — şimdilik ilerleme çubuğu (Spotify)."""
    import pymupdf

    if k.get("bicim") != "ilerleme":
        return
    x = float(k.get("x", 0.1)) * W
    y = float(k.get("y", 0.5)) * H
    w = float(k.get("w", 0.8)) * W
    kal = float(k.get("kalinlik", 0.004)) * H
    yari = float(k.get("boyut", 0.012)) * H
    oran = max(0.0, min(1.0, float(k.get("oran", 0))))
    renk = hex_to_cmyk(k.get("renk"))
    pasif = hex_to_cmyk(k.get("renk_pasif"))

    sayfa.draw_rect(pymupdf.Rect(x, y - kal / 2, x + w, y + kal / 2),
                    color=pasif, fill=pasif, width=0)
    if oran > 0:
        sayfa.draw_rect(pymupdf.Rect(x, y - kal / 2, x + w * oran, y + kal / 2),
                        color=renk, fill=renk, width=0)
    sayfa.draw_circle(pymupdf.Point(x + w * oran, y), yari,
                      color=renk, fill=renk, width=0)


def _yerlestir(sayfa, yol: Path, kutu, icc: bytes | None, crop: dict | None = None) -> None:
    """Dosyayı sayfaya koy. PDF/SVG ise VEKTÖREL gömülür (rasterleşmez),
    raster ise CMYK'ya çevrilip gömülür."""
    import pymupdf

    if yol.suffix.lower() in VEKTOR_UZANTILARI:
        kaynak = pymupdf.open(str(yol))
        try:
            if kaynak.page_count:
                # SVG/EPS gibi dosyalar önce PDF'e çevrilir (vektör korunur)
                if not kaynak.is_pdf:
                    kaynak = pymupdf.open("pdf", kaynak.convert_to_pdf())
                sayfa.show_pdf_page(kutu, kaynak, 0)
        finally:
            kaynak.close()
        return

    img = Image.open(yol)
    img.load()
    if crop:
        gw, gh = img.size
        kutu_px = (
            max(0, int(float(crop.get("x", 0)) * gw)),
            max(0, int(float(crop.get("y", 0)) * gh)),
            min(gw, int((float(crop.get("x", 0)) + float(crop.get("w", 1))) * gw)),
            min(gh, int((float(crop.get("y", 0)) + float(crop.get("h", 1))) * gh)),
        )
        if kutu_px[2] > kutu_px[0] and kutu_px[3] > kutu_px[1]:
            img = img.crop(kutu_px)
    sayfa.insert_image(kutu, stream=_cmyk_jpeg(img, icc))


def _gorsel(db, sayfa, k: dict, W: float, H: float, icc: bytes | None) -> None:
    import pymupdf

    yol = _asset_yolu(db, str(k.get("asset_id") or ""))
    if not yol:
        return
    x = float(k.get("x", 0)) * W
    y = float(k.get("y", 0)) * H
    kutu = pymupdf.Rect(x, y, x + float(k.get("w", 1)) * W, y + float(k.get("h", 1)) * H)
    _yerlestir(sayfa, yol, kutu, icc, k.get("crop"))


def _overlay(db, sayfa, k: dict, W: float, H: float, icc: bytes | None) -> None:
    """Hazır şablon: tabanda tüm sayfayı kaplar, alan öğesiyse kendi kutusuna."""
    import pymupdf
    from sqlalchemy import select

    from app.models import DesignOverlay

    try:
        o = db.scalar(select(DesignOverlay).where(
            DesignOverlay.id == str(k.get("overlay_id") or "")))
    except Exception:  # noqa: BLE001
        return
    if not o:
        return

    alan_key = k.get("field")
    if alan_key:
        alan = next((a for a in (o.alanlar or [])
                     if str(a.get("key")) == str(alan_key) and a.get("tip") == "gorsel"), None)
        if not alan or not alan.get("image_path"):
            return
        yol = STORAGE_ROOT / alan["image_path"]
        x = float(alan.get("x", 0)) * W
        y = float(alan.get("y", 0)) * H
        kutu = pymupdf.Rect(x, y, x + float(alan.get("w", 0.1)) * W,
                            y + float(alan.get("h", 0.1)) * H)
    else:
        yol = STORAGE_ROOT / o.image_path
        kutu = pymupdf.Rect(0, 0, W, H)

    if not yol.exists():
        log.warning("PDF: şablon dosyası yok: %s", yol)
        return
    _yerlestir(sayfa, yol, kutu, icc)
