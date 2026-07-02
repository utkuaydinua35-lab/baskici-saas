"""
PayTR iframe adapter.

Akış:
1. create_checkout → get-token (HMAC imzalı) → iframe URL
2. Müşteri iframe'de öder → PayTR SUNUCUDAN SUNUCUYA bildirim POST'lar
   (webhook; tarayıcıdan bağımsız)
3. handle_callback → hash'i merchant_key/salt ile yeniden hesaplar,
   hmac.compare_digest ile karşılaştırır, tutarı doğrular.
   Endpoint düz metin "OK" dönmek ZORUNDA (tekrarlar dahil).

Config (Store.config): paytr_merchant_id, paytr_merchant_key,
paytr_merchant_salt, paytr_test_mode ("1" varsayılan — canlıya geçerken "0").
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from decimal import Decimal

import requests

from app.payments.base import CheckoutInit, PaymentProvider, PaymentResult

GET_TOKEN_URL = "https://www.paytr.com/odeme/api/get-token"
IFRAME_URL = "https://www.paytr.com/odeme/guvenli/{token}"
_TIMEOUT = 30


class PayTRProvider(PaymentProvider):
    PROVIDER_NAME = "paytr"

    @property
    def merchant_id(self) -> str:
        return str(self.config.get("paytr_merchant_id") or "")

    @property
    def merchant_key(self) -> bytes:
        return str(self.config.get("paytr_merchant_key") or "").encode()

    @property
    def merchant_salt(self) -> str:
        return str(self.config.get("paytr_merchant_salt") or "")

    @property
    def test_mode(self) -> str:
        return str(self.config.get("paytr_test_mode", "1"))

    def create_checkout(self, session, callback_url: str) -> CheckoutInit:
        if not self.merchant_id or not self.merchant_key or not self.merchant_salt:
            raise ValueError("PayTR anahtarları eksik (mağaza ayarları)")

        cust = session.customer or {}
        # PayTR: tutar kuruş cinsinden tamsayı (349.90 → 34990)
        amount_kurus = int(Decimal(str(session.amount)) * 100)
        # merchant_oid alfanumerik olmalı — session id hex uygun
        merchant_oid = session.id.hex
        email = cust.get("email") or ""
        user_ip = session.client_ip or "127.0.0.1"

        basket = [
            [
                (f"{i.get('title', 'Ürün')} {i.get('model_display', '')}").strip()[:100],
                str(i.get("unit_price", "0")),
                int(i.get("quantity", 1)),
            ]
            for i in (session.cart_snapshot or [])
        ]
        user_basket = base64.b64encode(json.dumps(basket).encode()).decode()

        no_installment = "0"
        max_installment = "0"
        currency = "TL" if (session.currency or "TRY") == "TRY" else session.currency

        hash_str = (
            f"{self.merchant_id}{user_ip}{merchant_oid}{email}{amount_kurus}"
            f"{user_basket}{no_installment}{max_installment}{currency}{self.test_mode}"
        )
        paytr_token = base64.b64encode(
            hmac.new(self.merchant_key, (hash_str + self.merchant_salt).encode(),
                     hashlib.sha256).digest()
        ).decode()

        full_name = f"{cust.get('first_name', '')} {cust.get('last_name', '')}".strip() or "-"
        payload = {
            "merchant_id": self.merchant_id,
            "user_ip": user_ip,
            "merchant_oid": merchant_oid,
            "email": email,
            "payment_amount": amount_kurus,
            "paytr_token": paytr_token,
            "user_basket": user_basket,
            "debug_on": "1" if self.test_mode == "1" else "0",
            "no_installment": no_installment,
            "max_installment": max_installment,
            "user_name": full_name[:60],
            "user_address": (cust.get("address1") or "-")[:200],
            "user_phone": (cust.get("phone") or "-")[:20],
            "merchant_ok_url": callback_url + "?durum=ok",
            "merchant_fail_url": callback_url + "?durum=fail",
            "timeout_limit": "30",
            "currency": currency,
            "test_mode": self.test_mode,
            "lang": "tr",
        }

        resp = requests.post(GET_TOKEN_URL, data=payload, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "success":
            raise ValueError(f"PayTR başlatılamadı: {data.get('reason', 'bilinmeyen hata')}")

        return CheckoutInit(
            mode="iframe",
            url=IFRAME_URL.format(token=data["token"]),
            provider_ref=data["token"],
        )

    def handle_callback(self, form: dict, session) -> PaymentResult:
        """PayTR bildirim webhook'u (sunucudan sunucuya form POST)."""
        form = form or {}
        merchant_oid = str(form.get("merchant_oid") or "")
        status_ = str(form.get("status") or "")
        total_amount = str(form.get("total_amount") or "")
        received_hash = str(form.get("hash") or "")

        expected_hash = base64.b64encode(
            hmac.new(
                self.merchant_key,
                (merchant_oid + self.merchant_salt + status_ + total_amount).encode(),
                hashlib.sha256,
            ).digest()
        ).decode()

        if not hmac.compare_digest(expected_hash, received_hash):
            return PaymentResult(status="failed", error="hash doğrulanamadı")
        if merchant_oid != session.id.hex:
            return PaymentResult(status="failed", error="merchant_oid uyuşmuyor")

        safe_raw = {
            "status": status_,
            "total_amount": total_amount,
            "payment_type": form.get("payment_type"),
            "failed_reason_msg": form.get("failed_reason_msg"),
            "test_mode": form.get("test_mode"),
        }

        if status_ != "success":
            return PaymentResult(
                status="failed",
                error=form.get("failed_reason_msg") or "ödeme başarısız",
                raw=safe_raw,
            )
        # total_amount kuruş cinsinden — session tutarıyla karşılaştır
        expected_kurus = int(Decimal(str(session.amount)) * 100)
        if int(total_amount or 0) != expected_kurus:
            return PaymentResult(status="failed", error="tutar uyuşmuyor", raw=safe_raw)

        return PaymentResult(status="paid", provider_ref=merchant_oid, raw=safe_raw)
