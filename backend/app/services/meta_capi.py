"""
Meta Conversions API (CAPI) — sunucu taraflı Purchase gönderimi.

Neden: tarayıcı pikseli reklam engelleyici / iOS izleme kısıtlarında susar
(%15-25 olay kaybı). Sunucudan da gönderilir; tarayıcı pikseliyle AYNI
event_id kullanıldığı için Meta iki kaynağı tekilleştirir (çift sayım olmaz).

HANGİ OLAYLAR
  Purchase               — ödeme doğrulandığında, doğrudan sunucudan
  ViewContent/AddToCart/
  InitiateCheckout       — vitrinin KENDİ alan adındaki bir uca (beacon)
                           gidip oradan Meta'ya iletilir

Neden beacon: sepet tarayıcıda tutuluyor, sunucunun haberi olmuyor. Ama
istek BİZİM alan adımıza gittiği için reklam engelleyiciler onu kesmiyor
(facebook.net'i kesiyorlar) ve sunucu IP/User-Agent'ı olaya ekleyebiliyor —
ikisi de Meta'nın eşleşme kalitesini (EMQ) yükseltir.

Config anahtarları (mağaza bazlı):
  meta_pixel_id        — piksel kimliği (Pazarlama sekmesi)
  meta_capi_token      — Events Manager > Ayarlar > Conversions API erişim jetonu
  meta_test_event_code — (ops.) Test Events doğrulaması için TESTxxxxx kodu
"""
from __future__ import annotations

import hashlib
import logging
import threading

logger = logging.getLogger("meta_capi")

GRAPH_URL = "https://graph.facebook.com/v21.0/{pixel_id}/events"


def _h(value: str | None) -> str | None:
    """Meta user_data normalizasyonu: küçük harf + trim + sha256."""
    v = (value or "").strip().lower()
    return hashlib.sha256(v.encode()).hexdigest() if v else None


# Beacon ile kabul edilen olaylar — beyaz liste dışındakiler sessizce atılır.
# PageView: yeniden pazarlama kitleleri (site ziyaretçileri) bundan kurulur;
# tarayıcı pikseli engellendiğinde/yüklenmeden çıkıldığında kaybolmasın.
BEACON_OLAYLARI = {"PageView", "ViewContent", "AddToCart", "InitiateCheckout", "AddPaymentInfo"}

# Test olay kodu SÜRELİ: doluyken sunucu olayları yalnız "Olayları Test Et"
# ekranına düşer, reklam raporlarına/optimizasyona GİTMEZ. Unutulursa satışlar
# reklamda görünmez — bu yüzden kaydedildikten TEST_KODU_SAAT saat sonra
# kendiliğinden yok sayılır (panel kaydında meta_test_event_code_at yazılır).
TEST_KODU_SAAT = 3


def gecerli_test_kodu(config: dict) -> str | None:
    kod = (config.get("meta_test_event_code") or "").strip()
    if not kod:
        return None
    from datetime import datetime, timedelta, timezone
    try:
        zaman = datetime.fromisoformat(str(config.get("meta_test_event_code_at") or ""))
    except ValueError:
        return None   # zamanı bilinmeyen (eski) kod: canlı sayılır, test'e düşürülmez
    if zaman.tzinfo is None:
        zaman = zaman.replace(tzinfo=timezone.utc)
    return kod if datetime.now(timezone.utc) - zaman < timedelta(hours=TEST_KODU_SAAT) else None


def tr_telefon(tel) -> str | None:
    """Meta'nın beklediği biçim: ülke koduyla, yalnız rakam — 905321234567.

    ESKİ HATA: "9" + numara.lstrip("0") yapılıyordu → "0532…" "9532…" oluyor
    ve Meta telefonla HİÇ eşleştiremiyordu (Purchase eşleşme kalitesi düşük).
    """
    d = "".join(ch for ch in str(tel or "") if ch.isdigit())
    if d.startswith("00"):          # uluslararası önek: 0090… → 90…
        d = d[2:]
    if len(d) == 10 and d.startswith("5"):
        d = "90" + d
    elif len(d) == 11 and d.startswith("0"):
        d = "9" + d
    return d if len(d) >= 10 else None


def ziyaretci_kimligi(vid: str | None) -> str | None:
    """Birinci taraf ziyaretçi kimliği (bz_vid çerezi) → external_id.
    Tarayıcı pikseli aynı değeri init'te verir (piksel kendisi hash'ler);
    burada sha256'sı gönderilir — iki kaynak aynı kişiyi gösterir."""
    v = (vid or "").strip()
    return _h(v) if v and len(v) <= 64 else None


def _gonder_async(pixel_id: str, token: str, body: dict, etiket: str) -> None:
    """Meta'ya arka planda gönder — çağıran akışı asla bekletmez."""
    def _send() -> None:
        try:
            import httpx
            r = httpx.post(
                GRAPH_URL.format(pixel_id=pixel_id),
                params={"access_token": token}, json=body, timeout=8,
            )
            if r.status_code == 200:
                logger.info("[capi] %s gönderildi", etiket)
            else:
                logger.warning("[capi] Meta %s: %s", r.status_code, r.text[:300])
        except Exception as e:  # noqa: BLE001
            logger.warning("[capi] gönderim hatası: %s", e)

    threading.Thread(target=_send, daemon=True).start()


def _kimlik(config: dict) -> tuple[str, str] | None:
    pixel_id = (config.get("meta_pixel_id") or "").strip()
    token = (config.get("meta_capi_token") or "").strip()
    return (pixel_id, token) if pixel_id and token else None


def send_event(store, *, event_name: str, event_id: str, user_data: dict,
               custom_data: dict | None = None, source_url: str | None = None) -> bool:
    """Tek bir olayı sunucudan Meta'ya gönder. Config eksikse sessizce False."""
    config = store.config or {}
    kimlik = _kimlik(config)
    if not kimlik:
        return False
    pixel_id, token = kimlik
    import time
    event = {
        "event_name": event_name,
        "event_time": int(time.time()),
        "event_id": event_id,
        "action_source": "website",
        "event_source_url": source_url or None,
        "user_data": {k: v for k, v in user_data.items() if v},
        "custom_data": custom_data or None,
    }
    body: dict = {"data": [{k: v for k, v in event.items() if v is not None}]}
    test_code = gecerli_test_kodu(config)
    if test_code:
        body["test_event_code"] = test_code
    _gonder_async(pixel_id, token, body, f"{event_name} ({event_id})")
    return True


def purchase_event_id(session_token: str) -> str:
    """Tarayıcı pikseli (eventID) ile sunucunun paylaştığı dedup anahtarı."""
    return f"purchase_{session_token}"


def build_purchase_payload(store, session) -> dict | None:
    """CAPI Purchase gövdesi — config eksikse None (özellik kapalı)."""
    config = store.config or {}
    pixel_id = (config.get("meta_pixel_id") or "").strip()
    token = (config.get("meta_capi_token") or "").strip()
    if not pixel_id or not token:
        return None

    cust = session.customer or {}
    meta = cust.get("_meta") or {}
    snap = session.cart_snapshot or []
    from app.services.site import site_url
    site = site_url(config)

    user_data = {
        k: v for k, v in {
            "em": _h(cust.get("email")),
            "ph": _h(tr_telefon(cust.get("phone"))),
            "fn": _h(cust.get("first_name")),
            "ln": _h(cust.get("last_name")),
            "client_ip_address": meta.get("ip") or None,
            "client_user_agent": meta.get("ua") or None,
            "fbp": meta.get("fbp") or None,
            "fbc": meta.get("fbc") or None,
            # Kararlı müşteri kimliği — Meta'nın eşleşme kalitesini yükseltir.
            # Ziyaretçi kimliği (gezinme olaylarıyla AYNI) + e-posta hash'i;
            # Meta birden çok external_id'yi liste olarak kabul eder.
            "external_id": [x for x in (ziyaretci_kimligi(meta.get("vid")), _h(cust.get("email"))) if x] or None,
        }.items() if v
    }

    event = {
        "event_name": "Purchase",
        "event_time": int(session.paid_at.timestamp()) if session.paid_at else None,
        "event_id": purchase_event_id(session.token),
        "action_source": "website",
        "event_source_url": f"{site}/odeme/sonuc" if site else None,
        "user_data": user_data,
        "custom_data": {
            "currency": session.currency or "TRY",
            "value": float(session.amount or 0),
            "content_type": "product",
            "content_ids": [i.get("product_slug") for i in snap if i.get("product_slug")],
            "contents": [
                {"id": i.get("product_slug"), "quantity": i.get("quantity", 1),
                 "item_price": float(i.get("unit_price") or 0)}
                for i in snap if i.get("product_slug")
            ],
        },
    }
    body: dict = {"data": [{k: v for k, v in event.items() if v is not None}]}
    test_code = gecerli_test_kodu(config)
    if test_code:
        body["test_event_code"] = test_code
    return {"pixel_id": pixel_id, "token": token, "body": body}


def send_purchase_async(store, session) -> None:
    """Purchase'ı arka planda gönder — ödeme callback'ini asla geciktirmez,
    hata olursa yalnızca loglanır (sipariş akışı etkilenmez)."""
    payload = build_purchase_payload(store, session)
    if payload is None:
        return
    _gonder_async(payload["pixel_id"], payload["token"], payload["body"],
                  f"Purchase ({payload['body']['data'][0]['event_id']})")
