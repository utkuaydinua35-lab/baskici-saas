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
            mat = fitz.Matrix(300 / 72, 300 / 72)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            doc.close()
            return img
        return Image.open(full)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[mockup] tasarım yüklenemedi: {e}")
        return None


def _solve8(A, b):
    """8x8 lineer sistemi Gauss eliminasyonuyla coz (numpy'siz). x ya da None."""
    n = 8
    M = [A[i][:] + [b[i]] for i in range(n)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[piv][col]) < 1e-12:
            return None
        M[col], M[piv] = M[piv], M[col]
        pv = M[col][col]
        for j in range(col, n + 1):
            M[col][j] /= pv
        for r in range(n):
            if r != col and abs(M[r][col]) > 1e-12:
                f = M[r][col]
                for j in range(col, n + 1):
                    M[r][j] -= f * M[col][j]
    return [M[i][n] for i in range(n)]


def _perspective_coeffs(dst, src):
    """PIL PERSPECTIVE katsayilari (cikti->girdi eslemesi). dst: cikti quad noktalari,
    src: kaynak (tasarim) dikdortgeni koseleri. Ikisi de 4 (x,y)."""
    A, b = [], []
    for (dx, dy), (sx, sy) in zip(dst, src):
        A.append([dx, dy, 1, 0, 0, 0, -sx * dx, -sx * dy]); b.append(sx)
        A.append([0, 0, 0, dx, dy, 1, -sy * dx, -sy * dy]); b.append(sy)
    return _solve8(A, b)


def _render_quad(design: Image.Image, tpl: Image.Image, quad, overlay: bool) -> Image.Image:
    """Tasarimi 4 noktali perspektif quad'a (TL,TR,BR,BL) yerlestir.
    overlay=True: tasarim ARKADA, sablon (seffaf pencere) USTTE."""
    TW, TH = tpl.size
    pts = [(float(p[0]) * TW, float(p[1]) * TH) for p in quad]
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    bw = max(1, int(max(xs) - min(xs))); bh = max(1, int(max(ys) - min(ys)))
    # Quad'in sinir kutusu cozunurlugunde cover-fit (yeterli detay icin)
    fitted = _cover(design, bw, bh).convert("RGBA")
    fw, fh = fitted.size
    src = [(0, 0), (fw, 0), (fw, fh), (0, fh)]  # TL,TR,BR,BL kaynak koseleri
    coeffs = _perspective_coeffs(pts, src)
    if not coeffs:
        return tpl
    warped = fitted.transform((TW, TH), Image.PERSPECTIVE, coeffs,
                              resample=Image.BICUBIC, fillcolor=(0, 0, 0, 0))
    if overlay:
        return Image.alpha_composite(warped, tpl)  # tasarim altta, sablon ustte
    return Image.alpha_composite(tpl, warped)       # tasarim sablonun ustunde


def render_with_template(design: Image.Image, template_path: str, rect: dict) -> Image.Image:
    """Tasarımı gerçek ürün fotoğrafı şablonunun rect alanına oturt.
    rect: {x,y,w,h,radius,shadow,overlay,cutouts:[{x,y,w,h,radius}]} kesirsel (0..1).
    Alternatif: rect.quad = [[x,y]*4] (TL,TR,BR,BL) -> perspektif yerlesim.
    Köşeler/boş alanlar supersample ile anti-alias; gölge şiddeti ayarlanabilir."""
    tpl = Image.open(template_path).convert("RGBA")
    TW, TH = tpl.size

    # ── Perspektif quad (acili/3B foto sablonlari icin) ──
    _quad = rect.get("quad") if isinstance(rect, dict) else None
    if isinstance(_quad, (list, tuple)) and len(_quad) == 4 and all(
        isinstance(p, (list, tuple)) and len(p) == 2 for p in _quad
    ):
        return _render_quad(design, tpl, _quad, bool(rect.get("overlay")))
    rx = int(float(rect.get("x", 0)) * TW)
    ry = int(float(rect.get("y", 0)) * TH)
    rw = int(float(rect.get("w", 1)) * TW)
    rh = int(float(rect.get("h", 1)) * TH)
    if rw < 4 or rh < 4:
        return tpl
    overlay = bool(rect.get("overlay")) if isinstance(rect, dict) else False
    fitted = _cover(design, rw, rh).convert("RGB")
    rfrac = min(0.5, max(0.0, float(rect.get("radius", 0.08)) if isinstance(rect, dict) else 0.08))

    # Boş alanlar (kamera, parmak izi): tasarımdan hariç → fotoğraftaki detay üstte kalır.
    # Geriye dönük: tek 'camera' de desteklenir.
    cutouts = list(rect.get("cutouts") or []) if isinstance(rect, dict) else []
    legacy = rect.get("camera") if isinstance(rect, dict) else None
    if isinstance(legacy, dict) and all(k in legacy for k in ("x", "y", "w", "h")):
        cutouts = cutouts + [{**legacy, "radius": legacy.get("radius", 0.18)}]

    # ── Anti-alias maske: supersample'da çiz, LANCZOS ile küçült (pürüzsüz köşe) ──
    ss = max(1, min(4, 2400 // max(rw, rh, 1)))
    mw, mh = rw * ss, rh * ss
    mask = Image.new("L", (mw, mh), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, mw - 1, mh - 1], radius=int(min(mw, mh) * rfrac), fill=255)
    for c in cutouts:
        if not (isinstance(c, dict) and all(k in c for k in ("x", "y", "w", "h"))):
            continue
        cx = (int(float(c["x"]) * TW) - rx) * ss
        cy = (int(float(c["y"]) * TH) - ry) * ss
        ccw = int(float(c["w"]) * TW) * ss
        cch = int(float(c["h"]) * TH) * ss
        if ccw > 1 and cch > 1:
            crf = min(0.5, max(0.0, float(c.get("radius", 0.2))))
            md.rounded_rectangle([cx, cy, cx + ccw, cy + cch], radius=int(min(ccw, cch) * crf), fill=0)
    if ss != 1:
        mask = mask.resize((rw, rh), Image.LANCZOS)

    if overlay:
        # Şeffaf pencereli şablon: tasarım ARKADA, şablon (pencere + kamera + gölge) ÜSTTE
        base = Image.new("RGBA", (TW, TH), (0, 0, 0, 0))
        base.paste(fitted, (rx, ry), mask)
        return Image.alpha_composite(base, tpl)

    # ── Düz foto: kılıfın ışık/gölgesini tasarıma soft-light ile uygula (ayarlanabilir) ──
    sh = min(1.0, max(0.0, float(rect.get("shadow", 0.45)) if isinstance(rect, dict) else 0.45))
    if sh > 0:
        try:
            from PIL import ImageChops
            case = tpl.crop((rx, ry, rx + rw, ry + rh)).convert("RGB")
            fitted = Image.blend(fitted, ImageChops.soft_light(fitted, case), sh)
        except Exception:  # noqa: BLE001
            pass
    out = tpl.copy()
    out.paste(fitted, (rx, ry), mask)
    return out


def canon_variation(variation: str | None) -> str:
    """Varyasyonu kanonik TR forma getir (SİYAH/BEYAZ/ŞEFFAF/PARLAK/MAGSAFE).
    Eski 'siyah'/'seffaf' küçük harf girdileri de desteklenir."""
    v = (variation or "").strip().upper()
    if v in ("SIYAH", "SİYAH", ""):
        return "SİYAH"
    if v == "BEYAZ":
        return "BEYAZ"
    if v in ("SEFFAF", "ŞEFFAF"):
        return "ŞEFFAF"
    if v == "PARLAK":
        return "PARLAK"
    if v == "MAGSAFE":
        return "MAGSAFE"
    return v


def _pick_template(phone_model, var_key: str):
    """Varyasyona özel gerçek foto şablonu (varsa); yoksa varsayılan şablon.
    Dönüş: (template_url, rect) ya da (None, None)."""
    if not phone_model:
        return None, None
    variants = getattr(phone_model, "mockup_variants", None) or {}
    v = variants.get(var_key) if isinstance(variants, dict) else None
    if isinstance(v, dict) and v.get("template_url") and v.get("rect"):
        return v["template_url"], v["rect"]
    return getattr(phone_model, "mockup_template_url", None), getattr(phone_model, "mockup_rect", None)


def generate_mockup_url(design, tenant_id, variation: str = "siyah", phone_model=None) -> str | None:
    """Tasarımdan mockup üret, storage'a kaydet, /storage göreli URL döndür.

    Varyasyona özel gerçek foto şablonu (phone_model.mockup_variants) varsa onu;
    yoksa varsayılan şablonu (mockup_template_url); o da yoksa prosedürel çizimi
    kullanır. design: Design ORM. Hata olursa None.
    """
    img = _load_design_image(getattr(design, "file_path", None), getattr(design, "file_format", None))
    if img is None:
        return None
    try:
        from app.services.storage import STORAGE_ROOT
        var_key = canon_variation(variation)
        tpl_url, rect = _pick_template(phone_model, var_key)
        suffix = var_key.replace("İ", "I")
        mock = None
        if tpl_url and rect and str(tpl_url).startswith("/storage/"):
            tpl_path = STORAGE_ROOT / str(tpl_url)[len("/storage/"):]
            if tpl_path.exists():
                mock = render_with_template(img, str(tpl_path), rect)
                suffix = f"tpl_{getattr(phone_model, 'id', '')}_{suffix}"
        if mock is None:
            mock = render_mockup(img, "seffaf" if var_key == "ŞEFFAF" else "siyah")
        rel_dir = f"tenants/{tenant_id}/mockups"
        (STORAGE_ROOT / rel_dir).mkdir(parents=True, exist_ok=True)
        rel = f"{rel_dir}/{design.id}_{suffix}.png"
        mock.save(str(STORAGE_ROOT / rel), "PNG")
        return f"/storage/{rel}"
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[mockup] üretim hatası: {e}")
        return None


def _placed_quad(layer):
    """Smart object yerleşim transform'undan 4 köşe (TL,TR,BR,BL) px olarak."""
    from psd_tools.constants import Tag
    rec = layer._record
    for tg in (Tag.PLACED_LAYER2, Tag.PLACED_LAYER1):
        try:
            d = rec.tagged_blocks.get_data(tg)
        except Exception:  # noqa: BLE001
            d = None
        if d is not None and getattr(d, "transform", None):
            t = d.transform
            return [(t[0], t[1]), (t[2], t[3]), (t[4], t[5]), (t[6], t[7])]
    b = layer.bbox
    return [(b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3])]


def _is_placeholder_so(layer, layer_name):
    if layer.kind != "smartobject":
        return False
    if layer_name and layer.name == layer_name:
        return True
    so = getattr(layer, "smart_object", None)
    fn = (getattr(so, "filename", "") or "").lower()
    return ("your work here" in fn) or ("design" in fn) or (layer.name.lower() in ("design", "w1", "bc"))


def render_psd_mockup(psd_path: str, design: Image.Image, layer_name: str | None = None) -> Image.Image:
    """PSD mockup'ı sunucuda derle (Photoshopsuz). Tasarım, placeholder smart object'in
    YERLEŞİM z-SIRASINA konur: ALTINDA kalan katmanlar (case/gölge/arka plan) + tasarım +
    ÜSTÜNDEKİ katmanlar (yansıma/parlama/logo). Böylece gerçekçi (tasarım yansımanın altında)."""
    from psd_tools import PSDImage
    psd = PSDImage.open(psd_path)
    W, H = psd.width, psd.height
    leaves = [l for l in psd.descendants() if not l.is_group()]
    orig = {id(l): l.visible for l in leaves}
    placeholders = [l for l in leaves if _is_placeholder_so(l, layer_name)]

    chosen = None
    for l in placeholders:
        if layer_name and l.name == layer_name:
            chosen = l
            break
        if chosen is None and l.visible:
            chosen = l
    if chosen is None and placeholders:
        chosen = placeholders[0]
    quad_px = _placed_quad(chosen) if chosen else [(0, 0), (W, 0), (W, H), (0, H)]
    quad_frac = [[x / W, y / H] for (x, y) in quad_px]
    z = leaves.index(chosen) if chosen in leaves else len(leaves)

    def _pass(keep):
        for i, l in enumerate(leaves):
            try:
                l.visible = orig[id(l)] and (l not in placeholders) and keep(i)
            except Exception:  # noqa: BLE001
                pass
        img = psd.composite(force=True)
        return img.convert("RGBA") if img is not None else None

    try:
        below = _pass(lambda i: i < z) or Image.new("RGBA", (W, H), (255, 255, 255, 255))
        result = _render_quad(design, below, quad_frac, overlay=False)   # tasarım altın üstüne
        above = _pass(lambda i: i > z)                                    # yansıma/logo tasarımın üstüne
        if above is not None:
            result = Image.alpha_composite(result, above)
    finally:
        for l in leaves:
            try:
                l.visible = orig[id(l)]
            except Exception:  # noqa: BLE001
                pass
    return result
