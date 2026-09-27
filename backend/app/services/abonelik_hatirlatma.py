"""Abonelik e-posta hatırlatmaları — kiracının hesap sahiplerine.

Panel bandı yalnız panele GİREN kiracıya görünür; bitişi kaçıran kiracı
vitrini kapanana kadar fark etmeyebilir. Bu yüzden dört aşamada e-posta:

    yaklasiyor   bitişe ≤5 gün kala
    ek_sure      bitiş geçti (1-7. gün) — her şey açık
    salt_okunur  8-14. gün — panel yalnız okunur
    askida       15. gün+ — vitrin kapandı

KURALLAR
  • Her aşama HER DÖNEM için bir kez: gönderim kaydının anahtarı bitiş
    tarihini içerir (abonelik_<aşama>_<YYYYMMDD>). Ödeme bitişi ileri
    taşıyınca yeni dönemin hatırlatmaları kendiliğinden yeniden açılır.
  • Aşamalar tam güne değil ARALIĞA bakar: sunucu bir gün kapalı kalsa da
    hatırlatma kaçmaz, ertesi gün gider.
  • Gönderilemeyen (başarısız) e-posta ertesi gün yeniden denenir.
  • Yalnız ücretli plandaki, etkin, bitiş tarihi olan kiracılar. Elle askıya
    alınmış kiracıya (is_active=False) otomatik e-posta gitmez — o durum
    yöneticinin kararıdır, "ödeme yapın" demek yanlış olurdu.
"""
from __future__ import annotations

import logging
from datetime import date
from html import escape

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import EmailLog, Tenant, User
from app.services import abonelik
from app.services.email_log import gonder_ve_kaydet
from app.services.email_service import highlight_box, render_email

logger = logging.getLogger("abonelik")

YAKLASIYOR_GUN = 5

_BASLIK = {
    "yaklasiyor": ("🗓️", "Aboneliğinizin yenilenme zamanı yaklaşıyor"),
    "ek_sure": ("⏳", "Aboneliğinizin süresi doldu"),
    "salt_okunur": ("🔒", "Paneliniz salt okunur duruma geçti"),
    "askida": ("⛔", "Vitrininiz kapatıldı"),
}


def asama(tenant, bugun: date | None = None) -> str | None:
    """Hatırlatma gerektiren aşama; yoksa None."""
    if not getattr(tenant, "is_active", True) or tenant.active_until is None:
        return None
    d = abonelik.durum(tenant, bugun)
    if d.asama == "aktif":
        return "yaklasiyor" if d.kalan_gun is not None and d.kalan_gun <= YAKLASIYOR_GUN else None
    return d.asama


def anahtar(asama_: str, tenant) -> str:
    return f"abonelik_{asama_}_{tenant.active_until:%Y%m%d}"


def _ucretli(tenant) -> bool:
    plan = getattr(tenant, "plan_kaydi", None)
    return bool(plan and ((plan.aylik_ucret or 0) > 0 or (plan.komisyon_orani or 0) > 0))


def _icerik(db: Session, tenant, asama_: str, bugun: date | None) -> tuple[str, str]:
    emoji, baslik = _BASLIK[asama_]
    d = abonelik.durum(tenant, bugun)
    parcalar = [f"<p>Merhaba,</p><p>{escape(d.mesaj or baslik)}</p>"]

    try:
        th = abonelik.tahakkuk_hesapla(db, tenant, bugun=bugun)
    except ValueError:
        th = None
    if th is not None:
        satirlar = [
            f"<b>Plan:</b> {escape(th.plan_ad)}",
            f"<b>Ödenmiş son gün:</b> {tenant.active_until:%d.%m.%Y}",
            f"<b>Ödenecek tutar:</b> {_tl(th.toplam)}",
        ]
        if th.komisyon > 0:
            satirlar.append(f"<span style='font-size:13px;color:#6b7280'>"
                            f"{_tl(th.sabit_ucret)} sabit ücret + {_tl(th.komisyon)} vitrin satış "
                            f"komisyonu</span>")
        parcalar.append(highlight_box("<br>".join(satirlar)))

    h = abonelik.havale_bilgisi(db)
    if h.get("iban"):
        iban = " ".join(h["iban"][i:i + 4] for i in range(0, len(h["iban"]), 4))
        havale = [f"<b>IBAN:</b> <span style='font-family:monospace'>{escape(iban)}</span>"]
        if h.get("alici"):
            havale.insert(0, f"<b>Alıcı:</b> {escape(h['alici'])}")
        if h.get("banka"):
            havale.append(f"<b>Banka:</b> {escape(h['banka'])}")
        havale.append(f"<b>Açıklamaya yazın:</b> <span style='font-family:monospace'>"
                      f"{escape(tenant.slug)}</span>")
        parcalar.append("<p style='margin-bottom:6px'><b>Havale / EFT ile ödeme</b></p>"
                        + highlight_box("<br>".join(havale)))
        if h.get("aciklama"):
            parcalar.append(f"<p style='font-size:13px;color:#6b7280'>{escape(h['aciklama'])}</p>")

    if asama_ == "askida":
        parcalar.append("<p>Ödemeniz işlendiğinde vitrininiz ve paneliniz kaldığı yerden "
                        "devam eder; verileriniz silinmez.</p>")

    panel = get_settings().magaza_panel_url.rstrip("/")
    html = render_email(
        title=baslik, emoji=emoji, preheader=d.mesaj or baslik,
        body_html="".join(parcalar),
        button_text="Ödeme bilgileri" if panel else "",
        button_url=f"{panel}/abonelik" if panel else "",
        footer="Bu e-posta aboneliğinizle ilgili otomatik bir bilgilendirmedir.",
    )
    return baslik, html


def _tl(tutar) -> str:
    s = f"{tutar:,.2f}"                     # 1,234.50
    return s.replace(",", "X").replace(".", ",").replace("X", ".") + " TL"   # 1.234,50 TL


def hatirlatmalari_gonder(db: Session, bugun: date | None = None) -> dict:
    """Günlük iş: gereken hatırlatmaları gönderir. Döner: sayaçlar."""
    sayac = {"gonderilen": 0, "atlanan": 0, "alicisiz": 0, "basarisiz": 0}
    for t in db.scalars(select(Tenant).where(Tenant.active_until.is_not(None))).all():
        a = asama(t, bugun)
        if a is None or not _ucretli(t):
            continue
        k = anahtar(a, t)
        # Bu dönemin bu aşaması zaten GÖNDERİLDİYSE atla (başarısızlar yeniden denenir)
        if db.scalar(select(EmailLog.id).where(
                EmailLog.tenant_id == t.id, EmailLog.template_key == k,
                EmailLog.status != "basarisiz").limit(1)):
            sayac["atlanan"] += 1
            continue
        alicilar = db.scalars(select(User.email).where(
            User.tenant_id == t.id, User.role == "owner", User.is_active.is_(True))).all()
        if not alicilar:
            sayac["alicisiz"] += 1
            logger.warning("[abonelik] %s için hatırlatma alıcısı yok (owner)", t.slug)
            continue
        konu, html = _icerik(db, t, a, bugun)
        for e in alicilar:
            if gonder_ve_kaydet(db, tenant_id=t.id, to=e, subject=konu, html=html, template_key=k):
                sayac["gonderilen"] += 1
            else:
                sayac["basarisiz"] += 1
    db.commit()
    return sayac
