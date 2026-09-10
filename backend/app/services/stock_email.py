"""Eksik stok bildirimi — kalıptan çıkarılan ürün için müşteriye bilgilendirme.

Bir kalem stok yokluğu nedeniyle kalıptan çıkarılıp plana geri döndürüldüğünde,
müşteriye "şu ürün şu an stokta yok, tedarik ediliyor" maili gönderilir.
Gönderim İSTEĞE BAĞLIDIR (kalıptan çıkarma ekranındaki kutucuk).

Aynı sipariş + aynı ürün için tekrar gönderilmez (idempotent).
"""
from __future__ import annotations

import logging
from xml.sax.saxutils import escape

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Order, OrderStatusHistory, Store
from app.services import email_service

logger = logging.getLogger("stock_email")

ACTION = "stok_eksik_email"

# Durum -> (etiket rengi, zemin). Müşteri tabloya bakınca hangi ürünün neden
# beklediğini bir bakışta görsün.
_DURUM_RENK = {
    "Stok bekleniyor": ("#92400e", "#fef3c7"),
    "Üretimde": ("#3730a3", "#e0e7ff"),
    "Hazır": ("#065f46", "#d1fae5"),
    "Hazırlanıyor": ("#374151", "#f3f4f6"),
}


def _kacir(s) -> str:
    """HTML kaçırma — ürün/müşteri adı e-postaya GÖMÜLÜYOR."""
    return escape(str(s or ""))


def _kalem_tablosu(db: Session, order: Order, brand: dict) -> str:
    """Siparişteki tüm ürünler, modelleri ve mevcut durumları (HTML tablo).

    Tek kalemli siparişte tablo basılmaz: müşteri zaten yukarıda o ürünü
    okudu, altına aynı şeyi tekrar koymak gürültü olurdu.
    """
    try:
        from app.services import siparis_ozet
        kalemler = siparis_ozet.kalemler(db, order)
    except Exception as e:  # noqa: BLE001 — özet çıkarılamazsa mail YİNE gitsin
        logger.warning(f"[stok_eksik] sipariş özeti çıkarılamadı: {e}")
        return ""
    if len(kalemler) < 2:
        return ""

    satirlar = []
    for k in kalemler:
        renk, zemin = _DURUM_RENK.get(k["durum"], _DURUM_RENK["Hazırlanıyor"])
        adet = f" × {k['adet']}" if (k.get("adet") or 1) > 1 else ""
        satirlar.append(
            "<tr>"
            "<td style='padding:10px 12px;border-top:1px solid #e5e7eb;font-size:14px;"
            "color:#111827;line-height:1.45'>"
            f"{_kacir(k['urun'])}{_kacir(adet)}"
            + (f"<div style='font-size:12px;color:#6b7280;margin-top:2px'>"
               f"{_kacir(k['model'])}</div>" if k.get("model") else "")
            + "</td>"
            "<td style='padding:10px 12px;border-top:1px solid #e5e7eb;text-align:right;"
            "white-space:nowrap'>"
            f"<span style='display:inline-block;font-size:12px;font-weight:600;"
            f"color:{renk};background:{zemin};border-radius:999px;padding:3px 10px'>"
            f"{_kacir(k['durum'])}</span></td></tr>"
        )
    return (
        "<p style='margin:22px 0 8px;font-size:14px;font-weight:600;color:#111827'>"
        "Siparişinizdeki ürünler</p>"
        "<table role='presentation' cellpadding='0' cellspacing='0' width='100%' "
        "style='border:1px solid #e5e7eb;border-radius:10px;border-collapse:separate;"
        "border-spacing:0;overflow:hidden'>"
        + "".join(satirlar).replace("border-top:1px solid #e5e7eb", "border-top:0", 1)
        + "</table>"
    )


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
    destek = (get_settings().support_public_base_url or "").rstrip("/")

    body = (
        f"<p>Merhaba {_kacir(ad)},</p>"
        f"<p><b>{_kacir(siparis)}</b> numaralı siparişinizi hazırlarken bir ürünün "
        f"stoğumuzda kalmadığını fark ettik:</p>"
        + email_service.highlight_box(
            f"<div style='font-size:15px;font-weight:600;color:#111827'>{_kacir(urun)}</div>"
            f"<div style='font-size:13px;color:#6b7280;margin-top:4px'>şu an stokta yok</div>",
            accent=brand.get("accent") or email_service.DEFAULT_ACCENT,
        )
        + "<p>Tedarikini sağlamak için çalışıyoruz. Ürün elimize ulaşır ulaşmaz "
          "üretimini tamamlayıp siparişinizi göndereceğiz.</p>"
        # ⚠ SİPARİŞ İÇERİĞİ E-POSTANIN İÇİNDE: müşteri "diğer ürünlerim ne oldu?"
        # sorusunu link'e girmeden cevaplayabilsin. Eskiden yalnız "diğer
        # ürünleriniz etkilenmedi" yazıyordu — hangileri olduğu belli değildi.
        + _kalem_tablosu(db, order, brand)
        + "<p style='font-size:13px;color:#6b7280'>Beklemek istemez ya da farklı bir "
          "seçenek tercih ederseniz "
          f"<a href='{destek}' style='color:{brand.get('accent') or email_service.DEFAULT_ACCENT};"
          f"font-weight:600'>{_kacir(destek.replace('https://', ''))}</a> "
          "adresinden siparişinizle ilgili bize ulaşabilirsiniz.</p>"
    )
    html = email_service.render_email(
        title="Bir ürün için kısa bir gecikme",
        body_html=body,
        # Destek/takip sayfası: müşteri sipariş no + e-posta ile girip yazışabilir.
        button_text="Siparişim hakkında yazın" if destek else "",
        button_url=destek or "",
        preheader=f"{urun} tedarik ediliyor · siparişinizin durumu içeride",
        emoji="📦",
        **brand,
    )
    # ⚠ TEŞHİS: gönderim email_logs'a yazılır (sağlayıcı message id ile).
    # "Mail gelmedi" şikayetinin cevabı bu kayıtta; eskiden hiçbir iz yoktu.
    from app.services import email_log
    try:
        ok = email_log.gonder_ve_kaydet(
            db, tenant_id=order.tenant_id, to=to,
            subject="Siparişinizdeki bir ürün hakkında", html=html,
            order_id=order.id, template_key="stok_eksik")
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
