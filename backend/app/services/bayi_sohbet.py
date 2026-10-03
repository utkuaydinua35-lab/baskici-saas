"""Bayi ↔ atölye sohbeti — iki tarafın ORTAK kuralları.

Aynı konuşmaya iki ayrı uçtan yazılıyor (bayi portalı ve yönetim paneli).
Mesaj oluşturma, okunmamış sayaçları, aciliyet ve bildirim tek yerde durmalı;
kopyalanırsa bir taraf düzeltilip diğeri eskide kalır (bkz. telafi kodu
çakışması, açık sipariş ölçütü).

ACİLİYET: bayinin "bu iş yanıyor" diyebilmesi için. Yalnız renk değil —
acil/çok acil mesaj yöneticiye ANINDA push gönderir ve liste başına taşır.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BayiSohbet, BayiSohbetMesaji, Dealer, Notification, Order, User

BAYI, ATOLYE = "bayi", "atolye"
ACILIYETLER = ("normal", "acil", "cok_acil")
ACILIYET_ETIKET = {"normal": "", "acil": "ACİL", "cok_acil": "ÇOK ACİL"}
OZET_UZUNLUK = 160


def aciliyet_gecerli(deger: str | None) -> str:
    d = (deger or "normal").strip().lower()
    return d if d in ACILIYETLER else "normal"


def sohbet_bul(db: Session, dealer: Dealer, *, olustur: bool = True) -> BayiSohbet | None:
    """Bayinin sohbeti — bayi başına tek. Yoksa (istenirse) açılır."""
    s = db.scalar(select(BayiSohbet).where(BayiSohbet.dealer_id == dealer.id))
    if s is None and olustur:
        s = BayiSohbet(tenant_id=dealer.tenant_id, dealer_id=dealer.id)
        db.add(s)
        db.flush()
    return s


def _ozet(body: str | None, image_url: str | None, order_no: str | None) -> str:
    if (body or "").strip():
        return body.strip()[:OZET_UZUNLUK]
    if image_url:
        return "📎 Görsel"
    if order_no:
        return f"#{order_no} siparişi"
    return "—"


def mesaj_ekle(db: Session, dealer: Dealer, *, gonderen: str, body: str | None = None,
               image_url: str | None = None, order: Order | None = None,
               aciliyet: str = "normal", gonderen_ad: str | None = None) -> BayiSohbetMesaji:
    """Mesajı yaz, sayaçları güncelle. Bildirim ÇAĞIRAN tarafta değil, burada."""
    sohbet = sohbet_bul(db, dealer)
    aciliyet = aciliyet_gecerli(aciliyet)
    m = BayiSohbetMesaji(
        sohbet_id=sohbet.id, gonderen=gonderen, gonderen_ad=(gonderen_ad or None),
        body=(body or None), image_url=(image_url or None),
        order_id=(order.id if order is not None else None),
        order_no=(str(order.order_number) if order is not None and order.order_number else None),
        aciliyet=aciliyet,
    )
    db.add(m)
    sohbet.son_mesaj_at = datetime.now(UTC)
    sohbet.son_mesaj_ozet = _ozet(body, image_url, m.order_no)
    sohbet.son_gonderen = gonderen
    if gonderen == BAYI:
        sohbet.okunmamis_atolye = (sohbet.okunmamis_atolye or 0) + 1
        if aciliyet != "normal":
            sohbet.acil_bekliyor = True
    else:
        sohbet.okunmamis_bayi = (sohbet.okunmamis_bayi or 0) + 1
    db.flush()
    _bildir(db, dealer, m)
    return m


def okundu_isaretle(db: Session, dealer: Dealer, *, taraf: str) -> int:
    """`taraf` kendi okunmamışlarını sıfırlar. Döner: okunmuş sayılan mesaj sayısı."""
    sohbet = sohbet_bul(db, dealer, olustur=False)
    if sohbet is None:
        return 0
    karsi = BAYI if taraf == ATOLYE else ATOLYE
    sayi = 0
    for m in db.scalars(select(BayiSohbetMesaji).where(
            BayiSohbetMesaji.sohbet_id == sohbet.id,
            BayiSohbetMesaji.gonderen == karsi,
            BayiSohbetMesaji.okundu.is_(False))).all():
        m.okundu = True
        sayi += 1
    if taraf == ATOLYE:
        sohbet.okunmamis_atolye = 0
        sohbet.acil_bekliyor = False      # acil görüldü
    else:
        sohbet.okunmamis_bayi = 0
    return sayi


def _bildir(db: Session, dealer: Dealer, m: BayiSohbetMesaji) -> None:
    """Karşı tarafa haber ver. Bildirim patlarsa mesaj yine de kaydedilir."""
    etiket = ACILIYET_ETIKET.get(m.aciliyet) or ""
    ozet = _ozet(m.body, m.image_url, m.order_no)
    if m.gonderen == BAYI:
        baslik = f"{'🔴 ' + etiket + ' · ' if etiket else '💬 '}{dealer.name} yazdı"
        link = f"/bayi-sohbet?bayi={dealer.id}"
        try:
            db.add(Notification(tenant_id=dealer.tenant_id, store_id=dealer.store_id,
                                kind=("warn" if etiket else "bayii"),
                                title=baslik, body=ozet, link=link))
        except Exception:  # noqa: BLE001
            pass
        try:
            from app.services import push
            push.send_to_tenant(db, dealer.tenant_id, baslik, ozet, url=link,
                                tag=f"bayi-sohbet-{dealer.id}")
        except Exception:  # noqa: BLE001
            pass
        if etiket:
            try:
                from app.services import telegram
                telegram.send_message(f"🔴 <b>{etiket}</b> · {dealer.name}\n{ozet[:300]}")
            except Exception:  # noqa: BLE001
                pass
    else:
        link = "/bayii/sohbet"
        try:
            from app.services import push
            for u in db.scalars(select(User).where(
                    User.dealer_id == dealer.id, User.is_active.is_(True))).all():
                push.send_to_user(db, u.id, "💬 Atölyeden mesaj", ozet, url=link,
                                  tag=f"bayi-sohbet-{dealer.id}")
        except Exception:  # noqa: BLE001
            pass


def ser_mesaj(m: BayiSohbetMesaji, *, avatarlar: dict | None = None) -> dict:
    """avatarlar: {"bayi": url, "atolye": url} — WhatsApp gibi mesajın yanında.

    `durum`: iletildi | goruldu. Karşı taraf okuyunca çift tik olur; kendi
    mesajının nereye vardığını görmek sohbetin en çok sorulan sorusu.
    """
    avatarlar = avatarlar or {}
    return {
        "id": str(m.id),
        "gonderen": m.gonderen,
        "gonderen_ad": m.gonderen_ad,
        "avatar": avatarlar.get(m.gonderen),
        "durum": "goruldu" if m.okundu else "iletildi",
        "body": m.body,
        "image_url": m.image_url,
        "order_id": str(m.order_id) if m.order_id else None,
        "order_no": m.order_no,
        "aciliyet": m.aciliyet,
        "okundu": bool(m.okundu),
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


def avatarlar(db: Session, dealer: Dealer) -> dict:
    """Sohbette gösterilecek küçük görseller: bayinin logosu, atölyenin markası."""
    from app.models import Tenant
    t = db.get(Tenant, dealer.tenant_id)
    return {
        "bayi": getattr(dealer, "logo_url", None),
        "atolye": getattr(t, "logo_url", None) if t is not None else None,
    }


def mesajlari_getir(db: Session, dealer: Dealer, *, limit: int = 200,
                    since: datetime | None = None) -> list[dict]:
    sohbet = sohbet_bul(db, dealer, olustur=False)
    if sohbet is None:
        return []
    av = avatarlar(db, dealer)
    q = select(BayiSohbetMesaji).where(BayiSohbetMesaji.sohbet_id == sohbet.id)
    if since is not None:
        q = q.where(BayiSohbetMesaji.created_at > since)
    satirlar = db.scalars(q.order_by(BayiSohbetMesaji.created_at.desc()).limit(limit)).all()
    return [ser_mesaj(m, avatarlar=av) for m in reversed(satirlar)]


def ser_sohbet(s: BayiSohbet | None, dealer: Dealer) -> dict:
    return {
        "dealer_id": str(dealer.id),
        "dealer_ad": dealer.name,
        "son_mesaj_at": s.son_mesaj_at.isoformat() if s and s.son_mesaj_at else None,
        "son_mesaj_ozet": s.son_mesaj_ozet if s else None,
        "son_gonderen": s.son_gonderen if s else None,
        "okunmamis_atolye": (s.okunmamis_atolye or 0) if s else 0,
        "okunmamis_bayi": (s.okunmamis_bayi or 0) if s else 0,
        "acil_bekliyor": bool(s.acil_bekliyor) if s else False,
        "logo_url": getattr(dealer, "logo_url", None),
    }
