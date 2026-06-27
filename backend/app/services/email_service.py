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


# ─── Şık e-posta şablonu (tüm e-postalar ortak görünüm) ──────────────
DEFAULT_ACCENT = "#6d28d9"


def brand_kwargs(tenant) -> dict:
    """Tenant'tan render_email marka parametreleri (brand, accent, logo_url).
    Tenant yoksa boş döner -> render_email varsayılan BERNZ/mor kullanır."""
    if not tenant:
        return {}
    out: dict = {}
    name = getattr(tenant, "app_name", None) or getattr(tenant, "name", None)
    if name:
        out["brand"] = name
    bc = (getattr(tenant, "brand_color", None) or "").strip()
    if bc and not bc.startswith("#"):
        bc = "#" + bc
    if bc:
        out["accent"] = bc
    if getattr(tenant, "logo_url", None):
        out["logo_url"] = tenant.logo_url
    return out


def highlight_box(inner_html: str, accent: str = DEFAULT_ACCENT) -> str:
    """İçeriği vurgulu (sol kenarlıklı, açık zeminli) bir kutuya sar."""
    return (
        f'<div style="background:#f7f6fe;border-left:4px solid {accent};'
        f'border-radius:10px;padding:14px 18px;margin:6px 0 18px;'
        f'font-size:15px;color:#374151;line-height:1.6">{inner_html}</div>'
    )


def render_email(
    *,
    title: str,
    body_html: str,
    button_text: str = "",
    button_url: str = "",
    footer: str = "Bu otomatik bir e-postadır.",
    preheader: str = "",
    brand: str = "BERNZ",
    accent: str = DEFAULT_ACCENT,
    emoji: str = "",
    logo_url: str = "",
) -> str:
    """Markalı, responsive, email-client uyumlu HTML e-posta üret.

    body_html: gövde içeriği (paragraflar + opsiyonel highlight_box()).
    button_*: opsiyonel CTA butonu. preheader: gelen kutusu önizleme metni.
    logo_url: marka logosu ('/storage/...' göreli ise panel_base_url ile mutlaklaşır).
    """
    initial = (brand or "B").strip()[:1].upper() or "B"
    # Logo varsa beyaz yuvarlak çip içinde (her renkte görünür); yoksa baş harf rozeti
    logo = (logo_url or "").strip()
    if logo.startswith("/"):
        logo = get_settings().panel_base_url.rstrip("/") + logo
    if logo:
        brand_mark = (
            '<span style="display:inline-block;background:#ffffff;border-radius:9px;'
            'padding:6px 10px;vertical-align:middle;">'
            f'<img src="{logo}" alt="{brand}" height="24" '
            'style="height:24px;width:auto;max-width:130px;display:block;border:0;"></span>'
        )
    else:
        brand_mark = (
            '<span style="display:inline-block;width:36px;height:36px;line-height:36px;'
            'text-align:center;background:rgba(255,255,255,.20);border-radius:10px;color:#ffffff;'
            f'font-weight:700;font-size:19px;vertical-align:middle;">{initial}</span>'
        )
    pre = (
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;'
        f'mso-hide:all">{preheader}</div>'
    ) if preheader else ""
    btn = ""
    if button_text and button_url:
        btn = f"""
              <tr><td align="center" style="padding:6px 0 2px">
                <a href="{button_url}" style="display:inline-block;background:{accent};
                   color:#ffffff;text-decoration:none;font-weight:600;font-size:15px;
                   padding:13px 30px;border-radius:10px">{button_text}</a>
              </td></tr>"""
    head_emoji = f'{emoji} ' if emoji else ""
    return f"""<!doctype html>
<html lang="tr"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light only">
<meta name="supported-color-schemes" content="light only">
</head>
<body style="margin:0;padding:0;background:#eef0f4;-webkit-font-smoothing:antialiased;">
{pre}
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#eef0f4;padding:28px 12px;">
  <tr><td align="center">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:540px;background:#ffffff;border-radius:18px;overflow:hidden;font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;box-shadow:0 4px 24px rgba(17,24,39,.06);">
      <tr><td style="background:{accent};padding:22px 30px;">
        {brand_mark}
        <span style="color:#ffffff;font-size:18px;font-weight:600;letter-spacing:.3px;margin-left:11px;vertical-align:middle;">{brand}</span>
      </td></tr>
      <tr><td style="padding:30px 30px 26px;">
        <h1 style="margin:0 0 18px;font-size:21px;line-height:1.3;color:#111827;font-weight:700;">{head_emoji}{title}</h1>
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr><td style="font-size:15px;color:#374151;line-height:1.65;">{body_html}</td></tr>
          {btn}
        </table>
      </td></tr>
      <tr><td style="padding:16px 30px;border-top:1px solid #f0f1f3;background:#fafafb;">
        <p style="margin:0;font-size:12px;color:#9ca3af;line-height:1.5;">{footer}</p>
      </td></tr>
    </table>
    <p style="margin:14px 0 0;font-size:11px;color:#aab0bb;font-family:-apple-system,'Segoe UI',Roboto,Arial,sans-serif;">© {brand}</p>
  </td></tr>
</table>
</body></html>"""
