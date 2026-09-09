"""APNs (Apple Push Notification service) — iOS uygulamasına bildirim.

Web Push tarayıcı içindir ve uygulamada ÇALIŞMAZ: kabukta service worker yok,
sayfa `capacitor://localhost` origin'inde. Uygulamaya bildirim işletim sistemi
üzerinden, Apple'ın APNs'i ile gider.

YAPILANDIRMA (.env):
    APNS_KEY_PATH=/srv/baskici/gizli/AuthKey_XXXXXXXXXX.p8
    APNS_KEY_ID=XXXXXXXXXX          # Apple Developer → Keys
    APNS_TEAM_ID=XXXXXXXXXX         # Apple Developer → Membership
    APNS_BUNDLE_ID=com.bernzcompany.magazapanel
    APNS_ENV=sandbox                # Xcode'dan kurulan derleme; TestFlight/App Store → production

.p8 anahtarı ÜCRETLİ Apple Developer üyeliği gerektiriyor. Ayarlar eksikken
`apns_enabled()` False döner ve tüm gönderimler sessizce no-op olur — yani bu
modül yapılandırılmadan da sistem sorunsuz çalışır.

SANDBOX / PRODUCTION AYRIMI ÖNEMLİ: yanlış ortama gönderilen jeton
"BadDeviceToken" ile reddedilir. Xcode'dan telefona kurulan uygulama sandbox,
TestFlight ve App Store production kullanır.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger("push")

# APNs jetonu (JWT) en fazla 1 saat geçerli; Apple 20 dakikadan sık
# yenilenmesini de istemiyor. 50 dakikada bir tazeliyoruz.
_JETON_OMRU_SN = 50 * 60
_jeton: tuple[str, float] | None = None       # (jwt, uretim_zamani)

# Kalıcı olarak ölü jetonlar — kaydı silinmeli.
OLU_SEBEPLER = {"BadDeviceToken", "Unregistered", "DeviceTokenNotForTopic"}


def apns_enabled() -> bool:
    s = get_settings()
    return bool(s.apns_key_path and s.apns_key_id and s.apns_team_id and s.apns_bundle_id)


def _sunucu() -> str:
    s = get_settings()
    return ("https://api.push.apple.com" if s.apns_env == "production"
            else "https://api.sandbox.push.apple.com")


def _yetki_jetonu() -> str | None:
    """ES256 imzalı APNs sağlayıcı jetonu (önbellekli)."""
    global _jeton
    s = get_settings()
    if _jeton and time.time() - _jeton[1] < _JETON_OMRU_SN:
        return _jeton[0]

    try:
        anahtar = Path(s.apns_key_path).read_text()
    except OSError as e:
        logger.warning(f"[apns] .p8 okunamadi ({s.apns_key_path}): {e}")
        return None

    from jose import jwt as jose_jwt

    try:
        imzali = jose_jwt.encode(
            {"iss": s.apns_team_id, "iat": int(time.time())},
            anahtar,
            algorithm="ES256",
            headers={"kid": s.apns_key_id},
        )
    except Exception as e:  # noqa: BLE001 — bozuk anahtar tüm bildirimi durdurmasın
        logger.warning(f"[apns] jeton imzalanamadi: {str(e)[:160]}")
        return None

    _jeton = (imzali, time.time())
    return imzali


def gonder(tokens: list[str], title: str, body: str,
           url: str | None = None, tag: str | None = None,
           uygulama: str = "magaza") -> tuple[int, list[str]]:
    """Verilen cihaz jetonlarına bildirim gönderir.

    Dönüş: (basarili_sayisi, olu_jetonlar). Ölü jetonların kaydı silinmeli —
    cihazdan uygulama kaldırılmış ya da jeton yenilenmiş demektir.
    """
    if not apns_enabled() or not tokens:
        return 0, []

    yetki = _yetki_jetonu()
    if not yetki:
        return 0, []

    s = get_settings()
    govde = {
        "aps": {
            "alert": {"title": title, "body": (body or "")[:300]},
            "sound": "default",
            # Rozet sayısını sunucu bilmiyor; uygulama kendi hesaplasın diye
            # göndermiyoruz — yanlış sayı göstermektense hiç göstermemek iyi.
            "thread-id": tag or "genel",
        },
        # Uygulamanın bildirime dokununca gideceği yer. `app`, iki panelden
        # hangisinin açılacağını söyler (bkz. services/push.py:hedef_uygulama).
        "url": url or "/",
        "app": uygulama,
    }
    veri = json.dumps(govde).encode()

    basliklar = {
        "authorization": f"bearer {yetki}",
        "apns-topic": s.apns_bundle_id,
        "apns-push-type": "alert",
        "apns-priority": "10",
        "apns-expiration": str(int(time.time()) + 86400),
    }
    if tag:
        basliklar["apns-collapse-id"] = tag[:64]

    import httpx

    sunucu = _sunucu()
    gonderilen = 0
    olu: list[str] = []
    try:
        # APNs HTTP/2 zorunlu tutuyor; httpx bunun için `h2` paketini ister.
        with httpx.Client(http2=True, timeout=10.0) as c:
            for t in tokens:
                try:
                    r = c.post(f"{sunucu}/3/device/{t}", content=veri, headers=basliklar)
                except Exception as e:  # noqa: BLE001, PERF203
                    logger.warning(f"[apns] baglanti hatasi: {str(e)[:160]}")
                    continue
                if r.status_code == 200:
                    gonderilen += 1
                    continue
                sebep = ""
                try:
                    sebep = (r.json() or {}).get("reason", "")
                except Exception:  # noqa: BLE001
                    sebep = r.text[:120]
                if sebep in OLU_SEBEPLER:
                    olu.append(t)
                    logger.info(f"[apns] olu jeton ({sebep})")
                else:
                    logger.warning(f"[apns] gonderilemedi (HTTP {r.status_code}): {sebep}")
    except ImportError:
        logger.warning("[apns] httpx HTTP/2 destegi yok — `pip install 'httpx[http2]'`")
        return 0, []

    return gonderilen, olu
