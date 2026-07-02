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
    "Anime", "Doğa", "Soyut", "Minimal", "Sanat", "Araba", "Spor", "Müzik",
    "Sevimli", "Retro", "Lüks", "Motto/Yazı", "Çiçek", "Manzara", "Diğer",
]

_VISION_PROMPT = """Bu bir telefon kılıfı BASKI tasarımı görseli. Analiz et ve SADECE geçerli bir JSON döndür (markdown/açıklama YOK):
{{
  "design_name": "<2-4 kelimelik YARATICI, benzersiz Türkçe tasarım adı — örn: Neon Samuray, Gece Ormanı, Altın Dalgalar>",
  "niche": "<şunlardan biri: {niches}>",
  "collection": "<koleksiyon/seri adı, 1-2 kelime Türkçe — örn: Anime, Doğa, Soyut>",
  "keywords": ["<3-6 Türkçe anahtar kelime>"],
  "colors": ["<2-3 baskın renk, Türkçe>"],
  "style": "<tek Türkçe sıfat: Şık/Modern/Minimal/Sanatsal/Sevimli/Cesur/Retro/Lüks/Eğlenceli/Zarif>",
  "main_subject": "<ne betimliyor, 2-4 kelime Türkçe>",
  "mood": "<ruh hali, 2-3 kelime Türkçe>"
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


def build_content(analysis: dict, brand_name: str) -> dict:
    """Analizden Shopify başlığı/açıklaması/etiketleri üret."""
    a = analysis or {}
    dname = (a.get("design_name") or "Özel Tasarım").strip()
    coll = (a.get("collection") or a.get("niche") or "Özel").strip()
    colors = a.get("colors") or []
    keywords = a.get("keywords") or []
    subject = (a.get("main_subject") or dname).strip()
    style = (a.get("style") or "").strip()

    title = f'{brand_name} "{dname}" Tasarım Telefon Kılıfı – {coll} Serisi'

    intro = f"{subject} temalı bu özel tasarım, {style.lower() or 'şık'} bir görünüm sunar." if subject else ""
    d1 = f"{coll} serisinden özgün {dname} deseni"
    d2 = f"Baskın renkler: {', '.join(colors)}" if colors else "Canlı ve dengeli renk paleti"
    d3 = f"{style} tarzı, günlük kullanıma uygun" if style else "Günlük kullanıma uygun şık tasarım"
    body_html = (
        f"<p><strong>{dname}</strong> {intro}</p>"
        "<p><strong>Ürün Özellikleri:</strong></p><ul>"
        "<li>Yüksek çözünürlüklü UV baskı teknolojisi</li>"
        f"<li>{d1}</li><li>{d2}</li><li>{d3}</li>"
        "<li>Solmayan, soyulmaya karşı dirençli canlı renkler</li>"
        "<li>Tüm düğme ve kamera açıklıklarına tam uyum</li>"
        "<li>İnce ve hafif yapı ile rahat kullanım</li></ul>"
    )
    tags = list(dict.fromkeys(
        [t for t in ([a.get("niche")] + keywords + colors + [style, coll]) if t]
    ))
    return {"title": title, "body_html": body_html, "tags": tags, "design_name": dname}


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


def default_prefix(brand_name: str) -> str:
    for ch in (brand_name or ""):
        if ch.isalpha():
            return ch.upper()
    return "X"
