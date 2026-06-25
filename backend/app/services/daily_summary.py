"""Sabah Telegram özeti — her sabah otomatik üretim/operasyon özeti.

Scheduler (08:00 Europe/Istanbul) çağırır.
Sadece _SUMMARY_SLUGS içindeki tenant'lara gönderilir (bernz, lunera).
Mesaj sırası:
  1. bernz özeti
  2. lunera özeti
  3. Birleşik günlük üretim özeti
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

# Sabah özetini alacak markalar — slug VEYA isim içinde bu anahtarları arar
# (tam slug eşleşmesi yerine esnek; "bernz-company" gibi varyasyonları da yakalar).
_SUMMARY_KEYS = ("bernz", "lunera")


def _is_summary_tenant(t) -> bool:
    slug = (getattr(t, "slug", "") or "").lower()
    name = (getattr(t, "name", "") or "").lower()
    return any(k in slug or k in name for k in _SUMMARY_KEYS)


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

    bugun_tr = datetime.now(_TR).date()
    start_today = datetime.combine(bugun_tr, time.min, tzinfo=_TR).astimezone(timezone.utc)

    acik = oc(*acik_kosul, Order.current_stage < 9)
    acil = oc(Order.cancelled_at.is_(None), Order.is_acil.is_(True), Order.current_stage < 9)
    bugun = oc(Order.created_at_platform >= start_today)
    paketleme = oc(Order.cancelled_at.is_(None), Order.current_stage == 6)
    kargo = oc(Order.cancelled_at.is_(None), Order.current_stage == 7)

    # Kargo sözü (SLA): henüz kargoya verilmemiş (stage < 8), iptal değil
    _now = datetime.now(timezone.utc)
    _end_today = datetime.combine(bugun_tr, time.max, tzinfo=_TR).astimezone(timezone.utc)
    _dl_base = (
        Order.kargo_deadline.isnot(None),
        Order.cancelled_at.is_(None),
        Order.current_stage < 8,
    )
    kargo_sozu_bugun = oc(*_dl_base, Order.kargo_deadline >= _now, Order.kargo_deadline <= _end_today)
    kargo_sozu_gecti = oc(*_dl_base, Order.kargo_deadline < _now)

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
        "kargo_sozu_bugun": kargo_sozu_bugun, "kargo_sozu_gecti": kargo_sozu_gecti,
        "telafi_acik": telafi_acik, "acik_kalip": acik_kalip,
        "dusuk_stok": dusuk_stok,
    }


def _counts_combined(db, tids: list) -> dict:
    """Birden fazla tenant için birleşik üretim sayıları (3. mesaj)."""
    not_telafi = Order.is_telafi.is_(False)
    not_cancelled = Order.cancelled_at.is_(None)
    acik_kosul_ek = (
        (Order.fulfillment_status != "fulfilled") | (Order.fulfillment_status.is_(None)),
        (Order.financial_status != "refunded") | (Order.financial_status.is_(None)),
    )
    bugun_tr = datetime.now(_TR).date()
    start_today = datetime.combine(bugun_tr, time.min, tzinfo=_TR).astimezone(timezone.utc)

    def oc(*conds) -> int:
        return db.scalar(
            select(sql_func.count(Order.id)).where(
                Order.tenant_id.in_(tids), not_telafi, *conds
            )
        ) or 0

    return {
        "bugun": oc(not_cancelled, Order.created_at_platform >= start_today),
        # Stage 1-5: yeni→baskıda (basılması gereken)
        "uretimde": oc(not_cancelled, *acik_kosul_ek, Order.current_stage.between(1, 5)),
        # Stage 6: baskı tamam, paketleme bekliyor
        "paketleme": oc(not_cancelled, Order.current_stage == 6),
        # Stage 7: paketlendi, kargo bekliyor
        "kargo": oc(not_cancelled, Order.current_stage == 7),
        "acil": oc(not_cancelled, Order.is_acil.is_(True), Order.current_stage < 9),
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
    if c.get("kargo_sozu_gecti"):
        lines.append(f"⛔ Kargo sözü GEÇEN: <b>{c['kargo_sozu_gecti']}</b>")
    if c.get("kargo_sozu_bugun"):
        lines.append(f"⏰ Kargo sözü bugün dolan: <b>{c['kargo_sozu_bugun']}</b>")
    if c["acik_kalip"]:
        lines.append(f"🎯 Açık kalıp: <b>{c['acik_kalip']}</b>")
    if c["telafi_acik"]:
        lines.append(f"♻️ Açık telafi: <b>{c['telafi_acik']}</b>")
    if c["dusuk_stok"]:
        lines.append(f"⚠️ Düşük stok kalemi: <b>{c['dusuk_stok']}</b>")
    return "\n".join(lines)


def _build_production_text(c: dict) -> str:
    """3. mesaj: tüm markaların birleşik günlük üretim özeti."""
    tarih = datetime.now(_TR).strftime("%d.%m.%Y")
    lines = [
        f"🏭 <b>Günlük Üretim Özeti — {tarih}</b>",
        "",
        f"🆕 Bugün gelen sipariş: <b>{c['bugun']}</b>",
        f"🖨️ Basılması gereken: <b>{c['uretimde']}</b>",
    ]
    if c["paketleme"]:
        lines.append(f"🏷️ Paketleme bekleyen: <b>{c['paketleme']}</b>")
    if c["kargo"]:
        lines.append(f"🚚 Kargo bekleyen: <b>{c['kargo']}</b>")
    if c["acil"]:
        lines.append(f"🚨 Acil sipariş: <b>{c['acil']}</b>")
    return "\n".join(lines)


def send_daily_summary(db) -> int:
    """Bernz ve Lunera tenant'ları için sabah özetini Telegram'a gönder.
    1. mesaj: bernz  |  2. mesaj: lunera  |  3. mesaj: birleşik üretim özeti
    """
    sent = 0
    all_tenants = db.scalars(select(Tenant)).all()
    tenants = [t for t in all_tenants if _is_summary_tenant(t)]
    logger.info(
        f"[daily_summary] {len(tenants)}/{len(all_tenants)} tenant eslesti: "
        f"{[t.slug for t in tenants]}"
    )

    included_ids = []
    for t in tenants:
        try:
            c = _counts(db, t.id)
            text = _build_text(t.name or t.slug, c)
            if telegram.send_message(text):
                sent += 1
            included_ids.append(t.id)
        except Exception as e:
            logger.warning(f"[daily_summary] tenant={t.id} hata: {e}")

    # 3. mesaj: birleşik üretim özeti
    if included_ids:
        try:
            c2 = _counts_combined(db, included_ids)
            text3 = _build_production_text(c2)
            if telegram.send_message(text3):
                sent += 1
        except Exception as e:
            logger.warning(f"[daily_summary] uretim ozeti hata: {e}")

    return sent
