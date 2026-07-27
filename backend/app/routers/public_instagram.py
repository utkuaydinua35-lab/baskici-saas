"""Instagram DM webhook — Meta'dan gelen mesajları alır, kural tabanlı yanıt gönderir.

  GET  /api/public/instagram/webhook   → Meta doğrulaması (hub.challenge)
  POST /api/public/instagram/webhook   → gelen mesaj (X-Hub-Signature-256 ile imzalı)

Auth YOK (Meta çağırır) — güvenlik imza doğrulamasıyla sağlanır. IG_APP_SECRET ya da
IG_VERIFY_TOKEN boşsa webhook tamamen kapalıdır (404).

Hesap eşleme: entry[].id = Instagram business account id → store.config["ig_business_id"].
Yanıt gönderimi o mağazanın store.config["ig_access_token"] token'ı ile yapılır.
"""
from __future__ import annotations

import hashlib
import hmac
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import InstagramDM, Store
from app.services import ig_bot

logger = logging.getLogger("ig_webhook")
router = APIRouter(prefix="/api/public/instagram", tags=["instagram-webhook"])


def _enabled() -> bool:
    s = get_settings()
    return bool(s.ig_verify_token and s.ig_app_secret)


def _valid_signature(raw: bytes, header: str | None) -> bool:
    """Meta X-Hub-Signature-256: sha256=<hmac(app_secret, body)>."""
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(
        get_settings().ig_app_secret.encode(), raw, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, header.split("=", 1)[1].strip())


def _store_for(db: Session, ig_id: str | None) -> Store | None:
    """IG business id → mağaza. Tek eşleşme yoksa None."""
    if not ig_id:
        return None
    for st in db.scalars(select(Store)).all():
        cfg = st.config or {}
        if str(cfg.get("ig_business_id") or "").strip() == str(ig_id).strip():
            return st
    return None


def _send_dm(store: Store, recipient_id: str, text: str) -> tuple[bool, str | None]:
    """Graph API ile DM gönder. Döner: (ok, hata)."""
    import httpx
    cfg = store.config or {}
    token = (cfg.get("ig_access_token") or "").strip()
    ig_id = (cfg.get("ig_business_id") or "").strip()
    if not token or not ig_id:
        return False, "ig_access_token / ig_business_id eksik"
    ver = get_settings().ig_graph_version
    body = {"recipient": {"id": recipient_id}, "message": {"text": text[:950]}}
    # Meta'nın İKİ kurulum yolu farklı sunucu + uç kullanıyor:
    #   Facebook-login  -> graph.facebook.com  /{page|ig_id}/messages
    #   Instagram-login -> graph.instagram.com /me/messages
    # Hangisi kurulursa kurulsun çalışsın diye sırayla denenir (ilk başarı kazanır).
    page_id = (cfg.get("ig_page_id") or "").strip()
    attempts = [("https://graph.facebook.com", f"{ig_id}/messages")]
    if page_id:
        attempts.append(("https://graph.facebook.com", f"{page_id}/messages"))
    attempts += [
        ("https://graph.facebook.com", "me/messages"),
        ("https://graph.instagram.com", "me/messages"),
        ("https://graph.instagram.com", f"{ig_id}/messages"),
    ]
    last = None
    for base, p in attempts:
        try:
            r = httpx.post(f"{base}/{ver}/{p}", json=body,
                           params={"access_token": token}, timeout=15)
            if r.status_code in (200, 201):
                return True, None
            last = f"{p} → {r.status_code}: {r.text[:150]}"
        except Exception as e:  # noqa: BLE001
            last = f"{p} → {str(e)[:150]}"
    return False, last


@router.get("/webhook", response_model=None)
def verify_webhook(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
):
    """Meta panelinde webhook kaydederken çağrılır — token eşleşirse challenge döner."""
    s = get_settings()
    if not _enabled():
        raise HTTPException(404, "Not found")
    if hub_mode == "subscribe" and hub_verify_token == s.ig_verify_token:
        return Response(content=hub_challenge or "", media_type="text/plain")
    raise HTTPException(403, "Doğrulama başarısız")


@router.post("/webhook", response_model=None)
async def receive_webhook(request: Request, db: Session = Depends(get_db)):
    """Gelen DM'i işle: kural tabanlı yanıt üret, gönder, kaydet.
    Meta 200 bekler — hata olsa bile 200 döneriz (aksi halde tekrar tekrar dener)."""
    if not _enabled():
        raise HTTPException(404, "Not found")
    raw = await request.body()
    if not _valid_signature(raw, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(403, "İmza doğrulanamadı")

    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        return {"ok": True}

    for entry in (payload.get("entry") or []):
        store = _store_for(db, entry.get("id"))
        for ev in (entry.get("messaging") or []):
            msg = ev.get("message") or {}
            # Kendi gönderdiğimiz echo'ları ve tepki/okundu olaylarını atla
            if msg.get("is_echo") or not msg.get("text"):
                continue
            sender = str((ev.get("sender") or {}).get("id") or "")
            text = msg.get("text") or ""
            if not sender:
                continue
            if store is None:
                logger.warning(f"[ig] eşleşen mağaza yok (ig_business_id={entry.get('id')})")
                continue
            if not (store.config or {}).get("ig_enabled", True):
                continue

            reply, rule = ig_bot.build_reply(db, store.tenant_id, store, text)
            ok, err = _send_dm(store, sender, reply)
            db.add(InstagramDM(
                tenant_id=store.tenant_id, store_id=store.id, sender_id=sender,
                incoming=text[:2000], reply=reply[:2000], rule=rule,
                sent_ok=ok, error=err,
            ))
            # Kural eşleşmediyse panelde görünür bir bildirim düş (temsilci devralsın)
            if rule == "fallback":
                try:
                    from app.models import Notification
                    db.add(Notification(
                        tenant_id=store.tenant_id, store_id=store.id, kind="info",
                        title="Instagram: yanıtlanamayan mesaj",
                        body=text[:300],
                    ))
                    from app.services import push
                    push.send_to_tenant(
                        db, store.tenant_id, "📩 Instagram mesajı",
                        text[:120], url="/sosyal-medya", tag=f"ig-{sender}",
                    )
                except Exception:  # noqa: BLE001
                    pass
            db.commit()

    return {"ok": True}
