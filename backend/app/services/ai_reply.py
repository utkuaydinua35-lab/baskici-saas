"""AI destek yanıtı — Claude API ile müşteri destek mesajlarına taslak cevap.

Operatör taslağı görür, düzenler ve gönderir (otomatik gönderilmez).
ANTHROPIC_API_KEY .env'de yoksa özellik sessizce kapalıdır (DraftError döner).
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import SupportMessage, SupportThread

logger = logging.getLogger("ai_reply")

MODEL = "claude-opus-4-8"
MAX_TOKENS = 1024
# Çok uzun konuşmalarda son N mesaj yeterli (taslak için bağlam)
MAX_HISTORY = 30

_SYSTEM = """Sen BERNZ adlı telefon kılıfı baskı atölyesinin Türkçe müşteri \
destek temsilcisisin. Görevin, müşterinin son mesajına gönderilmeye hazır, \
kibar ve net bir yanıt taslağı yazmak.

KURALLAR:
- Yalnızca Türkçe yaz.
- Sıcak, profesyonel ve çözüm odaklı bir ton kullan.
- Kısa ve öz ol; gereksiz dolgu cümleleri kurma.
- ASLA uydurma bilgi verme: kesin kargo tarihi, takip numarası, iade onayı, \
indirim gibi şeyleri kendin uydurma. Bu bilgiler gerekiyorsa "[kargo tarihi]" \
gibi köşeli parantezli yer tutucu bırak ki operatör doldursun.
- Müşterinin sorununu anladığını göster, sonra net bir sonraki adım sun.
- İmza veya "BERNZ Destek" gibi kapanış ekleme; sadece mesaj gövdesini yaz.
- Çıktında ön söz, açıklama veya tırnak kullanma — DOĞRUDAN müşteriye \
gönderilecek mesaj metnini yaz."""


class DraftError(Exception):
    """AI taslak üretilemedi (anahtar yok, API hatası vb.)."""


def _history_messages(db: Session, thread: SupportThread) -> list[dict]:
    rows = db.scalars(
        select(SupportMessage)
        .where(SupportMessage.thread_id == thread.id)
        .order_by(SupportMessage.created_at.asc())
    ).all()
    rows = rows[-MAX_HISTORY:]

    messages: list[dict] = []
    for m in rows:
        role = "user" if m.sender == "musteri" else "assistant"
        text = (m.body or "").strip()
        if m.image_url:
            note = "[müşteri bir görsel ekledi]" if m.sender == "musteri" else "[görsel eklendi]"
            text = f"{text}\n{note}".strip()
        if not text:
            continue
        messages.append({"role": role, "content": text})

    # Claude'un ilk mesajı 'user' olmalı; baştaki admin mesajlarını at
    while messages and messages[0]["role"] != "user":
        messages.pop(0)
    return messages


def draft_reply(db: Session, thread: SupportThread) -> str:
    """Konuşma geçmişinden bir admin yanıt taslağı üret. Hata olursa DraftError."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise DraftError("AI taslak özelliği yapılandırılmamış (ANTHROPIC_API_KEY yok).")

    history = _history_messages(db, thread)
    if not history:
        raise DraftError("Taslak için müşteri mesajı bulunamadı.")

    try:
        import anthropic
    except ModuleNotFoundError as e:
        raise DraftError("anthropic SDK kurulu değil.") from e

    # Sipariş bağlamını sistem promptuna ekle
    ctx_parts = []
    if thread.order_number:
        ctx_parts.append(f"Sipariş no: {thread.order_number}")
    if thread.customer_name:
        ctx_parts.append(f"Müşteri: {thread.customer_name}")
    system = _SYSTEM
    if ctx_parts:
        system = f"{_SYSTEM}\n\nBAĞLAM: {' · '.join(ctx_parts)}"

    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        resp = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=history,
            output_config={"effort": "low"},
        )
    except anthropic.APIError as e:
        logger.warning(f"[ai_reply] API hatası: {e}")
        raise DraftError("AI servisi şu anda yanıt veremedi, lütfen tekrar deneyin.") from e
    except Exception as e:  # noqa: BLE001
        logger.exception(f"[ai_reply] beklenmeyen hata: {e}")
        raise DraftError("Taslak üretilirken bir hata oluştu.") from e

    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
    if not text:
        raise DraftError("AI boş bir taslak döndürdü, lütfen tekrar deneyin.")
    return text
