"""Webhook'lar — dış servis bildirimleri (auth yok, URL secret ile korunur).

Basit Kargo kargo durumu:
  POST /api/webhooks/basit-kargo/{secret}
Payload (status değişikliği): {id, barcode, status, handler{...}, handlerShipmentCode}
Order.kargo_info.barcode ile eşleştirir → kargo_info günceller, DELIVERED'da stage 9
(Teslim), sorunlu durumlarda Telegram uyarısı.
"""
from __future__ import annotations

import hmac

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Order, OrderStatusHistory, Store
from app.services import telegram

logger = logging.getLogger("webhooks")

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

# Basit Kargo status -> Türkçe etiket
_STATUS_TR = {
    "NEW": "Oluşturuldu",
    "READY_TO_SHIP": "Kargoya hazır",
    "SHIPPED": "Kargoda",
    "OUT_FOR_DELIVERY": "Dağıtımda",
    "DELIVERED": "Teslim edildi",
    "NEEDS_SUPPORT": "Destek gerekiyor",
    "DELAYED": "Gecikti",
    "RETURNING": "İade ediliyor",
    "RETURNED": "İade edildi",
    "LOST": "Kayıp",
}
# Operatöre Telegram uyarısı gerektiren sorunlu durumlar
_PROBLEM = {"NEEDS_SUPPORT", "DELAYED", "RETURNING", "RETURNED", "LOST"}


@router.post("/basit-kargo/{secret}", response_model=None)
def basit_kargo_webhook(
    secret: str,
    payload: dict = Body(default={}),
    db: Session = Depends(get_db),
):
    s = get_settings()
    expected = (s.basit_kargo_webhook_secret or "").strip()
    # Secret tanımsız ya da yanlışsa — varlığını belli etmeden 404.
    # compare_digest: düz `!=` ilk farklı bayta gelince döner ve karşılaştırma
    # süresi doğru ön ek uzunluğuyla değişir. Ağ gürültüsü altında sömürmek
    # zordur ama sır karşılaştırması sabit zamanlı olmalı — ölçüm ucuz.
    if not expected or not hmac.compare_digest(
            secret.encode("utf-8", "replace"),
            expected.encode("utf-8", "replace")):
        raise HTTPException(status_code=404, detail="Not found")

    barcode = str(payload.get("barcode") or "").strip()
    status = str(payload.get("status") or "").strip().upper()
    if not barcode:
        return {"ok": True, "skipped": "no barcode"}

    # Barkodla siparişi bul (tenant-bağımsız; barkod global benzersiz)
    order = db.scalar(select(Order).where(Order.kargo_info["barcode"].astext == barcode))
    if not order:
        logger.info(f"[webhook] basit-kargo barkod eşleşmedi: {barcode}")
        return {"ok": True, "matched": False}

    ki = dict(order.kargo_info or {})
    prev_status = (ki.get("status") or "").upper()
    changed = bool(status) and status != prev_status

    # kargo_info güncelle (durum + son hareket + zaman)
    if status:
        ki["status"] = status
    last_state = (payload.get("shipmentInfo") or {}).get("lastState") or _STATUS_TR.get(status)
    if last_state:
        ki["last_state"] = last_state
    ki["updated_at"] = datetime.now(UTC).isoformat()
    order.kargo_info = ki

    # Gerçek kargo firması takip no'su (handlerShipmentCode) sonradan gelirse:
    # kargo_info'yu güncelle + Shopify fulfillment takip no'sunu düzelt.
    hsc = str(payload.get("handlerShipmentCode") or "").strip()
    handler_name_in = ((payload.get("handler") or {}).get("name")
                       or ((payload.get("shipmentInfo") or {}).get("handler") or {}).get("name"))
    if hsc and hsc != (ki.get("takip_no") or ""):
        first_tracking = not (ki.get("takip_no") or "").strip()
        ki["takip_no"] = hsc
        if handler_name_in:
            ki["handler_name"] = handler_name_in
        order.kargo_info = ki
        # Takip no İLK kez doluyorsa vitrin müşterisine kargo bildirimi
        if first_tracking:
            from app.services.shipping_email import maybe_send_tracking_email
            maybe_send_tracking_email(db, order)
        try:
            store = db.get(Store, order.store_id) if order.store_id else None
            if store and store.platform == "shopify":
                from app.adapters import get_adapter
                adapter = get_adapter(store)
                company = ki.get("handler_name") or "Kargo"
                fid = ki.get("fulfillment_id")
                if fid:
                    adapter.update_tracking(fid, hsc, company)
                elif ki.get("shopify_oid"):
                    tr = adapter.add_tracking(ki["shopify_oid"], hsc, company)
                    nfid = (tr.get("fulfillment") or {}).get("id")
                    if nfid:
                        ki["fulfillment_id"] = nfid
                        order.kargo_info = ki
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[webhook] Shopify takip no güncelleme hatası: {e}")
        logger.info(f"[webhook] takip no güncellendi -> {hsc} (sipariş {order.order_number})")

    if changed:
        durum_tr = _STATUS_TR.get(status, status)
        if status == "DELIVERED":
            if (order.current_stage or 0) < 9:
                prev_stage = order.current_stage or 8
                order.current_stage = 9  # Teslim
                db.add(OrderStatusHistory(
                    tenant_id=order.tenant_id, order_id=order.id,
                    from_stage=prev_stage, to_stage=9, action="teslim_edildi",
                    note=f"{ki.get('handler_name', 'Kargo')} · {durum_tr} (webhook)",
                    created_by="Basit Kargo",
                ))
        else:
            action = "kargo_sorunu" if status in _PROBLEM else "kargo_durumu"
            db.add(OrderStatusHistory(
                tenant_id=order.tenant_id, order_id=order.id,
                from_stage=None, to_stage=order.current_stage, action=action,
                note=f"Kargo: {durum_tr} (webhook)", created_by="Basit Kargo",
            ))
            if status in _PROBLEM:
                telegram.send_message(
                    f"⚠️ <b>Kargo sorunu</b> · #{order.order_number or order.id}\n"
                    f"{ki.get('handler_name', 'Kargo')} · <b>{durum_tr}</b> · takip {ki.get('takip_no', '')}"
                )

    db.commit()
    return {"ok": True, "matched": True, "status": status, "changed": changed}
