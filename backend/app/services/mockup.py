"""Kişiye özel tasarım için kılıf mockup (numune) üretimi — Pillow.

Tasarım (PDF→PNG ya da görsel) prosedürel bir telefon kılıfı şablonunun üzerine
oturtulur (önden, dikdörtgen yerleşim). Siyah ve şeffaf için ayrı stil.
Harici şablon fotoğrafı gerekmez; her şey çizilir.
"""
from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

logger = logging.getLogger("mockup")

# Tuval / kılıf geometrisi (önden, telefon oranı)
W, H = 820, 1640
MARGIN = 46
RADIUS = 150


def _cover(img: Image.Image, w: int, h: int) -> Image.Image:
    """object-fit: cover — alanı tam kaplar, taşan kısmı kırpar."""
    img = img.convert("RGBA")
    sw, sh = img.size
    if sw == 0 or sh == 0:
        return Image.new("RGBA", (w, h), (240, 240, 240, 255))
    scale = max(w / sw, h / sh)
    nw, nh = max(1, int(sw * scale)), max(1, int(sh * scale))
    img = img.resize((nw, nh), Image.LANCZOS)
    left = (nw - w) // 2
    top = (nh - h) // 2
    return img.crop((left, top, left + w, top + h))


def _rounded_mask(w: int, h: int, r: int) -> Image.Image:
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=255)
    return m


def render_mockup(design: Image.Image, variation: str = "siyah") -> Image.Image:
    """Tasarımı kılıf şablonuna oturtulmuş numune görseli döndür (RGBA)."""
    seffaf = variation == "seffaf"
    cw, ch = W - 2 * MARGIN, H - 2 * MARGIN

    # ── Kılıf gövdesi: tasarım cover-fit + yuvarlatılmış maske ──
    body = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    body.paste(_cover(design, cw, ch), (0, 0), _rounded_mask(cw, ch, RADIUS))
    draw = ImageDraw.Draw(body)

    # Çerçeve (kılıf kenarı)
    if seffaf:
        draw.rounded_rectangle([0, 0, cw - 1, ch - 1], radius=RADIUS, outline=(236, 239, 245, 235), width=14)
        draw.rounded_rectangle([7, 7, cw - 8, ch - 8], radius=RADIUS - 7, outline=(255, 255, 255, 90), width=3)
    else:
        draw.rounded_rectangle([0, 0, cw - 1, ch - 1], radius=RADIUS, outline=(17, 17, 19, 255), width=18)

    # ── Kamera modülü (sol üst) ──
    mx, my, ms = 58, 58, 250
    if seffaf:
        draw.rounded_rectangle([mx, my, mx + ms, my + ms], radius=72,
                               fill=(245, 247, 250, 70), outline=(205, 210, 220, 200), width=4)
    else:
        draw.rounded_rectangle([mx, my, mx + ms, my + ms], radius=72,
                               fill=(24, 24, 27, 255), outline=(8, 8, 10, 255), width=4)
    for (lx, ly) in [(mx + 72, my + 72), (mx + 168, my + 72), (mx + 72, my + 168)]:
        if seffaf:
            draw.ellipse([lx - 40, ly - 40, lx + 40, ly + 40], fill=(180, 186, 198, 120), outline=(150, 156, 168, 180), width=3)
            draw.ellipse([lx - 20, ly - 20, lx + 20, ly + 20], fill=(150, 158, 172, 130))
        else:
            draw.ellipse([lx - 40, ly - 40, lx + 40, ly + 40], fill=(14, 14, 17, 255), outline=(70, 70, 78, 255), width=4)
            draw.ellipse([lx - 19, ly - 19, lx + 19, ly + 19], fill=(40, 42, 50, 255))
            draw.ellipse([lx - 8, ly - 8, lx + 8, ly + 8], fill=(80, 84, 96, 255))
    # flaş
    draw.ellipse([mx + 162, my + 162, mx + 188, my + 188], fill=(250, 244, 210, 220))

    # ── Tuval: gölge + gövde ──
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        [MARGIN + 4, MARGIN + 18, MARGIN + cw + 4, MARGIN + ch + 18], radius=RADIUS, fill=(0, 0, 0, 110))
    shadow = shadow.filter(ImageFilter.GaussianBlur(24))
    canvas = Image.alpha_composite(canvas, shadow)
    canvas.alpha_composite(body, (MARGIN, MARGIN))
    return canvas


def _load_design_image(file_path: str, file_format: str | None) -> Image.Image | None:
    """Tasarım dosyasını PIL görseli olarak yükle (PDF → fitz ile render)."""
    from app.services.storage import STORAGE_ROOT
    full = STORAGE_ROOT / file_path
    if not full.exists():
        return None
    fmt = (file_format or "").lower()
    try:
        if fmt == "pdf" or full.suffix.lower() == ".pdf":
            import fitz
            doc = fitz.open(str(full))
            page = doc[0]
            mat = fitz.Matrix(200 / 72, 200 / 72)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            doc.close()
            return img
        return Image.open(full)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[mockup] tasarım yüklenemedi: {e}")
        return None


def render_with_template(design: Image.Image, template_path: str, rect: dict) -> Image.Image:
    """Tasarımı gerçek ürün fotoğrafı şablonunun rect alanına oturt.
    rect: {x,y,w,h} kesirsel (0..1). Tasarım o alana cover + hafif yuvarlak köşe."""
    tpl = Image.open(template_path).convert("RGBA")
    TW, TH = tpl.size
    rx = int(float(rect.get("x", 0)) * TW)
    ry = int(float(rect.get("y", 0)) * TH)
    rw = int(float(rect.get("w", 1)) * TW)
    rh = int(float(rect.get("h", 1)) * TH)
    if rw < 4 or rh < 4:
        return tpl
    fitted = _cover(design, rw, rh)
    radius = max(0, int(min(rw, rh) * 0.08))
    mask = _rounded_mask(rw, rh, radius)
    out = tpl.copy()
    out.paste(fitted, (rx, ry), mask)
    return out


def generate_mockup_url(design, tenant_id, variation: str = "siyah", phone_model=None) -> str | None:
    """Tasarımdan mockup üret, storage'a kaydet, /storage göreli URL döndür.

    phone_model verilir ve mockup_template_url+mockup_rect doluysa GERÇEK FOTO şablonu
    kullanılır; yoksa prosedürel çizime düşülür. design: Design ORM. Hata olursa None.
    """
    img = _load_design_image(getattr(design, "file_path", None), getattr(design, "file_format", None))
    if img is None:
        return None
    try:
        from app.services.storage import STORAGE_ROOT
        tpl_url = getattr(phone_model, "mockup_template_url", None) if phone_model else None
        rect = getattr(phone_model, "mockup_rect", None) if phone_model else None
        suffix = variation
        mock = None
        if tpl_url and rect and str(tpl_url).startswith("/storage/"):
            tpl_path = STORAGE_ROOT / str(tpl_url)[len("/storage/"):]
            if tpl_path.exists():
                mock = render_with_template(img, str(tpl_path), rect)
                suffix = f"tpl_{getattr(phone_model, 'id', '')}"
        if mock is None:
            mock = render_mockup(img, variation)
        rel_dir = f"tenants/{tenant_id}/mockups"
        (STORAGE_ROOT / rel_dir).mkdir(parents=True, exist_ok=True)
        rel = f"{rel_dir}/{design.id}_{suffix}.png"
        mock.save(str(STORAGE_ROOT / rel), "PNG")
        return f"/storage/{rel}"
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[mockup] üretim hatası: {e}")
        return None
