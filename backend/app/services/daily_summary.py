"""Sabah Telegram özeti — her sabah otomatik üretim/operasyon özeti.

Scheduler (08:00 Europe/Istanbul) çağırır. Her tenant için sayımları hesaplar
ve Telegram'a gönderir (telegram servisi tek global chat'e gönderir — BERNZ).
Veri yoksa / token yoksa sessiz geçer.
"""
from __future__ import annotations

import logging
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func as sql_func, select

from app.models import Mold, Order, StockItem, Tenant
from app.services import telegram

logger = logging.getLogger("daily_summary")

_TR = ZoneInfo("Europe/Istanbul")


def _counts(db, tid) -> dict:
    """Bir tenant için özet sayılar (soft-delete global filtre otomatik dışlar)."""
    not_telafi = Order.is_telafi.is_(False)
    acik_kosul = (
        Order.cancelled_at.is_(None),
        (Order.fulfillment_status != "fulfilled") | (Order.fulfillment_status.is_(None)),
        (Order.financial_status != "refunded") | (Order.financial_status.is_(None)),
    )

    def oc(*conds) -> int:
        return db.scalar(
            select(sql_func.count(Order.id)).where(Order.tenant_id == tid, not_telafi, *conds)
        ) or 0

    # "Bugün" = Istanbul günü başlangıcı (UTC'ye çevrilmiş)
    bugun_tr = datetime.now(_TR).date()
    start_today = datetime.combine(bugun_tr, time.min, tzinfo=_TR).astimezone(timezone.utc)

    acik = oc(*acik_kosul, Order.current_stage < 9)
    acil = oc(Order.cancelled_at.is_(None), Order.is_acil.is_(True), Order.current_stage < 9)
    bugun = oc(Order.created_at_platform >= start_today)
    paketleme = oc(Order.cancelled_at.is_(None), Order.current_stage == 6)
    kargo = oc(Order.cancelled_at.is_(None), Order.current_stage == 7)

    telafi_acik = db.scalar(
        select(sql_func.count(Order.id)).where(
            Order.tenant_id == tid, Order.is_telafi.is_(True),
            Order.cancelled_at.is_(None), Order.current_stage < 9,
        )
    ) or 0

    acik_kalip = db.scalar(
        select(sql_func.count(Mold.id)).where(Mold.tenant_id == tid, Mold.current_stage < 5)
    ) or 0

    dusuk_stok = db.scalar(
        select(sql_func.count(StockItem.id)).where(
            StockItem.tenant_id == tid,
            StockItem.is_active.is_(True),
            StockItem.low_stock_threshold > 0,
            StockItem.quantity <= StockItem.low_stock_threshold,
        )
    ) or 0

    return {
        "acik": acik, "acil": acil, "bugun": bugun,
        "paketleme": paketleme, "kargo": kargo,
        "telafi_acik": telafi_acik, "acik_kalip": acik_kalip,
        "dusuk_stok": dusuk_stok,
    }


def _build_text(tenant_name: str, c: dict) -> str:
    tarih = datetime.now(_TR).strftime("%d.%m.%Y %A")
    lines = [
        f"☀️ <b>Günaydın — {tenant_name}</b>",
        f"<i>{tarih}</i>",
        "",
        f"📦 Açık sipariş: <b>{c['acik']}</b>",
    ]
    if c["acil"]:
        lines.append(f"🚨 Acil: <b>{c['acil']}</b>")
    lines.append(f"🆕 Bugün gelen: <b>{c['bugun']}</b>")
    if c["paketleme"]:
        lines.append(f"🏷️ Paketleme bekleyen: <b>{c['paketleme']}</b>")
    if c["kargo"]:
        lines.append(f"🚚 Kargo bekleyen: <b>{c['kargo']}</b>")
    if c["acik_kalip"]:
        lines.append(f"🎯 Açık kalıp: <b>{c['acik_kalip']}</b>")
    if c["telafi_acik"]:
        lines.append(f"♻️ Açık telafi: <b>{c['telafi_acik']}</b>")
    if c["dusuk_stok"]:
        lines.append(f"⚠️ Düşük stok kalemi: <b>{c['dusuk_stok']}</b>")
    return "\n".join(lines)


def send_daily_summary(db) -> int:
    """Tüm tenant'lar için sabah özetini Telegram'a gönder. Gönderilen mesaj sayısı."""
    sent = 0
    tenants = db.scalars(select(Tenant)).all()
    for t in tenants:
        try:
            c = _counts(db, t.id)
            # Tamamen boş gün (hiç açık iş yok) -> yine de gönder, "her şey temiz" bilgisi degerli
            text = _build_text(t.name or "Atölye", c)
            if telegram.send_message(text):
                sent += 1
        except Exception as e:
            logger.warning(f"[daily_summary] tenant={t.id} hata: {e}")
    return sent
