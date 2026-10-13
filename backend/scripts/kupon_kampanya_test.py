"""Kod girmek müşteriye DAHA FAZLA ödetmemeli.

BULGU (canlı, 2026-10-13): KACIRMA10 (%10) kuponu, 3 üründe otomatik
"3 Al 2 Öde" kampanyasının YERİNE geçiyordu: 899,97 TL'lik sepet kampanyayla
684,88 TL iken kod girilince 894,87 TL oluyor, ekranda "Kupon uygulandı"
yazıyordu. Kural: kod, otomatik kampanyadan az kazandırıyorsa uygulanmaz.
"""
from __future__ import annotations

import sys
import uuid
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, update  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import DiscountCode, Store  # noqa: E402
from app.services import checkout as co  # noqa: E402

GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


db = SessionLocal()
store = db.scalar(select(Store).where(Store.platform == "storefront"))
if not store:
    print("  · vitrin mağazası yok — atlandı\n\n0 GECTI, 0 KALDI"); sys.exit(0)

iz = uuid.uuid4().hex[:6].upper()
# Mağazadaki diğer otomatik indirimler sonucu etkilemesin: test süresince kapat
acik = db.scalars(select(DiscountCode.id).where(
    DiscountCode.store_id == store.id, DiscountCode.is_automatic.is_(True),
    DiscountCode.is_active.is_(True))).all()
db.execute(update(DiscountCode).where(DiscountCode.id.in_(acik or [uuid.uuid4()])).values(is_active=False))
oto = DiscountCode(tenant_id=store.tenant_id, store_id=store.id, code=f"T3AL2{iz}", kind="bxgy",
                   value=0, buy_x=3, pay_y=2, is_automatic=True, is_active=True)
kod = DiscountCode(tenant_id=store.tenant_id, store_id=store.id, code=f"TYUZDE10{iz}", kind="percent",
                   value=10, is_active=True, combinable=True)
db.add_all([oto, kod]); db.commit()
KARGO = Decimal("84.90")


def sepet(adet):
    return [{"product_id": str(uuid.uuid4()), "unit_price": "300.00", "quantity": adet}], Decimal("300") * adet


try:
    snap, toplam = sepet(3)
    kodsuz = co.resolve_discounts(db, store, None, toplam, None, KARGO, 3, snap)
    es("3 ürün, kodsuz: 3 Al 2 Öde (300 TL)", Decimal("300.00"), kodsuz.total)
    kodlu = co.resolve_discounts(db, store, kod.code, toplam, None, KARGO, 3, snap)
    es("3 ürün + %10 kodu: kampanya KORUNUR (müşteri fazla ödemez)", Decimal("300.00"), kodlu.total)
    es("…ve kodun uygulanmadığı bildirilir", kod.code, kodlu.kod_yok_sayildi)
    es("…uygulanan indirim kampanyanın kendisi", [oto.code], kodlu.codes)

    snap, toplam = sepet(1)
    tek = co.resolve_discounts(db, store, kod.code, toplam, None, KARGO, 1, snap)
    es("1 ürün + %10 kodu: kod uygulanır (30 TL)", (Decimal("30.00"), None), (tek.total, tek.kod_yok_sayildi))

    snap, toplam = sepet(2)
    iki = co.resolve_discounts(db, store, kod.code, toplam, None, KARGO, 2, snap)
    es("2 ürün + %10 kodu: kampanya koşulu yok → kod uygulanır (60 TL)", Decimal("60.00"), iki.total)

    kod.value = 50; db.commit()
    snap, toplam = sepet(3)
    buyuk = co.resolve_discounts(db, store, kod.code, toplam, None, KARGO, 3, snap)
    es("3 ürün + %50 kodu: kod kampanyadan iyi → kod uygulanır (450 TL)",
       (Decimal("450.00"), None), (buyuk.total, buyuk.kod_yok_sayildi))

    try:
        co.resolve_discounts(db, store, "BOYLEBIRKODYOK", toplam, None, KARGO, 3, snap)
        es("geçersiz kod yine hata verir", "hata", "hata yok")
    except co.CheckoutError:
        es("geçersiz kod yine hata verir", "hata", "hata")
finally:
    db.delete(oto); db.delete(kod)
    db.execute(update(DiscountCode).where(DiscountCode.id.in_(acik or [uuid.uuid4()])).values(is_active=True))
    db.commit(); db.close()

print(f"\n{GECTI} GECTI, {KALDI} KALDI")
sys.exit(1 if KALDI else 0)
