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

        # Couple ürün: ikinci model AYNI ürünün aktif varyantı olmalı
        second = None
        if (product.models_per_item or 1) >= 2:
            svid = str(entry.get("second_variant_id") or "")
            if not svid:
                raise CheckoutError(f"'{product.title}' için ikinci telefon modelini seçin")
            second = db.scalar(select(CatalogVariant).where(
                CatalogVariant.id == svid,
                CatalogVariant.product_id == product.id,
                CatalogVariant.is_active.is_(True),
            ))
            if not second:
                raise CheckoutError("İkinci model artık satışta değil")
            if second.track_stock and second.quantity < qty:
                raise CheckoutError(
                    f"'{product.title} — {second.model_display}' için yeterli stok yok")

        # Kişiye özel alanlar: ürün tanımına göre doğrula (bilinmeyen anahtar atılır)
        custom_clean = None
        fields = product.custom_fields or []
        if fields:
            raw_custom = entry.get("custom") or {}
            custom_clean = {}
            for f in fields:
                val = str(raw_custom.get(f["key"]) or "").strip()
                if f.get("required") and not val:
                    raise CheckoutError(f"'{product.title}': {f['label']} alanı zorunlu")
                if not val:
                    continue
                if f["type"] == "color" and f.get("options") and val not in f["options"]:
                    raise CheckoutError(f"'{f['label']}' için geçersiz seçim")
                custom_clean[f["key"]] = val[:500] if f["type"] != "image" else val[:500]
            if not custom_clean:
                custom_clean = None

        total += unit_price * qty
        snapshot.append({
            "variant_id": str(variant.id),
            "product_id": str(product.id),
            "product_slug": product.slug,   # piksel Purchase contents eşleşmesi
            "title": product.title,
            "model_key": variant.model_key,
            "model_display": variant.model_display,
            "variation": variant.variation,
            "sku": variant.sku,
            "quantity": qty,
            "unit_price": str(unit_price),
            "stock_item_id": str(variant.stock_item_id) if variant.stock_item_id else None,
            **({"second_variant_id": str(second.id),
                "second_model_key": second.model_key,
                "second_model_display": second.model_display} if second else {}),
            **({"custom": custom_clean} if custom_clean else {}),
            **({"custom_labels": {f["key"]: f["label"] for f in fields}} if custom_clean else {}),
        })

    return snapshot, total


def apply_discount(
    db: Session, store: Store, code: str, items_total: Decimal, email: str | None,
    items_count: int | None = None, snapshot: list[dict] | None = None,
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

    discount, free_shipping = evaluate_discount(
        db, dc, items_total, email, items_count, snapshot)
    return dc, discount, free_shipping


def _eligible_total(db: Session, dc: DiscountCode, snapshot: list[dict]) -> Decimal:
    """Koleksiyon kısıtlı kuponda: yalnızca o koleksiyondaki kalemlerin toplamı."""
    from app.models import catalog_product_collections
    product_ids = {i.get("product_id") for i in snapshot if i.get("product_id")}
    if not product_ids:
        return Decimal("0")
    rows = db.execute(
        select(catalog_product_collections.c.product_id).where(
            catalog_product_collections.c.collection_id == dc.collection_id,
            catalog_product_collections.c.product_id.in_(list(product_ids)),
        )
    ).all()
    in_collection = {str(r[0]) for r in rows}
    return sum(
        (Decimal(str(i.get("unit_price", "0"))) * int(i.get("quantity", 1))
         for i in snapshot if str(i.get("product_id")) in in_collection),
        Decimal("0"),
    )


def evaluate_discount(
    db: Session, dc: DiscountCode, items_total: Decimal, email: str | None,
    items_count: int | None = None, snapshot: list[dict] | None = None,
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
    if dc.min_quantity is not None and (items_count or 0) < dc.min_quantity:
        raise CheckoutError(f"Bu indirim en az {dc.min_quantity} ürünle geçerli")
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

    # Koleksiyon kısıtı: indirim yalnızca o koleksiyondaki kalemlere işler
    base_total = items_total
    if dc.collection_id is not None:
        if snapshot is None:
            raise CheckoutError("Bu kupon sepet içeriğiyle doğrulanmalı")
        base_total = _eligible_total(db, dc, snapshot)
        if base_total <= 0:
            raise CheckoutError("Bu kupon sepetinizdeki ürünlerde geçerli değil")

    free_shipping = dc.kind == "free_shipping"
    if dc.kind == "percent":
        discount = (base_total * Decimal(str(dc.value)) / 100).quantize(Decimal("0.01"))
    elif dc.kind == "amount":
        discount = min(Decimal(str(dc.value)), base_total)
    elif dc.kind == "bxgy":
        # X Al Y Öde: her X adetlik grupta en ucuz (X-Y) adet bedava.
        # Koleksiyon kısıtı varsa yalnız o kalemler; birim fiyat listesi açılır.
        if snapshot is None:
            raise CheckoutError("Bu kampanya sepet içeriğiyle doğrulanmalı")
        x = int(dc.buy_x or 0)
        y = int(dc.pay_y or 0)
        if x <= 0 or y <= 0 or y >= x:
            raise CheckoutError("Kampanya tanımı hatalı")
        eligible_items = snapshot
        if dc.collection_id is not None:
            from app.models import catalog_product_collections
            rows = db.execute(
                select(catalog_product_collections.c.product_id).where(
                    catalog_product_collections.c.collection_id == dc.collection_id,
                )
            ).all()
            in_col = {str(r[0]) for r in rows}
            eligible_items = [i for i in snapshot if str(i.get("product_id")) in in_col]
        units: list[Decimal] = []
        for i in eligible_items:
            units.extend([Decimal(str(i.get("unit_price", "0")))] * int(i.get("quantity", 1)))
        groups = len(units) // x
        if groups <= 0:
            raise CheckoutError(f"Bu kampanya için sepette en az {x} ürün olmalı")
        free_count = groups * (x - y)
        units.sort()  # en ucuzlar bedava
        discount = sum(units[:free_count], Decimal("0")).quantize(Decimal("0.01"))
    else:
        discount = Decimal("0")

    if items_total - discount < MIN_CHARGE:
        raise CheckoutError("Kupon bu sepette kullanılamıyor (tutar çok düşük)")
    return discount, free_shipping


def bucket_of(dc: DiscountCode) -> str:
    """İndirim kovası: 'kargo' (kargo bedava) | 'sepet' (%/TL/XalYöde).

    Aynı kovadan yalnız bir indirim uygulanır; farklı kovalar — iki taraf da
    'combinable' ise — birlikte uygulanabilir."""
    return "kargo" if dc.kind == "free_shipping" else "sepet"


def best_automatic_discount(
    db: Session, store: Store, items_total: Decimal, email: str | None,
    shipping_fee: Decimal, items_count: int | None = None,
    snapshot: list[dict] | None = None, *,
    bucket: str | None = None, combinable_only: bool = False,
) -> tuple[DiscountCode, Decimal, bool] | None:
    """Koşulu sağlayan otomatik indirimlerden en kazançlısını seç.

    Aynı kovada otomatikler birleşmez (Shopify davranışı) — tek kazanan olur.
    Kazanç = indirim tutarı + (kargo bedavaysa kargo ücreti)."""
    candidates = db.scalars(select(DiscountCode).where(
        DiscountCode.store_id == store.id,
        DiscountCode.is_automatic.is_(True),
        DiscountCode.is_active.is_(True),
    )).all()

    best: tuple[DiscountCode, Decimal, bool] | None = None
    best_saving = Decimal("0")
    for dc in candidates:
        if bucket and bucket_of(dc) != bucket:
            continue
        if combinable_only and not dc.combinable:
            continue
        try:
            discount, free_shipping = evaluate_discount(
                db, dc, items_total, email, items_count, snapshot)
        except CheckoutError:
            continue  # koşulu sağlamayan otomatik sessizce atlanır
        saving = discount + (shipping_fee if free_shipping else Decimal("0"))
        if saving > best_saving:
            best = (dc, discount, free_shipping)
            best_saving = saving
    return best


class DiscountPlan:
    """Sepete uygulanan indirimlerin sonucu (tek veya birleşik).

    total: para indirimi (kargo hariç — kargo free_shipping ile sıfırlanır)
    applied: [(DiscountCode, tutar, kargo_bedava)] — uygulanma sırasıyla
    """

    def __init__(self, applied: list[tuple[DiscountCode, Decimal, bool]]):
        self.applied = applied

    @property
    def total(self) -> Decimal:
        return sum((a for _, a, _ in self.applied), Decimal("0"))

    @property
    def free_shipping(self) -> bool:
        return any(fs for _, _, fs in self.applied)

    @property
    def primary(self) -> DiscountCode | None:
        """Sipariş/oturum kaydına yazılacak ana kupon: para indirimi varsa o,
        yoksa ilk uygulanan (kargo)."""
        for dc, amount, _ in self.applied:
            if amount > 0:
                return dc
        return self.applied[0][0] if self.applied else None

    @property
    def codes(self) -> list[str]:
        return [dc.code for dc, _, _ in self.applied]

    def breakdown(self) -> list[dict]:
        return [
            {
                "id": str(dc.id),
                "code": dc.code,
                "kind": dc.kind,
                "amount": str(amount),
                "free_shipping": fs,
                "automatic": bool(dc.is_automatic),
                "label": describe_discount(dc),
            }
            for dc, amount, fs in self.applied
        ]


def describe_discount(dc: DiscountCode) -> str:
    """Müşteriye gösterilecek kısa etiket ('%10 indirim', 'Ücretsiz kargo')."""
    if dc.promo_message:
        return dc.promo_message
    if dc.kind == "percent":
        return f"%{Decimal(str(dc.value)).normalize():f} indirim"
    if dc.kind == "amount":
        return f"{Decimal(str(dc.value)):.2f} TL indirim"
    if dc.kind == "free_shipping":
        return "Ücretsiz kargo"
    if dc.kind == "bxgy":
        return f"{dc.buy_x} Al {dc.pay_y} Öde"
    return dc.code


def resolve_discounts(
    db: Session, store: Store, code: str | None, items_total: Decimal,
    email: str | None, shipping_fee: Decimal, items_count: int | None = None,
    snapshot: list[dict] | None = None,
) -> DiscountPlan:
    """Sepete uygulanacak indirimleri belirle — TEK KAYNAK.

    Kurallar (Shopify "Combinations" mantığı):
    1. Kod girildiyse kod her zaman uygulanır (geçersizse hata fırlatır).
    2. Kod 'birleşebilir' ise, DİĞER kovadan (kod sepet indirimiyse kargo,
       kargo indirimiyse sepet) birleşebilir en iyi otomatik de eklenir.
    3. Kod yoksa: her kovanın en iyi otomatiği bulunur; ikisi de birleşebilir
       ise ikisi birden, değilse yalnız kazancı yüksek olan uygulanır.
    4. Toplam para indirimi sepeti MIN_CHARGE altına düşüremez (kırpılır).
    """
    applied: list[tuple[DiscountCode, Decimal, bool]] = []

    if code:
        dc, discount, free_shipping = apply_discount(
            db, store, code, items_total, email, items_count, snapshot)
        applied.append((dc, discount, free_shipping))
        if dc.combinable:
            other = "kargo" if bucket_of(dc) == "sepet" else "sepet"
            extra = best_automatic_discount(
                db, store, items_total, email, shipping_fee, items_count, snapshot,
                bucket=other, combinable_only=True)
            if extra and extra[0].id != dc.id:
                applied.append(extra)
    else:
        sepet = best_automatic_discount(
            db, store, items_total, email, shipping_fee, items_count, snapshot,
            bucket="sepet")
        kargo = best_automatic_discount(
            db, store, items_total, email, shipping_fee, items_count, snapshot,
            bucket="kargo")
        if sepet and kargo and sepet[0].combinable and kargo[0].combinable:
            applied = [sepet, kargo]
        else:
            best, best_saving = None, Decimal("0")
            for cand in (sepet, kargo):
                if not cand:
                    continue
                saving = cand[1] + (shipping_fee if cand[2] else Decimal("0"))
                if saving > best_saving:
                    best, best_saving = cand, saving
            if best:
                applied = [best]

    # Güvenlik tabanı: birleşik indirim sepeti sağlayıcının kabul etmeyeceği
    # tutara indirmesin — son indirim kırpılır (kırpma sunucuda, istemcide değil)
    total = sum((a for _, a, _ in applied), Decimal("0"))
    if applied and total > items_total - MIN_CHARGE:
        fazla = total - (items_total - MIN_CHARGE)
        dc, amount, fs = applied[-1]
        applied[-1] = (dc, max(Decimal("0"), amount - fazla), fs)

    return DiscountPlan(applied)


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

    email = (customer or {}).get("email")
    items_count = sum(int(i.get("quantity", 1)) for i in snapshot)
    plan = resolve_discounts(
        db, store, discount_code, items_total, email,
        _shipping_fee(store, items_total), items_count, snapshot)
    dc = plan.primary
    discount = plan.total
    free_shipping = plan.free_shipping

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
        discount_breakdown=plan.breakdown() or None,
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
    # .split()[0]: .env'de değere boşlukla başka bir şey yapışırsa
    # (örn "https://... env=production") iyzico müşteriyi çözülemeyen bir
    # adrese yönlendirir — URL'in yalnız ilk parçası kullanılır.
    raw = (get_settings().backend_url or "http://127.0.0.1:8000").strip()
    base = (raw.split()[0] if raw.split() else "http://127.0.0.1:8000").rstrip("/")
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

    # Meta CAPI Purchase — arka planda, best-effort (token tanımlıysa).
    # Tarayıcı pikseliyle aynı event_id sayesinde Meta çift saymaz.
    try:
        from app.services.meta_capi import send_purchase_async
        store = db.get(Store, session.store_id)
        if store:
            send_purchase_async(store, session)
    except Exception:  # noqa: BLE001 — analitik, sipariş akışını asla bozmaz
        pass


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
            CheckoutSession.status.in_(["pending", "draft"]),
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
