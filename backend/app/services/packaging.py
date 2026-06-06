"""
Paketleme servisi.

- suggest_for_order: siparişin line item'larını aksesuar stok kalemleriyle
  (kategori != bos_kilif) sku → product_id sırasıyla otomatik eşleştirme ÖNERİSİ.
  Boş kılıf kalıp basımında düştüğü için önerilerde yer almaz.
- complete_packaging: operatörün onayladığı düşümleri uygula (reason=paketleme,
  ref_order_id), stage'i 7'ye çek. İDEMPOTENT: aynı sipariş için 'paketleme'
  hareketi varsa tekrar düşmez. Stok yetersizse paketlemeyi BLOKLAMAZ.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Order, StockItem, StockMovement


def suggest_for_order(db: Session, tenant_id, order: Order) -> list[dict]:
    items = db.scalars(
        select(StockItem).where(
            StockItem.tenant_id == tenant_id,
            StockItem.is_active.is_(True),
            StockItem.category != "bos_kilif",
        )
    ).all()
    by_sku: dict[str, StockItem] = {}
    by_pid: dict[str, list[StockItem]] = {}
    for si in items:
        if si.sku:
            by_sku.setdefault(si.sku, si)
        if si.product_id:
            by_pid.setdefault(str(si.product_id), []).append(si)

    out = []
    for li in order.line_items:
        match = None
        if li.sku and li.sku in by_sku:
            match = by_sku[li.sku]
        elif li.product_id:
            cands = by_pid.get(str(li.product_id), [])
            if len(cands) == 1:
                match = cands[0]
        out.append({
            "line_item_id": str(li.id),
            "title": li.title,
            "variant_title": li.variant_title,
            "quantity": li.quantity,
            "sku": li.sku,
            "product_id": li.product_id,
            "is_kaliba_eklendi": li.is_kaliba_eklendi,
            "suggested_stock_item_id": str(match.id) if match else None,
            "suggested_name": match.name if match else None,
        })
    return out


def is_packaged(db: Session, tenant_id, order: Order) -> bool:
    mv = db.scalar(
        select(StockMovement.id).where(
            StockMovement.tenant_id == tenant_id,
            StockMovement.reason == "paketleme",
            StockMovement.ref_order_id == order.id,
        ).limit(1)
    )
    return bool(mv) or (order.current_stage or 0) >= 7


def complete_packaging(db: Session, tenant_id, order: Order,
                       deductions: list[dict], user=None) -> dict:
    """deductions: [{stock_item_id: UUID|str, quantity: int}]."""
    already = db.scalar(
        select(StockMovement.id).where(
            StockMovement.tenant_id == tenant_id,
            StockMovement.reason == "paketleme",
            StockMovement.ref_order_id == order.id,
        ).limit(1)
    )
    created_by = getattr(user, "email", None) if user else None
    deducted = 0
    shortages = []
    lines = []

    if not already:
        for d in deductions or []:
            sid = d.get("stock_item_id")
            qty = int(d.get("quantity", 1) or 0)
            if not sid or qty <= 0:
                continue
            si = db.scalar(
                select(StockItem).where(
                    StockItem.id == sid, StockItem.tenant_id == tenant_id
                )
            )
            if not si:
                shortages.append({"stock_item_id": str(sid), "need": qty, "reason": "kalem_yok"})
                continue
            take = min(si.quantity or 0, qty)
            if take > 0:
                si.quantity -= take
                db.add(StockMovement(
                    tenant_id=tenant_id,
                    stock_item_id=si.id,
                    delta=-take,
                    balance_after=si.quantity,
                    reason="paketleme",
                    ref_order_id=order.id,
                    note=f"Paketleme #{order.order_number}",
                    created_by=created_by,
                ))
                deducted += take
                lines.append({"sku": si.sku, "name": si.name, "deducted": take})
            if take < qty:
                shortages.append({
                    "sku": si.sku, "name": si.name,
                    "need": qty, "deducted": take, "reason": "yetersiz_stok",
                })

    stage_changed = False
    if (order.current_stage or 0) < 7:
        order.current_stage = 7
        stage_changed = True

    return {
        "already": bool(already),
        "deducted": deducted,
        "shortages": shortages,
        "lines": lines,
        "stage_changed": stage_changed,
    }
