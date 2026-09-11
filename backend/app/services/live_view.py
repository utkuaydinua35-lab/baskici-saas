"""Canlı Görünüm (Live View) — panelin anlık mağaza ekranını besleyen tek kaynak.

NE GÖSTERİR
───────────
Şu anki ziyaretçi · bugünkü oturum/sipariş/ciro (+ önceki güne göre değişim ve
saatlik seri) · müşteri davranışı hunisi · ülkeye göre oturumlar · yeni ve geri
dönen müşteri · son aktivite akışı.

VERİ KAYNAKLARI
───────────────
• StorefrontPresence — vitrindeki ping bileşeni ~20 sn'de bir yazar. Oturum
  başına TEK satır (first_seen/last_seen). Ziyaretçi ve oturum sayıları,
  aktif sepetler ve ülke dağılımı buradan gelir. Kişisel veri yok.
• Order — kanonik sipariş/ciro kaynağı. CheckoutSession DEĞİL: iptal,
  telafi ve iade ayrımı yalnız Order'da doğru tutuluyor.
• CheckoutSession — huninin "ödeme yapıyor" adımı (henüz sipariş değil).

ZAMAN
─────
"Bugün" TÜRKİYE günüdür; gece yarısı TR'de sıfırlanır. Karşılaştırma
"dün AYNI SAATE kadar" ile yapılır — yoksa sabahın 9'unda bütün metrikler
düne göre %90 düşük görünürdü.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import Numeric, cast, func as sql_func, select
from sqlalchemy.orm import Session

from app.models import CheckoutSession, Order, StorefrontPresence
from app.services.ulkeler import ulke_bilgi

TR = ZoneInfo("Europe/Istanbul")

# Huni pencereleri — üçü de AYNI olmalı, yoksa "aktif sepet 12 / ödeme 3"
# gibi karşılaştırılamayan sayılar çıkar
HUNI_DK = 30
ZIYARETCI_DK = 5      # "şu anki ziyaretçi" = son 5 dk'da ping atmış oturum
SAKLAMA_GUN = 7       # presence budama eşiği


def _tr_gun_basi(an: datetime) -> datetime:
    """Verilen anın içinde bulunduğu TR gününün başlangıcı (UTC olarak)."""
    tr = an.astimezone(TR)
    return datetime.combine(tr.date(), time.min, tzinfo=TR).astimezone(timezone.utc)


def _degisim(simdi: float, onceki: float) -> float | None:
    """Yüzde değişim. Önceki sıfırsa oran tanımsızdır — None döner ("yeni")."""
    if onceki <= 0:
        return None
    return round((simdi - onceki) / onceki * 100, 1)


def _saatlik_seri(satirlar) -> list[float]:
    """[(tr_saat_basi, deger)] → 24 elemanlı saat dizisi (0..23)."""
    seri = [0.0] * 24
    for saat, deger in satirlar:
        if saat is None:
            continue
        # date_trunc sonucu TR duvar saati (tzsiz) döner
        if 0 <= saat.hour < 24:
            seri[saat.hour] += float(deger or 0)
    return seri


def _tr_saat(kolon):
    """timestamptz → TR duvar saatine yuvarlanmış saat başı."""
    return sql_func.date_trunc("hour", sql_func.timezone("Europe/Istanbul", kolon))


def canli_gorunum(db: Session, store) -> dict:
    """Mağazanın canlı görünüm verisi. Panel ~10 sn'de bir çeker."""
    now = datetime.now(timezone.utc)
    bugun = _tr_gun_basi(now)
    dun = bugun - timedelta(days=1)
    dun_ayni_saat = now - timedelta(days=1)   # "dün bu saate kadar"

    # ── Presence (ziyaretçi / oturum / sepet / ülke) ──
    pres = (StorefrontPresence.store_id == store.id,)

    def _pres_say(*ek) -> int:
        return db.scalar(select(sql_func.count()).select_from(StorefrontPresence)
                         .where(*pres, *ek)) or 0

    ziyaretci = _pres_say(StorefrontPresence.last_seen > now - timedelta(minutes=ZIYARETCI_DK))
    oturum_bugun = _pres_say(StorefrontPresence.first_seen >= bugun)
    oturum_dun = _pres_say(StorefrontPresence.first_seen >= dun,
                           StorefrontPresence.first_seen < dun_ayni_saat)

    def _oturum_seri(baslangic, bitis):
        saat = _tr_saat(StorefrontPresence.first_seen)
        return _saatlik_seri(db.execute(
            select(saat, sql_func.count())
            .where(*pres, StorefrontPresence.first_seen >= baslangic,
                   StorefrontPresence.first_seen < bitis)
            .group_by(saat)).all())

    oturum_seri = _oturum_seri(bugun, now + timedelta(hours=1))
    oturum_seri_dun = _oturum_seri(dun, bugun)

    # ── Siparişler / ciro (Order kanonik) ──
    # Para birimine duyarlı TL tutarı (services/ciro) — dashboard ile aynı kural.
    from app.services import ciro as _ciro_svc
    tutar = _ciro_svc.tl_tutar()
    sip = (Order.store_id == store.id, Order.is_telafi.is_(False),
           Order.cancelled_at.is_(None),
           (Order.financial_status != "refunded") | (Order.financial_status.is_(None)))

    def _sip_ozet(baslangic, bitis=None):
        kosul = [Order.created_at_platform >= baslangic]
        if bitis is not None:
            kosul.append(Order.created_at_platform < bitis)
        satir = db.execute(
            select(sql_func.count(Order.id), sql_func.coalesce(sql_func.sum(tutar), 0))
            .where(*sip, *kosul)).one()
        return int(satir[0] or 0), Decimal(str(satir[1] or 0))

    sip_bugun, ciro_bugun = _sip_ozet(bugun)
    sip_dun, ciro_dun = _sip_ozet(dun, dun_ayni_saat)

    def _sip_seri(baslangic, bitis):
        saat = _tr_saat(Order.created_at_platform)
        satirlar = db.execute(
            select(saat, sql_func.count(Order.id),
                   sql_func.coalesce(sql_func.sum(tutar), 0))
            .where(*sip, Order.created_at_platform >= baslangic,
                   Order.created_at_platform < bitis)
            .group_by(saat)).all()
        return (_saatlik_seri([(s, a) for s, a, _ in satirlar]),
                _saatlik_seri([(s, c) for s, _, c in satirlar]))

    sip_seri, ciro_seri = _sip_seri(bugun, now + timedelta(hours=1))
    sip_seri_dun, ciro_seri_dun = _sip_seri(dun, bugun)

    # ── Müşteri davranışı hunisi ──
    huni_an = now - timedelta(minutes=HUNI_DK)
    aktif_sepet = _pres_say(StorefrontPresence.cart_items > 0,
                            StorefrontPresence.last_seen > huni_an)
    odeme_yapiyor = db.scalar(select(sql_func.count()).select_from(CheckoutSession).where(
        CheckoutSession.store_id == store.id, CheckoutSession.status == "pending",
        CheckoutSession.created_at > huni_an)) or 0
    satin_aldi = db.scalar(select(sql_func.count()).select_from(CheckoutSession).where(
        CheckoutSession.store_id == store.id, CheckoutSession.status == "paid",
        CheckoutSession.paid_at > huni_an)) or 0

    # ── Ülkeye göre oturumlar (bugün) ──
    konumlar = []
    for kod, adet in db.execute(
        select(StorefrontPresence.country, sql_func.count())
        .where(*pres, StorefrontPresence.first_seen >= bugun)
        .group_by(StorefrontPresence.country)
        .order_by(sql_func.count().desc()).limit(20)
    ).all():
        bilgi = ulke_bilgi(kod)
        bilgi["oturum"] = int(adet or 0)
        konumlar.append(bilgi)

    # ── Yeni ve geri dönen müşteriler (bugün sipariş verenler) ──
    # Aynı e-postanın İLK siparişi bugünse yeni, değilse geri dönen.
    yeni = geri_donen = 0
    for _eposta, ilk in db.execute(
        select(Order.customer_email, sql_func.min(Order.created_at_platform))
        .where(*sip, Order.customer_email.isnot(None))
        .group_by(Order.customer_email)
        .having(sql_func.max(Order.created_at_platform) >= bugun)
    ).all():
        if ilk is not None and ilk >= bugun:
            yeni += 1
        else:
            geri_donen += 1

    return {
        "zaman": now.isoformat(),
        "ziyaretci": ziyaretci,
        "oturumlar": {
            "bugun": oturum_bugun, "onceki": oturum_dun,
            "degisim": _degisim(oturum_bugun, oturum_dun),
            "seri": oturum_seri, "seri_onceki": oturum_seri_dun,
        },
        "siparisler": {
            "bugun": sip_bugun, "onceki": sip_dun,
            "degisim": _degisim(sip_bugun, sip_dun),
            "seri": sip_seri, "seri_onceki": sip_seri_dun,
        },
        "satislar": {
            "bugun": str(ciro_bugun), "onceki": str(ciro_dun),
            "degisim": _degisim(float(ciro_bugun), float(ciro_dun)),
            "seri": ciro_seri, "seri_onceki": ciro_seri_dun,
        },
        "davranis": {"aktif_sepet": aktif_sepet, "odeme_yapiyor": odeme_yapiyor,
                     "satin_aldi": satin_aldi, "pencere_dk": HUNI_DK},
        "konumlar": konumlar,
        "musteriler": {"yeni": yeni, "geri_donen": geri_donen},
        "aktivite": _aktivite(db, store, now),
        "su_anki_saat": now.astimezone(TR).hour,
        # ── Geriye uyum: Dashboard'daki küçük Canlı Görünüm kartı bu adları
        # okuyor; yeni ekran gelince kart bozulmasın diye korunuyor ──
        "current_visitors": ziyaretci,
        "today_sessions": oturum_bugun,
        "active_carts": aktif_sepet,
        "checking_out": odeme_yapiyor,
        "purchased_recent": satin_aldi,
        "today_orders": sip_bugun,
        "today_revenue": str(ciro_bugun),
    }


def _maskele(ad: str | None) -> str:
    """'Ahmet Yılmaz' → 'Ahmet Y.' — kim olduğu anlaşılsın ama canlı ekranda
    tam ad dolaşmasın."""
    parcalar = (ad or "").strip().split()
    if not parcalar:
        return "Misafir"
    kalan = " ".join(f"{p[0]}." for p in parcalar[1:] if p)
    return f"{parcalar[0]} {kalan}".strip()


def _aktivite(db: Session, store, now: datetime) -> list[dict]:
    """Son siparişler + ödeme oturumları, yeniden eskiye."""
    cikti = []
    for o in db.scalars(
        select(Order).where(Order.store_id == store.id, Order.is_telafi.is_(False))
        .order_by(Order.created_at_platform.desc().nulls_last()).limit(8)
    ).all():
        cikti.append({
            "tur": "siparis",
            "zaman": o.created_at_platform.isoformat() if o.created_at_platform else None,
            "kim": _maskele(o.customer_name),
            "metin": f"{o.name or '#' + str(o.order_number)} sipariş verdi",
            "tutar": (o.raw or {}).get("total_price"),
        })
    etiket = {"pending": "ödeme sayfasında", "paid": "ödemeyi tamamladı",
              "failed": "ödemesi başarısız oldu", "expired": "sepeti terk etti"}
    for s in db.scalars(
        select(CheckoutSession).where(
            CheckoutSession.store_id == store.id,
            CheckoutSession.created_at >= now - timedelta(hours=12))
        .order_by(CheckoutSession.created_at.desc()).limit(8)
    ).all():
        m = s.customer or {}
        cikti.append({
            "tur": f"odeme_{s.status}",
            "zaman": s.created_at.isoformat() if s.created_at else None,
            "kim": _maskele(f"{m.get('first_name', '')} {m.get('last_name', '')}".strip()),
            "metin": etiket.get(s.status, s.status),
            "tutar": str(s.amount),
        })
    cikti.sort(key=lambda a: a["zaman"] or "", reverse=True)
    return cikti[:12]


def presence_buda(db: Session, store_id, now: datetime | None = None) -> int:
    """Eski presence satırlarını sil — tablo sonsuza kadar büyümesin."""
    now = now or datetime.now(timezone.utc)
    silinen = db.query(StorefrontPresence).filter(
        StorefrontPresence.store_id == store_id,
        StorefrontPresence.last_seen < now - timedelta(days=SAKLAMA_GUN),
    ).delete(synchronize_session=False)
    db.commit()
    return silinen
