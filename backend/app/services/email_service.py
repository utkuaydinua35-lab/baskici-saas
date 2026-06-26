"""E-posta gönderimi — generic SMTP (Gmail/hosting/SendGrid SMTP).

SMTP_* env'leri boşsa özellik kapalıdır (is_configured() False döner).
STARTTLS (587) varsayılan; 465 için SSL kullanılır.
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.config import get_settings

logger = logging.getLogger("email")


def is_configured() -> bool:
    s = get_settings()
    return bool(s.smtp_host and s.smtp_user and s.smtp_password)


def send_email(to: str, subject: str, html: str, text: str | None = None) -> bool:
    """E-posta gönder. Başarılıysa True. SMTP ayarlı değilse / hata olursa False."""
    s = get_settings()
    if not is_configured():
        logger.warning("[email] SMTP yapılandırılmamış — gönderilmedi")
        return False

    sender = s.smtp_from or s.smtp_user
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg.set_content(text or "Bu e-postayı görüntülemek için HTML destekli bir istemci kullanın.")
    msg.add_alternative(html, subtype="html")

    try:
        if int(s.smtp_port) == 465:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, context=ctx, timeout=20) as srv:
                srv.login(s.smtp_user, s.smtp_password)
                srv.send_message(msg)
        else:
            with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as srv:
                srv.starttls(context=ssl.create_default_context())
                srv.login(s.smtp_user, s.smtp_password)
                srv.send_message(msg)
        logger.info(f"[email] gönderildi -> {to} ({subject})")
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[email] gönderim hatası: {e}")
        return False
