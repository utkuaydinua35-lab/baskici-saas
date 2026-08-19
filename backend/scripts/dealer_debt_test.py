"""Bayi cari borç geri alma testleri — veritabanı GEREKTİRMEZ.

Para işlemi olduğu için hesap saf bir fonksiyona (dealer_debt.hesapla) ayrıldı;
burada hem o hesap hem de bakiyeye işleyen kısım (uygula) sahte oturumla
sınanıyor. Bu dosyaya dokunan bir değişiklik yaptıysan çalıştır:

    cd ~/baskici-saas/backend && .venv/bin/python scripts/dealer_debt_test.py
"""
from __future__ import annotations

import sys
import uuid
from decimal import Decimal as D
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import Dealer, DealerTransaction  # noqa: E402
from app.services import dealer_debt  # noqa: E402
from app.services.dealer_debt import hesapla  # noqa: E402

_gecti = 0
_basarisiz = 0


def sina(ad, kosul, ek=""):
    global _gecti, _basarisiz
    print(("  ✓ " if kosul else "  ✗ ") + ad + ("" if kosul else f"  → {ek}"))
    if kosul:
        _gecti += 1
    else:
        _basarisiz += 1


def h(dealer, kind, amount, cur="TRY"):
    return {"dealer_id": dealer, "currency": cur, "kind": kind, "amount": amount}


class _Order:
    def __init__(self):
        self.id = uuid.uuid4()
        self.tenant_id = uuid.uuid4()
        self.order_number = "9001"


class _FakeDB:
    """uygula()'nın dokunduğu yüzey: scalars(...).all(), scalar(...), add(...)"""

    def __init__(self, txler, dealer):
        self.txler, self.dealer, self.eklenen = txler, dealer, []

    def scalars(self, q):
        return self

    def all(self):
        return self.txler

    def scalar(self, q):
        return self.dealer

    def add(self, o):
        self.eklenen.append(o)
        self.txler.append(o)


def _tx(dealer_id, kind, amount, cur="TRY"):
    return DealerTransaction(dealer_id=dealer_id, kind=kind,
                             amount=D(str(amount)), currency=cur)


def hesap_testleri():
    B, C = "bayi1", "bayi2"
    print("── Hesap: silme ──")
    tx = [h(B, "siparis", 100), h(B, "kargo", 20)]
    sina("ürün+kargo tek para birimi", hesapla(tx, reverse=True), )
    sina("ürün+kargo = -120", hesapla(tx, reverse=True) == {(B, "TRY"): D("-120.00")})
    sina("USD ürün + TRY kargo AYRI",
         hesapla([h(B, "siparis", 100, "USD"), h(B, "kargo", 20, "TRY")], reverse=True)
         == {(B, "USD"): D("-100.00"), (B, "TRY"): D("-20.00")})

    print("── Hesap: idempotens ──")
    silinmis = tx + [h(B, "duzeltme", D("-120"))]
    sina("ikinci silme hiçbir şey yazmaz", hesapla(silinmis, reverse=True) == {})
    sina("geri alma borcu tekrar yazar",
         hesapla(silinmis, reverse=False) == {(B, "TRY"): D("120.00")})
    geri = silinmis + [h(B, "duzeltme", D("120"))]
    sina("ikinci geri alma hiçbir şey yazmaz", hesapla(geri, reverse=False) == {})
    sina("geri alınmışı tekrar silme",
         hesapla(geri, reverse=True) == {(B, "TRY"): D("-120.00")})

    print("── Hesap: sil-geri-sil-geri döngüsü ──")
    durum, net = list(tx), D("0")
    for i in range(4):
        for (dd, cc), v in hesapla(durum, reverse=(i % 2 == 0)).items():
            durum.append(h(dd, "duzeltme", v, cc))
            net += v
    sina("4 adım sonunda net sıfır", net == D("0.00"), net)
    sina("toplam = orijinal borç",
         sum(D(str(x["amount"])) for x in durum) == D("120"))

    print("── Hesap: uç durumlar ──")
    sina("hiç hareket yok", hesapla([], reverse=True) == {})
    sina("yalnız kargo", hesapla([h(B, "kargo", 15)], reverse=True) == {(B, "TRY"): D("-15.00")})
    sina("sıfır tutar kayıt üretmez", hesapla([h(B, "siparis", 0)], reverse=True) == {})
    sina("ödeme hareketi SAYILMAZ",
         hesapla([h(B, "siparis", 100), h(B, "odeme", -50)], reverse=True)
         == {(B, "TRY"): D("-100.00")})
    sina("kuruş hassasiyeti",
         hesapla([h(B, "siparis", D("33.33")), h(B, "kargo", D("0.01"))], reverse=True)
         == {(B, "TRY"): D("-33.34")})
    sina("iki farklı bayi ayrı",
         hesapla([h(B, "siparis", 100), h(C, "siparis", 50)], reverse=True)
         == {(B, "TRY"): D("-100.00"), (C, "TRY"): D("-50.00")})
    sina("para birimi büyük/küçük harf",
         hesapla([h(B, "siparis", 10, "usd"), h(B, "kargo", 5, "Try")], reverse=True)
         == {(B, "USD"): D("-10.00"), (B, "TRY"): D("-5.00")})


def bakiye_testleri():
    print("── Bakiye: silme ──")
    o = _Order()
    d = Dealer(id=uuid.uuid4(), name="Test", balance=D("500.00"), balance_usd=D("0.00"))
    db = _FakeDB([_tx(d.id, "siparis", 100), _tx(d.id, "kargo", 20)], d)
    dealer_debt.uygula(db, o, reverse=True)
    sina("bakiye 500 → 380", d.balance == D("380.00"), d.balance)
    sina("tek düzeltme kaydı", len(db.eklenen) == 1, len(db.eklenen))
    sina("kayıt tutarı -120", db.eklenen[0].amount == D("-120.00"), db.eklenen[0].amount)
    sina("balance_after doğru", db.eklenen[0].balance_after == D("380.00"))

    print("── Bakiye: aynı silme tekrar ──")
    b, k = d.balance, len(db.eklenen)
    dealer_debt.uygula(db, o, reverse=True)
    sina("bakiye DEĞİŞMEDİ", d.balance == b, d.balance)
    sina("yeni kayıt YOK", len(db.eklenen) == k, len(db.eklenen))

    print("── Bakiye: geri alma ──")
    dealer_debt.uygula(db, o, reverse=False)
    sina("bakiye 380 → 500", d.balance == D("500.00"), d.balance)
    b, k = d.balance, len(db.eklenen)
    dealer_debt.uygula(db, o, reverse=False)
    sina("tekrar geri alma etkisiz", d.balance == b and len(db.eklenen) == k)

    print("── Bakiye: USD ürün + TRY kargo ──")
    o2 = _Order()
    d2 = Dealer(id=uuid.uuid4(), name="USD", balance=D("200.00"), balance_usd=D("90.00"))
    db2 = _FakeDB([_tx(d2.id, "siparis", 50, "USD"), _tx(d2.id, "kargo", 30, "TRY")], d2)
    dealer_debt.uygula(db2, o2, reverse=True)
    sina("USD 90 → 40", d2.balance_usd == D("40.00"), d2.balance_usd)
    sina("TRY 200 → 170", d2.balance == D("170.00"), d2.balance)
    dealer_debt.uygula(db2, o2, reverse=False)
    sina("geri alınca USD 90", d2.balance_usd == D("90.00"))
    sina("geri alınca TRY 200", d2.balance == D("200.00"))

    print("── Bakiye: borç kaydı olmayan sipariş ──")
    o3 = _Order()
    d3 = Dealer(id=uuid.uuid4(), balance=D("10.00"), balance_usd=D("0"))
    db3 = _FakeDB([], d3)
    sina("boş özet", dealer_debt.uygula(db3, o3, reverse=True) == [])
    sina("bakiye dokunulmadı", d3.balance == D("10.00"))


def main():
    hesap_testleri()
    print()
    bakiye_testleri()
    print(f"\n{'=' * 46}\n  {_gecti} geçti, {_basarisiz} başarısız\n{'=' * 46}")
    sys.exit(1 if _basarisiz else 0)


if __name__ == "__main__":
    main()
