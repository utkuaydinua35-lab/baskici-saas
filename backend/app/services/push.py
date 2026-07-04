"""Web Push (PWA mobil bildirim) servisi.

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
"""
from __future__ import annotations

import base64
import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import PushSubscription, User

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


def _dispatch(db: Session, subs: list[PushSubscription], title: str, body: str,
              url: str | None = None, tag: str | None = None) -> int:
    if not push_enabled() or not subs:
        return 0
    payload = {"title": title, "body": (body or "")[:300], "url": url or "/", "tag": tag}
    sent = 0
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
    return sent


def send_to_user(db: Session, user_id, title: str, body: str,
                 url: str | None = None, tag: str | None = None) -> int:
    subs = db.scalars(select(PushSubscription).where(PushSubscription.user_id == user_id)).all()
    return _dispatch(db, list(subs), title, body, url, tag)


def send_to_tenant(db: Session, tenant_id, title: str, body: str,
                   url: str | None = None, tag: str | None = None) -> int:
    subs = db.scalars(select(PushSubscription).where(PushSubscription.tenant_id == tenant_id)).all()
    return _dispatch(db, list(subs), title, body, url, tag)


def send_to_platform_admins(db: Session, title: str, body: str,
                            url: str | None = None, tag: str | None = None) -> int:
    admin_ids = db.scalars(select(User.id).where(User.is_platform_admin == True)).all()  # noqa: E712
    if not admin_ids:
        return 0
    subs = db.scalars(select(PushSubscription).where(PushSubscription.user_id.in_(admin_ids))).all()
    return _dispatch(db, list(subs), title, body, url, tag)


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
