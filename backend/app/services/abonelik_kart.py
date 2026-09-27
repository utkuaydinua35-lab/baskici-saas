"""Kiracının abonelik ödemesi — PLATFORMUN iyzico hesabıyla (Faz 4).

Mağazaların kendi iyzico anahtarları (vitrin satışları) BURADA KULLANILMAZ:
kiralama geliri platformun ayrı hesabına geçer (karar 2026-09-27). Anahtarlar
.env'de: IYZICO_PLATFORM_API_KEY / _SECRET_KEY / _BASE_URL (boşsa sandbox).

Güvenlik: tarayıcının iyzico'dan dönüşüne GÜVENİLMEZ. Dönüşte gelen token
ile iyzico'ya SUNUCUDAN sorulur (IyzicoProvider.handle_callback): durum,
conversationId (= kayıt kimliği) ve ödenen tutar kuruşu kuruşuna tutmalı.
"""
from __future__ import annotations

from types import SimpleNamespace

from app.config import get_settings
from app.payments.base import PaymentResult
from app.payments.iyzico import SANDBOX_URL, IyzicoProvider


def acik_mi() -> bool:
    s = get_settings()
    return bool(s.iyzico_platform_api_key and s.iyzico_platform_secret_key)


def _saglayici() -> IyzicoProvider:
    s = get_settings()
    return IyzicoProvider({
        "iyzico_api_key": s.iyzico_platform_api_key,
        "iyzico_secret_key": s.iyzico_platform_secret_key,
        "iyzico_base_url": s.iyzico_platform_base_url or SANDBOX_URL,
    })


def donus_adresi(kayit_id) -> str:
    """iyzico'nun ödeme sonrası tarayıcıyı POST'ladığı adres (mağaza paneli
    alan adı /api'yi backend'e aktarır)."""
    return f"{get_settings().magaza_panel_url.rstrip('/')}/api/abonelik/kart/donus/{kayit_id}"


def odeme_baslat(kayit, tenant, sahip, *, istemci_ip: str | None = None) -> str:
    """iyzico ödeme formunu başlat; müşterinin yönlendirileceği adresi döner."""
    if not acik_mi():
        raise ValueError("Kartla ödeme henüz açık değil.")
    tutar = str(kayit.toplam)
    ad, _, soyad = (getattr(sahip, "full_name", "") or tenant.name or "-").strip().partition(" ")
    adres = {"contactName": (tenant.name or "-")[:100], "city": "-", "country": "Turkey",
             "address": "-", "zipCode": ""}
    donem = f"{kayit.donem_bas:%d.%m.%Y}–{kayit.donem_bit:%d.%m.%Y}"
    govde = {
        "locale": "tr",
        "conversationId": str(kayit.id),
        "price": tutar,
        "paidPrice": tutar,
        "currency": "TRY",
        "basketId": str(kayit.id),
        "paymentGroup": "SUBSCRIPTION",
        "callbackUrl": donus_adresi(kayit.id),
        "buyer": {
            "id": str(tenant.id),
            "name": (ad or "-")[:50],
            "surname": (soyad or "-")[:50],
            "gsmNumber": "",
            "email": getattr(sahip, "email", "") or "",
            # Vitrin ödemesiyle aynı: TCKN toplanmıyor, iyzico zorunlu alanı için yer tutucu
            "identityNumber": "11111111111",
            "registrationAddress": "-",
            "ip": istemci_ip or "85.34.78.112",
            "city": "-",
            "country": "Turkey",
        },
        "shippingAddress": adres,
        "billingAddress": adres,
        "basketItems": [{
            "id": str(kayit.id),
            "name": f"Abonelik ({donem})"[:120],
            "category1": "Yazılım Aboneliği",
            "itemType": "VIRTUAL",
            "price": tutar,
        }],
    }
    veri = _saglayici()._post("/payment/iyzipos/checkoutform/initialize/auth/ecom", govde)
    if veri.get("status") != "success" or not veri.get("paymentPageUrl"):
        raise ValueError(f"Ödeme başlatılamadı: {veri.get('errorMessage') or 'bilinmeyen hata'}")
    return veri["paymentPageUrl"]


def dogrula(kayit, form: dict) -> PaymentResult:
    """Dönüşü iyzico'ya sorarak doğrula (tutar + conversationId + durum)."""
    oturum = SimpleNamespace(token=str(kayit.id), amount=kayit.toplam)
    return _saglayici().handle_callback(form, oturum)
