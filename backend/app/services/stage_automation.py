"""Sipariş ve kalıp aşama otomasyonu — zaman + olay bazlı.

Scheduler tarafından periyodik çağrılır. Sadece İLERİ aşama geçişi yapar.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models import Mold, MoldItem, Order, OrderStatusHistory, MoldStatusHistory, LineItem

logger = logging.getLogger("stage_automation")

SYSTEM_ACTOR = "Sistem (otomatik)"

# Zaman eşikleri
ISLENIYOR_SAAT = 4      # sipariş +4s -> İşleniyor (2)
BARKOD_SAAT = 8         # sipariş +8s -> Barkod Oluştu (3)
BASKIDA_DAKIKA = 30     # kalıp PDF indirme +30dk -> Baskıda (4)


def _log_order(db, order, from_stage, to_stage, note):
    db.add(OrderStatusHistory(
        tenant_id=order.tenant_id, order_id=order.id,
        from_stage=from_stage, to_stage=to_stage,
        action="stage_change", note=note, created_by=SYSTEM_ACTOR,
    ))


def _log_mold(db, mold, from_stage, to_stage, note):
    db.add(MoldStatusHistory(
        tenant_id=mold.tenant_id, mold_id=mold.id,
        from_stage=from_stage, to_stage=to_stage,
        action="stage_change", note=note, created_by=SYSTEM_ACTOR,
    ))


def _order_acik(o) -> bool:
    """Sipariş açık mı (iptal/iade/teslim değil)."""
    if o.cancelled_at is not None:
        return False
    if (o.financial_status or "").lower() == "refunded":
        return False
    if o.current_stage >= 9:  # teslim
        return False
    return True


def run_time_based(db) -> dict:
    """Zaman bazlı aşama geçişleri. Döner: {orders_isleniyor, orders_barkod, molds_baskida}."""
    now = datetime.now(timezone.utc)
    res = {"orders_isleniyor": 0, "orders_barkod": 0, "molds_baskida": 0}

    # --- Siparişler: zaman bazlı (sadece ileri) ---
    orders = db.scalars(
        select(Order).where(
            Order.current_stage < 3,  # 1 veya 2 olanlar ilerleyebilir
        )
    ).all()
    for o in orders:
        if not _order_acik(o):
            continue
        if o.created_at_platform is None:
            continue
        cap = o.created_at_platform
        if cap.tzinfo is None:
            cap = cap.replace(tzinfo=timezone.utc)
        yas = now - cap
        # +8s -> Barkod Oluştu (3) — daha yüksek önce kontrol
        if yas >= timedelta(hours=BARKOD_SAAT) and o.current_stage < 3:
            old = o.current_stage
            o.current_stage = 3
            _log_order(db, o, old, 3, f"+{BARKOD_SAAT}s otomatik (Barkod Oluştu)")
            res["orders_barkod"] += 1
        # +4s -> İşleniyor (2)
        elif yas >= timedelta(hours=ISLENIYOR_SAAT) and o.current_stage < 2:
            old = o.current_stage
            o.current_stage = 2
            _log_order(db, o, old, 2, f"+{ISLENIYOR_SAAT}s otomatik (İşleniyor)")
            res["orders_isleniyor"] += 1

    # --- Kalıplar: PDF indirme +30dk -> Baskıda (4) ---
    molds = db.scalars(
        select(Mold).where(
            Mold.current_stage == 3,  # baskiya_gonderildi
            Mold.pdf_indirilme_zamani.isnot(None),
        )
    ).all()
    for m in molds:
        piz = m.pdf_indirilme_zamani
        if piz.tzinfo is None:
            piz = piz.replace(tzinfo=timezone.utc)
        if now - piz >= timedelta(minutes=BASKIDA_DAKIKA):
            old = m.current_stage
            m.current_stage = 4  # baskida
            _log_mold(db, m, old, 4, f"PDF +{BASKIDA_DAKIKA}dk otomatik (Baskıda)")
            res["molds_baskida"] += 1

    db.commit()
    return res
