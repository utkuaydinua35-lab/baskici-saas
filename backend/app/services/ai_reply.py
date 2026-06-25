"""AI destek yanıtı — Claude API ile müşteri destek mesajlarına taslak cevap.

Operatör taslağı görür, düzenler ve gönderir (otomatik gönderilmez).
ANTHROPIC_API_KEY .env'de yoksa özellik sessizce kapalıdır (DraftError döner).
"""
from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import SupportMessage, SupportThread, Tenant

logger = logging.getLogger("ai_reply")

# Kullanici secimi -> gercek model ID (settings'te haiku|sonnet|opus tutulur)
MODEL_MAP = {
    "haiku": "claude-haiku-4-5",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-8",
}
DEFAULT_MODEL_KEY = "opus"
MAX_TOKENS = 1024
# Çok uzun konuşmalarda son N mesaj yeterli (taslak için bağlam)
MAX_HISTORY = 30

_SYSTEM = """Sen BERNZ adlı telefon kılıfı baskı atölyesinin Türkçe müşteri \
destek temsilcisisin. Müşterinin son mesajı için İKİ şey üretirsin: bir yanıt \
taslağı (draft) ve operatöre kısa bir not (note).

DRAFT (müşteriye gönderilmeye hazır yanıt):
- KARARLI ve NET ol. Tereddüt etme; operatöre ya da müşteriye gereksiz soru sorma.
- Doğrudan, çözüm odaklı, sıcak ve profesyonel; kısa tut.
- ASLA uydurma bilgi verme: kesin kargo tarihi, takip numarası, iade onayı, \
indirim gibi emin olmadığın şeyleri uydurma. Gerekiyorsa "[kargo tarihi]" gibi \
köşeli parantezli yer tutucu bırak; operatör doldurur.
- İmza veya "BERNZ Destek" gibi kapanış ekleme; sadece mesaj gövdesi.

NOTE (yalnızca operatöre, müşteriye GÖSTERİLMEZ):
- draft içinde operatörün doldurması gereken yer tutucuları ve karar vermesi \
gereken konuları kısa madde madde özetle (ör. "• [kargo tarihi] doldur  • \
İade onayı verilecek mi karar ver").
- Doldurulacak veya karar verilecek bir şey yoksa boş string ("") döndür.

Her ikisini de yalnızca Türkçe yaz."""

# Yapılandırılmış çıktı şeması (draft + note garantili JSON)
_FORMAT = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "draft": {"type": "string"},
            "note": {"type": "string"},
        },
        "required": ["draft", "note"],
        "additionalProperties": False,
    },
}


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


def draft_reply(db: Session, thread: SupportThread) -> dict:
    """Konuşma geçmişinden {draft, note} üret. Hata olursa DraftError.

    draft: müşteriye gönderilmeye hazır yanıt.
    note:  operatöre kısa not (doldurulacak/karar verilecek konular; yoksa "").
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise DraftError("AI taslak özelliği yapılandırılmamış (ANTHROPIC_API_KEY yok).")

    # Tenant ayari: AI acik mi + hangi model
    tenant = db.get(Tenant, thread.tenant_id) if thread.tenant_id else None
    if tenant is not None and not tenant.ai_reply_enabled:
        raise DraftError("AI yanıt özelliği kapalı. Ayarlar > AI Destek'ten açın.")
    model_key = (getattr(tenant, "ai_reply_model", None) or DEFAULT_MODEL_KEY)
    model = MODEL_MAP.get(model_key, MODEL_MAP[DEFAULT_MODEL_KEY])

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
        # Yapılandırılmış çıktı: {draft, note}. effort yalnizca opus/sonnet'te
        # desteklenir (haiku'da 400 verir) — format ile birlikte gonderiyoruz.
        output_config = {"format": _FORMAT}
        if model_key in ("opus", "sonnet"):
            output_config["effort"] = "low"
        resp = client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=history,
            output_config=output_config,
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

    # output_config.format JSON garantiler; yine de güvenli parse + fallback
    try:
        data = json.loads(text)
        draft = (data.get("draft") or "").strip()
        note = (data.get("note") or "").strip()
    except (json.JSONDecodeError, AttributeError):
        draft, note = text, ""

    if not draft:
        raise DraftError("AI boş bir taslak döndürdü, lütfen tekrar deneyin.")
    return {"draft": draft, "note": note}
