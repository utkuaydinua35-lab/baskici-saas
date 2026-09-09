"""Bildirim servisi — tarayici (Web Push) + uygulama (APNs).

VAPID imzali Web Push gonderir (pywebpush). Anahtarlar .env'de:
  VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY (base64url) + VAPID_SUBJECT (mailto:...).

Anahtar uretimi (bir kez, yerelde ya da VPS'te):
    python -m app.services.push --genkeys
ciktisindaki iki satiri .env'e yapistir, backend'i yeniden baslat.

Gonderim yardimcilari:
  - send_to_user(db, user_id, ...)        tek kullanicinin tum cihazlari
  - send_to_tenant(db, tenant_id, ...)    atolyedeki tum kullanicilarin cihazlari
  - send_to_platform_admins(db, ...)      is_platform_admin kullanicilar (cross-tenant)

Olu abonelikler (404/410) otomatik silinir. push_enabled() False ise sessizce no-op.

UYGULAMA BILDIRIMI: ayni cagrilar native uygulamaya da gider. Kullanicinin
kayitli cihaz jetonlari (DeviceToken) APNs uzerinden beslenir; boylece
mevcut TETIKLEYICILERIN HICBIRI degismeden uygulama da bildirim alir.
APNs yapilandirilmamissa o kisim sessizce atlanir (bkz. services/apns.py).
"""
from __future__ import annotations

import base64
import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import DeviceToken, PushSubscription, User

logger = logging.getLogger("push")


def push_enabled() -> bool:
    s = get_settings()
    return bool(s.vapid_public_key and s.vapid_private_key)


def _claims() -> dict:
    s = get_settings()
    sub = s.vapid_subject or "mailto:admin@example.com"
    if not sub.startswith("mailto:") and not sub.startswith("http"):
        sub = f"mailto:{sub}"
    return {"sub": sub}


def _send_one(sub: PushSubscription, payload: dict) -> bool:
    """Tek abonelige gonder. Basarisiz + kalici hata (404/410) ise False + silinmeli."""
    from pywebpush import webpush, WebPushException  # lazy: paket yoksa import patlamasin

    s = get_settings()
    try:
        webpush(
            subscription_info={
                "endpoint": sub.endpoint,
                "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
            },
            data=json.dumps(payload),
            vapid_private_key=s.vapid_private_key,
            vapid_claims=dict(_claims()),
            ttl=86400,
        )
        return True
    except WebPushException as e:  # noqa: PERF203
        status = getattr(getattr(e, "response", None), "status_code", None)
        if status in (404, 410):
            logger.info(f"[push] olu abonelik silinecek (HTTP {status})")
            raise _DeadSubscription() from e
        logger.warning(f"[push] gonderim hatasi (HTTP {status}): {str(e)[:160]}")
        return False
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[push] beklenmeyen hata: {str(e)[:160]}")
        return False


class _DeadSubscription(Exception):
    pass


# ─── Bildirim hangi paneli acmali? ────────────────────────────────────────
# Uygulamada iki panel TEK kabukta: mağaza paneli kökte, Studio `/studio/`
# altinda. Bildirime dokunuldugunda dogru olani acmak icin adresin hangi
# panele ait oldugunu bilmemiz gerekiyor — `/orders/123` yalnizca Studio'da,
# `/siparisler/123` yalnizca magaza panelinde var.
#
# Liste Studio'nun (frontend/src/App.jsx) KENDINE OZGU ust duzey rotalari.
# Iki panelde de bulunan yollar (/analitik, /ayarlar, /musteriler, /) magaza
# paneline gider — uygulamanin varsayilan yuzu orasi.
#
# YENI TETIKLEYICI EKLERKEN buraya bakin; scripts/bildirim_hedef_test.py
# kullanimdaki tum adresleri sabitliyor.
_STUDIO_ONEKLERI = (
    "/orders", "/bayii", "/bayiler", "/bayi-siparisleri", "/destek",
    "/kalip", "/paketleme", "/notlar", "/aski", "/designs", "/kisiye-ozel",
    "/stok", "/telafiler", "/pipeline", "/platform", "/denetim", "/stores",
    "/urun-studyosu", "/varyantli-urunler", "/aksesuarlar", "/couple",
    "/telefon-modelleri", "/sosyal-medya", "/pazarlama", "/baskici-paneli",
    "/shortcuts", "/profil-sec", "/aksesuar",
)


def hedef_uygulama(url: str | None) -> str:
    """'studio' | 'magaza' — bildirimin acacagi panel."""
    if not url:
        return "magaza"
    yol = url.split("?", 1)[0].rstrip("/") or "/"
    for on in _STUDIO_ONEKLERI:
        if yol == on or yol.startswith(on + "/"):
            return "studio"
    return "magaza"


def _dispatch(db: Session, subs: list[PushSubscription], title: str, body: str,
              url: str | None = None, tag: str | None = None,
              cihazlar: list[DeviceToken] | None = None) -> int:
    """Tarayici aboneliklerine ve uygulama cihazlarina gonderir.

    Iki tasiyici birbirinden BAGIMSIZ: biri yapilandirilmamis ya da hatali
    olsa oteki calismaya devam eder. Donus, toplam basarili gonderim sayisi.
    """
    sent = 0

    # ── tarayici (Web Push) ──
    if push_enabled() and subs:
        payload = {"title": title, "body": (body or "")[:300], "url": url or "/", "tag": tag}
        dead: list[PushSubscription] = []
        for sub in subs:
            try:
                if _send_one(sub, payload):
                    sent += 1
            except _DeadSubscription:
                dead.append(sub)
        if dead:
            for d in dead:
                db.delete(d)
            try:
                db.commit()
            except Exception:  # noqa: BLE001
                db.rollback()

    # ── uygulama (APNs) ──
    sent += _cihazlara(db, cihazlar or [], title, body, url, tag)
    return sent


def _cihazlara(db: Session, cihazlar: list[DeviceToken], title: str, body: str,
               url: str | None, tag: str | None) -> int:
    """Native cihaz jetonlarina gonder; olu jetonlarin kaydini sil."""
    if not cihazlar:
        return 0
    from app.services import apns

    if not apns.apns_enabled():
        return 0

    ios = [c for c in cihazlar if c.platform == "ios"]
    if not ios:
        return 0

    try:
        gonderilen, olu = apns.gonder([c.token for c in ios], title, body, url, tag,
                                      uygulama=hedef_uygulama(url))
    except Exception as e:  # noqa: BLE001 — bildirim hicbir is akisini durdurmasin
        logger.warning(f"[push] apns gonderimi patladi: {str(e)[:160]}")
        return 0

    if olu:
        olu_kume = set(olu)
        for c in ios:
            if c.token in olu_kume:
                db.delete(c)
        try:
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
    return gonderilen


def send_to_user(db: Session, user_id, title: str, body: str,
                 url: str | None = None, tag: str | None = None) -> int:
    subs = db.scalars(select(PushSubscription).where(PushSubscription.user_id == user_id)).all()
    cihaz = db.scalars(select(DeviceToken).where(DeviceToken.user_id == user_id)).all()
    return _dispatch(db, list(subs), title, body, url, tag, list(cihaz))


def send_to_tenant(db: Session, tenant_id, title: str, body: str,
                   url: str | None = None, tag: str | None = None) -> int:
    """Tenant'in PANEL kullanicilarina bildirim.

    Bayi portali hesaplari HARIC: onlar ayni tenant icinde ama yonetim
    bildirimlerini ("yeni bayi siparisi", senkron ozeti...) gormemeli. Kendi
    bildirimleri send_to_user ile gonderilir.
    """
    bayi_ids = select(User.id).where(User.dealer_id.isnot(None))
    subs = db.scalars(select(PushSubscription).where(
        PushSubscription.tenant_id == tenant_id,
        PushSubscription.user_id.notin_(bayi_ids),
    )).all()
    cihaz = db.scalars(select(DeviceToken).where(
        DeviceToken.tenant_id == tenant_id,
        DeviceToken.user_id.notin_(bayi_ids),
    )).all()
    return _dispatch(db, list(subs), title, body, url, tag, list(cihaz))


def send_to_platform_admins(db: Session, title: str, body: str,
                            url: str | None = None, tag: str | None = None) -> int:
    admin_ids = db.scalars(select(User.id).where(User.is_platform_admin == True)).all()  # noqa: E712
    if not admin_ids:
        return 0
    subs = db.scalars(select(PushSubscription).where(PushSubscription.user_id.in_(admin_ids))).all()
    cihaz = db.scalars(select(DeviceToken).where(DeviceToken.user_id.in_(admin_ids))).all()
    return _dispatch(db, list(subs), title, body, url, tag, list(cihaz))


# ─── VAPID anahtar uretimi (CLI) ──────────────────────────────────────────
def generate_vapid_keys() -> tuple[str, str]:
    """(public_key_b64url, private_key_b64url) — web-push standart formati."""
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization

    priv = ec.generate_private_key(ec.SECP256R1())
    pub = priv.public_key()

    pub_bytes = pub.public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    priv_val = priv.private_numbers().private_value.to_bytes(32, "big")

    def _b64(b: bytes) -> str:
        return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

    return _b64(pub_bytes), _b64(priv_val)


if __name__ == "__main__":
    import sys
    if "--genkeys" in sys.argv:
        pub, prv = generate_vapid_keys()
        print("# .env'e ekle (backend/.env):")
        print(f"VAPID_PUBLIC_KEY={pub}")
        print(f"VAPID_PRIVATE_KEY={prv}")
        print("VAPID_SUBJECT=mailto:imalchera.gfx@gmail.com")
    else:
        print("Kullanim: python -m app.services.push --genkeys")
