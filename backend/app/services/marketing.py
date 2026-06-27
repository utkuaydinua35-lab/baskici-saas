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
from app.models import MarketingSubscriber, Tenant
from app.services import email_service

logger = logging.getLogger("marketing")

CONSENT_TEXT = "Kampanya, yeni ürün ve bilgilendirme e-postaları almak için açık rıza verdim."
_JOIN_SALT = "mkt-join"
_JOIN_MAX_AGE = 60 * 60 * 24 * 120  # 120 gün


def _signer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().session_secret, salt=_JOIN_SALT)


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
    db.commit()
    db.refresh(sub)
    return sub


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
