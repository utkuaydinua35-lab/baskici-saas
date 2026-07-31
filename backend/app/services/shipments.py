"""Kısmi kargolama servisi — bir siparişin parça parça gönderilmesi.

Shopify'da bir siparişten "hazır olanı gönder, kalanı sonra" yapılır; burada
aynısı OrderShipment satırlarıyla tutulur. Kurallar:

- Bir kalemden gönderilen toplam adet, sipariş adedini AŞAMAZ (sunucuda
  doğrulanır — panelden gelen adede güvenilmez).
- Tüm kalemler gönderildiğinde sipariş "kargoda" aşamasına geçer; eksik
  varsa sipariş açık kalır ve panelde "kısmi" rozeti görünür.
- İlk gönderinin takip numarası Order.kargo_info'ya da yazılır: Basit Kargo
  entegrasyonu, webhook eşleşmesi ve arama orayı okumaya devam eder.
- Her gönderi için müşteriye ayrı bilgilendirme e-postası gidebilir.
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.models import Order, OrderShipment, OrderStatusHistory, Store
from app.services import email_service

log = logging.getLogger("shipments")

STAGE_KARGODA = 8


class ShipmentError(Exception):
    """Panelde gösterilebilir doğrulama hatası."""


def shipped_counts(order: Order) -> dict[str, int]:
    """Kalem başına şu ana kadar gönderilmiş adet."""
    out: dict[str, int] = {}
    for s in (order.shipments or []):
        for it in (s.items or []):
            lid = str(it.get("line_item_id") or "")
            if lid:
                out[lid] = out.get(lid, 0) + int(it.get("quantity") or 0)
    return out


def remaining_counts(order: Order) -> dict[str, int]:
    """Kalem başına gönderilmeyi bekleyen adet."""
    gonderilen = shipped_counts(order)
    return {
        str(li.id): max(0, int(li.quantity or 1) - gonderilen.get(str(li.id), 0))
        for li in (order.line_items or [])
    }


def is_fully_shipped(order: Order) -> bool:
    kalan = remaining_counts(order)
    return bool(kalan) and all(v == 0 for v in kalan.values())


def serialize(order: Order) -> dict:
    """Panel için gönderi durumu özeti."""
    kalan = remaining_counts(order)
    return {
        "shipments": [
            {
                "id": str(s.id),
                "takip_no": s.takip_no,
                "kargo_firma": s.kargo_firma,
                "takip_url": s.takip_url,
                "items": s.items or [],
                "note": s.note,
                "created_by": s.created_by,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in (order.shipments or [])
        ],
        "remaining": kalan,
        "fully_shipped": is_fully_shipped(order),
        "partial": bool(order.shipments) and not is_fully_shipped(order),
    }


def create_shipment(
    db: Session, order: Order, *, items: list[dict], takip_no: str | None,
    kargo_firma: str | None, takip_url: str | None = None, note: str | None = None,
    user_label: str | None = None, send_email: bool = True,
) -> OrderShipment:
    """Yeni gönderi kaydet. items: [{line_item_id, quantity}].

    Adetler sunucuda kalan miktara karşı doğrulanır; aşan istek reddedilir.
    """
    kalan = remaining_counts(order)
    li_map = {str(li.id): li for li in (order.line_items or [])}

    temiz: list[dict] = []
    for it in items or []:
        lid = str(it.get("line_item_id") or "")
        li = li_map.get(lid)
        if not li:
            raise ShipmentError("Bu siparişte olmayan bir kalem gönderilmeye çalışıldı")
        try:
            adet = int(it.get("quantity") or 0)
        except (TypeError, ValueError):
            raise ShipmentError("Adet sayı olmalı")
        if adet <= 0:
            continue
        if adet > kalan.get(lid, 0):
            raise ShipmentError(
                f"'{li.title}' için en fazla {kalan.get(lid, 0)} adet gönderilebilir")
        temiz.append({"line_item_id": lid, "quantity": adet,
                      "title": li.title, "variant_title": li.variant_title})

    if not temiz:
        raise ShipmentError("En az bir kalem seçmelisiniz")

    shipment = OrderShipment(
        tenant_id=order.tenant_id, order_id=order.id,
        takip_no=(takip_no or "").strip() or None,
        kargo_firma=(kargo_firma or "").strip() or None,
        takip_url=(takip_url or "").strip() or None,
        items=temiz, note=(note or "").strip() or None,
        created_by=user_label,
    )
    db.add(shipment)
    order.shipments.append(shipment)

    adet_toplam = sum(i["quantity"] for i in temiz)
    tamam = is_fully_shipped(order)

    # İlk gönderinin takip no'su kargo_info'ya da yazılır (Basit Kargo/arama)
    if shipment.takip_no:
        ki = dict(order.kargo_info or {})
        if not (ki.get("takip_no") or "").strip():
            ki["takip_no"] = shipment.takip_no
            if shipment.kargo_firma:
                ki["handler_name"] = shipment.kargo_firma
            if shipment.takip_url:
                ki["takip_url"] = shipment.takip_url
            order.kargo_info = ki

    eski_stage = order.current_stage
    if tamam and order.current_stage < STAGE_KARGODA:
        order.current_stage = STAGE_KARGODA

    db.add(OrderStatusHistory(
        tenant_id=order.tenant_id, order_id=order.id,
        from_stage=eski_stage, to_stage=order.current_stage,
        action="kargoya_verildi" if tamam else "kismi_kargo",
        note=(f"{adet_toplam} adet gönderildi"
              + (f" · {shipment.kargo_firma or 'Kargo'} {shipment.takip_no}"
                 if shipment.takip_no else "")
              + ("" if tamam else " · sipariş kısmen açık")),
        created_by=user_label or "sistem",
    ))

    if send_email:
        try:
            _send_shipment_email(db, order, shipment, tamam)
        except Exception:  # e-posta hatası kargolamayı geri almaz
            log.exception("kısmi kargo e-postası gönderilemedi (order=%s)", order.id)

    return shipment


def delete_shipment(db: Session, order: Order, shipment_id: uuid.UUID,
                    user_label: str | None = None) -> None:
    """Yanlış girilen gönderiyi geri al (adetler tekrar bekleyene döner)."""
    hedef = next((s for s in (order.shipments or []) if s.id == shipment_id), None)
    if not hedef:
        raise ShipmentError("Gönderi bulunamadı")
    order.shipments.remove(hedef)
    db.delete(hedef)
    db.flush()

    # Sipariş artık eksik → "Kargoda" aşamasında kalmasın (yanlış bilgi verir).
    # Gönderi öncesi aşamaya dönülür; bulunamazsa paketlendi (7) kabul edilir.
    geri_donuldu = None
    if order.current_stage == STAGE_KARGODA and not is_fully_shipped(order):
        from sqlalchemy import desc, select

        onceki = db.scalar(
            select(OrderStatusHistory.from_stage)
            .where(OrderStatusHistory.order_id == order.id,
                   OrderStatusHistory.action == "kargoya_verildi",
                   OrderStatusHistory.from_stage.isnot(None))
            .order_by(desc(OrderStatusHistory.created_at)).limit(1)
        )
        order.current_stage = onceki if onceki and onceki < STAGE_KARGODA else 7
        geri_donuldu = order.current_stage

    db.add(OrderStatusHistory(
        tenant_id=order.tenant_id, order_id=order.id,
        from_stage=STAGE_KARGODA if geri_donuldu else None,
        to_stage=geri_donuldu,
        action="kismi_kargo_geri",
        note=f"Gönderi geri alındı ({hedef.takip_no or 'takip no yok'})"
             + (" · aşama geri alındı" if geri_donuldu else ""),
        created_by=user_label or "sistem",
    ))


def _send_shipment_email(db: Session, order: Order, shipment: OrderShipment,
                         tamam: bool) -> bool:
    """Bu gönderideki kalemler için müşteriye bilgilendirme."""
    from sqlalchemy import select

    from app.models import CheckoutSession

    store = db.get(Store, order.store_id) if order.store_id else None
    if not store or store.platform != "storefront":
        return False        # Shopify siparişinin maili Shopify'dan gider
    config = store.config or {}
    if config.get("shipping_email_enabled") is False:
        return False
    email = (order.customer_email or "").strip()
    if not email or not shipment.takip_no or not email_service.is_configured():
        return False

    session = db.scalar(select(CheckoutSession).where(
        CheckoutSession.order_id == order.id).limit(1))
    site = (config.get("storefront_url")
            or f"https://{config.get('shop_domain', '')}").rstrip("/")
    status_url = f"{site}/siparis/{session.lookup_token}" if session else None
    tenant = getattr(store, "tenant", None)
    brand = email_service.brand_kwargs(tenant) if tenant else {}
    firma = shipment.kargo_firma or "Kargo"

    rows = "".join(
        f"<tr><td style='padding:4px 0;color:#374151;font-size:14px'>"
        f"{i.get('title')} {('— ' + i['variant_title']) if i.get('variant_title') else ''}"
        f" × {i.get('quantity')}</td></tr>"
        for i in (shipment.items or [])
    )
    baslik = ("Siparişiniz kargoda! 📦" if tamam
              else "Siparişinizin bir bölümü kargoda 📦")
    aciklama = ("" if tamam else
                "<p style='font-size:13px;color:#6b7280'>Kalan ürünleriniz hazır "
                "olduğunda ayrıca bilgilendirileceksiniz.</p>")
    body = (
        f"<p><b>{order.name or ('#' + str(order.order_number or ''))}</b> numaralı "
        f"siparişinizin {'tamamı' if tamam else 'bir bölümü'} kargoya verildi.</p>"
        f"<p style='font-size:14px'>Kargo firması: <b>{firma}</b><br/>"
        f"Takip numarası: <b style='font-family:monospace'>{shipment.takip_no}</b></p>"
        + (f"<table width='100%' style='border-collapse:collapse;margin:10px 0'>{rows}</table>"
           if rows else "")
        + aciklama
    )
    html = email_service.render_email(
        title=baslik, body_html=body,
        button_text="Siparişimi Takip Et" if status_url else "",
        button_url=status_url or "",
        preheader=f"{firma} · takip no {shipment.takip_no}",
        emoji="📦", **brand,
    )
    ok = email_service.send_email(email, baslik, html)
    if ok:
        db.add(OrderStatusHistory(
            tenant_id=order.tenant_id, order_id=order.id,
            action="kargo_email",
            note=f"Gönderi bildirimi → {email} ({firma} {shipment.takip_no})",
            created_by="sistem",
        ))
    return ok
