"""Otomatik e-posta akışları — hoş geldin + yorum daveti.

Shopify'da bunlar ayrı uygulama (Klaviyo/Judge.me) gerektirir; burada
yerleşiktir. İkisi de KVKK-güvenli: tek seferlik, opt-out edilebilir,
tekrar göndermez (idempotent işaretler).

1) Hoş geldin: bültene abone olan müşteriye hemen indirim kodu.
2) Yorum daveti: sipariş TESLİM edildikten N gün sonra "değerlendirin".
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Customer, DiscountCode, Order, Store
from app.services import email_service

logger = logging.getLogger("email_flows")

WELCOME_DEFAULT_PERCENT = 10
WELCOME_VALID_DAYS = 30
REVIEW_INVITE_DAYS = 7        # teslimden kaç gün sonra
REVIEW_INVITE_MAX_AGE = 45    # bu kadar eski siparişlere hiç gönderme


def _site(store: Store) -> str:
    config = store.config or {}
    return (config.get("storefront_url")
            or f"https://{config.get('shop_domain', '')}").rstrip("/")


# ─── 1) Hoş geldin (bülten kaydı) ────────────────────────────

def _make_welcome_code(db: Session, store: Store, percent: int) -> DiscountCode:
    """Kişiye özel tek kullanımlık indirim kodu üretir."""
    code = f"HOSGELDIN{secrets.token_hex(3).upper()}"
    dc = DiscountCode(
        tenant_id=store.tenant_id, store_id=store.id, code=code,
        kind="percent", value=Decimal(str(percent)),
        usage_limit=1, usage_count=0, once_per_customer=True,
        ends_at=datetime.now(timezone.utc) + timedelta(days=WELCOME_VALID_DAYS),
        is_active=True,
    )
    db.add(dc)
    db.flush()
    return dc


def send_welcome(db: Session, store: Store, customer: Customer) -> bool:
    """Bültene yeni abone olana hoş geldin + indirim kodu. Tek sefer."""
    config = store.config or {}
    if not config.get("welcome_email_enabled", True):
        return False
    if not customer.email or customer.welcome_sent_at:
        return False
    if not email_service.is_configured():
        return False

    percent = int(config.get("welcome_discount_percent") or WELCOME_DEFAULT_PERCENT)
    site = _site(store)
    dc = _make_welcome_code(db, store, percent)
    brand = email_service.store_brand_kwargs(store)

    subject, intro = email_service.store_email_text(store, "hosgeldin")
    html = email_service.render_email(
        title=subject or f"Aramıza hoş geldiniz — %{percent} indirim 🎁",
        body_html=(
            (intro or
             "<p>Bültenimize katıldığınız için teşekkürler! İlk siparişinizde "
             "kullanabileceğiniz indirim kodunuz hazır:</p>")
            + f"<p style='font-size:22px;font-weight:700;letter-spacing:2px;"
              f"text-align:center;padding:14px;background:#f6f6f7;border-radius:12px'>"
              f"{dc.code}</p>"
            + f"<p style='text-align:center;color:#6d7175;font-size:13px'>"
              f"%{percent} indirim · {WELCOME_VALID_DAYS} gün geçerli · tek kullanımlık</p>"
        ),
        button_text="Alışverişe Başla",
        button_url=f"{site}/urunler?kupon={dc.code}",
        preheader=f"%{percent} indirim kodunuz içeride",
        emoji="🎁",
        **brand,
    )
    ok = email_service.send_email(
        customer.email, subject or f"Aramıza hoş geldiniz — %{percent} indirim 🎁", html)
    if ok:
        customer.welcome_sent_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("[flows] hoş geldin gönderildi -> %s (%s)", customer.email, dc.code)
    return ok


# ─── 2) Yorum daveti (teslimden N gün sonra) ─────────────────

def _review_invite_html(store: Store, order: Order, site: str) -> tuple[str, str]:
    brand = email_service.store_brand_kwargs(store)
    subject, intro = email_service.store_email_text(store, "yorum_daveti")
    subject = subject or "Siparişinizi değerlendirir misiniz? ⭐"

    # Buton URL'i çağıran tarafta sipariş takip linkiyle değiştirilir
    body = (intro or
            f"<p>Merhaba,</p><p><b>{order.name or ''}</b> numaralı siparişiniz elinize "
            "ulaştı. Deneyiminizi paylaşır mısınız? Yorumunuz hem bize hem de "
            "diğer müşterilerimize çok yardımcı oluyor.</p>")
    html = email_service.render_email(
        title="Ürününüzü değerlendirin",
        body_html=body,
        button_text="Değerlendirme Yaz",
        button_url=f"{site}/urunler",
        preheader="30 saniyenizi alır ⭐",
        emoji="⭐",
        **brand,
    )
    return subject, html


def send_review_invites(db: Session) -> dict:
    """Teslim edilmiş ve N günü dolmuş siparişlere yorum daveti (tek sefer).

    Zamanlayıcı günde bir çağırır. Yalnız vitrin siparişleri, yalnız
    pazarlama iznine dokunmadan (işlem sonrası hizmet e-postası)."""
    from sqlalchemy import func as sa_func

    from app.models import CheckoutSession, OrderStatusHistory

    if not email_service.is_configured():
        return {"sent": 0, "skipped": "email_not_configured"}

    now = datetime.now(timezone.utc)
    due_before = now - timedelta(days=REVIEW_INVITE_DAYS)
    too_old = now - timedelta(days=REVIEW_INVITE_MAX_AGE)

    stores = {s.id: s for s in db.scalars(
        select(Store).where(Store.platform == "storefront")).all()}
    if not stores:
        return {"sent": 0}

    # Teslim ZAMANI: aşama geçmişindeki "9'a geçiş" kaydı (Order'da
    # updated_at yok; created_at_platform sipariş tarihi, teslim değil)
    delivered_at = (
        select(OrderStatusHistory.order_id,
               sa_func.max(OrderStatusHistory.created_at).label("at"))
        .where(OrderStatusHistory.to_stage == 9)
        .group_by(OrderStatusHistory.order_id).subquery()
    )
    orders = db.scalars(
        select(Order)
        .join(delivered_at, delivered_at.c.order_id == Order.id)
        .where(
            Order.store_id.in_(list(stores)),
            Order.current_stage == 9,                 # halen teslim durumunda
            Order.review_invite_sent_at.is_(None),
            delivered_at.c.at < due_before,           # N günü doldu
            delivered_at.c.at > too_old,              # ama çok eski değil
            Order.is_iptal.is_(False),
        ).limit(50)
    ).all()

    sent = 0
    for order in orders:
        store = stores.get(order.store_id)
        if not store or not (store.config or {}).get("review_invite_enabled", True):
            continue
        email = (order.customer_email or "").strip()
        if not email:
            continue
        site = _site(store)
        # Sipariş takip token'ı (yorum formu orada açılır)
        session = db.scalar(select(CheckoutSession).where(
            CheckoutSession.order_id == order.id))
        subject, html = _review_invite_html(store, order, site)
        if session and session.lookup_token:
            html = html.replace(f"{site}/urunler", f"{site}/siparis/{session.lookup_token}")
        if email_service.send_email(email, subject, html):
            order.review_invite_sent_at = now
            db.add(OrderStatusHistory(
                tenant_id=order.tenant_id, order_id=order.id,
                action="yorum_daveti", note="Yorum daveti e-postası gönderildi",
            ))
            sent += 1
    if sent:
        db.commit()
    logger.info("[flows] yorum daveti: %s gönderildi", sent)
    return {"sent": sent, "candidates": len(orders)}
