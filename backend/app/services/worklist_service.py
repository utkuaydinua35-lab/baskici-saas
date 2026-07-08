"""Rol bazlı sabah görev listesi — her kullanıcının yetkisine göre kişiselleştirilmiş.

build_worklist(db, user) → { role_label, greeting, items: [...] }

items içindeki her kayıt:
  key      – tekil tanımlayıcı
  label    – Türkçe açıklama
  count    – adet
  icon     – emoji
  severity – "normal" | "warning" | "urgent"
  link     – frontend yönlendirme yolu (/orders?tab=acil vb.)
"""
from __future__ import annotations

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func as sql_func, select
from sqlalchemy.orm import Session

from app.auth.permissions import effective_permissions, is_admin
from app.models import CustomerRequest, Mold, Order, StockItem

_TR = ZoneInfo("Europe/Istanbul")

# Yönetici rolleri için Türkçe etiket
_ROLE_LABELS: dict[str, str] = {
    "yonetici": "Yönetici",
    "owner": "Yönetici",
    "operator": "Operatör",
    "baskici": "Baskıcı",
    "paketlemeci": "Paketlemeci",
}


def build_worklist(db: Session, user) -> dict:
    """Kullanıcının yetkilerine göre sabah görev listesini oluştur."""
    tid = user.tenant_id
    perms = set(effective_permissions(user))

    # "Bugün" = Istanbul günü başlangıcı (UTC)
    bugun = datetime.now(_TR).date()
    start_today = datetime.combine(bugun, time.min, tzinfo=_TR).astimezone(timezone.utc)

    items = []

    def oc(*conds) -> int:
        return db.scalar(
            select(sql_func.count(Order.id)).where(
                Order.tenant_id == tid,
                Order.is_telafi.is_(False),
                *conds,
            )
        ) or 0

    # ── siparisler izni ──────────────────────────────────────────────
    if "siparisler" in perms:
        acil = oc(
            Order.cancelled_at.is_(None),
            Order.is_acil.is_(True),
            Order.current_stage < 9,
        )
        if acil:
            items.append({
                "key": "acil_siparis", "icon": "🚨", "severity": "urgent",
                "label": "Acil sipariş", "count": acil, "link": "/orders?tab=acil",
            })

        yeni = oc(Order.created_at_platform >= start_today)
        if yeni:
            items.append({
                "key": "yeni_siparis", "icon": "🆕", "severity": "normal",
                "label": "Bugün gelen yeni sipariş", "count": yeni, "link": "/orders",
            })

    # ── paketleme izni ───────────────────────────────────────────────
    if "paketleme" in perms:
        # GERÇEK açık: fulfilled/iade/iptal değil — Shopify'da kargolanmış ama stage'i
        # 6/7'de kalmış siparişleri sayma (aksi halde "paketleme > açık" tutarsızlığı).
        _acik = (
            Order.cancelled_at.is_(None),
            (Order.fulfillment_status != "fulfilled") | (Order.fulfillment_status.is_(None)),
            (Order.financial_status != "refunded") | (Order.financial_status.is_(None)),
        )
        paket = oc(*_acik, Order.current_stage == 6)
        if paket:
            items.append({
                "key": "paket_bekleyen", "icon": "🏷️", "severity": "normal",
                "label": "Paketlenecek sipariş", "count": paket, "link": "/paketleme",
            })

        kargo = oc(*_acik, Order.current_stage == 7)
        if kargo:
            items.append({
                "key": "kargo_bekleyen", "icon": "🚚", "severity": "normal",
                "label": "Kargoya verilecek sipariş", "count": kargo, "link": "/paketleme",
            })

        # Kargo sözü (SLA) — GERÇEK açık sipariş: iptal/iade/fulfilled değil + stage<8
        _now = datetime.now(timezone.utc)
        _end_today = datetime.combine(bugun, time.max, tzinfo=_TR).astimezone(timezone.utc)
        _dl_base = (
            Order.kargo_deadline.isnot(None),
            Order.cancelled_at.is_(None),
            (Order.fulfillment_status != "fulfilled") | (Order.fulfillment_status.is_(None)),
            (Order.financial_status != "refunded") | (Order.financial_status.is_(None)),
            Order.current_stage < 8,
        )
        kargo_gecti = oc(*_dl_base, Order.kargo_deadline < _now)
        if kargo_gecti:
            items.append({
                "key": "kargo_sozu_gecti", "icon": "⛔", "severity": "urgent",
                "label": "Kargo sözü geçen sipariş", "count": kargo_gecti,
                "link": "/orders?deadline=overdue",
            })
        kargo_bugun = oc(*_dl_base, Order.kargo_deadline >= _now, Order.kargo_deadline <= _end_today)
        if kargo_bugun:
            items.append({
                "key": "kargo_sozu_bugun", "icon": "⏰", "severity": "warning",
                "label": "Kargo sözü bugün dolan", "count": kargo_bugun,
                "link": "/orders?deadline=bugun",
            })

    # ── destek izni ─────────────────────────────────────────────────
    if "destek" in perms:
        destek = db.scalar(
            select(sql_func.count(CustomerRequest.id)).where(
                CustomerRequest.tenant_id == tid,
                CustomerRequest.status == "acik",
            )
        ) or 0
        if destek:
            items.append({
                "key": "destek_bekleyen", "icon": "💬", "severity": "warning",
                "label": "Yanıt bekleyen müşteri talebi", "count": destek, "link": "/destek",
            })

    # ── kalip izni ───────────────────────────────────────────────────
    if "kalip" in perms:
        kalip = db.scalar(
            select(sql_func.count(Mold.id)).where(
                Mold.tenant_id == tid,
                Mold.current_stage < 5,
            )
        ) or 0
        if kalip:
            items.append({
                "key": "acik_kalip", "icon": "🎯", "severity": "normal",
                "label": "Açık kalıp", "count": kalip, "link": "/baskici-paneli",
            })

    # ── stok izni ────────────────────────────────────────────────────
    if "stok" in perms:
        dusuk = db.scalar(
            select(sql_func.count(StockItem.id)).where(
                StockItem.tenant_id == tid,
                StockItem.is_active.is_(True),
                StockItem.low_stock_threshold > 0,
                StockItem.quantity <= StockItem.low_stock_threshold,
            )
        ) or 0
        if dusuk:
            items.append({
                "key": "dusuk_stok", "icon": "⚠️", "severity": "warning",
                "label": "Düşük stok kalemi", "count": dusuk, "link": "/stok",
            })

    # ── selamlama ────────────────────────────────────────────────────
    role = (getattr(user, "role", None) or "operator").lower()
    role_label = _ROLE_LABELS.get(role, role.title())
    ad = ((user.full_name or "").split()[0]) if user.full_name else ""
    greeting = f"Günaydın{', ' + ad if ad else ''}! 🌅"

    return {
        "role_label": role_label,
        "greeting": greeting,
        "items": items,
    }
