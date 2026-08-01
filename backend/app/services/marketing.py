"""Pazarlama abone servisi — KVKK uyumlu (çift opt-in + açık rıza kaydı).

Abone olma yolları:
- E-posta linki (sipariş/destek maili): müşteri kendi gelen kutusundan tıklar →
  e-posta sahipliği zaten doğru → direkt 'subscribed' + rıza kaydı.
- Public form / panelden manuel: e-posta sahipliği doğrulanmadığı için 'pending' +
  onay maili (çift opt-in) → onay linki tıklanınca 'subscribed' + rıza kaydı.

Her durumda rıza kanıtı (consent_at/ip/text) saklanır; her abonenin kalıcı
unsubscribe_token'ı vardır (her e-postada 'abonelikten çık' linki).
"""
from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import func as safunc
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import MarketingCampaign, MarketingSend, MarketingSubscriber, Tenant
from app.services import email_service

logger = logging.getLogger("marketing")

CONSENT_TEXT = "Kampanya, yeni ürün ve bilgilendirme e-postaları almak için açık rıza verdim."
_JOIN_SALT = "mkt-join"
_JOIN_MAX_AGE = 60 * 60 * 24 * 120  # 120 gün


def _signer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().session_secret, salt=_JOIN_SALT)


_LINK_SALT = "mkt-link"


def _link_signer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().session_secret, salt=_LINK_SALT)


def _track_link(base: str, send_id: str | None, url: str) -> str:
    """Linki tıklama-takip endpoint'ine sar (imzalı hedef → open-redirect yok).
    send_id yoksa (önizleme) linki olduğu gibi döndürür."""
    if not url:
        return ""
    if not send_id:
        return url
    return f"{base}/api/pazarlama/t/{send_id}?u={_link_signer().dumps(url)}"


def unsign_link(token: str) -> str | None:
    try:
        return _link_signer().loads(token, max_age=60 * 60 * 24 * 60)
    except (BadSignature, SignatureExpired):
        return None


def _base() -> str:
    return (get_settings().panel_base_url or "").rstrip("/")


def _norm_email(e: str | None) -> str:
    return (e or "").strip().lower()


# ─── Link üreticiler ─────────────────────────────────────────

def build_join_token(tenant_id, email: str, name: str = "", source: str = "order_mail") -> str:
    return _signer().dumps({"t": str(tenant_id), "e": _norm_email(email), "n": name or "", "s": source})


def join_url(tenant_id, email: str, name: str = "", source: str = "order_mail") -> str:
    return f"{_base()}/api/pazarlama/katil/{build_join_token(tenant_id, email, name, source)}"


def unsubscribe_url(sub: MarketingSubscriber) -> str:
    return f"{_base()}/api/pazarlama/cik/{sub.unsubscribe_token}"


def consume_join_token(token: str) -> dict | None:
    try:
        return _signer().loads(token, max_age=_JOIN_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


# ─── Çekirdek ────────────────────────────────────────────────

def _get(db: Session, tenant_id, email: str) -> MarketingSubscriber | None:
    return db.scalar(select(MarketingSubscriber).where(
        MarketingSubscriber.tenant_id == tenant_id,
        MarketingSubscriber.email == _norm_email(email),
    ))


def _ensure_unsub(sub: MarketingSubscriber) -> None:
    if not sub.unsubscribe_token:
        sub.unsubscribe_token = secrets.token_urlsafe(24)


def _record_consent(sub: MarketingSubscriber, ip: str | None) -> None:
    sub.consent_at = datetime.now(UTC)
    sub.consent_ip = (ip or "")[:60]
    sub.consent_text = CONSENT_TEXT


def subscribe_confirmed(db: Session, tenant_id, email: str, name: str, source: str, ip: str | None) -> MarketingSubscriber | None:
    """Doğrulanmış abone (e-posta linki tıklaması) -> direkt subscribed + rıza."""
    email = _norm_email(email)
    if not email or "@" not in email:
        return None
    sub = _get(db, tenant_id, email)
    if not sub:
        sub = MarketingSubscriber(tenant_id=tenant_id, email=email, name=name or None, source=source)
        db.add(sub)
    if sub.status != "subscribed":
        sub.status = "subscribed"
        sub.confirmed_at = datetime.now(UTC)
        _record_consent(sub, ip)
    if name and not sub.name:
        sub.name = name
    sub.confirm_token = None
    sub.unsubscribed_at = None
    _ensure_unsub(sub)
    db.commit()
    db.refresh(sub)
    return sub


def subscribe_public(db: Session, tenant_id, email: str, name: str, ip: str | None) -> tuple[MarketingSubscriber | None, str]:
    """Public form / manuel -> pending + çift opt-in onay maili. (sub, durum)."""
    email = _norm_email(email)
    if not email or "@" not in email:
        return None, "invalid"
    sub = _get(db, tenant_id, email)
    if sub and sub.status == "subscribed":
        return sub, "already"
    if not sub:
        sub = MarketingSubscriber(tenant_id=tenant_id, email=email, name=name or None, source="public_form")
        db.add(sub)
    sub.status = "pending"
    sub.confirm_token = secrets.token_urlsafe(24)
    if name and not sub.name:
        sub.name = name
    _ensure_unsub(sub)
    db.commit()
    db.refresh(sub)
    _send_confirm_email(db, sub)
    return sub, "pending"


def confirm(db: Session, token: str, ip: str | None) -> MarketingSubscriber | None:
    sub = db.scalar(select(MarketingSubscriber).where(MarketingSubscriber.confirm_token == token)) if token else None
    if not sub:
        return None
    if sub.status != "subscribed":
        sub.status = "subscribed"
        sub.confirmed_at = datetime.now(UTC)
        _record_consent(sub, ip)
    sub.confirm_token = None
    sub.unsubscribed_at = None
    _ensure_unsub(sub)
    db.commit()
    db.refresh(sub)
    return sub


def unsubscribe(db: Session, token: str) -> MarketingSubscriber | None:
    sub = db.scalar(select(MarketingSubscriber).where(MarketingSubscriber.unsubscribe_token == token)) if token else None
    if not sub:
        return None
    sub.status = "unsubscribed"
    sub.unsubscribed_at = datetime.now(UTC)
    sync_customer_flag(db, sub.tenant_id, sub.email, False)
    db.commit()
    db.refresh(sub)
    return sub


# ─── Vitrin müşteri kaydıyla eşitleme ────────────────────────
# Vitrin bülten formu Customer.accepts_marketing'e yazar, kampanyalar ise
# marketing_subscribers'tan gönderir. İki liste eşitlenmezse vitrinden
# abone olan müşteri hiçbir kampanyayı ALMAZ (ya da abonelikten çıkan
# müşteriye kampanya GİTMEYE devam eder).

def sync_customer_flag(db: Session, tenant_id, email: str, subscribed: bool) -> None:
    """Abone durumunu Customer.accepts_marketing'e yansıt (commit etmez)."""
    from app.models import Customer

    email = _norm_email(email)
    if not email:
        return
    customer = db.scalar(select(Customer).where(
        Customer.tenant_id == tenant_id, Customer.email == email))
    if not customer:
        return
    customer.accepts_marketing = subscribed
    if subscribed and not customer.marketing_opted_at:
        customer.marketing_opted_at = datetime.now(UTC)
    elif not subscribed:
        customer.marketing_opted_at = None


def sync_from_customer(db: Session, tenant_id, email: str, name: str | None,
                       subscribed: bool, ip: str | None = None,
                       source: str = "vitrin") -> None:
    """Vitrin tarafındaki abonelik değişikliğini kampanya listesine yansıt.

    Vitrin formunda KVKK onayı açıkça alındığı için doğrudan 'subscribed'
    kabul edilir (ikinci bir onay maili istenmez); rıza kanıtı yazılır.
    """
    try:
        if subscribed:
            subscribe_confirmed(db, tenant_id, email, name or "", source, ip)
        else:
            sub = _get(db, tenant_id, _norm_email(email))
            if sub and sub.status != "unsubscribed":
                sub.status = "unsubscribed"
                sub.unsubscribed_at = datetime.now(UTC)
                db.commit()
    except Exception:  # noqa: BLE001 — eşitleme hatası vitrin akışını bozmaz
        logger.warning("[marketing] abone eşitlenemedi: %s", email)


def counts(db: Session, tenant_id) -> dict:
    rows = db.execute(
        select(MarketingSubscriber.status, safunc.count())
        .where(MarketingSubscriber.tenant_id == tenant_id)
        .group_by(MarketingSubscriber.status)
    ).all()
    d = {s: int(c) for s, c in rows}
    return {
        "total": sum(d.values()),
        "subscribed": d.get("subscribed", 0),
        "pending": d.get("pending", 0),
        "unsubscribed": d.get("unsubscribed", 0),
    }


def _send_confirm_email(db: Session, sub: MarketingSubscriber) -> bool:
    if not email_service.is_configured() or not sub.confirm_token:
        return False
    tenant = db.get(Tenant, sub.tenant_id)
    confirm_link = f"{_base()}/api/pazarlama/onay/{sub.confirm_token}"
    ad = (sub.name or "").split()[0] if sub.name else ""
    body = (
        f"<p style='margin:0 0 14px'>Merhaba {ad},</p>"
        "<p style='margin:0 0 14px'>Kampanya, yeni ürün ve bilgilendirme e-postalarımıza "
        "abone olmak üzeresiniz. Aboneliğinizi tamamlamak için aşağıdaki butona tıklayın.</p>"
        "<p style='margin:0;font-size:13px;color:#6b7280'>Onaylamadığınız sürece size e-posta göndermeyiz.</p>"
    )
    html = email_service.render_email(
        title="Aboneliğini onayla",
        emoji="📩",
        body_html=body,
        button_text="Aboneliğimi Onayla",
        button_url=confirm_link,
        preheader="Tek adım kaldı — aboneliğini onayla",
        footer="Bu e-postayı siz talep etmediyseniz yok sayabilirsiniz.",
        **email_service.brand_kwargs(tenant),
    )
    text = f"Aboneliğini onaylamak için: {confirm_link}"
    return email_service.send_email(sub.email, "Aboneliğini onayla", html, text)


# ─── Kampanya (Faz 2) ────────────────────────────────────────

def _body_to_html(text: str | None) -> str:
    from html import escape
    text = (text or "").strip()
    if not text:
        return ""
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    return "".join(
        "<p style='margin:0 0 14px'>" + escape(p).replace("\n", "<br>") + "</p>"
        for p in paras
    )


def _campaign_plain(camp: MarketingCampaign) -> str:
    parts = [camp.title or camp.subject, "", (camp.body or "")]
    if camp.button_url:
        parts += ["", f"{camp.button_label or 'Bağlantı'}: {camp.button_url}"]
    return "\n".join(parts)


def _render_products(products, base: str, tracking_send_id: str | None, escape) -> str:
    """Ürün kartları ızgarası (2 sütun) — görsel + başlık, kart tıklanınca ürüne gider."""
    items = [p for p in (products or [])
             if isinstance(p, dict) and ((p.get("image") or "").strip() or (p.get("title") or "").strip())]
    if not items:
        return ""
    cells = []
    for p in items:
        img = (p.get("image") or "").strip()
        if img.startswith("/"):
            img = base + img
        title = escape((p.get("title") or "").strip())
        url = _track_link(base, tracking_send_id, (p.get("url") or "").strip())
        inner = ""
        if img:
            inner += f"<img src='{escape(img)}' alt='' style='width:100%;border-radius:10px;display:block'>"
        if title:
            inner += f"<div style='font-size:14px;color:#374151;margin-top:8px;line-height:1.4'>{title}</div>"
        if url:
            inner = f"<a href='{url}' style='text-decoration:none;color:inherit;display:block'>{inner}</a>"
        cells.append(inner)
    rows = []
    for i in range(0, len(cells), 2):
        pair = cells[i:i + 2]
        tds = "".join(f"<td width='50%' valign='top' style='padding:6px'>{c}</td>" for c in pair)
        if len(pair) == 1:
            tds += "<td width='50%'></td>"
        rows.append(f"<tr>{tds}</tr>")
    return ("<table role='presentation' width='100%' cellpadding='0' cellspacing='0' border='0' "
            "style='margin:10px 0 4px'>" + "".join(rows) + "</table>")


def render_campaign_email(tenant, camp: MarketingCampaign, unsubscribe_link: str,
                          *, tracking_send_id: str | None = None, recipient_name: str = "") -> str:
    from html import escape
    base = _base()
    parts: list[str] = []
    # İsimle kişiselleştirme
    if camp.personalize and (recipient_name or "").strip():
        parts.append(f"<p style='margin:0 0 14px'>Merhaba {escape(recipient_name.split()[0])},</p>")
    # Üst görsel (/storage göreli ise mutlaklaştır)
    if camp.image_url:
        img = camp.image_url
        if img.startswith("/"):
            img = base + img
        parts.append(f"<p style='margin:0 0 16px'><img src='{escape(img)}' alt='' "
                     "style='max-width:100%;border-radius:12px;display:block'></p>")
    parts.append(_body_to_html(camp.body))
    # Ürün kartları ızgarası
    prods = _render_products(getattr(camp, "products", None) or [], base, tracking_send_id, escape)
    if prods:
        parts.append(prods)
    body = "".join(parts)

    # Buton linki tıklama-takip ile sarılır (imzalı hedef)
    btn_url = _track_link(base, tracking_send_id, camp.button_url or "")
    # Açılma takibi: görünmez 1x1 pixel
    if tracking_send_id:
        body += (f"<img src='{base}/api/pazarlama/a/{tracking_send_id}' width='1' height='1' "
                 "alt='' style='display:none;width:1px;height:1px'>")
    footer = (
        "Bu e-postayı, pazarlama iletilerimize abone olduğunuz için aldınız. "
        f"<a href='{unsubscribe_link}' style='color:#9ca3af'>Abonelikten çık</a>"
    )
    return email_service.render_email(
        title=camp.title or camp.subject,
        body_html=body,
        button_text=camp.button_label or "",
        button_url=btn_url,
        preheader=camp.preheader or camp.subject,
        footer=footer,
        **email_service.brand_kwargs(tenant),
    )


def send_test(db: Session, camp: MarketingCampaign, to_email: str) -> bool:
    to_email = _norm_email(to_email)
    if not to_email or "@" not in to_email:
        return False
    tenant = db.get(Tenant, camp.tenant_id)
    html = render_campaign_email(tenant, camp, f"{_base()}/api/pazarlama/cik/test")
    return email_service.send_email(to_email, f"[TEST] {camp.subject}", html, _campaign_plain(camp))


def start_campaign(db: Session, camp: MarketingCampaign) -> tuple[bool, str]:
    if camp.status == "sending":
        return False, "Kampanya zaten gönderiliyor"
    if camp.status == "sent":
        return False, "Bu kampanya zaten gönderilmiş"
    if not email_service.is_configured():
        return False, "SMTP yapılandırılmamış"
    n = db.scalar(
        select(safunc.count()).select_from(MarketingSubscriber).where(
            MarketingSubscriber.tenant_id == camp.tenant_id,
            MarketingSubscriber.status == "subscribed",
        )
    ) or 0
    if not n:
        return False, "Onaylı abone yok"
    camp.status = "sending"
    camp.recipient_count = int(n)
    camp.sent_count = 0
    camp.fail_count = 0
    db.commit()
    import threading
    threading.Thread(target=_send_campaign_worker, args=(str(camp.id),), daemon=True).start()
    return True, f"{n} aboneye gönderim başladı"


def _send_campaign_worker(campaign_id: str) -> None:
    import time
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        camp = db.get(MarketingCampaign, campaign_id)
        if not camp:
            return
        tenant = db.get(Tenant, camp.tenant_id)
        subs = db.scalars(
            select(MarketingSubscriber).where(
                MarketingSubscriber.tenant_id == camp.tenant_id,
                MarketingSubscriber.status == "subscribed",
            )
        ).all()
        sent = fail = 0
        for sub in subs:
            send = MarketingSend(campaign_id=camp.id, subscriber_id=sub.id, email=sub.email)
            db.add(send)
            db.flush()  # send.id (tracking token)
            unsub = unsubscribe_url(sub)
            html = render_campaign_email(tenant, camp, unsub, tracking_send_id=str(send.id),
                                         recipient_name=sub.name or "")
            ok = email_service.send_email(
                sub.email, camp.subject, html, _campaign_plain(camp),
                headers={"List-Unsubscribe": f"<{unsub}>"},
            )
            send.status = "sent" if ok else "failed"
            send.sent_at = datetime.now(UTC) if ok else None
            sent += 1 if ok else 0
            fail += 0 if ok else 1
            if (sent + fail) % 20 == 0:
                camp.sent_count, camp.fail_count = sent, fail
                db.commit()
            time.sleep(0.4)  # Gmail'i yormamak için
        camp.sent_count, camp.fail_count = sent, fail
        camp.status = "sent"
        camp.sent_at = datetime.now(UTC)
        db.commit()
        logger.info(f"[marketing] kampanya {campaign_id}: {sent} gönderildi, {fail} hata")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[marketing] kampanya worker hatası: {e}")
        try:
            c = db.get(MarketingCampaign, campaign_id)
            if c and c.status == "sending":
                c.status = "failed"
                db.commit()
        except Exception:  # noqa: BLE001
            pass
    finally:
        db.close()


# ─── Açılma / tıklama takibi ─────────────────────────────────

def _get_send(db: Session, send_id: str) -> MarketingSend | None:
    import uuid as _uuid
    try:
        sid = _uuid.UUID(send_id)
    except (ValueError, AttributeError):
        return None
    return db.get(MarketingSend, sid)


def record_open(db: Session, send_id: str) -> None:
    send = _get_send(db, send_id)
    if not send:
        return
    first = send.opened_at is None
    if first:
        send.opened_at = datetime.now(UTC)
        camp = db.get(MarketingCampaign, send.campaign_id)
        if camp:
            camp.open_count = (camp.open_count or 0) + 1
    send.open_count = (send.open_count or 0) + 1
    db.commit()


def record_click(db: Session, send_id: str, signed_url: str | None = None) -> str | None:
    """Tıklamayı kaydet, yönlendirilecek hedef URL'i döndür (imzalı link veya buton)."""
    send = _get_send(db, send_id)
    if not send:
        return None
    camp = db.get(MarketingCampaign, send.campaign_id)
    # Tıklama aynı zamanda açılma sayılır
    if send.opened_at is None:
        send.opened_at = datetime.now(UTC)
        if camp:
            camp.open_count = (camp.open_count or 0) + 1
    if send.clicked_at is None:
        send.clicked_at = datetime.now(UTC)
        if camp:
            camp.click_count = (camp.click_count or 0) + 1
    send.click_count = (send.click_count or 0) + 1
    db.commit()
    target = unsign_link(signed_url) if signed_url else None
    if not target and camp:
        target = camp.button_url
    return target or None



def backfill_from_customers(db: Session, tenant_id, *, dry_run: bool = True) -> dict:
    """Vitrinden abone olmuş müşterileri kampanya listesine taşı.

    Bu özellik eklenmeden ÖNCE bültene kaydolanlar yalnızca Customer
    tablosundaydı; kampanya gönderiminde atlanıyorlardı. Rıza kanıtı olarak
    müşterinin kendi opt-in tarihi (marketing_opted_at) yazılır — yeni bir
    rıza uydurulmaz, var olan kayıt taşınır.
    """
    from app.models import Customer

    aday = db.scalars(select(Customer).where(
        Customer.tenant_id == tenant_id,
        Customer.accepts_marketing.is_(True),
        Customer.email.isnot(None),
    )).all()

    eklenecek, mevcut, atlanan = [], 0, 0
    for c in aday:
        email = _norm_email(c.email)
        if not email or "@" not in email:
            atlanan += 1
            continue
        sub = _get(db, tenant_id, email)
        if sub:
            mevcut += 1
            continue
        eklenecek.append((email, c.name, c.marketing_opted_at))

    if not dry_run:
        for email, name, opted_at in eklenecek:
            sub = MarketingSubscriber(
                tenant_id=tenant_id, email=email, name=name or None,
                source="vitrin_bulten", status="subscribed",
                confirmed_at=opted_at or datetime.now(UTC),
                consent_at=opted_at or datetime.now(UTC),
                consent_text=CONSENT_TEXT,
            )
            _ensure_unsub(sub)
            db.add(sub)
        db.commit()

    return {
        "aday": len(aday),
        "eklendi": 0 if dry_run else len(eklenecek),
        "eklenecek": len(eklenecek),
        "zaten_vardi": mevcut,
        "gecersiz_email": atlanan,
        "dry_run": dry_run,
    }
