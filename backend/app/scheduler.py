"""Saatlik otomatik senkronizasyon — APScheduler."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from app.database import SessionLocal
from app.services.sync_service import sync_all_stores
from app.services.uploads import cleanup_old as _cleanup_uploads
from app.services import stage_automation
from app.services import daily_summary

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


def _daily_summary_job():
    logger.info("[scheduler] sabah ozeti gonderiliyor")
    db = SessionLocal()
    try:
        sent = daily_summary.send_daily_summary(db)
        logger.info(f"[scheduler] sabah ozeti: {sent} mesaj gonderildi")
    except Exception as e:
        logger.exception(f"[scheduler] sabah ozeti hata: {e}")
    finally:
        db.close()


def _daily_summary_catchup_job():
    logger.info("[scheduler] sabah ozeti catch-up kontrolu")
    db = SessionLocal()
    try:
        sent = daily_summary.send_daily_summary_catchup(db)
        if sent:
            logger.info(f"[scheduler] catch-up: {sent} mesaj gonderildi")
    except Exception as e:
        logger.exception(f"[scheduler] catch-up hata: {e}")
    finally:
        db.close()


def _backup_job():
    logger.info("[scheduler] gunluk yedek aliniyor")
    try:
        from app.services import backup
        r = backup.run_backup()
        logger.info(f"[scheduler] yedek alindi: {r['name']} ({r['size']} bayt)")
    except Exception as e:
        logger.exception(f"[scheduler] yedek hata: {e}")


def _abandoned_reminder_job():
    """Terk sepet otomatik hatırlatması — yalnızca config'inde
    abandoned_reminder_enabled=true olan vitrin mağazaları; 2-24 saat önce
    süresi dolmuş, e-postalı, daha önce hatırlatılmamış oturumlar (1 kez)."""
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select
    from app.models import CheckoutSession, Store
    from app.routers.checkout_admin import _send_reminder_email

    db = SessionLocal()
    try:
        stores = db.scalars(select(Store).where(
            Store.platform == "storefront", Store.is_active.is_(True))).all()
        enabled_ids = [s.id for s in stores
                       if (s.config or {}).get("abandoned_reminder_enabled") in (True, "true", "1")]
        if not enabled_ids:
            return
        now = datetime.now(timezone.utc)
        sessions = db.scalars(select(CheckoutSession).where(
            CheckoutSession.store_id.in_(enabled_ids),
            CheckoutSession.status.in_(["expired", "failed"]),
            CheckoutSession.order_id.is_(None),
            CheckoutSession.reminder_sent_at.is_(None),
            CheckoutSession.customer["email"].astext != "",
            CheckoutSession.created_at >= now - timedelta(hours=24),
            CheckoutSession.created_at <= now - timedelta(hours=2),
        ).limit(50)).all()
        sent = 0
        store_by_id = {s.id: s for s in stores}
        for sess in sessions:
            if _send_reminder_email(db, sess, store_by_id[sess.store_id]):
                sess.reminder_sent_at = now
                sent += 1
        db.commit()
        if sent:
            logger.info(f"[scheduler] terk sepet hatirlatmasi: {sent} e-posta")
    except Exception as e:
        logger.exception(f"[scheduler] terk sepet hatirlatma hata: {e}")
    finally:
        db.close()


def _checkout_sweep_job():
    logger.info("[scheduler] vitrin odeme oturumu temizligi")
    db = SessionLocal()
    try:
        from app.services.checkout import sweep_sessions
        res = sweep_sessions(db)
        logger.info(f"[scheduler] vitrin temizlik: {res}")
    except Exception as e:
        logger.exception(f"[scheduler] vitrin temizlik hata: {e}")
    finally:
        db.close()


def _stage_job():
    logger.info("[scheduler] asama otomasyonu basliyor")
    db = SessionLocal()
    try:
        res = stage_automation.run_time_based(db)
        res_mold = stage_automation.run_mold_based(db)
        logger.info(f"[scheduler] asama otomasyonu: zaman={res} kalip={res_mold}")
    except Exception as e:
        logger.exception(f"[scheduler] asama otomasyonu hata: {e}")
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
    # Gunluk destek gorsel temizligi (14 gunden eski)
    _scheduler.add_job(lambda: _cleanup_uploads(14), "interval", hours=24,
                       id="cleanup_support_uploads", max_instances=1, coalesce=True)
    # Asama otomasyonu — her 10 dk (zaman bazli gecisler)
    _scheduler.add_job(_stage_job, "interval", minutes=10,
                       id="stage_automation", max_instances=1, coalesce=True)
    # Sabah ozeti — her gun 08:00 (Europe/Istanbul)
    _scheduler.add_job(_daily_summary_job, "cron", hour=8, minute=0,
                       id="daily_summary", max_instances=1, coalesce=True,
                       misfire_grace_time=3600)
    # Acilis catch-up: 08:00'dan sonra restart olduysa bugunku ozet atlanmistir;
    # ~45 sn sonra kontrol et, gerekiyorsa bir kez gonder.
    _scheduler.add_job(_daily_summary_catchup_job, "date",
                       run_date=datetime.now() + timedelta(seconds=45),
                       id="daily_summary_catchup", max_instances=1)
    # Gunluk veritabani yedegi — her gece 03:30 (Europe/Istanbul)
    _scheduler.add_job(_backup_job, "cron", hour=3, minute=30,
                       id="daily_backup", max_instances=1, coalesce=True)
    # Vitrin: suresi dolan odeme oturumlari + KVKK PII temizligi — her gece 04:00
    _scheduler.add_job(_checkout_sweep_job, "cron", hour=4, minute=0,
                       id="checkout_sweep", max_instances=1, coalesce=True)
    # Vitrin: terk sepet otomatik hatirlatmasi (magaza config kapili) — saatlik
    _scheduler.add_job(_abandoned_reminder_job, "interval", hours=1,
                       id="abandoned_reminder", max_instances=1, coalesce=True)
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
