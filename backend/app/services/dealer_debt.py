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
