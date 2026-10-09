"""Vitrin oturumları — Shopify "Oturumlar" ölçüsü ve trafik kaynağı.

Oturum: aynı ziyaretçinin 30 dk'dan uzun ara vermeden sürdürdüğü ziyaret
(Google Analytics/Shopify tanımı). Presence ping'i (~20 sn) her geldiğinde
ziyaretçinin açık oturumu uzatılır; 30 dk sessizlikten sonraki ping yeni
oturum açar. Dönüşüm oranı = sipariş / oturum.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Store, VitrinOturum

ARA = timedelta(minutes=30)

KAYNAK_ETIKET = {
    "meta_reklam": "Meta reklamı",
    "instagram": "Instagram",
    "facebook": "Facebook",
    "google_reklam": "Google reklamı",
    "google": "Google arama",
    "tiktok": "TikTok",
    "e_posta": "E-posta",
    "diger": "Diğer siteler",
    "dogrudan": "Doğrudan",
}


def kaynak_sinifla(ref: str | None, utm: str | None, tik: str | None, kendi_host: str | None) -> str:
    """Trafik kaynağı. Öncelik: reklam tıklama kimliği > utm_source > yönlendiren site.

    tik: tıklama kimliği türü ("fbclid" | "gclid" | "ttclid") — reklamdan geldi.
    fbclid organik Instagram/Facebook paylaşım linkine de eklenir; utm yoksa
    yönlendirene bakılır, o da Meta ise organik sayılmaz (reklam varsayılır)."""
    u = (utm or "").lower().strip()
    if tik == "gclid":
        return "google_reklam"
    if tik == "ttclid" or "tiktok" in u:
        return "tiktok"
    if u:
        if u in {"ig", "instagram"} or "insta" in u:
            return "meta_reklam" if tik == "fbclid" else "instagram"
        if u in {"fb", "facebook", "meta"} or "facebook" in u:
            return "meta_reklam" if tik == "fbclid" else "facebook"
        if "google" in u:
            return "google_reklam"
        if u in {"email", "e-posta", "eposta", "newsletter", "klaviyo", "mail"}:
            return "e_posta"
    if tik == "fbclid":
        return "meta_reklam"
    host = (urlparse(ref).hostname or "").lower() if ref else ""
    # www./magaza. gibi alt alan adları aynı site: son iki etiket karşılaştırılır
    kok = ".".join((kendi_host or "").split(".")[-2:])
    if not host or (kok and (host == kok or host.endswith("." + kok))):
        return "dogrudan"
    if "instagram" in host:
        return "instagram"
    if "facebook" in host or host in {"fb.com", "m.me", "l.messenger.com"}:
        return "facebook"
    if "google" in host:
        return "google"
    if "tiktok" in host:
        return "tiktok"
    if any(m in host for m in ("mail.", "outlook", "gmail")):
        return "e_posta"
    return "diger"


def kaydet(db: Session, store: Store, *, ziyaretci: str, yol: str | None, sepet: int,
           now: datetime, ulke: str | None = None, ref: str | None = None,
           utm: str | None = None, tik: str | None = None, mobil: bool | None = None,
           kendi_host: str | None = None) -> VitrinOturum:
    """Ziyaretçinin açık oturumunu uzat ya da yenisini aç. commit ÇAĞIRANDA."""
    o = db.scalar(
        select(VitrinOturum).where(
            VitrinOturum.store_id == store.id,
            VitrinOturum.ziyaretci == ziyaretci,
            VitrinOturum.son >= now - ARA,
        ).order_by(VitrinOturum.son.desc()).limit(1)
    )
    yol = (yol or "/")[:300]
    if o is None:
        o = VitrinOturum(
            tenant_id=store.tenant_id, store_id=store.id, ziyaretci=ziyaretci,
            basladi=now, son=now, giris_yolu=yol, son_yol=yol, sayfa_sayisi=1,
            kaynak=kaynak_sinifla(ref, utm, tik, kendi_host),
            cihaz=None if mobil is None else ("mobil" if mobil else "masaustu"),
            ulke=ulke,
        )
        db.add(o)
    else:
        o.son = now
        if yol != o.son_yol:
            o.sayfa_sayisi = (o.sayfa_sayisi or 1) + 1
            o.son_yol = yol
    p = yol.lower()
    if p.startswith("/urun/"):
        o.urun_gordu = True
    if sepet > 0:
        o.sepete_ekledi = True
    if p.startswith("/odeme"):
        o.odemeye_gecti = True
    return o
