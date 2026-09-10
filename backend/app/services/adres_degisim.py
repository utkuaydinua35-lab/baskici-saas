"""Müşteri teslimat adresi değişikliği — bağlantı üretimi ve güvenlik kapıları.

⚠ BU AKIŞ MODEL DEĞİŞİKLİĞİNDEN DAHA RİSKLİ. Yanlış kişi adresi değiştirirse
paket ona gider. Erişim üç katmanla korunuyor:

  1. Bağlantıyı OPERATÖR üretir ve siparişteki telefona WhatsApp'tan gönderir.
     Yani erişimin şartı o numaranın sahibi olmak. Sistemde otomatik SMS/OTP
     gönderecek bir sağlayıcı yok; numaraya mesaj atmak elimizdeki en güçlü
     "sahiplik kanıtı" ve zaten kurulu.
  2. Bağlantı KISA ÖMÜRLÜ (varsayılan 1 saat) ve TEK KULLANIMLIK. Model
     değişikliğindeki 12 saat burada fazla: adres değişikliği müşteri bizimle
     yazışırken yapılıyor ve dolandırıcılıkta zaman en büyük düşman.
  3. Sipariş kargoya çıkmışsa bağlantı hiç üretilmez, üretilmişse de
     uygulanmaz — durum arada değişebilir, İKİ yerde de bakılır.

⚠ SHOPIFY'A YAZMAK ZORUNLU. Senkron her çalıştığında `order.raw` Shopify'dan
yeniden yazılıyor (routers/orders.py:_upsert_order). Adresi yalnız yerelde
değiştirmek bir sonraki senkronda SESSİZCE geri alınır ve kargo ESKİ adrese
çıkar. Bu yüzden önce Shopify güncellenir; başarısızsa yerel de değişmez.
"""
from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AdresDegisimTalebi, Order

GECERLILIK_DAKIKA = 60


# ─── Kapı: adres değiştirilebilir mi? ────────────────────────────────────
def degistirilebilir_mi(order: Order) -> tuple[bool, str]:
    """(izin, sebep). Kargo başladıysa adres DEĞİŞTİRİLEMEZ.

    Kontroller bilinçli olarak geniş: barkod üretimi (`kargo_info`), Shopify
    fulfillment durumu, iptal ve arşiv. Biri bile doluysa paket yola çıkmış
    ya da etiketi basılmış demektir; adresi değiştirmek etiketle veriyi
    ayrıştırır ve paket yine eski adrese gider.
    """
    if order is None:
        return False, "Sipariş bulunamadı."
    if order.cancelled_at:
        return False, "Bu sipariş iptal edilmiş."
    if getattr(order, "closed_at", None):
        return False, "Bu sipariş kapatılmış."

    ki = order.kargo_info or {}
    if ki.get("takip_no") or ki.get("barcode") or ki.get("id"):
        return False, ("Siparişiniz kargo sürecine girmiş (kargo etiketi oluşturulmuş). "
                       "Adres değişikliği için bizimle iletişime geçin.")
    if getattr(order, "barkod_kodu", None):
        return False, ("Siparişinizin kargo barkodu oluşturulmuş. Adres değişikliği "
                       "için bizimle iletişime geçin.")
    if (order.fulfillment_status or "").lower() in ("fulfilled", "partial"):
        return False, "Siparişiniz kargoya verilmiş. Adres değişikliği yapılamıyor."
    return True, ""


# ─── Bağlantı ─────────────────────────────────────────────────────────────
def link(token: str) -> str:
    base = get_settings().support_public_base_url.rstrip("/")
    return f"{base}/adres-degisim/{token}"


def talep_olustur(db: Session, order: Order) -> AdresDegisimTalebi:
    """Yeni talep; hâlâ geçerli olan varsa süresi tazelenip o döndürülür."""
    simdi = datetime.now(UTC)
    mevcut = next(
        (t for t in db.query(AdresDegisimTalebi).filter(
            AdresDegisimTalebi.order_id == order.id,
            AdresDegisimTalebi.durum == "bekliyor",
        ).all() if t.expires_at and t.expires_at > simdi),
        None,
    )
    if mevcut:
        # Tekrar gönderimde süre baştan başlar (bkz. model_degisim).
        mevcut.expires_at = simdi + timedelta(minutes=GECERLILIK_DAKIKA)
        db.flush()
        return mevcut

    t = AdresDegisimTalebi(
        tenant_id=order.tenant_id,
        order_id=order.id,
        token=secrets.token_urlsafe(24),
        durum="bekliyor",
        eski_adres=dict((order.raw or {}).get("shipping_address") or {}),
        expires_at=simdi + timedelta(minutes=GECERLILIK_DAKIKA),
    )
    db.add(t)
    db.flush()
    return t


def mesaj(order: Order, baglanti: str) -> str:
    """Operatörün WhatsApp'tan göndereceği hazır metin."""
    ad = (order.customer_name or "").strip().split(" ")[0]
    merhaba = f"Merhaba {ad}," if ad else "Merhaba,"
    no = order.name or (f"#{order.order_number}" if order.order_number else "")
    return (
        f"{merhaba} {no} numaralı siparişinizin teslimat adresini aşağıdaki güvenli "
        f"bağlantıdan güncelleyebilirsiniz: {baglanti} Bağlantı "
        f"{GECERLILIK_DAKIKA} dakika geçerlidir ve yalnız bir kez kullanılabilir. "
        f"Bu bağlantıyı kimseyle paylaşmayınız."
    )


# ─── Form doğrulama ───────────────────────────────────────────────────────
_TEL = re.compile(r"\D")


def telefon_gecerli(ham: str) -> str | None:
    """TR cep numarasını 0XXXXXXXXXX biçimine getirir; geçersizse None.

    Kargo entegrasyonu telefonu buradan okuyor; geçersiz numara etiketi
    üretilemez hale getiriyor, bu yüzden formda ZORUNLU ve doğrulanıyor.
    """
    r = _TEL.sub("", ham or "")
    if r.startswith("0090"):
        r = r[4:]
    elif r.startswith("90") and len(r) == 12:
        r = r[2:]
    elif r.startswith("0") and len(r) == 11:
        r = r[1:]
    if len(r) == 10 and r.startswith("5"):
        return "0" + r
    return None


def eposta_gecerli(ham: str) -> bool:
    e = (ham or "").strip()
    return bool(e) and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]{2,}", e) is not None


def adres_kur(form: dict, eski: dict) -> dict:
    """Formdan Shopify `shipping_address` sözlüğü kurar.

    Eski adresin dokunmadığımız alanları (country, zip…) KORUNUR — Shopify
    eksik alanlarla güncellenince bunları düşürüyor ve kargo entegrasyonu
    posta kodundan il çözemez hale geliyor.
    """
    yeni = dict(eski or {})
    yeni.update({
        "first_name": form["ad"],
        "last_name": form["soyad"],
        "name": f"{form['ad']} {form['soyad']}".strip(),
        "address1": form["adres"],
        "address2": form.get("adres2") or "",
        "province": form["il"],
        "city": form["ilce"],
        "phone": form["telefon"],
    })
    yeni.setdefault("country", "Turkey")
    yeni.setdefault("country_code", "TR")
    return yeni


def ozet(adres: dict) -> str:
    """Panel bildirimi/geçmişi için tek satırlık adres özeti."""
    a = adres or {}
    parcalar = [
        (a.get("name") or f"{a.get('first_name', '')} {a.get('last_name', '')}").strip(),
        (a.get("address1") or "").strip(),
        (a.get("address2") or "").strip(),
        " / ".join(x for x in [(a.get("city") or "").strip(),
                               (a.get("province") or "").strip()] if x),
        (a.get("phone") or "").strip(),
    ]
    return " · ".join(p for p in parcalar if p)
