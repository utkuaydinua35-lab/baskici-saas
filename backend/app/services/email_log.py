"""Gönderilen e-postanın kaydı + teslimat durumu — "mail ulaştı mı?" sorusu.

⚠ NEDEN VAR: müşteri "mail gelmedi" dediğinde elimizde HİÇBİR kanıt yoktu.
`send_email` yalnız True/False dönüyordu, Resend'in message id'si atılıyordu ve
bounce/complaint bildirimi hiç toplanmıyordu. "Gönderdik" diyebiliyorduk ama
"kutuya düştü" diyemiyorduk — eksik stok akışının WhatsApp'a taşınmasının asıl
sebebi buydu.

Akış: gonderilirken `kaydet()` bir satır açar (message id ile), Resend webhook'u
(routers/webhooks.py) o kimliği bulup durumu günceller.

⚠ KAYIT GÖNDERİMİ BOZMAZ. Log yazılamazsa mail yine gitmiş sayılır; bu yüzden
tüm gövde try/except içinde.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EmailLog
from app.services import email_service

logger = logging.getLogger("email")

# durum -> panelde gösterilecek etiket (tek kaynak; panel bunu kullanır)
DURUM_ETIKET = {
    "gonderildi": "Gönderildi",
    "iletildi": "Ulaştı",
    "gecikti": "Gecikiyor",
    "sekti": "ULAŞMADI (geri döndü)",
    "sikayet": "Spam olarak işaretlendi",
    "basarisiz": "Gönderilemedi",
}

# Resend olayı -> (durum, zaman alanı)
OLAY_DURUM = {
    "email.sent": ("gonderildi", None),
    "email.delivered": ("iletildi", "delivered_at"),
    "email.delivery_delayed": ("gecikti", None),
    "email.bounced": ("sekti", "bounced_at"),
    "email.complained": ("sikayet", None),
    "email.opened": (None, "opened_at"),      # durumu DEĞİŞTİRMEZ
    "email.clicked": (None, None),
}

# Bir kez "sekti"/"sikayet" olduysa geriye dönme: geç gelen "delivered"
# olayı gerçeği gizlerdi.
_KESIN = ("sekti", "sikayet")


def gonder_ve_kaydet(db: Session, *, tenant_id, to: str, subject: str, html: str,
                     text: str | None = None, headers: dict | None = None,
                     order_id=None, template_key: str | None = None) -> bool:
    """Maili gönder, kaydını aç. Gönderim başarılıysa True.

    Commit ETMEZ — çağıranın işlem sınırına karışmaz.
    """
    sonuc = email_service.send_email_ex(to, subject, html, text, headers)
    kaydet(db, tenant_id=tenant_id, to=to, subject=subject, sonuc=sonuc,
           order_id=order_id, template_key=template_key, html=html)
    return bool(sonuc)


def kaydet(db: Session, *, tenant_id, to: str, subject: str,
           sonuc: email_service.Sonuc, order_id=None,
           template_key: str | None = None, html: str | None = None) -> None:
    """Gönderim sonucunu email_logs'a yaz. Hata OLURSA sessizce geçer.

    ⚠ SAVEPOINT içinde yazılır. Düz try/except + rollback, kayıt yazılamazsa
    ÇAĞIRANIN işlemini de geri alırdı — kargo bildirimi gönderilirken bu,
    az önce yazılmış kargo kaydını (kargo_info, aşama değişimi) silmek
    demekti. Savepoint yalnız bu INSERT'i geri alır.
    """
    try:
        with db.begin_nested():
            db.add(EmailLog(
                tenant_id=tenant_id,
                order_id=order_id,
                template_key=(template_key or None),
                to_email=(to or "")[:200],
                subject=(subject or "")[:300],
                # Gövde teşhis için değerli ama tabloyu şişirmesin.
                body=(html or None) if (html and len(html) <= 20000) else None,
                status="gonderildi" if sonuc.ok else "basarisiz",
                provider=(sonuc.saglayici or None),
                provider_message_id=(sonuc.message_id or None),
                error=(sonuc.hata or None),
            ))
    except Exception as e:  # noqa: BLE001 — kayıt hatası gönderimi BOZMAZ
        logger.warning(f"[email] log yazılamadı: {e}")


def olay_isle(db: Session, olay: str, message_id: str, zaman) -> bool:
    """Resend webhook olayını ilgili kayda uygula. Kayıt bulunduysa True."""
    if not message_id:
        return False
    kayit = db.scalar(select(EmailLog).where(
        EmailLog.provider_message_id == message_id).limit(1))
    if kayit is None:
        return False

    durum, alan = OLAY_DURUM.get(olay, (None, None))
    if durum and kayit.status not in _KESIN:
        kayit.status = durum
    if alan and getattr(kayit, alan, None) is None:
        setattr(kayit, alan, zaman)
    kayit.last_event = olay[:40]
    kayit.last_event_at = zaman
    return True


def ozet(k: EmailLog) -> dict:
    """Panel için tek kayıt."""
    return {
        "id": str(k.id),
        "to": k.to_email,
        "subject": k.subject,
        "template_key": k.template_key,
        "durum": k.status,
        "durum_etiket": DURUM_ETIKET.get(k.status, k.status),
        # Resend kullanılıyorsa webhook beklenir; SMTP'de teslimat bilgisi
        # hiç gelmez — panel "bilinmiyor" ile "ulaşmadı"yı karıştırmasın.
        "geri_bildirim_bekleniyor": bool(
            k.provider == "resend" and k.status == "gonderildi" and not k.last_event),
        "saglayici": k.provider,
        "hata": k.error,
        "son_olay": k.last_event,
        "gonderildi_at": k.created_at.isoformat() if k.created_at else None,
        "iletildi_at": k.delivered_at.isoformat() if k.delivered_at else None,
        "sekti_at": k.bounced_at.isoformat() if k.bounced_at else None,
        "acildi_at": k.opened_at.isoformat() if k.opened_at else None,
    }
