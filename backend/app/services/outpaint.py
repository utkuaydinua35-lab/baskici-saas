"""Görsel genişletme (outpaint) — oran uymayan tasarımı alta yaslayıp üstünü AI ile
tamamlar (telefon kılıfı ~1:2). Pluggable: fal.ai (FLUX Fill, maskeli) + Gemini (talimatlı).

Anahtar(lar) .env'de: FAL_KEY ve/veya GEMINI_API_KEY. İkisi de yoksa None döner (kenara alınır).
Sonuçta ALT bölge (özgün tasarım) değiştirilmez — yalnızca üst boşluk üretilir.
"""
from __future__ import annotations

import base64
import io
import logging

import requests
from PIL import Image, ImageDraw

from app.config import get_settings

logger = logging.getLogger("outpaint")

_PROMPT = (
    "Extend this phone case print design UPWARD to fill the empty area at the top. "
    "Seamlessly continue the exact same art style, colors, patterns, brush strokes and background. "
    "Do NOT add any borders, frames, text, logos or watermarks. "
    "Keep the bottom part completely unchanged. Output a single cohesive full image."
)


def _data_uri(im: Image.Image, mode: str) -> str:
    buf = io.BytesIO()
    im.convert(mode).save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _prep(img: Image.Image, target_ratio: float):
    """Tasarımı hedef-oran tuvalinin ALTINA yasla; üst boşluk + maske döndür.
    Yalnızca tasarım 'çok kısa' (w/h > hedef) ise genişletir; değilse None."""
    dw, dh = img.size
    if dw <= 0 or dh <= 0:
        return None
    cur = dw / dh
    # Zaten yeterince uzun (ya da daha uzun) -> üstten genişletme gerekmez/uygun değil
    if cur <= target_ratio * 1.03:
        return None
    target_h = max(dh + 1, round(dw / target_ratio))
    canvas = Image.new("RGB", (dw, target_h), (250, 250, 250))
    top = target_h - dh
    canvas.paste(img.convert("RGB"), (0, top))
    mask = Image.new("L", (dw, target_h), 255)      # beyaz = üret
    ImageDraw.Draw(mask).rectangle([0, top, dw, target_h], fill=0)  # siyah = koru (tasarım)
    return canvas, mask, top


def _fal(canvas, mask, key, model) -> bytes | None:
    body = {"image_url": _data_uri(canvas, "RGB"), "mask_url": _data_uri(mask, "L"), "prompt": _PROMPT}
    r = requests.post(f"https://fal.run/{model}", json=body,
                      headers={"Authorization": f"Key {key}", "Content-Type": "application/json"}, timeout=180)
    if r.status_code not in (200, 201):
        logger.warning(f"[outpaint] fal HTTP {r.status_code}: {r.text[:200]}")
        return None
    d = r.json() or {}
    imgs = d.get("images") or d.get("image") or []
    url = (imgs[0].get("url") if isinstance(imgs, list) and imgs else (imgs.get("url") if isinstance(imgs, dict) else None))
    if not url:
        return None
    if url.startswith("data:"):
        return base64.b64decode(url.split(",", 1)[1])
    ir = requests.get(url, timeout=60)
    return ir.content if ir.ok else None


def _gemini(canvas, key, model) -> bytes | None:
    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, "PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    body = {
        "contents": [{"parts": [
            {"text": _PROMPT + " Return the edited image."},
            {"inline_data": {"mime_type": "image/png", "data": b64}},
        ]}],
        "generationConfig": {"responseModalities": ["IMAGE"]},
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    r = requests.post(url, json=body, timeout=180)
    if r.status_code != 200:
        logger.warning(f"[outpaint] gemini HTTP {r.status_code}: {r.text[:200]}")
        return None
    d = r.json() or {}
    for cand in d.get("candidates", []):
        for part in (cand.get("content", {}) or {}).get("parts", []):
            inl = part.get("inline_data") or part.get("inlineData")
            if inl and inl.get("data"):
                return base64.b64decode(inl["data"])
    return None


def expand_to_aspect(img_bytes: bytes, target_ratio: float, provider: str = "auto") -> bytes | None:
    """Tasarımı ~target_ratio (w/h) olacak şekilde ALTA yaslayıp üstünü AI ile genişlet.
    provider: 'auto' | 'fal' | 'gemini'. Başarısızsa None (kenara alınır)."""
    s = get_settings()
    try:
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    except Exception:  # noqa: BLE001
        return None
    prep = _prep(img, target_ratio)
    if prep is None:
        return None
    canvas, mask, top = prep

    order = []
    if provider in ("fal", "auto") and s.fal_key:
        order.append("fal")
    if provider in ("gemini", "auto") and s.gemini_api_key:
        order.append("gemini")
    if not order:
        return None

    for p in order:
        try:
            out = _fal(canvas, mask, s.fal_key, s.fal_model) if p == "fal" \
                else _gemini(canvas, s.gemini_api_key, s.gemini_image_model)
            if not out:
                continue
            res = Image.open(io.BytesIO(out)).convert("RGB")
            if res.size != canvas.size:
                res = res.resize(canvas.size, Image.LANCZOS)
            # BÜTÜNLÜK: özgün tasarımı alta geri yapıştır (yalnızca üst üretilmiş olsun)
            res.paste(img, (0, top))
            buf = io.BytesIO()
            res.save(buf, "JPEG", quality=95)
            return buf.getvalue()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[outpaint] {p} hata: {e}")
    return None
