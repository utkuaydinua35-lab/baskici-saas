"""Ciro tutarı — PARA BİRİMİNE DUYARLI tek kaynak.

⚠ NEDEN VAR: dashboard ve analitik ciroyu `raw.total_price` toplayarak
hesaplıyordu. Oysa bayi siparişlerinde tutar BAYİNİN PARA BİRİMİNDE tutuluyor:
KE-MARKET ve Alysa Case USD bayisi (kılıf başı 2,50 / 1,91 $). Son 3 ayda 79
USD siparişin 250 doları panele 250 TL olarak ekleniyordu. Ayrıca bayi
siparişinin kargosu (`shipping_fee`, HER ZAMAN TL) toplama hiç girmiyordu;
Shopify siparişlerinde kargo zaten `total_price`'ın içinde.

Kur çevirisi YAPILMAZ: sistemde kur kaynağı yok ve uydurma bir kur, yanlış
toplamdan daha tehlikeli. TL ve USD AYRI toplanır, panel ikisini yan yana
gösterir (bayi cari hesabıyla aynı ilke — bkz. services/dealer_debt).
"""
from __future__ import annotations

from sqlalchemy import Numeric, case, cast, func

from app.models import Order


def _sayi(anahtar: str):
    """raw içindeki sayısal alan; boş/yoksa 0."""
    return func.coalesce(cast(func.nullif(Order.raw[anahtar].astext, ""), Numeric), 0)


def _para_birimi():
    return func.upper(func.coalesce(Order.raw["currency"].astext, "TRY"))


def tl_tutar():
    """Siparişin TL cinsinden tutarı (SQL ifadesi).

    TRY (ya da para birimi yazılmamış) siparişin toplamı + bayi siparişinin
    kargosu. USD siparişin ÜRÜN bedeli buraya girmez; kargosu TL olduğu için girer.
    """
    urun = case((_para_birimi() == "USD", 0), else_=_sayi("total_price"))
    kargo = case((Order.raw["source"].astext == "bayii", _sayi("shipping_fee")), else_=0)
    return urun + kargo


def usd_tutar():
    """Siparişin USD cinsinden ürün tutarı (SQL ifadesi); USD değilse 0."""
    return case((_para_birimi() == "USD", _sayi("total_price")), else_=0)


def tl_siparis_mi():
    """AOV gibi oranlarda paydaya yalnız TL siparişleri almak için."""
    return _para_birimi() != "USD"
