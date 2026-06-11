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

def run_mold_based(db) -> dict:
    """Kalip durumlarindan siparis asamasini turet (sadece ileri).
    - >=1 kalemi kaliba eklendi -> Kaliba Alindi (4)
    - >=1 kalemi baskidaki kalipta (mold stage 4) -> Baskida (5)
    - TUM kaliba eklenmis kalemlerin kaliplari tamamlandi (mold stage 5) -> Baski Tamam (6)
    """
    res = {"kaliba_alindi": 0, "baskida": 0, "baski_tamam": 0}

    # Acik, asamasi 6'dan kucuk siparisleri al (ilerleyebilir olanlar)
    orders = db.scalars(
        select(Order).where(Order.current_stage < 6)
    ).all()
    if not orders:
        db.commit()
        return res

    for o in orders:
        if not _order_acik(o):
            continue
        # Siparisin kalemleri
        lis = db.scalars(select(LineItem).where(LineItem.order_id == o.id)).all()
        if not lis:
            continue
        li_ids = [li.id for li in lis]
        # Kaliba eklenmis kalemler (baskilik): is_kaliba_eklendi=True
        kaliba_eklenenler = [li for li in lis if getattr(li, "is_kaliba_eklendi", False)]
        if not kaliba_eklenenler:
            continue  # hic kaliba eklenmemis -> bu otomasyon dokunmaz

        # Bu kalemlerin kalip item'lari + kalip asamalari
        mold_items = db.scalars(
            select(MoldItem).where(MoldItem.line_item_id.in_(li_ids))
        ).all()
        if not mold_items:
            continue
        mold_ids = {mi.mold_id for mi in mold_items if mi.mold_id}
        molds = db.scalars(select(Mold).where(Mold.id.in_(mold_ids))).all()
        mold_stage = {m.id: m.current_stage for m in molds}

        # Kalip item'i olan line_item id'leri
        li_to_mold = {}
        for mi in mold_items:
            if mi.line_item_id and mi.mold_id:
                li_to_mold[mi.line_item_id] = mi.mold_id

        # En yuksek asama hesapla (sadece ileri)
        hedef = o.current_stage

        # (4) Kaliba Alindi — en az 1 kalem kaliba eklendi (zaten var)
        if hedef < 4:
            hedef = 4

        # (5) Baskida — en az 1 kalemin kalibi baskida (mold stage 4) veya uzeri
        kalemler_baskida = any(
            mold_stage.get(li_to_mold.get(li.id)) in (4, 5)
            for li in kaliba_eklenenler if li.id in li_to_mold
        )
        if kalemler_baskida and hedef < 5:
            hedef = 5

        # (6) Baski Tamam — TUM kaliba eklenmis kalemlerin kaliplari tamamlandi (mold stage 5)
        # Kosul: her kaliba eklenmis kalemin bir kalibi olmali VE o kalip stage 5 olmali
        tum_tamam = (
            len(kaliba_eklenenler) > 0
            and all(li.id in li_to_mold for li in kaliba_eklenenler)
            and all(mold_stage.get(li_to_mold[li.id]) == 5 for li in kaliba_eklenenler)
        )
        if tum_tamam and hedef < 6:
            hedef = 6

        if hedef > o.current_stage:
            old = o.current_stage
            o.current_stage = hedef
            label = {4: "Kalıba Alındı", 5: "Baskıda", 6: "Baskı Tamam"}.get(hedef, str(hedef))
            _log_order(db, o, old, hedef, f"Kalıp durumundan otomatik ({label})")
            if hedef == 4: res["kaliba_alindi"] += 1
            elif hedef == 5: res["baskida"] += 1
            elif hedef == 6: res["baski_tamam"] += 1

    db.commit()
    return res
