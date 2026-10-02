"""'Panelde duran kalıp' tanımı — TEK kaynak.

Baskıcı Paneli ekranı kalıpları şu ölçütle süzüyor (frontend/BaskiciPaneliPage):
içinde kılıf OLAN ve aşaması taslak(1) ya da tamamlandı(5) OLMAYAN kalıplar.
"Toplam Eksik" ve "Gerekli Modeller" aynı listeyi anlatmalı; ölçüt kopyalanınca
ayrışıyordu:

  • Toplam Eksik yalnız `print_status == "basildi"` olanları eliyordu. Taslak
    kalıplar ve TAMAMLANMIŞ (stage 5) kalıplar listeye giriyor, aylar önce
    basılmış işler "eksik" diye sayılıyordu — ekranda görünmeyen kalıpların
    ihtiyacı listeyi şişiriyordu.
  • Paketleme ise stage 5'i zaten "basıldı" sayıyor (routers/packaging).

Buradaki iki fonksiyon bu üç yerin ortak dili.
"""
from __future__ import annotations

TASLAK = 1
TAMAMLANDI = 5


def panelde_mi(mold) -> bool:
    """Kalıp Baskıcı Paneli ekranında görünüyor mu (içi dolu + üretim aşamasında)."""
    if (getattr(mold, "kilif_sayisi", 0) or 0) <= 0:
        return False
    st = getattr(mold, "current_stage", None)
    return st is None or (TASLAK < st < TAMAMLANDI)


def basildi_mi(mold) -> bool:
    """Basılmış sayılır: baskıcı 'basıldı' işaretlemiş YA DA kalıp tamamlanmış."""
    return (getattr(mold, "print_status", None) == "basildi") \
        or (getattr(mold, "current_stage", None) == TAMAMLANDI)


def panelde_basilmamis(mold) -> bool:
    """Şu an panelde duran ve HENÜZ BASILMAMIŞ kalıp — stok ihtiyacını bunlar doğurur."""
    return panelde_mi(mold) and not basildi_mi(mold)
