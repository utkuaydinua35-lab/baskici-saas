"""Web Push abonelik yonetimi — /api/push/*

- GET  /api/push/vapid-key   → tarayicinin abone olurken kullanacagi public key + enabled
- POST /api/push/subscribe    → tarayici aboneligini kaydet (upsert, endpoint benzersiz)
- POST /api/push/unsubscribe  → aboneligi sil (endpoint ile)
- POST /api/push/test         → mevcut kullaniciya deneme bildirimi gonder
- POST /api/push/device       → native uygulama cihaz jetonunu kaydet (upsert)
- DELETE /api/push/device     → cihaz jetonunu sil (cikista)
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import DeviceToken, PushSubscription, User
from app.services import push as push_svc

router = APIRouter(prefix="/api/push", tags=["push"])


class SubKeys(BaseModel):
    p256dh: str
    auth: str


class SubscribeIn(BaseModel):
    endpoint: str
    keys: SubKeys
    user_agent: str | None = None


@router.get("/vapid-key", response_model=dict)
def vapid_key(user: User = Depends(get_current_user)):
    s = get_settings()
    return {"enabled": push_svc.push_enabled(), "public_key": s.vapid_public_key or None}


@router.post("/subscribe", response_model=dict)
def subscribe(
    body: SubscribeIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = db.scalar(select(PushSubscription).where(PushSubscription.endpoint == body.endpoint))
    now = datetime.now(timezone.utc)
    if existing:
        # Ayni cihaz baska kullaniciya/tenant'a gecmis olabilir — sahiplendir + anahtarlari tazele
        existing.user_id = user.id
        existing.tenant_id = user.tenant_id
        existing.p256dh = body.keys.p256dh
        existing.auth = body.keys.auth
        existing.user_agent = (body.user_agent or existing.user_agent or "")[:300] or None
        existing.last_used_at = now
    else:
        db.add(PushSubscription(
            tenant_id=user.tenant_id,
            user_id=user.id,
            endpoint=body.endpoint,
            p256dh=body.keys.p256dh,
            auth=body.keys.auth,
            user_agent=(body.user_agent or "")[:300] or None,
            last_used_at=now,
        ))
    db.commit()
    return {"ok": True}


class UnsubscribeIn(BaseModel):
    endpoint: str


@router.post("/unsubscribe", response_model=dict)
def unsubscribe(
    body: UnsubscribeIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub = db.scalar(select(PushSubscription).where(
        PushSubscription.endpoint == body.endpoint,
        PushSubscription.user_id == user.id,
    ))
    if sub:
        db.delete(sub)
        db.commit()
    return {"ok": True}


class DeviceIn(BaseModel):
    token: str
    platform: str = "ios"
    device_name: str | None = None


@router.post("/device", response_model=dict)
def register_device(
    body: DeviceIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Native uygulamanin cihaz jetonunu kaydeder.

    Jeton cihaza ozgu ve DEGISEBILIR. Ayni jeton baska bir kullaniciya
    gecmisse (telefonu devreden biri) kayit sahiplendirilir; aksi halde eski
    sahibin bildirimleri yeni kullanicinin telefonuna duserdi.
    """
    if body.platform not in ("ios", "android"):
        return {"ok": False, "reason": "bilinmeyen platform"}

    jeton = (body.token or "").strip()
    if not jeton or len(jeton) > 400:
        return {"ok": False, "reason": "gecersiz jeton"}

    now = datetime.now(timezone.utc)
    mevcut = db.scalar(select(DeviceToken).where(DeviceToken.token == jeton))
    if mevcut:
        mevcut.user_id = user.id
        mevcut.tenant_id = user.tenant_id
        mevcut.platform = body.platform
        mevcut.device_name = (body.device_name or mevcut.device_name or "")[:120] or None
        mevcut.last_used_at = now
    else:
        db.add(DeviceToken(
            tenant_id=user.tenant_id,
            user_id=user.id,
            token=jeton,
            platform=body.platform,
            device_name=(body.device_name or "")[:120] or None,
            last_used_at=now,
        ))
    db.commit()
    return {"ok": True}


@router.delete("/device", response_model=dict)
def unregister_device(
    token: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    kayit = db.scalar(select(DeviceToken).where(
        DeviceToken.token == token,
        DeviceToken.user_id == user.id,
    ))
    if kayit:
        db.delete(kayit)
        db.commit()
    return {"ok": True}


@router.post("/test", response_model=dict)
def test_push(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.services import apns as apns_svc

    if not push_svc.push_enabled() and not apns_svc.apns_enabled():
        return {"ok": False, "sent": 0,
                "reason": "Sunucuda ne VAPID ne APNs anahtarlari tanimli"}
    sent = push_svc.send_to_user(
        db, user.id, f"{get_settings().brand_name} — deneme bildirimi",
        "Mobil bildirimler calisiyor ✅", url="/", tag="test",
    )
    return {"ok": sent > 0, "sent": sent}
