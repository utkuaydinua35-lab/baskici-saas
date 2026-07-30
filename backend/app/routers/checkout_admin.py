"""
Terk Edilmiş Sepetler (admin) — /api/checkout-sessions/*

Ödemesi tamamlanmamış (pending/expired/failed) ama e-postası bilinen checkout
oturumları + tek seferlik hatırlatma e-postası.

KVKK: hatırlatma, müşterinin KENDİ başlattığı satın alma işleminin tek seferlik
bildirimi (meşru menfaat); PII 90 günlük saklama penceresi içinde zaten mevcut.
Session başına EN FAZLA 1 hatırlatma gönderilir (reminder_sent_at kilidi).
"""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.database import get_db
from app.models import CheckoutSession, Store, User
from app.services import checkout as checkout_svc
from app.services import email_service

router = APIRouter(
    prefix="/api/checkout-sessions", tags=["checkout-admin"],
    dependencies=[Depends(require_permission("vitrin"))],
)

ABANDONED_STATUSES = ("pending", "expired", "failed")


def _serialize(s: CheckoutSession) -> dict:
    cust = s.customer or {}
    return {
        "id": str(s.id),
        "status": s.status,
        "customer_name": f"{cust.get('first_name', '')} {cust.get('last_name', '')}".strip(),
        "email": cust.get("email"),
        "amount": str(s.amount),
        "item_count": sum(int(i.get("quantity", 1)) for i in (s.cart_snapshot or [])),
        "discount_code": s.discount_code,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "reminder_sent_at": s.reminder_sent_at.isoformat() if s.reminder_sent_at else None,
        "expires_at": s.expires_at.isoformat() if s.expires_at else None,
        # Taslaklar panelden link kopyalanabilsin diye lookup_token taşır
        "lookup_token": s.lookup_token if s.status == "draft" else None,
    }


@router.get("", response_model=dict)
def list_abandoned(
    store_id: uuid.UUID | None = Query(None),
    kind: str = Query("abandoned", pattern="^(abandoned|draft)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    statuses = ("draft",) if kind == "draft" else ABANDONED_STATUSES
    conds = [
        CheckoutSession.tenant_id == user.tenant_id,
        CheckoutSession.status.in_(statuses),
        CheckoutSession.order_id.is_(None),
        CheckoutSession.customer["email"].astext != "",
    ]
    if store_id:
        conds.append(CheckoutSession.store_id == store_id)

    total, total_amount = db.execute(
        select(func.count(CheckoutSession.id),
               func.coalesce(func.sum(CheckoutSession.amount), 0)).where(*conds)
    ).one()
    rows = db.scalars(
        select(CheckoutSession).where(*conds)
        .order_by(CheckoutSession.created_at.desc())
        .offset((page - 1) * per_page).limit(per_page)
    ).all()

    return {"total": total, "total_amount": str(total_amount),
            "page": page, "per_page": per_page,
            "items": [_serialize(s) for s in rows]}


@router.get("/{session_id}", response_model=dict)
def abandoned_detail(
    session_id: uuid.UUID,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Terk edilen sepetin tam dökümü + NEREDE VAZGEÇTİĞİ analizi.

    Aşama, ziyaretçi ping'leri (presence) ve ödeme oturumundan birleştirilir;
    her aşamanın tipik sebebi ve önerilen aksiyon döner."""
    from app.models import StorefrontPresence
    from app.services import funnel

    s = db.scalar(select(CheckoutSession).where(
        CheckoutSession.id == session_id,
        CheckoutSession.tenant_id == user.tenant_id))
    if not s:
        raise HTTPException(404, "Sepet bulunamadı")

    # Aşama: oturumun kendi ilerlemesi + (varsa) ziyaretçi ping'i
    stage = s.last_stage or "checkout_opened"   # kayıt varsa en az form açılmış
    if s.status == "failed":
        stage = funnel.merge_stage(stage, "payment_failed")
    presence = db.scalar(
        select(StorefrontPresence).where(
            StorefrontPresence.store_id == s.store_id,
            StorefrontPresence.stage.isnot(None),
        ).order_by(StorefrontPresence.last_seen.desc()).limit(1)
    ) if not s.last_stage else None
    if presence:
        stage = funnel.merge_stage(stage, presence.stage)

    cust = s.customer or {}
    info = funnel.describe(stage)
    # Huni: hangi adımlar tamamlandı (panelde görsel şerit)
    steps = [
        {"key": k, "label": funnel.STAGE_LABEL[k],
         "done": funnel.STAGE_ORDER[k] <= funnel.STAGE_ORDER.get(stage, 0)}
        for k in ("browsing", "cart", "checkout_opened", "form_completed",
                  "provider_redirect")
    ]
    return {
        "id": str(s.id),
        "status": s.status,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "last_stage_at": (s.last_stage_at or s.created_at).isoformat()
                         if (s.last_stage_at or s.created_at) else None,
        "amount": str(s.amount),
        "shipping_amount": str(s.shipping_amount or 0),
        "discount_code": s.discount_code,
        "discount_amount": str(s.discount_amount or 0),
        "reminder_sent_at": s.reminder_sent_at.isoformat() if s.reminder_sent_at else None,
        "restore_url": f"/sepet?restore={s.lookup_token}",
        # Müşteri — iletişim kurabilmek için (KVKK: 90 günde temizlenir)
        "customer": {
            "name": f"{cust.get('first_name','')} {cust.get('last_name','')}".strip(),
            "email": cust.get("email"),
            "phone": cust.get("phone"),
            "city": cust.get("city"),
            "province": cust.get("province"),
            "address1": cust.get("address1"),
            "note": cust.get("note"),
        },
        # Sepet içeriği
        "items": [
            {
                "title": i.get("title"),
                "model": i.get("model_display"),
                "variation": i.get("variation"),
                "quantity": i.get("quantity", 1),
                "unit_price": i.get("unit_price"),
                "product_slug": i.get("product_slug"),
            }
            for i in (s.cart_snapshot or [])
        ],
        # NEREDE VAZGEÇTİ
        "funnel": {**info, "steps": steps},
    }


@router.post("/{session_id}/reminder", response_model=dict)
def send_reminder(
    session_id: uuid.UUID,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    session = db.scalar(
        select(CheckoutSession).where(
            CheckoutSession.id == session_id,
            CheckoutSession.tenant_id == user.tenant_id,
        ).with_for_update()
    )
    if not session or session.status not in ABANDONED_STATUSES or session.order_id:
        raise HTTPException(404, "Uygun oturum bulunamadı")
    if session.reminder_sent_at:
        raise HTTPException(409, "Bu sepet için hatırlatma zaten gönderildi")
    email = (session.customer or {}).get("email")
    if not email:
        raise HTTPException(422, "Oturumda e-posta yok")

    store = db.get(Store, session.store_id)
    ok = _send_reminder_email(db, session, store)
    if not ok:
        raise HTTPException(502, "E-posta gönderilemedi (SMTP ayarlarını kontrol edin)")
    session.reminder_sent_at = datetime.now(timezone.utc)
    db.commit()
    return {"sent": True, "email": email}


class DraftItem(BaseModel):
    variant_id: uuid.UUID
    quantity: int = Field(1, ge=1, le=100)


class DraftCreate(BaseModel):
    store_id: uuid.UUID
    items: list[DraftItem] = Field(..., min_length=1, max_length=50)
    customer_name: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    note: str | None = Field(None, max_length=500)
    send_email: bool = True


@router.post("/draft", response_model=dict, status_code=201)
def create_draft(
    body: DraftCreate,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Taslak sipariş (Shopify draft order): panelden sepet kur, müşteriye
    ödeme linki gönder. Order YINE yalnızca müşteri ödeyince doğar — taslak,
    linki taşıyan bilgi kaydıdır; 30 gün sonra sweeper süresini doldurur."""
    store = db.scalar(select(Store).where(
        Store.id == body.store_id, Store.tenant_id == user.tenant_id,
        Store.platform == "storefront",
    ))
    if not store:
        raise HTTPException(404, "Vitrin mağazası bulunamadı")

    try:
        snapshot, items_total = checkout_svc.validate_and_snapshot(
            db, store, [i.model_dump() for i in body.items])
    except checkout_svc.CheckoutError as e:
        raise HTTPException(422, str(e))

    parts = body.customer_name.strip().split(" ", 1)
    shipping = checkout_svc._shipping_fee(store, items_total)
    session = CheckoutSession(
        tenant_id=store.tenant_id,
        store_id=store.id,
        token=secrets.token_urlsafe(32),
        lookup_token=secrets.token_urlsafe(32),
        status="draft",
        provider=(store.config or {}).get("payment_provider") or "iyzico",
        amount=items_total + shipping,
        shipping_amount=shipping,
        currency="TRY",
        cart_snapshot=snapshot,
        customer={
            "first_name": parts[0], "last_name": parts[1] if len(parts) > 1 else "",
            "email": str(body.email).lower(), "note": body.note or None,
        },
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    db.add(session)
    db.flush()

    link = _payment_link(store, session)
    emailed = False
    if body.send_email:
        emailed = _send_draft_email(session, store, link)
        if emailed:
            session.reminder_sent_at = datetime.now(timezone.utc)
    db.commit()
    return {"id": str(session.id), "payment_link": link,
            "amount": str(session.amount), "emailed": emailed}


def _payment_link(store: Store, session: CheckoutSession) -> str:
    config = store.config or {}
    site = (config.get("storefront_url") or f"https://{config.get('shop_domain', '')}").rstrip("/")
    return f"{site}/sepet?restore={session.lookup_token}"


def _send_draft_email(session: CheckoutSession, store: Store, link: str) -> bool:
    cust = session.customer or {}
    tenant = getattr(store, "tenant", None)
    brand = email_service.brand_kwargs(tenant) if tenant else {}
    subj_over, intro_over = email_service.store_email_text(store, "odeme_linki")
    rows = "".join(
        f"<tr><td style='padding:5px 0;color:#374151;font-size:14px'>"
        f"{i.get('title', '')} — {i.get('model_display', '')} × {i.get('quantity', 1)}</td>"
        f"<td align='right' style='padding:5px 0;font-size:14px;white-space:nowrap'>"
        f"{Decimal(str(i.get('unit_price', '0'))) * int(i.get('quantity', 1)):.2f} ₺</td></tr>"
        for i in (session.cart_snapshot or [])
    )
    body = (
        f"<p>Merhaba {cust.get('first_name', '')},</p>"
        + (intro_over or "")
        + f"<p>Sizin için hazırladığımız sipariş aşağıdadır. Ödemeyi güvenli "
        f"ödeme sayfamızdan tamamlayabilirsiniz:</p>"
        f"<table width='100%' style='border-collapse:collapse;margin:10px 0'>{rows}</table>"
        f"<p style='font-size:14px'><b>Toplam (kargo dahil): {Decimal(str(session.amount)):.2f} ₺</b></p>"
        f"<p style='color:#6b7280;font-size:12px'>Bağlantı 30 gün geçerlidir. "
        f"Kart bilgileriniz bize değil, yalnızca ödeme kuruluşuna iletilir.</p>"
    )
    html = email_service.render_email(
        title="Siparişiniz hazır — ödemeyi tamamlayın",
        body_html=body,
        button_text="Ödemeyi Tamamla",
        button_url=link,
        preheader="Sizin için hazırlanan siparişin ödeme bağlantısı",
        emoji="🧾",
        **brand,
    )
    return email_service.send_email(
        cust.get("email"), subj_over or "Siparişiniz için ödeme bağlantınız 🧾", html)


def _send_reminder_email(db: Session, session: CheckoutSession, store: Store) -> bool:
    cust = session.customer or {}
    email = cust.get("email")
    if not email:
        return False
    tenant = getattr(store, "tenant", None)
    brand = email_service.brand_kwargs(tenant) if tenant else {}
    subj_over, intro_over = email_service.store_email_text(store, "terk_sepet")

    config = store.config or {}
    site = (config.get("storefront_url") or f"https://{config.get('shop_domain', '')}").rstrip("/")
    restore_url = f"{site}/sepet?restore={session.lookup_token}"

    rows = "".join(
        f"<tr><td style='padding:5px 0;color:#374151;font-size:14px'>"
        f"{i.get('title', '')} — {i.get('model_display', '')} × {i.get('quantity', 1)}</td>"
        f"<td align='right' style='padding:5px 0;font-size:14px;white-space:nowrap'>"
        f"{Decimal(str(i.get('unit_price', '0'))) * int(i.get('quantity', 1)):.2f} ₺</td></tr>"
        for i in (session.cart_snapshot or [])
    )
    body = (
        f"<p>Merhaba {cust.get('first_name', '')},</p>"
        + (intro_over or "")
        + f"<p>Sepetinizde bıraktığınız ürünler sizi bekliyor. Tek tıkla kaldığınız "
        f"yerden devam edebilirsiniz:</p>"
        f"<table width='100%' style='border-collapse:collapse;margin:10px 0'>{rows}</table>"
        f"<p style='color:#6b7280;font-size:12px'>Bu e-posta, tamamlanmayan "
        f"siparişinizle ilgili tek seferlik bir hatırlatmadır.</p>"
    )
    html = email_service.render_email(
        title="Sepetiniz sizi bekliyor",
        body_html=body,
        button_text="Sepetime Dön",
        button_url=restore_url,
        preheader="Sepetinizdeki ürünler tükenmeden tamamlayın",
        emoji="🛒",
        **brand,
    )
    return email_service.send_email(
        email, subj_over or "Sepetinizdeki ürünler sizi bekliyor 🛒", html)
