"""Güvenlik uyarıları — şüpheli aktivite (brute-force, dağıtık giriş saldırısı)
tespit edilince platform yöneticilerine anlık bildirim.

Kanallar: Telegram (varsa) + Web Push (platform admin abonelikleri).
Her uyarı ANAHTARI için cooldown ile throttle edilir (spam önler).
Hata-toleranslı: bildirim gönderimi hata verse bile giriş akışını BOZMAZ.
"""
from __future__ import annotations

import logging
import time

logger = logging.getLogger("security")

_last_alert: dict[str, float] = {}
_ALERT_COOLDOWN = 600  # aynı anahtar için 10 dk'da bir uyarı


def alert(key: str, title: str, body: str, url: str = "/denetim",
          cooldown: int = _ALERT_COOLDOWN) -> None:
    now = time.time()
    if now - _last_alert.get(key, 0) < cooldown:
        return
    _last_alert[key] = now
    # eski anahtarları buda (bellek sızıntısı önle)
    if len(_last_alert) > 2000:
        for k in [k for k, t in _last_alert.items() if now - t > cooldown]:
            _last_alert.pop(k, None)

    logger.warning(f"[security] {title} — {body}")

    # Telegram
    try:
        from app.services import telegram
        telegram.send_message(f"🚨 <b>{title}</b>\n{body}")
    except Exception:  # noqa: BLE001
        pass

    # Web Push — platform yöneticileri
    try:
        from app.database import SessionLocal
        from app.services import push
        db = SessionLocal()
        try:
            push.send_to_platform_admins(db, f"🚨 {title}", body, url=url, tag="security")
        finally:
            db.close()
    except Exception:  # noqa: BLE001
        pass
