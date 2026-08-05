"""
Mağaza Ayarları — /api/store-settings/{store_id}

Mağaza Paneli'nin yapılandırılmış ayar yüzeyi. Tek kaynak Store.config JSONB —
Baskıcı Atölyeler modalıyla aynı veriyi yazar (PATCH merge, tam replace değil).
Secretlar okuma yönünde maskelenir (_mask_config); '••' içeren değer yazılmaz.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.database import get_db
from app.models import Store, User
from app.routers.stores import _SECRET_KEYS, _mask_config
from app.services import activity

router = APIRouter(
    prefix="/api/store-settings", tags=["store-settings"],
    dependencies=[Depends(require_permission("vitrin"))],
)

# Panelden yönetilebilen config anahtarları (whitelist — serbest yazım yok)
_MONEY_KEYS = {"shipping_fee", "free_shipping_over", "min_order_amount",
               # Kâr marjı raporu girdileri (yalnız rapor — müşteri yüzeyine çıkmaz)
               "profit_default_unit_cost", "profit_shipping_cost",
               "profit_packaging_cost", "profit_commission_pct"}
# KDV oranı (%) — fiyatlar KDV DAHİL, fatura için içindeki vergi ayrıştırılır
_TAX_KEYS = {"tax_rate"}
_TEXT_KEYS = {
    "payment_provider", "storefront_url", "custom_domain", "shop_domain",
    "contact_email", "contact_phone", "contact_address", "contact_instagram",
    "kvkk_text", "mesafeli_satis_text", "iade_text", "sla_days",
    "iyzico_base_url", "paytr_test_mode",
    "meta_pixel_id", "ga4_id", "tiktok_pixel_id",
    "meta_test_event_code",
    "storefront_password",
    # Tasarım stüdyosu: fiyat ve telefon modelleri bu üründen alınır
    "studio_product_slug",
}
_SECRET_CFG_KEYS = {
    "iyzico_api_key", "iyzico_secret_key",
    "paytr_merchant_id", "paytr_merchant_key", "paytr_merchant_salt",
    "meta_capi_token",
}
_BOOL_KEYS = {"abandoned_reminder_enabled", "shipping_email_enabled", "gift_wrap_enabled",
              "support_chat_enabled", "welcome_email_enabled", "review_invite_enabled"}
# E-posta bildirim metinleri: {tip: {subject, intro}} (Shopify Notifications)
_EMAIL_TEXT_TYPES = {"siparis_onay", "kargo", "terk_sepet", "odeme_linki", "stok",
                     "hosgeldin", "yorum_daveti"}
ALLOWED_KEYS = (_MONEY_KEYS | _TAX_KEYS | _TEXT_KEYS | _SECRET_CFG_KEYS | _BOOL_KEYS
                | {"email_texts", "support_faq", "welcome_discount_percent"})


def _sanitize_support_faq(value) -> list:
    """Destek asistanı SSS listesi: [{q, a}] en fazla 12 madde."""
    if not isinstance(value, list):
        raise HTTPException(422, "support_faq liste olmalı")
    out = []
    for item in value[:12]:
        if not isinstance(item, dict):
            continue
        q = str(item.get("q") or "").strip()[:200]
        a = str(item.get("a") or "").strip()[:2000]
        if q and a:
            out.append({"q": q, "a": a})
    return out


def _sanitize_email_texts(value) -> dict:
    """email_texts sözlüğünü temizle: yalnız bilinen tipler + subject/intro."""
    if not isinstance(value, dict):
        raise HTTPException(422, "email_texts sözlük olmalı")
    out = {}
    for t, v in value.items():
        if t not in _EMAIL_TEXT_TYPES or not isinstance(v, dict):
            continue
        entry = {}
        subject = str(v.get("subject") or "").strip()[:200]
        intro = str(v.get("intro") or "").strip()[:1000]
        if subject:
            entry["subject"] = subject
        if intro:
            entry["intro"] = intro
        if entry:
            out[t] = entry
    return out


class SettingsPatch(BaseModel):
    store_name: str | None = Field(None, min_length=1, max_length=200)
    config: dict = Field(default_factory=dict)


def _get_store(db: Session, user: User, store_id: uuid.UUID,
               *, for_update: bool = False) -> Store:
    q = select(Store).where(
        Store.id == store_id, Store.tenant_id == user.tenant_id,
        Store.platform == "storefront",
    )
    # config JSONB'yi yazan uçlar satır kilidi almalı — aksi halde eşzamanlı
    # istekler (örn. tema Kaydet + canlı önizleme PUT'u) birbirinin
    # değişikliğini ezer (oku-değiştir-yaz yarışı).
    if for_update:
        q = q.with_for_update()
    store = db.scalar(q)
    if not store:
        raise HTTPException(404, "Vitrin mağazası bulunamadı")
    return store


@router.get("/{store_id}", response_model=dict)
def get_settings(
    store_id: uuid.UUID,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    store = _get_store(db, user, store_id)
    config = _mask_config(store.config or {})
    return {
        "store_id": str(store.id),
        "store_name": store.name,
        "slug": store.slug,
        "config": {k: config.get(k) for k in sorted(ALLOWED_KEYS)},
    }


@router.patch("/{store_id}", response_model=dict)
def patch_settings(
    store_id: uuid.UUID,
    body: SettingsPatch,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    store = _get_store(db, user, store_id, for_update=True)

    if body.store_name:
        store.name = body.store_name.strip()

    config = dict(store.config or {})
    for key, value in (body.config or {}).items():
        if key not in ALLOWED_KEYS:
            raise HTTPException(422, f"Bilinmeyen ayar: {key}")
        # Maskeli secret geri yazılmaz (kullanıcı değiştirmedi demektir)
        if key in (_SECRET_CFG_KEYS | _SECRET_KEYS) and isinstance(value, str) and "••" in value:
            continue
        if key in _MONEY_KEYS and value not in (None, ""):
            try:
                value = str(Decimal(str(value)).quantize(Decimal("0.01")))
            except (InvalidOperation, ValueError):
                raise HTTPException(422, f"Geçersiz tutar: {key}")
        # None "dokunulmadı" demektir — bool(None)=False'a zorlanırsa
        # varsayılanı açık olan özellikler (destek balonu) istem dışı kapanır
        if key in _BOOL_KEYS and value is not None:
            value = bool(value)
        if key == "email_texts" and value not in (None, ""):
            value = _sanitize_email_texts(value)
            if not value:
                value = None  # tümü boşsa anahtarı sil
        if key == "support_faq" and value not in (None, ""):
            value = _sanitize_support_faq(value)
            if not value:
                value = None
        if value in (None, ""):
            config.pop(key, None)
        else:
            config[key] = value

    store.config = config
    flag_modified(store, "config")
    # Hangi ayarların değiştiği günlüğe düşer (gizli anahtar DEĞERLERİ yazılmaz)
    activity.record(db, user, "ayar_guncelle", store_id=store.id, entity_type="ayar",
                    entity_label=store.name,
                    detail={"alanlar": sorted(k for k in body.config
                                              if k not in (_SECRET_CFG_KEYS | _SECRET_KEYS))})
    db.commit()
    db.refresh(store)
    return {
        "store_id": str(store.id),
        "store_name": store.name,
        "slug": store.slug,
        "config": {k: _mask_config(store.config).get(k) for k in sorted(ALLOWED_KEYS)},
    }


@router.get("/{store_id}/readiness", response_model=dict)
def store_readiness(
    store_id: uuid.UUID,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Canlıya hazırlık kontrolü — yayına engel olan eksikleri tek yerde toplar.

    Panel ana sayfası bu listeyi gösterir; 'blocker' işaretliler satışı
    fiilen durduran sorunlardır (ödeme alınamaz / ürün satın alınamaz /
    müşteri giriş yapamaz)."""
    from sqlalchemy import func as sql_func

    from app.models import CatalogProduct, CatalogVariant
    from app.services import email_service

    store = _get_store(db, user, store_id)
    config = store.config or {}
    checks: list[dict] = []

    def add(key: str, ok: bool, label: str, hint: str, blocker: bool = False,
            to: str | None = None, count: int | None = None) -> None:
        checks.append({"key": key, "ok": ok, "label": label, "hint": hint,
                       "blocker": blocker and not ok, "to": to, "count": count})

    # 1) Ödeme sağlayıcı — canlı mod mu, anahtar var mı
    provider = (config.get("payment_provider") or "iyzico").lower()
    if provider == "iyzico":
        has_keys = bool(config.get("iyzico_api_key") and config.get("iyzico_secret_key"))
        is_live = "sandbox" not in (config.get("iyzico_base_url") or "").lower()
        add("payment_keys", has_keys, "Ödeme sağlayıcı bağlı",
            "Ayarlar → Ödeme'ye iyzico API + güvenlik anahtarlarını girin",
            blocker=True, to="/ayarlar")
        add("payment_live", has_keys and is_live, "Ödeme CANLI modda",
            "iyzico ortamı 'Sandbox (test)' — gerçek tahsilat yapılmaz, 'Canlı'ya alın",
            blocker=True, to="/ayarlar")
    else:
        has_keys = bool(config.get("paytr_merchant_id") and config.get("paytr_merchant_key"))
        add("payment_keys", has_keys, "Ödeme sağlayıcı bağlı",
            "Ayarlar → Ödeme'ye PayTR bilgilerini girin", blocker=True, to="/ayarlar")
        add("payment_live", has_keys and str(config.get("paytr_test_mode")) == "0",
            "Ödeme CANLI modda", "PayTR modu 'Test' — 'Canlı'ya alın",
            blocker=True, to="/ayarlar")

    # 2) E-posta servisi — müşteri giriş kodu + sipariş onayı buna bağlı
    add("email", email_service.is_configured(), "E-posta servisi çalışıyor",
        "RESEND_API_KEY (veya SMTP) tanımlı değil: sipariş onayı, kargo bildirimi "
        "ve müşteri giriş kodu e-postaları GÖNDERİLEMİYOR", blocker=True)

    # 3) Varyantsız ürünler — model seçilemediği için satın alınamaz
    has_variant = select(CatalogVariant.id).where(
        CatalogVariant.product_id == CatalogProduct.id).exists()
    no_variant = db.scalar(
        select(sql_func.count()).select_from(CatalogProduct).where(
            CatalogProduct.store_id == store.id,
            CatalogProduct.status == "active",
            ~has_variant)) or 0
    add("variants", no_variant == 0, "Tüm yayındaki ürünler satın alınabilir",
        f"{no_variant} yayındaki üründe telefon modeli yok — müşteri sepete "
        "EKLEYEMEZ. Ürünler → Varyant Seti Uygula ile toplu düzeltin",
        blocker=True, to="/urunler", count=no_variant)

    # 4) Vitrin adresi + yayın kilidi
    from app.services.site import site_url

    add("storefront_url", bool(site_url(store)), "Vitrin adresi tanımlı",
        "Ayarlar → Yayın & Domain'e vitrin adresini yazın — ödeme dönüşü, "
        "e-postalardaki takip linkleri ve piksel olayları bu adresi kullanır",
        blocker=True, to="/ayarlar")
    add("unlocked", not (config.get("storefront_password") or "").strip(),
        "Mağaza ziyaretçilere açık",
        "Yayın öncesi kilit AÇIK — ziyaretçiler şifre ekranı görüyor",
        blocker=True, to="/ayarlar")

    # 5) Pazarlama + içerik (engel değil, öneri)
    add("pixel", bool(config.get("meta_pixel_id")), "Meta Pixel bağlı",
        "Reklam ölçümü için Ayarlar → Pazarlama'ya piksel ID girin", to="/ayarlar")
    add("capi", bool(config.get("meta_capi_token")), "Conversions API bağlı",
        "Reklam engelleyicili ziyaretçilerin satın almaları ölçülemiyor", to="/ayarlar")
    add("contact_email", bool(config.get("contact_email")), "İletişim e-postası tanımlı",
        "Müşteri mesajları ve test mailleri buraya gider", to="/ayarlar")
    add("legal", bool(config.get("kvkk_text") or config.get("mesafeli_satis_text")),
        "Yasal metinler özelleştirildi",
        "Hazır şablon kullanılıyor — kendi metinlerinizi girmeniz önerilir", to="/sayfalar")

    blockers = [c for c in checks if c["blocker"]]
    return {
        "ready": not blockers,
        "blocker_count": len(blockers),
        "checks": checks,
    }


# ─── E-posta şablon önizleme + test gönderimi ────────────────
# Panel E-posta sekmesi: formdaki (henüz kaydedilmemiş) konu+giriş metniyle
# örnek veri üzerinden gerçek şablonu render eder / test maili yollar.

_EMAIL_PREVIEW_SAMPLES = {
    "siparis_onay": {
        "default_subject": "Siparişiniz alındı — #1042",
        "emoji": "✅",
        "title": "Siparişiniz alındı!",
        "body": (
            "<p>Merhaba <b>Ayşe</b>,</p>"
            "<table width='100%' cellpadding='6' style='border-collapse:collapse;font-size:14px'>"
            "<tr style='border-bottom:1px solid #eee'><td>Mystic Blade Soul Kılıf — iPhone 15 Pro ×1</td>"
            "<td align='right'>349,99 ₺</td></tr>"
            "<tr style='border-bottom:1px solid #eee'><td>Kargo</td><td align='right'>94,90 ₺</td></tr>"
            "<tr><td><b>Toplam</b></td><td align='right'><b>444,89 ₺</b></td></tr></table>"
        ),
        "button": ("Siparişimi Takip Et", "#"),
    },
    "kargo": {
        "default_subject": "Siparişiniz kargoya verildi 📦",
        "emoji": "🚚",
        "title": "Kargonuz yola çıktı!",
        "body": ("<p>Merhaba <b>Ayşe</b>,</p><p>#1042 numaralı siparişiniz kargoya verildi."
                 "<br>Takip No: <b>72900312455</b></p>"),
        "button": ("Kargomu Takip Et", "#"),
    },
    "terk_sepet": {
        "default_subject": "Sepetinizdeki ürünler sizi bekliyor 🛒",
        "emoji": "🛒",
        "title": "Sepetinizi unutmayın",
        "body": ("<p>Merhaba <b>Ayşe</b>,</p><p>Sepetinizde <b>Mystic Blade Soul Kılıf</b> "
                 "sizi bekliyor — tek tıkla kaldığınız yerden devam edin.</p>"),
        "button": ("Sepetime Dön", "#"),
    },
    "odeme_linki": {
        "default_subject": "Siparişiniz için ödeme bağlantınız 🧾",
        "emoji": "🧾",
        "title": "Ödeme bağlantınız hazır",
        "body": ("<p>Merhaba <b>Ayşe</b>,</p><p>Sizin için hazırladığımız siparişin tutarı "
                 "<b>444,89 ₺</b>. Aşağıdaki bağlantıyla güvenle ödeyebilirsiniz.</p>"),
        "button": ("Güvenli Ödeme", "#"),
    },
    "stok": {
        "default_subject": "Beklediğiniz ürün yeniden stokta 🔔",
        "emoji": "🔔",
        "title": "Yeniden stokta!",
        "body": ("<p>Merhaba,</p><p><b>Mystic Blade Soul Kılıf (iPhone 15 Pro)</b> "
                 "yeniden stokta — tükenmeden alın.</p>"),
        "button": ("Ürüne Git", "#"),
    },
}


def _render_email_preview(store: Store, body: dict) -> tuple[str, str]:
    """(konu, html) — formdaki taslak konu/giriş uygulanmış örnek şablon."""
    from app.services import email_service

    etype = str(body.get("type") or "")
    sample = _EMAIL_PREVIEW_SAMPLES.get(etype)
    if not sample:
        raise HTTPException(422, "Bilinmeyen şablon türü")
    subject = str(body.get("subject") or "").strip() or sample["default_subject"]
    intro = str(body.get("intro") or "").strip()
    tenant = getattr(store, "tenant", None)
    brand = email_service.brand_kwargs(tenant) if tenant else {}
    html = email_service.render_email(
        title=sample["title"],
        body_html=(f"<p>{intro}</p>" if intro else "") + sample["body"],
        button_text=sample["button"][0], button_url=sample["button"][1],
        preheader=subject, emoji=sample["emoji"], **brand,
    )
    return subject, html


@router.post("/{store_id}/email-preview", response_model=dict)
def email_preview(
    store_id: uuid.UUID,
    body: dict,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    store = _get_store(db, user, store_id)
    subject, html = _render_email_preview(store, body)
    return {"subject": subject, "html": html}


@router.post("/{store_id}/email-test", response_model=dict)
def email_test(
    store_id: uuid.UUID,
    body: dict,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Örnek şablonu mağaza sahibinin kendi adresine gönderir."""
    from app.services import email_service

    store = _get_store(db, user, store_id)
    to = ((store.config or {}).get("contact_email") or "").strip() or (user.email or "")
    if not to:
        raise HTTPException(422, "Önce Ayarlar → Genel'e iletişim e-postası girin")
    subject, html = _render_email_preview(store, body)
    if not email_service.send_email(to, f"[TEST] {subject}", html):
        raise HTTPException(500, "Gönderilemedi — e-posta servisi ayarlı değil (RESEND/SMTP)")
    return {"ok": True, "to": to}


# ─── Tema ────────────────────────────────────────────────────

from fastapi import File, Form, UploadFile  # noqa: E402

from app.services.theme import resolve_theme, validate_theme_patch  # noqa: E402


@router.get("/{store_id}/theme", response_model=dict)
def get_theme(
    store_id: uuid.UUID,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    store = _get_store(db, user, store_id)
    return resolve_theme(store.config)


@router.post("/{store_id}/odeme-testi", response_model=dict)
def odeme_testi(
    store_id: uuid.UUID,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Ödeme sağlayıcısına GERÇEK bir başlatma isteği atar ve sonucu döner.

    Canlıya çıkmadan "ödeme başlatılamadı" hatasının sebebini görmek için:
    anahtar yanlış mı, IP izinli değil mi, sandbox anahtarı canlı adreste mi
    kullanılıyor… Sağlayıcının kendi hata mesajı aynen gösterilir. Sipariş
    OLUŞTURULMAZ; sadece ödeme sayfası açılabiliyor mu ona bakılır.
    """
    from types import SimpleNamespace

    from app.payments import get_payment_provider

    store = _get_store(db, user, store_id)
    config = store.config or {}
    saglayici = (config.get("payment_provider") or "iyzico").lower()
    ortam = ("Sandbox (test)" if "sandbox" in (config.get("iyzico_base_url") or "").lower()
             else "Canlı") if saglayici == "iyzico" else (
        "Test" if str(config.get("paytr_test_mode")) == "1" else "Canlı")

    # Gerçek CheckoutSession açmıyoruz — sağlayıcıya gidecek asgari sahte oturum
    sahte = SimpleNamespace(
        id=uuid.uuid4(),
        token=f"test-{uuid.uuid4().hex[:12]}",
        amount=Decimal("1.00"),
        shipping_amount=Decimal("0"),
        currency="TRY",
        client_ip="85.34.78.112",
        customer={"first_name": "Test", "last_name": "Kullanici",
                  "email": "test@example.com", "phone": "+905000000000",
                  "address1": "Test Mah. 1 Sk. No:1", "city": "Istanbul", "zip": "34000"},
        # cart_snapshot LİSTEdir ve kalem tutarı unit_price × quantity'den doğar
        cart_snapshot=[{"variant_id": "test", "title": "Test Ürün",
                        "model_display": "", "quantity": 1, "unit_price": "1.00"}],
        discount_amount=Decimal("0"),
    )
    try:
        provider = get_payment_provider(store)
        init = provider.create_checkout(sahte, f"{(config.get('storefront_url') or '').rstrip('/')}/odeme/sonuc")
        return {
            "ok": True,
            "saglayici": saglayici, "ortam": ortam,
            "mesaj": "Ödeme sayfası başarıyla açıldı — sağlayıcı bağlantısı çalışıyor.",
            "url_var": bool(init.url),
        }
    except Exception as e:  # noqa: BLE001 — sebebi kullanıcıya göstereceğiz
        return {
            "ok": False,
            "saglayici": saglayici, "ortam": ortam,
            "mesaj": str(e)[:400] or e.__class__.__name__,
            "ipucu": _odeme_ipucu(str(e), saglayici),
        }


def _odeme_ipucu(hata: str, saglayici: str) -> str:
    """Sağlayıcının ham hatasını anlaşılır bir öneriye çevirir."""
    h = (hata or "").lower()
    if "anahtar" in h or "eksik" in h:
        return ("Ayarlar → Ödeme bölümünde API ve güvenlik anahtarları boş. "
                "iyzico panelinden alıp buraya yapıştırın.")
    if ("api bilgileri" in h or "bulunamadı" in h or "invalid api" in h
            or "signature" in h or "imza" in h or "unauthorized" in h or "5001" in h):
        return ("Anahtarlar kabul edilmedi. En sık sebep: SANDBOX anahtarını "
                "CANLI adreste (veya tersini) kullanmak — “iyzico ortamı” seçimi "
                "ile anahtar takımı aynı olmalı. Anahtarları iyzico panelinden "
                "yeniden kopyalayıp (baştaki/sondaki boşluklara dikkat) kaydedin.")
    if "ip" in h and ("izin" in h or "restrict" in h or "not allowed" in h):
        return ("iyzico hesabınızda IP kısıtlaması var. Sunucunun IP adresini "
                "(91.132.49.107) iyzico panelinde izinli listesine ekleyin.")
    if "timeout" in h or "connection" in h or "resolve" in h:
        return ("Sunucudan sağlayıcıya bağlanılamadı. Güvenlik duvarı dış "
                "bağlantıyı engelliyor olabilir.")
    if "merchant" in h:
        return "Üye iş yeri bilgileri hatalı — mağaza numarası/anahtarını kontrol edin."
    return ("Sağlayıcının mesajını yukarıda görüyorsunuz. Anahtarlar, ortam "
            "(test/canlı) ve iyzico hesabının aktif olup olmadığını kontrol edin.")


def _revalidate_storefront(store: Store) -> None:
    """Vitrine tema cache'ini düşürme sinyali (best-effort, hatalar yutulur).

    Yoksa "Kaydet ve Yayınla"dan sonra vitrin 60 sn eski temayı gösterir —
    favicon/tema değişiminde "tema karıştı" izlenimi veriyordu."""
    from app.services.site import site_url

    base = site_url(store)
    if not base:
        return
    try:
        import httpx
        httpx.post(f"{base}/api/revalidate-theme", timeout=3)
    except Exception:  # noqa: BLE001
        pass


@router.put("/{store_id}/theme", response_model=dict)
def put_theme(
    store_id: uuid.UUID,
    body: dict,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    store = _get_store(db, user, store_id, for_update=True)
    config = dict(store.config or {})
    config["theme"] = validate_theme_patch(body or {})
    store.config = config
    flag_modified(store, "config")
    db.commit()
    db.refresh(store)
    _revalidate_storefront(store)
    return resolve_theme(store.config)


@router.put("/{store_id}/theme/preview", response_model=dict)
def put_theme_preview(
    store_id: uuid.UUID,
    body: dict,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Canlı editör taslağı — vitrin ?onizleme=1 modunda bunu gösterir,
    gerçek tema değişmez. Kaydet'e basılınca normal PUT /theme çalışır."""
    store = _get_store(db, user, store_id, for_update=True)
    config = dict(store.config or {})
    config["theme_preview"] = validate_theme_patch(body or {})
    store.config = config
    flag_modified(store, "config")
    db.commit()
    return {"ok": True}


@router.delete("/{store_id}/theme/preview", status_code=204)
def clear_theme_preview(
    store_id: uuid.UUID,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    store = _get_store(db, user, store_id, for_update=True)
    config = dict(store.config or {})
    if config.pop("theme_preview", None) is not None:
        store.config = config
        flag_modified(store, "config")
        db.commit()


# ── Kişiye özel alan preset'leri (Uygulamalar sayfası) ──
# config["custom_field_presets"] = [{"name", "fields": [...]}] — hazır alan
# düzenleri; ürün detayında tek tıkla uygulanır.

MAX_FIELD_PRESETS = 20


@router.get("/{store_id}/custom-field-presets", response_model=dict)
def get_field_presets(
    store_id: uuid.UUID,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    store = _get_store(db, user, store_id)
    return {"presets": (store.config or {}).get("custom_field_presets") or []}


@router.put("/{store_id}/custom-field-presets", response_model=dict)
def put_field_presets(
    store_id: uuid.UUID,
    body: dict,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    from app.routers.catalog import _clean_custom_fields

    raw = (body or {}).get("presets")
    if not isinstance(raw, list):
        raise HTTPException(422, "presets listesi gerekli")
    presets = []
    for p_ in raw[:MAX_FIELD_PRESETS]:
        if not isinstance(p_, dict):
            continue
        name = str(p_.get("name") or "").strip()[:80]
        fields = _clean_custom_fields(p_.get("fields") or [])
        if name and fields:
            presets.append({"name": name, "fields": fields})
    store = _get_store(db, user, store_id, for_update=True)
    config = dict(store.config or {})
    config["custom_field_presets"] = presets
    store.config = config
    flag_modified(store, "config")
    db.commit()
    return {"ok": True, "presets": presets}


# ── Taslak temalar (tema kütüphanesi) ──
# config["theme_drafts"] = {key: {"name", "theme", "updated_at"}} — yayındaki
# temayı bozmadan ayrı temalar düzenlenir; Yayınla ile takas edilir (eski
# yayın taslak olarak saklanır, Shopify tema kütüphanesi gibi).

MAX_THEME_DRAFTS = 10


@router.get("/{store_id}/theme/drafts", response_model=dict)
def list_theme_drafts(
    store_id: uuid.UUID,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    store = _get_store(db, user, store_id)
    drafts = (store.config or {}).get("theme_drafts") or {}
    return {"drafts": [
        {"key": k, "name": d.get("name") or "Adsız taslak",
         "updated_at": d.get("updated_at"),
         "theme": resolve_theme({"theme": d.get("theme") or {}})}
        for k, d in drafts.items()
    ]}


@router.put("/{store_id}/theme/drafts/{draft_key}", response_model=dict)
def put_theme_draft(
    store_id: uuid.UUID,
    draft_key: str,
    body: dict,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    if not re.fullmatch(r"[a-z0-9-]{1,60}", draft_key):
        raise HTTPException(422, "Geçersiz taslak anahtarı")
    store = _get_store(db, user, store_id, for_update=True)
    config = dict(store.config or {})
    drafts = dict(config.get("theme_drafts") or {})
    if draft_key not in drafts and len(drafts) >= MAX_THEME_DRAFTS:
        raise HTTPException(422, f"En fazla {MAX_THEME_DRAFTS} taslak tema tutulabilir")
    entry = dict(drafts.get(draft_key) or {})
    if "name" in (body or {}):
        entry["name"] = str(body["name"] or "")[:80] or "Adsız taslak"
    if "theme" in (body or {}):
        entry["theme"] = validate_theme_patch(body["theme"] or {})
    if "theme" not in entry:  # ilk oluşturmada tema zorunlu
        raise HTTPException(422, "theme alanı gerekli")
    entry["updated_at"] = datetime.now(timezone.utc).isoformat()
    drafts[draft_key] = entry
    config["theme_drafts"] = drafts
    store.config = config
    flag_modified(store, "config")
    db.commit()
    return {"ok": True, "key": draft_key}


@router.delete("/{store_id}/theme/drafts/{draft_key}", status_code=204)
def delete_theme_draft(
    store_id: uuid.UUID,
    draft_key: str,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    store = _get_store(db, user, store_id, for_update=True)
    config = dict(store.config or {})
    drafts = dict(config.get("theme_drafts") or {})
    if drafts.pop(draft_key, None) is not None:
        config["theme_drafts"] = drafts
        store.config = config
        flag_modified(store, "config")
        db.commit()


@router.post("/{store_id}/theme/drafts/{draft_key}/publish", response_model=dict)
def publish_theme_draft(
    store_id: uuid.UUID,
    draft_key: str,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Taslağı yayına al — eski yayın, taslak olarak saklanır (geri dönülebilir)."""
    store = _get_store(db, user, store_id, for_update=True)
    config = dict(store.config or {})
    drafts = dict(config.get("theme_drafts") or {})
    draft = drafts.pop(draft_key, None)
    if not draft or not draft.get("theme"):
        raise HTTPException(404, "Taslak bulunamadı")
    now = datetime.now(timezone.utc)
    old_key = f"eski-{now.strftime('%Y%m%d%H%M%S')}"
    drafts[old_key] = {
        "name": f"Önceki yayın — {now.astimezone().strftime('%d.%m.%Y %H:%M')}",
        "theme": validate_theme_patch(config.get("theme") or {}),
        "updated_at": now.isoformat(),
    }
    # Otomatik yedekler sınırı aşarsa en eski "eski-*" kayıtları buda
    while len(drafts) > MAX_THEME_DRAFTS:
        old_backups = sorted(k for k in drafts if k.startswith("eski-"))
        if not old_backups:
            break
        drafts.pop(old_backups[0])
    config["theme"] = validate_theme_patch(draft["theme"])
    config["theme_drafts"] = drafts
    config.pop("theme_preview", None)  # bayat önizleme kalmasın
    store.config = config
    flag_modified(store, "config")
    activity.record(db, user, "tema_yayinla", store_id=store.id, entity_type="tema",
                    entity_label=draft.get("name") or draft_key)
    db.commit()
    db.refresh(store)
    _revalidate_storefront(store)
    return resolve_theme(store.config)


@router.get("/{store_id}/theme/presets", response_model=list[dict])
def list_theme_presets(
    store_id: uuid.UUID,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Hazır tema şablonları — panel 'Uygula' deyince istemci tarafında
    mevcut temaya merge edilir (logo/özel kod korunur), Kaydet ile kalıcılaşır."""
    from app.services.theme import THEME_PRESETS

    _get_store(db, user, store_id)
    return [
        {"key": key, "label": p_["label"], "description": p_["description"],
         "colors": p_["theme"]["colors"], "font": p_["theme"]["font"],
         "theme": p_["theme"]}
        for key, p_ in THEME_PRESETS.items()
    ]


@router.post("/{store_id}/assets", response_model=dict)
async def upload_asset(
    store_id: uuid.UUID,
    file: UploadFile = File(...),
    kind: str = Form(...),
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Tema varlığı (logo | favicon | hero) yükle → /storage URL'i döner."""
    from app.services import storage as storage_svc

    store = _get_store(db, user, store_id)
    data = await file.read()
    try:
        url = storage_svc.save_store_asset(
            user.tenant_id, store.id, kind, data, file.filename or "asset.png")
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"url": url, "kind": kind}


# ─── Özel domain doğrulama ───────────────────────────────────

@router.post("/{store_id}/verify-domain", response_model=dict)
def verify_domain(
    store_id: uuid.UUID,
    body: dict | None = None,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """custom_domain'in DNS A kaydını sunucu IP'siyle karşılaştır.

    Panel forma yazılan (henüz kaydedilmemiş) domaini body.domain ile
    gönderir — kullanıcı Kaydet'e basmadan da doğrulayabilsin.
    DNS yayılımı saatler sürebilir — başarısızlık 'yanlış kayıt' anlamına
    gelmeyebilir; mesaj bunu dürüstçe söyler.
    """
    import socket
    from datetime import datetime, timezone

    from app.config import get_settings

    store = _get_store(db, user, store_id)
    domain = (str((body or {}).get("domain") or "")
              or (store.config or {}).get("custom_domain") or "").strip().lower()
    if not domain:
        raise HTTPException(422, "Önce yukarıya alan adınızı yazın")

    expected_ip = (get_settings().server_ip or "").strip()
    try:
        infos = socket.getaddrinfo(domain, 443, proto=socket.IPPROTO_TCP)
        resolved = sorted({i[4][0] for i in infos})
    except socket.gaierror:
        return {
            "verified": False,
            "domain": domain,
            "resolved_ips": [],
            "expected_ip": expected_ip or None,
            "message": "Alan adı çözümlenemedi — DNS kaydı henüz yayılmamış olabilir "
                       "(birkaç saat sonra tekrar deneyin) veya kayıt eksik.",
        }

    verified = bool(expected_ip) and expected_ip in resolved
    if verified:
        config = dict(store.config or {})
        config["custom_domain_verified_at"] = datetime.now(timezone.utc).isoformat()
        store.config = config
        flag_modified(store, "config")
        db.commit()

    return {
        "verified": verified,
        "domain": domain,
        "resolved_ips": resolved,
        "expected_ip": expected_ip or None,
        "message": "Alan adı doğrulandı ✓" if verified else (
            f"Alan adı şu an {', '.join(resolved)} adresine işaret ediyor; "
            f"beklenen {expected_ip or 'SERVER_IP tanımsız'}. DNS değişikliği "
            f"yayılıyorsa birkaç saat sonra tekrar deneyin."
        ),
    }


# ─── Özel sayfalar + özel kod ────────────────────────────────

MAX_PAGES = 20
MAX_CODE_LEN = 20_000
_PAGE_SLUG_BLOCKLIST = {
    "urunler", "urun", "sepet", "odeme", "siparis", "koleksiyon",
    "gizlilik", "mesafeli-satis", "iade", "api", "sayfa",
}


@router.get("/{store_id}/pages", response_model=dict)
def get_pages(
    store_id: uuid.UUID,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    store = _get_store(db, user, store_id)
    return {"pages": (store.config or {}).get("pages") or []}


@router.put("/{store_id}/pages", response_model=dict)
def put_pages(
    store_id: uuid.UUID,
    body: dict,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Özel sayfalar: [{slug,title,content}] — düz metin (HTML render edilmez)."""
    from app.routers.catalog import slugify

    store = _get_store(db, user, store_id, for_update=True)
    cleaned, seen = [], set()
    for page in (body.get("pages") or [])[:MAX_PAGES]:
        if not isinstance(page, dict):
            continue
        title = str(page.get("title") or "").strip()[:200]
        if not title:
            continue
        slug = slugify(str(page.get("slug") or title))
        if slug in _PAGE_SLUG_BLOCKLIST or slug in seen:
            raise HTTPException(422, f"Sayfa adresi kullanılamaz: /{slug}")
        seen.add(slug)
        cleaned.append({
            "slug": slug,
            "title": title,
            "content": str(page.get("content") or "")[:20_000],
            # Sayfaya özel görseller (tutorial vb.) — içeriğin üstünde gösterilir
            "images": [str(u)[:500] for u in (page.get("images") or [])[:4]
                       if isinstance(u, str) and u.startswith("/storage/")],
            # Yönlendirme butonu (ops.) — "Tüm Ürünler" / koleksiyon hedefi
            "cta_text": str(page.get("cta_text") or "").strip()[:60],
            "cta_url": str(page.get("cta_url") or "").strip()[:300],
        })

    config = dict(store.config or {})
    config["pages"] = cleaned
    store.config = config
    flag_modified(store, "config")
    db.commit()
    return {"pages": cleaned}


@router.get("/{store_id}/custom-code", response_model=dict)
def get_custom_code(
    store_id: uuid.UUID,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    store = _get_store(db, user, store_id)
    code = (store.config or {}).get("custom_code") or {}
    return {k: code.get(k, "") for k in ("head_html", "css", "body_html")}


@router.put("/{store_id}/custom-code", response_model=dict)
def put_custom_code(
    store_id: uuid.UUID,
    body: dict,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    """Vitrine kod enjeksiyonu — YALNIZCA mağazanın kendi vitrininde çalışır
    (panel/backend'e dokunmaz). Panel açık uyarı gösterir."""
    store = _get_store(db, user, store_id, for_update=True)
    code = {}
    for key in ("head_html", "css", "body_html"):
        value = str(body.get(key) or "")
        if len(value) > MAX_CODE_LEN:
            raise HTTPException(422, f"{key} çok uzun (max {MAX_CODE_LEN // 1000}KB)")
        code[key] = value

    config = dict(store.config or {})
    if any(code.values()):
        config["custom_code"] = code
    else:
        config.pop("custom_code", None)
    store.config = config
    flag_modified(store, "config")
    db.commit()
    return code
