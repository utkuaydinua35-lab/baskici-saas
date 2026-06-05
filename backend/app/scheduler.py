"""Saatlik otomatik senkronizasyon — APScheduler."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from app.database import SessionLocal
from app.services.sync_service import sync_all_stores

logger = logging.getLogger("scheduler")
logging.basicConfig(level=logging.INFO)
_scheduler: BackgroundScheduler | None = None


def _sync_job(reason="interval"):
    logger.info(f"[scheduler] senkronizasyon başlıyor (reason={reason})")
    db = SessionLocal()
    try:
        results = sync_all_stores(db)
        ok = sum(1 for r in results if r.get("success"))
        new = sum(r.get("new_count", 0) for r in results)
        logger.info(f"[scheduler] tamamlandı: {ok}/{len(results)} mağaza, {new} yeni sipariş")
    except Exception as e:
        logger.exception(f"[scheduler] hata: {e}")
    finally:
        db.close()


def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    _scheduler = BackgroundScheduler(timezone="Europe/Istanbul")
    # Saat başı senk
    _scheduler.add_job(lambda: _sync_job("interval"), "interval", hours=1,
                       id="hourly_sync", max_instances=1, coalesce=True)
    # Açılıştan 20 sn sonra ısınma senki (her başlatmada güncel veri + doğrulama)
    _scheduler.add_job(lambda: _sync_job("warmup"), "date",
                       run_date=datetime.now() + timedelta(seconds=20),
                       id="warmup_sync", max_instances=1)
    _scheduler.start()
    jobs = _scheduler.get_jobs()
    logger.info(f"[scheduler] başlatıldı — {len(jobs)} job:")
    for j in jobs:
        logger.info(f"[scheduler]   • {j.id} → next run: {j.next_run_time}")
    return _scheduler


def shutdown_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
