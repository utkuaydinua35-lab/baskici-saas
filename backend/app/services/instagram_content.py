"""Instagram içerik üretimi — AI caption (Claude) + görsel seçimi.

- generate_caption: markaya uygun, insan-yazmış gibi TR caption + hashtag üretir.
  Onaylanmış/düzenlenmiş önceki gönderiler FEW-SHOT olarak beslenir -> zamanla
  markanın tonunu öğrenir.
- Görsel: ilk sürümde tasarımın mockup/thumbnail görseli kullanılır. UGC
  ("müşteriden çekilmiş gibi", tasarım gerçek sahnede) görsel üretimi = Faz 2
  (kullanıcının ileteceği örnek görsellerle prompt eğitilecek).

ANTHROPIC_API_KEY yoksa None döner (özellik sessizce kapalı).
"""
from __future__ import annotations

import json
import logging

from app.config import get_settings

logger = logging.getLogger("instagram")


_PROMPT = """Sen {brand} markasının Instagram sosyal medya editörüsün. Telefon kılıfı
satan bir markayız. Aşağıdaki ürün/tasarım için Instagram gönderisi metni yaz.

Tasarım/ürün: {subject}
Gönderi türü: {kind}
Ton: samimi, insan tarafından yazılmış gibi, satış diliyle boğmayan; 1-2 emoji.
Dil: Türkçe.

Kurallar:
- 2-4 cümle, akıcı ve doğal (reklam gibi değil).
- Sonunda 8-15 alakalı hashtag (Türkçe + telefon kılıfı/tasarım nişine uygun).
- Marka adını doğal geçir, spam yapma.

{examples}

YALNIZCA şu JSON'u döndür (başka metin yok):
{{"caption": "...", "hashtags": "#... #..."}}"""


def _examples_block(examples: list[dict]) -> str:
    """Onaylanmış önceki gönderilerden few-shot bloğu (ton öğrenme)."""
    if not examples:
        return ""
    lines = ["Marka tonunu yakala — beğenilen önceki örnekler:"]
    for e in examples[:5]:
        cap = (e.get("caption") or "").strip()
        if cap:
            lines.append(f"- {cap[:280]}")
    return "\n".join(lines)


def generate_caption(*, brand: str, subject: str, kind: str = "post",
                     model_key: str = "sonnet", examples: list[dict] | None = None) -> dict | None:
    """{'caption', 'hashtags'} ya da None. subject: tasarım adı + niş + renk vb."""
    s = get_settings()
    if not s.anthropic_api_key:
        return None
    try:
        import anthropic
        from app.services.ai_reply import MODEL_MAP
        client = anthropic.Anthropic(api_key=s.anthropic_api_key)
        prompt = _PROMPT.format(
            brand=brand or "markamız",
            subject=subject or "telefon kılıfı tasarımı",
            kind=("Story" if kind == "story" else "Gönderi (feed)"),
            examples=_examples_block(examples or []),
        )
        resp = client.messages.create(
            model=MODEL_MAP.get(model_key, "claude-sonnet-4-6"),
            max_tokens=600,
            temperature=0.8,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", None) == "text")
        return _parse_json(text)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[instagram] caption hata: {e}")
        return None


def _parse_json(text: str) -> dict | None:
    if not text:
        return None
    t = text.strip()
    # ```json ... ``` sarmalını temizle
    if t.startswith("```"):
        t = t.split("```", 2)[1] if "```" in t[3:] else t
        t = t.lstrip("json").strip("` \n")
    try:
        start, end = t.find("{"), t.rfind("}")
        if start >= 0 and end > start:
            d = json.loads(t[start:end + 1])
            if isinstance(d, dict) and d.get("caption"):
                return {"caption": str(d.get("caption")).strip(),
                        "hashtags": str(d.get("hashtags") or "").strip()}
    except Exception:  # noqa: BLE001
        pass
    return None
