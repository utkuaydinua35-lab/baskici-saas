"""Panel ana sayfa raporu — Shopify "Analytics" benzeri.

Seçilen aralık + karşılaştırma aralığı için: ciro, sipariş, ortalama sepet,
oturum, dönüşüm oranı, zaman serisi; ayrıca son 8 haftanın karşılaştırması,
şehirler, en çok satanlar, birlikte satılanlar, trafik kaynakları ve huni.

Ciro kuralları analytics.summary ile AYNI (telafi/iptal/tam iade hariç, para
birimine duyarlı — services/ciro). Kanal: "perakende" = vitrin + Shopify
geçmişi (bayi siparişleri hariç); "vitrin" = yalnız vitrin; "hepsi" = bayi dahil.
"""
from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from datetime import date, timedelta

from sqlalchemy import Numeric, cast, func, select
from sqlalchemy.orm import Session

from app.models import LineItem, Order, Store, VitrinOturum
from app.services import ciro as _ciro
from app.services import gun as _gun
from app.services.oturum import KAYNAK_ETIKET

KANALLAR = {"perakende": ("storefront", "shopify"), "vitrin": ("storefront",), "hepsi": None}


def karsilastirma_araligi(bas: date, bit: date, tur: str) -> tuple[date, date] | None:
    if tur == "yok":
        return None
    if tur == "gecen_yil":
        try:
            return bas.replace(year=bas.year - 1), bit.replace(year=bit.year - 1)
        except ValueError:   # 29 Şubat
            return bas - timedelta(days=365), bit - timedelta(days=365)
    gun = (bit - bas).days + 1
    return bas - timedelta(days=gun), bas - timedelta(days=1)


def _kosullar(tid, magazalar: list[uuid.UUID] | None, bas_dt, bit_dt) -> list:
    k = [
        Order.tenant_id == tid,
        Order.is_telafi.is_(False),
        Order.cancelled_at.is_(None),
        (Order.financial_status != "refunded") | (Order.financial_status.is_(None)),
        Order.created_at_platform >= bas_dt,
        Order.created_at_platform < bit_dt,
    ]
    if magazalar is not None:
        k.append(Order.store_id.in_(magazalar or [uuid.uuid4()]))
    return k


def _birim(bas: date, bit: date) -> str:
    gun = (bit - bas).days + 1
    return "saat" if gun == 1 else ("gun" if gun <= 92 else "ay")


def _seri_anahtarlari(bas: date, bit: date, birim: str) -> list[str]:
    if birim == "saat":
        return [f"{h:02d}" for h in range(24)]
    if birim == "gun":
        return [(bas + timedelta(days=i)).isoformat() for i in range((bit - bas).days + 1)]
    anahtarlar, y, m = [], bas.year, bas.month
    while (y, m) <= (bit.year, bit.month):
        anahtarlar.append(f"{y}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return anahtarlar


def _donem(db: Session, tid, magazalar, vitrin_ids: list, bas: date, bit: date) -> dict:
    bas_dt, bit_dt = _gun.aralik(bas, bit)
    kos = _kosullar(tid, magazalar, bas_dt, bit_dt)
    tl = _ciro.tl_tutar()
    r = db.execute(select(
        func.coalesce(func.sum(tl), 0), func.count(Order.id),
        func.count(Order.id).filter(_ciro.tl_siparis_mi()),
        func.coalesce(func.sum(_ciro.usd_tutar()), 0),
    ).where(*kos)).one()
    ciro, adet, tl_adet, usd = float(r[0] or 0), int(r[1] or 0), int(r[2] or 0), float(r[3] or 0)

    # Oturum ve dönüşüm YALNIZ vitrin (Shopify geçmişinde oturum verisi yok)
    oturum = db.scalar(select(func.count(VitrinOturum.id)).where(
        VitrinOturum.store_id.in_(vitrin_ids or [uuid.uuid4()]),
        VitrinOturum.basladi >= bas_dt, VitrinOturum.basladi < bit_dt)) or 0
    vitrin_siparis = db.scalar(select(func.count(Order.id)).where(
        *_kosullar(tid, vitrin_ids, bas_dt, bit_dt))) or 0

    # Zaman serisi (İstanbul saatine göre)
    birim = _birim(bas, bit)
    yerel = func.timezone("Europe/Istanbul", Order.created_at_platform)
    kol = {"saat": func.to_char(yerel, "HH24"), "gun": func.to_char(yerel, "YYYY-MM-DD"),
           "ay": func.to_char(yerel, "YYYY-MM")}[birim]
    harita = {k: (float(t or 0), int(a or 0)) for k, t, a in db.execute(
        select(kol, func.coalesce(func.sum(tl), 0), func.count(Order.id)).where(*kos).group_by(kol)
    ).all()}
    oyerel = func.timezone("Europe/Istanbul", VitrinOturum.basladi)
    okol = {"saat": func.to_char(oyerel, "HH24"), "gun": func.to_char(oyerel, "YYYY-MM-DD"),
            "ay": func.to_char(oyerel, "YYYY-MM")}[birim]
    oharita = dict(db.execute(
        select(okol, func.count(VitrinOturum.id)).where(
            VitrinOturum.store_id.in_(vitrin_ids or [uuid.uuid4()]),
            VitrinOturum.basladi >= bas_dt, VitrinOturum.basladi < bit_dt).group_by(okol)
    ).all())
    seri = [{"k": k, "ciro": round(harita.get(k, (0, 0))[0], 2), "siparis": harita.get(k, (0, 0))[1],
             "oturum": int(oharita.get(k, 0))}
            for k in _seri_anahtarlari(bas, bit, birim)]

    return {
        "bas": bas.isoformat(), "bit": bit.isoformat(), "birim": birim,
        "ciro": round(ciro, 2), "ciro_usd": round(usd, 2), "siparis": adet,
        "ortalama_sepet": round(ciro / tl_adet, 2) if tl_adet else 0.0,
        "oturum": int(oturum), "vitrin_siparis": int(vitrin_siparis),
        "donusum": round(100 * vitrin_siparis / oturum, 2) if oturum else None,
        "seri": seri,
    }


def _sehir_adi(raw: dict) -> str | None:
    adr = (raw or {}).get("shipping_address") or {}
    ad = (adr.get("province") or adr.get("city") or "").strip()
    return ad or None


def rapor(db: Session, tid, *, bas: date, bit: date, karsilastir: str = "onceki",
          kanal: str = "perakende") -> dict:
    platformlar = KANALLAR.get(kanal, KANALLAR["perakende"])
    magazalar_q = select(Store.id, Store.platform).where(Store.tenant_id == tid)
    satirlar = db.execute(magazalar_q).all()
    magazalar = None if platformlar is None else [i for i, p in satirlar if p in platformlar]
    vitrin_ids = [i for i, p in satirlar if p == "storefront"]

    simdi = _donem(db, tid, magazalar, vitrin_ids, bas, bit)
    kars = karsilastirma_araligi(bas, bit, karsilastir)
    onceki = _donem(db, tid, magazalar, vitrin_ids, *kars) if kars else None

    bas_dt, bit_dt = _gun.aralik(bas, bit)
    kos = _kosullar(tid, magazalar, bas_dt, bit_dt)
    tl = _ciro.tl_tutar()

    # ── Son 8 hafta (bitişe kadar, Pazartesi başlangıçlı) ──
    hafta_bas = bit - timedelta(days=bit.weekday()) - timedelta(weeks=7)
    h_bas_dt, h_bit_dt = _gun.aralik(hafta_bas, bit)
    hyerel = func.date_trunc("week", func.timezone("Europe/Istanbul", Order.created_at_platform))
    hmap = {r[0].date().isoformat(): (float(r[1] or 0), int(r[2] or 0)) for r in db.execute(
        select(hyerel, func.coalesce(func.sum(tl), 0), func.count(Order.id))
        .where(*_kosullar(tid, magazalar, h_bas_dt, h_bit_dt)).group_by(hyerel)).all() if r[0]}
    haftalar = []
    for i in range(8):
        hb = hafta_bas + timedelta(weeks=i)
        c, a = hmap.get(hb.isoformat(), (0.0, 0))
        haftalar.append({"hafta": hb.isoformat(), "ciro": round(c, 2), "siparis": a})

    # ── Şehirler (Türkçe büyük/küçük harf farkı birleştirilir) ──
    sehir_ciro: dict[str, float] = defaultdict(float)
    sehir_adet: Counter[str] = Counter()
    sehir_gorunen: dict[str, Counter] = defaultdict(Counter)
    from app.services.arama import normalize
    for raw, tutar in db.execute(select(Order.raw, tl).where(*kos)).all():
        ad = _sehir_adi(raw)
        if not ad:
            continue
        anahtar = normalize(ad)
        sehir_adet[anahtar] += 1
        sehir_ciro[anahtar] += float(tutar or 0)
        sehir_gorunen[anahtar][ad] += 1
    sehirler = [{"sehir": sehir_gorunen[k].most_common(1)[0][0], "siparis": n,
                 "ciro": round(sehir_ciro[k], 2)} for k, n in sehir_adet.most_common(10)]

    # ── En çok satanlar (adet + yaklaşık ciro: satır fiyatı × adet) ──
    fiyat = func.coalesce(cast(func.nullif(LineItem.raw["price"].astext, ""), Numeric), 0)
    urunler = [
        {"urun": r[0] or "—", "adet": int(r[1] or 0), "ciro": round(float(r[2] or 0), 2)}
        for r in db.execute(
            select(LineItem.title, func.sum(LineItem.quantity), func.sum(fiyat * LineItem.quantity))
            .join(Order, LineItem.order_id == Order.id).where(*kos)
            .group_by(LineItem.title).order_by(func.sum(LineItem.quantity).desc()).limit(10)
        ).all()
    ]

    # ── Birlikte satılanlar (aynı siparişte iki farklı ürün) ──
    sepetler: dict = defaultdict(set)
    for oid, baslik in db.execute(
        select(LineItem.order_id, LineItem.title).join(Order, LineItem.order_id == Order.id)
        .where(*kos)).all():
        if baslik:
            sepetler[oid].add(baslik)
    ciftler: Counter = Counter()
    for urunler_set in sepetler.values():
        s = sorted(urunler_set)
        if 2 <= len(s) <= 8:
            for i in range(len(s)):
                for j in range(i + 1, len(s)):
                    ciftler[(s[i], s[j])] += 1
    birlikte = [{"a": a, "b": b, "siparis": n} for (a, b), n in ciftler.most_common(10) if n >= 1]

    # ── Müşteri: yeni / geri dönen (e-postaya göre) ──
    eposta = func.lower(Order.customer_email)
    donem_epostalar = select(eposta).where(*kos, Order.customer_email.isnot(None)).distinct()
    musteri = db.scalar(select(func.count()).select_from(donem_epostalar.subquery())) or 0
    eski = db.scalar(select(func.count(func.distinct(eposta))).where(
        Order.tenant_id == tid, Order.created_at_platform < bas_dt,
        eposta.in_(donem_epostalar))) or 0

    # ── Trafik: kaynak, cihaz, giriş sayfası, huni (yalnız vitrin) ──
    okos = [VitrinOturum.store_id.in_(vitrin_ids or [uuid.uuid4()]),
            VitrinOturum.basladi >= bas_dt, VitrinOturum.basladi < bit_dt]
    kaynaklar = [{"kaynak": KAYNAK_ETIKET.get(k or "dogrudan", k), "anahtar": k or "dogrudan",
                  "oturum": int(n)}
                 for k, n in db.execute(select(VitrinOturum.kaynak, func.count(VitrinOturum.id))
                                        .where(*okos).group_by(VitrinOturum.kaynak)
                                        .order_by(func.count(VitrinOturum.id).desc())).all()]
    cihazlar = {k or "bilinmiyor": int(n) for k, n in db.execute(
        select(VitrinOturum.cihaz, func.count(VitrinOturum.id)).where(*okos)
        .group_by(VitrinOturum.cihaz)).all()}
    girisler = [{"yol": y or "/", "oturum": int(n)} for y, n in db.execute(
        select(VitrinOturum.giris_yolu, func.count(VitrinOturum.id)).where(*okos)
        .group_by(VitrinOturum.giris_yolu).order_by(func.count(VitrinOturum.id).desc()).limit(8)).all()]
    h = db.execute(select(
        func.count(VitrinOturum.id),
        func.count(VitrinOturum.id).filter(VitrinOturum.urun_gordu),
        func.count(VitrinOturum.id).filter(VitrinOturum.sepete_ekledi),
        func.count(VitrinOturum.id).filter(VitrinOturum.odemeye_gecti),
    ).where(*okos)).one()
    huni = [
        {"asama": "Oturum", "sayi": int(h[0] or 0)},
        {"asama": "Ürün gördü", "sayi": int(h[1] or 0)},
        {"asama": "Sepete ekledi", "sayi": int(h[2] or 0)},
        {"asama": "Ödemeye geçti", "sayi": int(h[3] or 0)},
        {"asama": "Satın aldı", "sayi": simdi["vitrin_siparis"]},
    ]

    return {
        "kanal": kanal, "karsilastir": karsilastir,
        "simdi": simdi, "onceki": onceki,
        "haftalar": haftalar, "sehirler": sehirler, "urunler": urunler,
        "birlikte": birlikte,
        "musteri": {"toplam": int(musteri), "geri_donen": int(eski),
                    "yeni": int(musteri) - int(eski)},
        "kaynaklar": kaynaklar, "cihazlar": cihazlar, "girisler": girisler, "huni": huni,
        "oturum_baslangici": _oturum_baslangici(db, vitrin_ids),
    }


def _oturum_baslangici(db: Session, vitrin_ids: list) -> str | None:
    """Oturum kaydı ilk ne zaman başladı — öncesindeki aralıkta 'veri yok' denir."""
    ilk = db.scalar(select(func.min(VitrinOturum.basladi)).where(
        VitrinOturum.store_id.in_(vitrin_ids or [uuid.uuid4()])))
    return ilk.isoformat() if ilk else None

