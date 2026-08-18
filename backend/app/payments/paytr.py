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
import logging
from decimal import Decimal

import requests

from app.payments.base import CheckoutInit, PaymentProvider, PaymentResult, RefundResult

log = logging.getLogger("odeme.paytr")

GET_TOKEN_URL = "https://www.paytr.com/odeme/api/get-token"
IFRAME_URL = "https://www.paytr.com/odeme/guvenli/{token}"
REFUND_URL = "https://www.paytr.com/odeme/iade"
_TIMEOUT = 30


def _json_coz(resp, ne: str) -> dict:
    """PayTR cevabını JSON'a çevir; değilse SEBEBİ görünür bir hataya dönüştür.

    resp.json() ham JSONDecodeError fırlatıyordu ("Expecting value: line 1
    column 1") — panelde bu mesaj görünüyor ama PayTR'nin ne dediği kayboluyordu.
    Sağlayıcı hata durumunda HTML dönebiliyor (geçersiz merchant_ok_url, IP
    kısıtı, bakım sayfası); teşhis için gövdenin başı gerekiyor.
    """
    govde = (resp.text or "").strip()
    try:
        return resp.json()
    except ValueError:
        ozet = " ".join(govde.split())[:200] or "(cevap boş)"
        # Panelde kısaltılmış hâli görünür; tam gövde günlükte kalsın
        log.error("paytr %s cevabi JSON degil: HTTP %s ct=%s govde=%r",
                  ne, resp.status_code, resp.headers.get("content-type"), govde[:1000])
        raise ValueError(
            f"PayTR {ne} isteğine JSON dönmedi (HTTP {resp.status_code}): {ozet}"
        ) from None


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
        # PayTR merchant_ok_url/fail_url'i MUTLAK ister. Vitrin adresi tanımsız
        # kalınca "/odeme/sonuc" gibi göreli bir adres gidiyor ve istek daha
        # anlamsız bir hatayla reddediliyordu — sebebi burada söylüyoruz.
        if not str(callback_url or "").startswith(("http://", "https://")):
            raise ValueError(
                "Vitrin adresi tanımlı değil, PayTR'ye geçerli bir dönüş adresi "
                "verilemiyor. Ayarlar → Genel'de mağazanın alan adını kaydedin.")

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
        data = _json_coz(resp, "ödeme başlatma")
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

    def refund(self, session, amount) -> RefundResult:
        """Kısmi/tam iade — PayTR /odeme/iade (kısmi ve tekrarlı iadeyi destekler)."""
        merchant_oid = session.id.hex
        return_amount = f"{Decimal(str(amount)):.2f}"
        paytr_token = base64.b64encode(
            hmac.new(
                self.merchant_key,
                (str(self.merchant_id) + merchant_oid + return_amount + self.merchant_salt).encode(),
                hashlib.sha256,
            ).digest()
        ).decode()
        try:
            resp = requests.post(REFUND_URL, data={
                "merchant_id": self.merchant_id,
                "merchant_oid": merchant_oid,
                "return_amount": return_amount,
                "paytr_token": paytr_token,
            }, timeout=_TIMEOUT)
            resp.raise_for_status()
            data = _json_coz(resp, "iade")
        except (requests.RequestException, ValueError) as e:
            return RefundResult(status="failed", error=f"PayTR iade isteği başarısız: {e}")

        if data.get("status") != "success":
            return RefundResult(
                status="failed",
                error=data.get("err_msg") or data.get("reason") or "iade reddedildi",
                raw={"status": data.get("status"), "err_no": data.get("err_no")},
            )
        return RefundResult(
            status="succeeded",
            provider_ref=merchant_oid,
            raw={"return_amount": data.get("return_amount"), "is_test": data.get("is_test")},
        )
