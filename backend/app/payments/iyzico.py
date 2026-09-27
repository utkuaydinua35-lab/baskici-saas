"""
iyzico Checkout Form (CF) adapter — sağlayıcı barındırmalı ödeme sayfası.

Akış:
1. create_checkout → CF initialize (IYZWSv2 HMAC imzalı) → paymentPageUrl (redirect)
2. Müşteri iyzico sayfasında öder → iyzico tarayıcıyı callback URL'imize POST'lar
   (body: token)
3. handle_callback → tarayıcı POST'una GÜVENMEZ; token ile sunucudan sunucuya
   retrieve çağrısı yapar, paymentStatus + paidPrice + conversationId doğrular.

Config (Store.config): iyzico_api_key, iyzico_secret_key,
iyzico_base_url (default sandbox).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from decimal import Decimal

import requests

from app.payments.base import (
    CheckoutInit, PaymentProvider, PaymentResult, RefundResult, scaled_basket_lines,
)

SANDBOX_URL = "https://sandbox-api.iyzipay.com"
_TIMEOUT = 30


class IyzicoProvider(PaymentProvider):
    PROVIDER_NAME = "iyzico"

    @property
    def base_url(self) -> str:
        return (self.config.get("iyzico_base_url") or SANDBOX_URL).rstrip("/")

    @property
    def api_key(self) -> str:
        return self.config.get("iyzico_api_key") or ""

    @property
    def secret_key(self) -> str:
        return self.config.get("iyzico_secret_key") or ""

    # ── IYZWSv2 imzalı istek ──
    def _headers(self, uri_path: str, body: str) -> dict:
        random_key = uuid.uuid4().hex
        payload = random_key + uri_path + body
        signature = hmac.new(
            self.secret_key.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()
        auth_str = (
            f"apiKey:{self.api_key}"
            f"&randomKey:{random_key}"
            f"&signature:{signature}"
        )
        b64 = base64.b64encode(auth_str.encode()).decode()
        return {
            "Authorization": f"IYZWSv2 {b64}",
            "Content-Type": "application/json",
        }

    def _post(self, uri_path: str, payload: dict) -> dict:
        body = json.dumps(payload)
        resp = requests.post(
            f"{self.base_url}{uri_path}",
            data=body,
            headers=self._headers(uri_path, body),
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    # ── PaymentProvider ──
    def create_checkout(self, session, callback_url: str) -> CheckoutInit:
        if not self.api_key or not self.secret_key:
            raise ValueError("iyzico anahtarları eksik (mağaza ayarları)")

        cust = session.customer or {}
        total = str(session.amount)
        # iyzico: basketItems fiyat toplamı price alanına eşit olmalı; indirim
        # ayrı satır olamayacağından kalem toplamları indirimli tutara ölçeklenir.
        # Kalem kimliği varyant kimliği; aynı model farklı ek seçenekle iki satır
        # olabildiğinden tekrar eden kimliğe sıra no eklenir (tek satırlı sepet
        # eskisi gibi kalır).
        satirlar = scaled_basket_lines(session)
        vid_sayisi: dict[str, int] = {}
        for item, _ in satirlar:
            v = str(item.get("variant_id"))
            vid_sayisi[v] = vid_sayisi.get(v, 0) + 1
        basket_items = [
            {
                "id": (str(item.get("variant_id", i)) if vid_sayisi.get(str(item.get("variant_id")), 0) <= 1
                       else f"{item.get('variant_id')}-{i + 1}"),
                "name": (f"{item.get('title', 'Ürün')} {item.get('model_display', '')}").strip()[:120],
                "category1": "Telefon Kılıfı",
                "itemType": "PHYSICAL",
                "price": str(line_total),
            }
            for i, (item, line_total) in enumerate(satirlar)
        ]
        if session.shipping_amount and Decimal(str(session.shipping_amount)) > 0:
            basket_items.append({
                "id": "kargo",
                "name": "Kargo",
                "category1": "Kargo",
                "itemType": "VIRTUAL",
                "price": str(session.shipping_amount),
            })

        address = (cust.get("address1") or "-")[:200]
        city = (cust.get("city") or "-")[:60]
        full_name = f"{cust.get('first_name', '')} {cust.get('last_name', '')}".strip() or "-"
        addr_obj = {
            "contactName": full_name,
            "city": city,
            "country": "Turkey",
            "address": address,
            "zipCode": (cust.get("zip") or "")[:20],
        }
        payload = {
            "locale": "tr",
            "conversationId": session.token,
            "price": total,
            "paidPrice": total,
            "currency": session.currency or "TRY",
            "basketId": str(session.id),
            "paymentGroup": "PRODUCT",
            "callbackUrl": callback_url,
            "buyer": {
                "id": str(session.id),
                "name": cust.get("first_name") or "-",
                "surname": cust.get("last_name") or "-",
                "gsmNumber": cust.get("phone") or "",
                "email": cust.get("email") or "",
                # Misafir checkout: TCKN toplanmıyor (KVKK veri minimizasyonu);
                # iyzico zorunlu alanı için sabit placeholder kabul ediyor.
                "identityNumber": "11111111111",
                "registrationAddress": address,
                "ip": session.client_ip or "85.34.78.112",
                "city": city,
                "country": "Turkey",
            },
            "shippingAddress": addr_obj,
            "billingAddress": addr_obj,
            "basketItems": basket_items,
        }

        data = self._post("/payment/iyzipos/checkoutform/initialize/auth/ecom", payload)
        if data.get("status") != "success":
            raise ValueError(f"iyzico başlatılamadı: {data.get('errorMessage', 'bilinmeyen hata')}")

        return CheckoutInit(
            mode="redirect",
            url=data["paymentPageUrl"],
            provider_ref=data.get("token"),
        )

    def handle_callback(self, form: dict, session) -> PaymentResult:
        token = (form or {}).get("token")
        if not token:
            return PaymentResult(status="failed", error="token eksik")
        # Tarayıcı POST'una güvenme — sunucudan sunucuya retrieve ile doğrula.
        try:
            data = self._post(
                "/payment/iyzipos/checkoutform/auth/ecom/detail",
                {"locale": "tr", "conversationId": session.token, "token": token},
            )
        except requests.RequestException as e:
            return PaymentResult(status="failed", error=f"iyzico doğrulama erişilemedi: {e}")

        # Loglanabilir güvenli özet (kart/PII alanları hariç)
        safe_raw = {k: data.get(k) for k in (
            "status", "paymentStatus", "paidPrice", "price", "currency",
            "conversationId", "paymentId", "fraudStatus", "errorMessage",
        )}
        # İade için kalem işlem kimlikleri (session.callback_raw'a akar)
        safe_raw["itemTransactions"] = [
            {"paymentTransactionId": t.get("paymentTransactionId"),
             "paidPrice": t.get("paidPrice")}
            for t in (data.get("itemTransactions") or [])
            if t.get("paymentTransactionId")
        ]

        if data.get("status") != "success" or data.get("paymentStatus") != "SUCCESS":
            return PaymentResult(
                status="failed",
                error=data.get("errorMessage") or f"paymentStatus={data.get('paymentStatus')}",
                raw=safe_raw,
            )
        if data.get("conversationId") != session.token:
            return PaymentResult(status="failed", error="conversationId uyuşmuyor", raw=safe_raw)
        # Tutar doğrulama — kuruş toleransı yok.
        if Decimal(str(data.get("paidPrice", "0"))) != Decimal(str(session.amount)):
            return PaymentResult(status="failed", error="tutar uyuşmuyor", raw=safe_raw)

        return PaymentResult(
            status="paid",
            provider_ref=str(data.get("paymentId") or token),
            raw=safe_raw,
        )

    def _get_item_transactions(self, session) -> list[dict]:
        """İade için kalem işlemleri: önce callback_raw, yoksa /payment/detail."""
        txs = (session.callback_raw or {}).get("itemTransactions") or []
        if txs:
            return txs
        # Eski oturumlar (itemTransactions kaydedilmeden önce ödenmiş) için fallback
        data = self._post("/payment/detail", {
            "locale": "tr",
            "conversationId": session.token,
            "paymentId": session.provider_ref,
        })
        if data.get("status") != "success":
            raise ValueError(data.get("errorMessage") or "ödeme detayı alınamadı")
        return [
            {"paymentTransactionId": t.get("paymentTransactionId"),
             "paidPrice": t.get("paidPrice")}
            for t in (data.get("itemTransactions") or [])
            if t.get("paymentTransactionId")
        ]

    def refund(self, session, amount) -> RefundResult:
        """Kısmi/tam iade — iyzico kalem bazlı çalışır; tutar kalemler
        üzerinde greedy dağıtılır (kalem başına ödenen tutarı aşmadan)."""
        remaining = Decimal(str(amount))
        try:
            txs = self._get_item_transactions(session)
        except (requests.RequestException, ValueError) as e:
            return RefundResult(status="failed", error=f"işlem listesi alınamadı: {e}")
        if not txs:
            return RefundResult(status="failed", error="iade edilecek işlem bulunamadı")

        refunded_parts: list[dict] = []
        for tx in txs:
            if remaining <= 0:
                break
            tx_price = Decimal(str(tx.get("paidPrice", "0")))
            part = min(remaining, tx_price)
            if part <= 0:
                continue
            try:
                data = self._post("/payment/refund", {
                    "locale": "tr",
                    "conversationId": session.token,
                    "paymentTransactionId": tx["paymentTransactionId"],
                    "price": str(part),
                    "currency": session.currency or "TRY",
                    "ip": session.client_ip or "127.0.0.1",
                })
            except requests.RequestException as e:
                return RefundResult(
                    status="failed",
                    error=f"iade isteği başarısız: {e}",
                    raw={"refunded_parts": refunded_parts},
                )
            if data.get("status") != "success":
                return RefundResult(
                    status="failed",
                    error=data.get("errorMessage") or "iade reddedildi",
                    raw={"refunded_parts": refunded_parts,
                         "failed_tx": tx["paymentTransactionId"]},
                )
            refunded_parts.append({
                "paymentTransactionId": tx["paymentTransactionId"],
                "price": str(part),
                "paymentId": data.get("paymentId"),
            })
            remaining -= part

        if remaining > 0:
            return RefundResult(
                status="failed",
                error=f"tutarın {remaining} TL'si iade edilemedi (işlem kapasitesi yetersiz)",
                raw={"refunded_parts": refunded_parts},
            )
        return RefundResult(
            status="succeeded",
            provider_ref=str(refunded_parts[0].get("paymentId") or session.provider_ref),
            raw={"refunded_parts": refunded_parts},
        )
