"""
Telegram bildirim servisi (Paket 4).

Yeni müşteri destek mesajında Utku'ya anlık bildirim. Token/chat_id .env'den
gelir; ikisi de doluysa gönderir, yoksa sessizce atlar. Hata olursa (Telegram
down, ağ vb.) sessiz geçer — asıl iş akışını (mesaj kaydı) ASLA bozmaz.
"""
from __future__ import annotations

import logging

import requests

from app.config import get_settings

logger = logging.getLogger("telegram")


def send_message(text: str) -> bool:
    s = get_settings()
    token = (s.telegram_bot_token or "").strip()
    chat_id = (s.telegram_chat_id or "").strip()
    if not token or not chat_id:
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=8,
        )
        if r.status_code != 200:
            logger.warning(f"[telegram] sendMessage HTTP {r.status_code}: {r.text[:160]}")
            return False
        return True
    except Exception as e:
        logger.warning(f"[telegram] gönderilemedi: {e}")
        return False


def notify_support_message(order_number: str | None, shopify_order_id: str,
                           body: str, has_image: bool = False,
                           thread_id: str | None = None) -> bool:
    """Yeni müşteri destek mesajı bildirimi (panel deep-link ile)."""
    ref = order_number or shopify_order_id
    preview = (body or "").strip()
    if len(preview) > 300:
        preview = preview[:300] + "…"
    img = " 📷" if has_image else ""
    base = (get_settings().panel_base_url or "").rstrip("/")
    link = f"{base}/destek?thread={thread_id}" if (base and thread_id) else (f"{base}/destek" if base else "")
    link_line = f'\n\n<a href="{link}">↳ Talebi aç ve cevapla</a>' if link else ""
    text = (
        f"🔔 <b>Yeni Destek Mesajı</b>{img}\n"
        f"Sipariş: <b>#{ref}</b>\n\n"
        f"{preview or '(görsel)'}"
        f"{link_line}"
    )
    return send_message(text)
