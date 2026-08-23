"""Bayi siparişinin cari borcunu geri alma / yeniden uygulama — TEK kaynak.

Sipariş silinince bayinin borcundan düşülmeli, geri alınınca tekrar eklenmeli.
Bu para işlemi olduğu için iki kural kritik:

  1) İDEMPOTENT olmalı. Aynı silme iki kez çalışırsa bayiye iki kez alacak
     yazılmamalı. Bu yüzden "borcu düş" değil, "borcun NET durumunu hedefe
     getir" mantığı kullanılıyor: mevcut net hesaplanır, hedefe göre FARK
     uygulanır. Fark sıfırsa hiçbir şey yazılmaz.

  2) Para birimleri ayrı yürür. Ürün bedeli bayinin para biriminde (TRY/USD),
     kargo HER ZAMAN ₺. Bu yüzden gruplama (bayi, para birimi) ikilisiyle.

Ters kayıtlar kind='duzeltme' + ref_order_id ile yazılır; bu ikili yalnızca
buradan üretilir, başka bir akışla karışmaz.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

# Siparişin bayiye yazdığı BORÇ hareketleri
BORC_TURLERI = ("siparis", "kargo")
# Bu servisin yazdığı TERS kayıtlar
DUZELTME = "duzeltme"

_SIFIR = Decimal("0.00")


def _d(v) -> Decimal:
    return Decimal(str(v or 0))


def hesapla(hareketler: list[dict], *, reverse: bool) -> dict[tuple, Decimal]:
    """Uygulanacak farkları hesapla — saf fonksiyon, veritabanı yok.

    hareketler: [{"dealer_id", "currency", "kind", "amount"}]
    reverse=True  -> hedef net 0 (borç tamamen geri alınır)
    reverse=False -> hedef net = orijinal borç (borç yeniden uygulanır)

    Dönüş: {(dealer_id, currency): delta}. Delta 0 olanlar ELENİR — böylece
    tekrar çalıştırmak hiçbir kayıt üretmez.
    """
    borc: dict[tuple, Decimal] = {}
    duz: dict[tuple, Decimal] = {}
    for h in hareketler:
        anahtar = (h["dealer_id"], (h.get("currency") or "TRY").upper())
        tutar = _d(h.get("amount"))
        if h.get("kind") in BORC_TURLERI:
            borc[anahtar] = borc.get(anahtar, _SIFIR) + tutar
        elif h.get("kind") == DUZELTME:
            duz[anahtar] = duz.get(anahtar, _SIFIR) + tutar

    out: dict[tuple, Decimal] = {}
    for anahtar in set(borc) | set(duz):
        b = borc.get(anahtar, _SIFIR)
        net = b + duz.get(anahtar, _SIFIR)
        hedef = _SIFIR if reverse else b
        fark = (hedef - net).quantize(Decimal("0.01"))
        if fark != _SIFIR:
            out[anahtar] = fark
    return out


def uygula(db: Session, order, *, reverse: bool) -> list[dict]:
    """Farkları bayi bakiyesine işle + 'duzeltme' hareketi yaz.

    Dönüş: uygulanan hareketlerin özeti (boş liste = yapacak bir şey yoktu).
    """
    from app.models import Dealer, DealerTransaction

    txler = db.scalars(
        select(DealerTransaction).where(DealerTransaction.ref_order_id == order.id)
    ).all()
    farklar = hesapla(
        [{"dealer_id": t.dealer_id, "currency": t.currency,
          "kind": t.kind, "amount": t.amount} for t in txler],
        reverse=reverse,
    )
    if not farklar:
        return []

    aciklama = (f"Sipariş #{order.order_number} silindi — borç iptali" if reverse
                else f"Sipariş #{order.order_number} geri alındı — borç tekrar")
    ozet = []
    for (dealer_id, cur), fark in farklar.items():
        dealer = db.scalar(select(Dealer).where(Dealer.id == dealer_id))
        if not dealer:
            continue
        if cur == "USD":
            yeni = _d(dealer.balance_usd) + fark
            dealer.balance_usd = yeni
        else:
            yeni = _d(dealer.balance) + fark
            dealer.balance = yeni
        db.add(DealerTransaction(
            tenant_id=order.tenant_id, dealer_id=dealer_id,
            amount=fark, kind=DUZELTME, currency=cur,
            description=aciklama, ref_order_id=order.id, balance_after=yeni,
        ))
        ozet.append({"dealer_id": str(dealer_id), "currency": cur,
                     "delta": float(fark), "balance_after": float(yeni)})
    return ozet


# ─── İlk borcu yazma ─────────────────────────────────────────
# uygula() var olan hareketlerin NET'ini hedefe çeker; hiç hareket yoksa
# yapacak bir şey bulamaz. Siparişin İLK borcunu yazan yer burası.
# İki çağıran var: yönetim panelinden bayi siparişi (anında) ve bayi
# portalinden gelen siparişin ONAYI. İkisi de aynı kodu kullansın diye
# ortaklaştırıldı — fiyat/kur kuralı tek yerde.
def ilk_borc(db: Session, dealer, order, *, adet: int, kargo_uygula: bool) -> dict:
    """Sipariş için ürün (+ kargo) borcunu yaz. Zaten yazılmışsa tekrar yazmaz.

    Ürün bedeli bayinin para biriminde (USD/TRY), kargo HER ZAMAN ₺ ve ayrı
    hareket olarak işlenir.
    """
    from app.models import DealerTransaction

    var = db.scalar(select(DealerTransaction.id).where(
        DealerTransaction.ref_order_id == order.id,
        DealerTransaction.kind.in_(tuple(BORC_TURLERI)),
    ).limit(1))
    if var:  # idempotent: iki kez onaylanırsa borç ikilenmesin
        return {"yazildi": False, "urun": 0.0, "kargo": 0.0,
                "currency": (dealer.currency or "TRY").upper()}

    cur = (dealer.currency or "TRY").upper()
    urun = _d(dealer.unit_price) * Decimal(int(adet))
    kargo = _d(dealer.shipping_fee) if (kargo_uygula and dealer.shipping_fee) else Decimal("0")

    if cur == "USD":
        dealer.balance_usd = _d(dealer.balance_usd) + urun
        urun_bakiye = dealer.balance_usd
    else:
        dealer.balance = _d(dealer.balance) + urun
        urun_bakiye = dealer.balance
    db.add(DealerTransaction(
        tenant_id=order.tenant_id, dealer_id=dealer.id, amount=urun, kind="siparis",
        currency=cur, description=f"Sipariş #{order.order_number} — {adet} adet",
        ref_order_id=order.id, balance_after=urun_bakiye,
    ))

    if kargo > 0:
        dealer.balance = _d(dealer.balance) + kargo
        db.add(DealerTransaction(
            tenant_id=order.tenant_id, dealer_id=dealer.id, amount=kargo, kind="kargo",
            currency="TRY", description=f"Kargo — Sipariş #{order.order_number}",
            ref_order_id=order.id, balance_after=dealer.balance,
        ))
    return {"yazildi": True, "urun": float(urun), "kargo": float(kargo),
            "currency": cur, "bakiye": float(urun_bakiye)}
