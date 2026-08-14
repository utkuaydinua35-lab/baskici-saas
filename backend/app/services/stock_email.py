"""Eksik stok bildirimi — kalıptan çıkarılan ürün için müşteriye bilgilendirme.

Bir kalem stok yokluğu nedeniyle kalıptan çıkarılıp plana geri döndürüldüğünde,
müşteriye "şu ürün şu an stokta yok, tedarik ediliyor" maili gönderilir.
Gönderim İSTEĞE BAĞLIDIR (kalıptan çıkarma ekranındaki kutucuk).

Aynı sipariş + aynı ürün için tekrar gönderilmez (idempotent).
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Order, OrderStatusHistory, Store
from app.services import email_service

logger = logging.getLogger("stock_email")

ACTION = "stok_eksik_email"


def _zaten_gonderildi(db: Session, order: Order, urun: str) -> bool:
    rows = db.scalars(
        select(OrderStatusHistory.note).where(
            OrderStatusHistory.order_id == order.id,
            OrderStatusHistory.action == ACTION,
        )
    ).all()
    return any((r or "").strip().endswith(urun) for r in rows)


def send_stok_eksik(db: Session, order: Order, urun: str) -> tuple[bool, str]:
    """(gonderildi, mesaj). Akışı ASLA bozmaz — çağıran hatayı yutmalı.

    urun: müşteriye gösterilecek ürün tanımı, örn "Beyaz iPhone 14 Pro".
    """
    if not email_service.is_configured():
        return False, "E-posta gönderimi yapılandırılmamış (.env)"
    to = (order.customer_email or "").strip()
    if not to:
        return False, "Siparişte müşteri e-postası yok"
    if _zaten_gonderildi(db, order, urun):
        return False, "Bu ürün için zaten bildirim gönderilmiş"

    store = db.scalar(select(Store).where(Store.id == order.store_id)) if order.store_id else None
    brand = email_service.store_brand_kwargs(store)

    ad = (order.customer_name or "").split(" ")[0]
    siparis = order.name or f"#{order.order_number or ''}"

    body = (
        f"<p>Merhaba {ad},</p>"
        f"<p><b>{siparis}</b> numaralı siparişinizi hazırlarken bir ürünün "
        f"stoğumuzda kalmadığını fark ettik:</p>"
        + email_service.highlight_box(
            f"<div style='font-size:15px;font-weight:600;color:#111827'>{urun}</div>"
            f"<div style='font-size:13px;color:#6b7280;margin-top:4px'>şu an stokta yok</div>"
        )
        + "<p>Tedarikini sağlamak için çalışıyoruz. Ürün elimize ulaşır ulaşmaz "
          "üretimini tamamlayıp siparişinizi göndereceğiz.</p>"
        "<p>Siparişinizin diğer ürünleri etkilenmedi; hazırlanmaya devam ediyor.</p>"
        "<p style='font-size:13px;color:#6b7280'>Beklemek istemez ya da farklı bir "
        "seçenek tercih ederseniz bu e-postayı yanıtlamanız yeterli — size yardımcı olalım.</p>"
    )
    html = email_service.render_email(
        title="Bir ürün için kısa bir gecikme",
        body_html=body,
        preheader=f"{urun} tedarik ediliyor",
        emoji="📦",
        **brand,
    )
    try:
        ok = email_service.send_email(to, "Siparişinizdeki bir ürün hakkında", html)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[stok_eksik] gonderilemedi: {e}")
        return False, f"Gönderilemedi: {str(e)[:120]}"
    if not ok:
        return False, "E-posta gönderilemedi"

    db.add(OrderStatusHistory(
        tenant_id=order.tenant_id, order_id=order.id,
        action=ACTION,
        note=f"Eksik stok bildirimi gönderildi ({to}) — {urun}",
        created_by="Sistem (otomatik)",
    ))
    logger.info(f"[stok_eksik] {siparis} -> {to} ({urun})")
    return True, f"{to} adresine bildirim gönderildi"
