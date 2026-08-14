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
    return bool(s.resend_api_key) or bool(s.smtp_host and s.smtp_user and s.smtp_password)


def _send_resend(s, to: str, subject: str, html: str, text: str | None,
                 headers: dict | None) -> bool:
    """HTTPS (443) üzerinden Resend API ile gönder — SMTP portları kapalı VPS için."""
    import httpx
    sender = s.resend_from or s.smtp_from or s.smtp_user
    payload = {"from": sender, "to": [to], "subject": subject, "html": html}
    if text:
        payload["text"] = text
    if headers:
        payload["headers"] = {k: v for k, v in headers.items() if v}
    try:
        r = httpx.post(
            "https://api.resend.com/emails",
            json=payload,
            headers={"Authorization": f"Bearer {s.resend_api_key}"},
            timeout=20,
        )
        if r.status_code in (200, 201):
            logger.info(f"[email] gönderildi (resend) -> {to} ({subject})")
            return True
        logger.warning(f"[email] resend hata {r.status_code}: {r.text[:300]}")
        return False
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[email] resend gönderim hatası: {e}")
        return False


def send_email(to: str, subject: str, html: str, text: str | None = None,
               headers: dict | None = None) -> bool:
    """E-posta gönder. Başarılıysa True. Ayarlı değilse / hata olursa False.
    RESEND_API_KEY doluysa HTTPS API ile, değilse SMTP ile gönderir.
    headers: ek e-posta başlıkları (örn. List-Unsubscribe)."""
    s = get_settings()
    if not is_configured():
        logger.warning("[email] mail yapılandırılmamış — gönderilmedi")
        return False

    # SMTP portları kapalı VPS'lerde Resend (443) tercih edilir
    if s.resend_api_key:
        return _send_resend(s, to, subject, html, text, headers)

    sender = s.smtp_from or s.smtp_user
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    for k, v in (headers or {}).items():
        if v:
            msg[k] = v
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


def store_email_text(store, key: str) -> tuple[str | None, str | None]:
    """Panelden özelleştirilen e-posta metni: (subject, intro) — yoksa (None, None).

    intro, gövdenin başına ayrı paragraf olarak eklenir; subject varsayılanı ezer.
    """
    from xml.sax.saxutils import escape
    cfg = ((getattr(store, "config", None) or {}).get("email_texts") or {}).get(key) or {}
    subject = (cfg.get("subject") or "").strip() or None
    intro = (cfg.get("intro") or "").strip() or None
    return subject, (f"<p>{escape(intro)}</p>" if intro else None)


def store_brand_kwargs(store) -> dict:
    """MAĞAZANIN markası (ad, tema rengi, logo) — müşteriye giden e-postalar.

    Vitrin e-postalarında marka KİRACI değil MAĞAZA olmalı: aynı kurulumda
    birden fazla marka olabilir ve müşteri yalnız alışveriş yaptığı mağazayı
    tanır. Mağazanın teması yoksa kiracıya, o da yoksa boşa düşer (boş marka
    → e-postada marka satırı hiç basılmaz, yanlış marka görünmez).
    """
    if not store:
        return {}
    out: dict = {}
    ad = (getattr(store, "name", None) or "").strip()
    if ad:
        out["brand"] = ad
    try:
        from app.services.theme import resolve_theme
        th = resolve_theme(getattr(store, "config", None) or {})
        renk = (th.get("colors") or {}).get("primary")
        if renk:
            out["accent"] = renk
        if th.get("logo_url"):
            out["logo_url"] = th["logo_url"]
    except Exception:  # noqa: BLE001 — tema okunamazsa marka adı yeter
        pass
    if "accent" not in out or "logo_url" not in out:
        # Tema eksikse kiracının kurumsal renkleri yedek
        for k, v in brand_kwargs(getattr(store, "tenant", None)).items():
            out.setdefault(k, v)
    return out


def brand_kwargs(tenant) -> dict:
    """Tenant'tan render_email marka parametreleri (brand, accent, logo_url).
    Tenant yoksa boş döner -> render_email markasız (nötr) e-posta üretir."""
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
    brand: str = "",            # boşsa marka satırı basılmaz (bkz. store_brand_kwargs)
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
