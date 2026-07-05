"""
Checkout servisi — sepet doğrulama, CheckoutSession yaşam döngüsü, ödeme sonucu.

Güvenlik ilkeleri:
- İstemciden yalnızca [{variant_id, quantity}] + müşteri bilgisi alınır;
  FİYAT HER ZAMAN SUNUCUDA hesaplanır (cart_snapshot'a yazılır).
- Order YALNIZCA doğrulanmış ödeme callback'inde oluşturulur (PR4'te bağlanır).
- Callback idempotent: satır kilidi (FOR UPDATE) + status kontrolü.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, update as sa_update
from sqlalchemy.orm import Session

from app.models import CatalogProduct, CatalogVariant, CheckoutSession, DiscountCode, Store
from app.payments import get_payment_provider
from app.payments.base import CheckoutInit, PaymentResult

SESSION_TTL = timedelta(hours=2)
MAX_ITEM_TYPES = 30
MAX_QTY_PER_ITEM = 20
# Sağlayıcılar 0'a yakın tahsilatı reddeder — indirim sonrası ürün toplamı tabanı
MIN_CHARGE = Decimal("1.00")


class CheckoutError(Exception):
    """Müşteriye gösterilebilir doğrulama hatası."""


def _shipping_fee(store: Store, items_total: Decimal) -> Decimal:
    """Sabit kargo ücreti (config: shipping_fee). free_shipping_over üzerinde 0."""
    config = store.config or {}
    try:
        fee = Decimal(str(config.get("shipping_fee", "0") or "0"))
    except ArithmeticError:
        fee = Decimal("0")
    try:
        free_over_raw = config.get("free_shipping_over")
        if free_over_raw and items_total >= Decimal(str(free_over_raw)):
            return Decimal("0")
    except ArithmeticError:
        pass
    return fee


def validate_and_snapshot(
    db: Session, store: Store, items: list[dict],
) -> tuple[list[dict], Decimal]:
    """Sepeti sunucu verisiyle doğrula; (snapshot, ürün toplamı) döndür.

    items: [{"variant_id": str, "quantity": int}]
    """
    if not items:
        raise CheckoutError("Sepet boş")
    if len(items) > MAX_ITEM_TYPES:
        raise CheckoutError("Sepette çok fazla kalem var")

    snapshot: list[dict] = []
    total = Decimal("0")
    seen: set[str] = set()

    for entry in items:
        vid = str(entry.get("variant_id") or "")
        qty = int(entry.get("quantity") or 0)
        if not vid or vid in seen:
            raise CheckoutError("Geçersiz sepet kalemi")
        seen.add(vid)
        if not (1 <= qty <= MAX_QTY_PER_ITEM):
            raise CheckoutError(f"Adet 1-{MAX_QTY_PER_ITEM} arasında olmalı")

        variant = db.scalar(
            select(CatalogVariant).where(
                CatalogVariant.id == vid,
                CatalogVariant.tenant_id == store.tenant_id,
                CatalogVariant.is_active.is_(True),
            )
        )
        if not variant:
            raise CheckoutError("Sepetteki bir ürün artık satışta değil")
        product = db.get(CatalogProduct, variant.product_id)
        if not product or product.store_id != store.id or product.status != "active":
            raise CheckoutError("Sepetteki bir ürün artık satışta değil")
        if variant.track_stock and variant.quantity < qty:
            raise CheckoutError(
                f"'{product.title} — {variant.model_display}' için yeterli stok yok"
            )

        unit_price = Decimal(str(
            variant.price_override if variant.price_override is not None
            else product.base_price
        ))
        total += unit_price * qty
        snapshot.append({
            "variant_id": str(variant.id),
            "product_id": str(product.id),
            "title": product.title,
            "model_key": variant.model_key,
            "model_display": variant.model_display,
            "variation": variant.variation,
            "sku": variant.sku,
            "quantity": qty,
            "unit_price": str(unit_price),
            "stock_item_id": str(variant.stock_item_id) if variant.stock_item_id else None,
        })

    return snapshot, total


def apply_discount(
    db: Session, store: Store, code: str, items_total: Decimal, email: str | None,
) -> tuple[DiscountCode, Decimal, bool]:
    """Kupon kodunu doğrula; (kupon, indirim_tutarı, kargo_bedava) döndür.

    Geçersiz her durumda müşteriye gösterilebilir CheckoutError fırlatır.
    usage_count burada ARTMAZ — yalnızca ödeme doğrulanınca (storefront_order).
    """
    normalized = (code or "").strip().upper()
    if not normalized:
        raise CheckoutError("Kupon kodu boş")

    dc = db.scalar(select(DiscountCode).where(
        DiscountCode.store_id == store.id,
        DiscountCode.code == normalized,
        DiscountCode.is_active.is_(True),
    ))
    if not dc:
        raise CheckoutError("Kupon kodu geçersiz")

    discount, free_shipping = evaluate_discount(db, dc, items_total, email)
    return dc, discount, free_shipping


def evaluate_discount(
    db: Session, dc: DiscountCode, items_total: Decimal, email: str | None,
) -> tuple[Decimal, bool]:
    """Kuponun koşullarını denetle, (indirim_tutarı, kargo_bedava) hesapla."""
    now = datetime.now(timezone.utc)
    if dc.starts_at and now < dc.starts_at:
        raise CheckoutError("Kupon henüz aktif değil")
    if dc.ends_at and now > dc.ends_at:
        raise CheckoutError("Kuponun süresi dolmuş")
    if dc.usage_limit is not None and dc.usage_count >= dc.usage_limit:
        raise CheckoutError("Kuponun kullanım limiti doldu")
    if dc.min_subtotal is not None and items_total < Decimal(str(dc.min_subtotal)):
        raise CheckoutError(
            f"Bu kupon en az {Decimal(str(dc.min_subtotal)):.2f} TL sepet tutarında geçerli"
        )
    if dc.once_per_customer and email:
        used = db.scalar(
            select(CheckoutSession.id).where(
                CheckoutSession.discount_code_id == dc.id,
                CheckoutSession.status == "paid",
                CheckoutSession.customer["email"].astext == email.lower(),
            ).limit(1)
        )
        if used:
            raise CheckoutError("Bu kuponu daha önce kullandınız")

    free_shipping = dc.kind == "free_shipping"
    if dc.kind == "percent":
        discount = (items_total * Decimal(str(dc.value)) / 100).quantize(Decimal("0.01"))
    elif dc.kind == "amount":
        discount = min(Decimal(str(dc.value)), items_total)
    else:
        discount = Decimal("0")

    if items_total - discount < MIN_CHARGE:
        raise CheckoutError("Kupon bu sepette kullanılamıyor (tutar çok düşük)")
    return discount, free_shipping


def best_automatic_discount(
    db: Session, store: Store, items_total: Decimal, email: str | None,
    shipping_fee: Decimal,
) -> tuple[DiscountCode, Decimal, bool] | None:
    """Kod girilmemiş sepette koşulu sağlayan otomatik indirimlerden en
    kazançlısını seç (Shopify gibi: otomatikler birleşmez, tek kazanan olur).
    Kazanç = indirim tutarı + (kargo bedavaysa kargo ücreti)."""
    candidates = db.scalars(select(DiscountCode).where(
        DiscountCode.store_id == store.id,
        DiscountCode.is_automatic.is_(True),
        DiscountCode.is_active.is_(True),
    )).all()

    best: tuple[DiscountCode, Decimal, bool] | None = None
    best_saving = Decimal("0")
    for dc in candidates:
        try:
            discount, free_shipping = evaluate_discount(db, dc, items_total, email)
        except CheckoutError:
            continue  # koşulu sağlamayan otomatik sessizce atlanır
        saving = discount + (shipping_fee if free_shipping else Decimal("0"))
        if saving > best_saving:
            best = (dc, discount, free_shipping)
            best_saving = saving
    return best


def create_session(
    db: Session,
    store: Store,
    *,
    items: list[dict],
    customer: dict,
    client_ip: str | None,
    discount_code: str | None = None,
) -> tuple[CheckoutSession, CheckoutInit]:
    """Sepeti doğrula, CheckoutSession yarat, sağlayıcıda ödeme başlat."""
    provider = get_payment_provider(store)  # config hatası varsa erkenden patlasın

    snapshot, items_total = validate_and_snapshot(db, store, items)

    # Minimum sepet tutarı (mağaza ayarı) — indirim ÖNCESİ ürün toplamına bakılır
    min_raw = (store.config or {}).get("min_order_amount")
    if min_raw:
        try:
            min_amount = Decimal(str(min_raw))
        except ArithmeticError:
            min_amount = Decimal("0")
        if min_amount > 0 and items_total < min_amount:
            raise CheckoutError(
                f"Minimum sipariş tutarı {min_amount:.2f} TL — "
                f"sepetinize ürün ekleyerek devam edebilirsiniz"
            )

    dc = None
    discount = Decimal("0")
    free_shipping = False
    email = (customer or {}).get("email")
    if discount_code:
        # Kod girildiyse kod kazanır (otomatikle birleşmez — Shopify davranışı)
        dc, discount, free_shipping = apply_discount(
            db, store, discount_code, items_total, email)
    else:
        auto = best_automatic_discount(
            db, store, items_total, email, _shipping_fee(store, items_total))
        if auto:
            dc, discount, free_shipping = auto

    shipping = Decimal("0") if free_shipping else _shipping_fee(store, items_total)

    session = CheckoutSession(
        tenant_id=store.tenant_id,
        store_id=store.id,
        token=secrets.token_urlsafe(32),
        lookup_token=secrets.token_urlsafe(32),
        status="pending",
        provider=provider.PROVIDER_NAME,
        amount=items_total - discount + shipping,
        shipping_amount=shipping,
        currency="TRY",
        cart_snapshot=snapshot,
        customer=customer,
        kvkk_accepted_at=datetime.now(timezone.utc),
        client_ip=client_ip,
        discount_code=dc.code if dc else None,
        discount_amount=discount,
        discount_code_id=dc.id if dc else None,
        expires_at=datetime.now(timezone.utc) + SESSION_TTL,
    )
    db.add(session)
    db.flush()

    callback_url = build_callback_url(store, session)
    init = provider.create_checkout(session, callback_url)
    session.provider_ref = init.provider_ref
    db.commit()
    return session, init


def build_callback_url(store: Store, session: CheckoutSession) -> str:
    """Sağlayıcının callback POST'layacağı backend URL'i."""
    from app.config import get_settings
    base = (get_settings().backend_url or "http://127.0.0.1:8000").rstrip("/")
    if session.provider == "paytr":
        # PayTR bildirim URL'i panelden tanımlanır (tek global webhook);
        # merchant_ok/fail_url ise müşteri dönüş sayfasıdır.
        return storefront_result_url(store, session)
    return f"{base}/api/shop/payments/iyzico/callback/{session.token}"


def storefront_result_url(store: Store, session: CheckoutSession) -> str:
    """Müşterinin döneceği vitrin sonuç sayfası."""
    config = store.config or {}
    base = (config.get("storefront_url") or f"https://{config.get('shop_domain', '')}").rstrip("/")
    return f"{base}/odeme/sonuc?token={session.token}"


def get_session_by_token(db: Session, token: str, *, for_update: bool = False) -> CheckoutSession | None:
    q = select(CheckoutSession).where(CheckoutSession.token == token)
    if for_update:
        q = q.with_for_update()
    return db.scalar(q)


def process_payment_result(
    db: Session, session: CheckoutSession, result: PaymentResult,
) -> CheckoutSession:
    """Doğrulanmış sağlayıcı sonucunu session'a uygula (idempotent).

    ÇAĞIRMADAN ÖNCE session FOR UPDATE ile kilitlenmiş olmalı.
    Sipariş oluşturma (paid → Order) finalize_paid_session'da (PR4).
    """
    if session.status == "paid":
        return session  # tekrar callback — hiçbir şey yapma

    now = datetime.now(timezone.utc)
    session.callback_raw = result.raw or None

    if result.status != "paid":
        session.status = "failed"
        db.commit()
        return session

    if session.expires_at and now > session.expires_at and session.status != "pending":
        # expired işaretlenmişse bile ödeme sağlayıcıdan geldiyse kabul et
        pass

    session.status = "paid"
    session.paid_at = now
    if result.provider_ref:
        session.provider_ref = result.provider_ref

    finalize_paid_session(db, session)
    db.commit()
    return session


def finalize_paid_session(db: Session, session: CheckoutSession) -> None:
    """Ödemesi doğrulanmış session'ı siparişe çevirir: Order + LineItem,
    stok düşümü, onay e-postası. İkinci kez sipariş oluşmasına karşı hem
    process_payment_result'taki status kontrolü hem de orders tablosundaki
    (store_id, external_id) tekilliği koruma sağlar."""
    from app.services.storefront_order import create_order_from_session
    create_order_from_session(db, session)


# ─── Bakım: süresi dolan oturumlar + KVKK veri temizliği ─────

PII_RETENTION_DAYS = 90


def sweep_sessions(db: Session) -> dict:
    """1) Süresi geçmiş 'pending' oturumları 'expired' işaretle.
    2) Siparişe dönüşmemiş (failed/expired/cancelled) ve 90 günden eski
       oturumlardan müşteri PII'sini sil (KVKK saklama sınırı).
       'paid' oturumlara dokunulmaz — sözleşme ifası kaydı."""
    now = datetime.now(timezone.utc)

    expired = db.execute(
        sa_update(CheckoutSession)
        .where(
            CheckoutSession.status == "pending",
            CheckoutSession.expires_at.isnot(None),
            CheckoutSession.expires_at < now,
        )
        .values(status="expired")
    ).rowcount

    cutoff = now - timedelta(days=PII_RETENTION_DAYS)
    purged = db.execute(
        sa_update(CheckoutSession)
        .where(
            CheckoutSession.status.in_(["failed", "expired", "cancelled"]),
            CheckoutSession.created_at < cutoff,
            CheckoutSession.customer != {},
        )
        .values(customer={}, client_ip=None, callback_raw=None)
    ).rowcount

    db.commit()
    return {"expired": expired, "pii_purged": purged}
