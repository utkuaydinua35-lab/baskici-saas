"""Ürün Stüdyosu — tasarım görselini AI ile analiz et, Shopify içeriği (başlık/açıklama/
etiket) üret, marka bazlı benzersiz tasarım kodu ver.

Mockup yerleştirme mockup.py'de; Shopify upload adapter.create_product'ta.
"""
from __future__ import annotations

import base64
import json
import logging
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Design

logger = logging.getLogger("product_studio")

NICHES = [
    "Anime", "Nature", "Abstract", "Minimal", "Art", "Cars", "Sports", "Music",
    "Cute", "Retro", "Luxury", "Quote", "Floral", "Landscape", "Other",
]

_VISION_PROMPT = """This is a phone case PRINT design image. Analyze it and return ONLY valid JSON
(no markdown/explanation). ALL text values MUST be in ENGLISH words:
{{
  "design_name": "<2-4 word CREATIVE, unique ENGLISH design name — e.g., Neon Samurai, Night Forest, Golden Waves>",
  "niche": "<one of: {niches}>",
  "collection": "<collection/series name, 1-2 ENGLISH words — e.g., Anime, Nature, Abstract>",
  "keywords": ["<3-6 ENGLISH keywords>"],
  "colors": ["<2-3 dominant colors in ENGLISH>"],
  "style": "<one ENGLISH adjective: Elegant/Modern/Minimal/Artistic/Cute/Bold/Retro/Luxury/Playful/Sleek>",
  "main_subject": "<what it depicts, 2-4 ENGLISH words>",
  "mood": "<mood, 2-3 ENGLISH words>"
}}"""


def _parse_json(text: str) -> dict | None:
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:  # noqa: BLE001
        return None


def analyze_design(image_bytes: bytes, media_type: str = "image/jpeg", model_key: str = "sonnet") -> dict | None:
    """Claude vision ile tasarımı analiz et -> {design_name, niche, collection, keywords,
    colors, style, main_subject, mood} ya da None (anahtar yoksa/başarısızsa)."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        return None
    try:
        import anthropic
        from app.services.ai_reply import MODEL_MAP
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        b64 = base64.standard_b64encode(image_bytes).decode()
        resp = client.messages.create(
            model=MODEL_MAP.get(model_key, "claude-sonnet-4-6"),
            max_tokens=512,
            temperature=0.5,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                    {"type": "text", "text": _VISION_PROMPT.format(niches=", ".join(NICHES))},
                ],
            }],
        )
        text = "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", None) == "text")
        return _parse_json(text)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[product_studio] vision hata: {e}")
        return None


# Sabit ürün açıklaması. *x* -> kalın, **x** -> kalın + altı çizik.
_DESC_TEMPLATE = """Ürünlerimiz stoklarımızda **baskısız olarak** bulunmaktadır; görseller yalnızca **baskı önizlemeleridir.**

Tüm ürünlerimiz *sipariş üzerine, kişiye özel olarak* üretilmektedir.

Bu nedenle *6502 sayılı Tüketicinin Korunması Hakkında Kanun’un 15. maddesi* uyarınca **cayma hakkı kapsamında iade veya iptal işlemi yapılamamaktadır.**

Ancak ürünün üretiminde veya tesliminde bir hata olması durumunda **yenisiyle değişimi yapılır.**"""


def _md_to_html(text: str) -> str:
    """**x** -> <strong><u>x</u></strong>, *x* -> <strong>x</strong>. Paragraflar <p>."""
    from html import escape
    out = []
    for p in [x.strip() for x in text.split("\n\n") if x.strip()]:
        p = escape(p)
        p = re.sub(r"\*\*(.+?)\*\*", r"<strong><u>\1</u></strong>", p)
        p = re.sub(r"\*(.+?)\*", r"<strong>\1</strong>", p)
        out.append(f"<p>{p}</p>")
    return "".join(out)


def description_html() -> str:
    return _md_to_html(_DESC_TEMPLATE)


_TR_ASCII = str.maketrans({
    "ş": "s", "Ş": "S", "ç": "c", "Ç": "C", "ğ": "g", "Ğ": "G",
    "ü": "u", "Ü": "U", "ö": "o", "Ö": "O", "ı": "i", "İ": "I",
    "â": "a", "Â": "A", "î": "i", "Î": "I", "û": "u", "Û": "U",
    "–": "-", "—": "-", "’": "'", "“": '"', "”": '"',
})


def ascii_fold(s: str | None) -> str:
    """Türkçe/özel karakterleri İngilizce harflere çevir (ürün adı İngilizce harf)."""
    if not s:
        return ""
    return str(s).translate(_TR_ASCII)


def seo_fields(title: str, analysis: dict | None = None) -> dict:
    """SEO başlık (≤60) + açıklama (≤160) üret — İngilizce harf, düz metin."""
    a = analysis or {}
    dname = ascii_fold((a.get("design_name") or "").strip())
    coll = ascii_fold((a.get("collection") or a.get("niche") or "").strip())
    kw = [ascii_fold(k) for k in (a.get("keywords") or []) if k][:4]
    seo_title = ascii_fold(title)[:60].strip()
    desc = f"{dname} design phone case."
    if coll:
        desc += f" {coll} series."
    if kw:
        desc += " " + ", ".join(kw) + "."
    desc += " High quality print, full protection."
    seo_desc = ascii_fold(desc)[:160].strip()
    return {"seo_title": seo_title, "seo_description": seo_desc}


def build_content(analysis: dict, brand_name: str) -> dict:
    """Analizden Shopify başlığı (İngilizce harf) + (sabit) açıklama + etiketler + SEO."""
    a = analysis or {}
    dname = ascii_fold((a.get("design_name") or "Custom Design").strip())
    coll = ascii_fold((a.get("collection") or a.get("niche") or "Custom").strip())
    colors = a.get("colors") or []
    keywords = a.get("keywords") or []
    style = (a.get("style") or "").strip()

    title = ascii_fold(f'{brand_name} "{dname}" Design Phone Case - {coll} Series')
    body_html = description_html()
    tags = list(dict.fromkeys(
        [t for t in ([a.get("niche")] + keywords + colors + [style, coll]) if t]
    ))
    seo = seo_fields(title, a)
    return {"title": title, "body_html": body_html, "tags": tags, "design_name": dname,
            "seo_title": seo["seo_title"], "seo_description": seo["seo_description"]}


def next_design_code(db: Session, store_id, prefix: str, reserved=None) -> str:
    """Marka öneki + sıralı numara ile benzersiz tasarım kodu (örn B777, B778).
    Mevcut '{prefix}<sayı>' kodlarının + reserved'in en büyüğü + 1; hiç yoksa {prefix}777."""
    prefix = (prefix or "X").upper()
    rows = list(db.scalars(select(Design.code).where(Design.store_id == store_id)).all())
    if reserved:
        rows += list(reserved)
    mx = 776
    pat = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    for c in rows:
        m = pat.match(c or "")
        if m:
            mx = max(mx, int(m.group(1)))
    return f"{prefix}{mx + 1}"


# Telefon kılıfı baskı oranı ~ 1100:2162 (w/h ≈ 0.509). Bu banttan sapan görseller kenara alınır.
CASE_RATIO = 1100 / 2162
RATIO_MIN, RATIO_MAX = 0.44, 0.60  # ~1:2.27 .. 1:1.67


def aspect_ok(w: int, h: int) -> bool:
    if not w or not h:
        return False
    return RATIO_MIN <= (w / h) <= RATIO_MAX


def make_print_pdf(image, dpi: int = 300, k_offset_pct: int = 5) -> bytes:
    """Tasarımı baskı için CMYK PDF'e çevir (mold/üretim akışı PDF bekler).
    k_offset_pct: K kanalına eklenen offset (%). +5 -> en beyaz renk 0,0,0,5 olur
    (kullanıcı isteği). Negatif verilirse K azalır (koyular açılır).
    Not: RIP/ICC profili olmadan naif RGB->CMYK; matbaa ICC profili istenirse eklenebilir."""
    import io
    from PIL import Image as _Img
    img = image if hasattr(image, "convert") else _Img.open(io.BytesIO(image))
    rgb = img.convert("RGB")
    try:
        out = rgb.convert("CMYK")
    except Exception:  # noqa: BLE001
        out = rgb
    if out.mode == "CMYK" and k_offset_pct:
        off = round(float(k_offset_pct) / 100.0 * 255.0)   # % -> 0..255
        c, m, y, k = out.split()
        k = k.point(lambda v: max(0, min(255, v + off)))
        out = _Img.merge("CMYK", (c, m, y, k))
    buf = io.BytesIO()
    out.save(buf, "PDF", resolution=float(dpi))
    return buf.getvalue()


def default_prefix(brand_name: str) -> str:
    for ch in (brand_name or ""):
        if ch.isalpha():
            return ch.upper()
    return "X"
