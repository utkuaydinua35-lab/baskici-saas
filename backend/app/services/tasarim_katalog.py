"""Katalogda hangi tasarım GÖRÜNÜR — tek kaynak.

Silinen (çöp kutusundaki) siparişin tasarımı katalogda durmamalı: bayi aynı
işi tekrar seçebiliyor, liste de zamanla ölü kayıtlarla şişiyor.

Kural, silme anında bir bayrak yazmak yerine SORGU anında hesaplanıyor. Bunun
iki nedeni var:

  1) Silme birden çok yerden oluyor (yönetim paneli, bayi paneli, toplu
     işlem, telafi akışı). Her birine "tasarımı da gizle" satırı eklemek,
     birini atlayınca sessizce yanlış davranan bir sistem demekti.
  2) Silme GERİ ALINABİLİR (çöp kutusu). Sipariş geri gelince tasarımın da
     kataloğa dönmesi gerekiyor; hesaplanan kural bunu bedavaya veriyor.

Gizlenme koşulu DAR tutuldu — yanlış gizlemek, bayinin tasarımını kaybetmesi
demek: tasarımın EN AZ BİR siparişi olacak ve BU SİPARİŞLERİN HEPSİ silinmiş
olacak. Hiç siparişi olmayan tasarım (elle yüklenmiş katalog görseli) SAKLI
KALIR. İptal edilmiş sipariş de gizlemez: iptal silme değildir, bayi aynı
tasarımla tekrar sipariş verebilmeli.
"""
from __future__ import annotations

from sqlalchemy import or_, select

from app.models import Design, LineItem, Order

# Bir kalem İKİ tasarım taşıyabilir (couple / kişiye özel: 2. kılıfın
# tasarımı ayrı sütunda). Yalnız birinciye bakmak, ikinci sütunda hâlâ
# kullanılan bir tasarımı "kimse kullanmıyor" saymak demekti.
def _kullanan(*ekstra):
    return select(LineItem.id).where(
        or_(LineItem.assigned_design_id == Design.id,
            LineItem.assigned_design_id_2 == Design.id), *ekstra)


def gorunur_kosulu():
    """Design sorgusuna eklenecek WHERE koşulu.

    Kullanım:  select(Design).where(..., tasarim_katalog.gorunur_kosulu())
    """
    # NOT: Order'a global soft-delete süzgeci var ama burada koşul AÇIKÇA
    # yazılıyor — bu ifade ham SQL'e de, include_deleted=True ile çalışan bir
    # sorguya da girebilir; doğruluğu çağıranın ayarına bırakmıyoruz.
    kalemi_var = _kullanan().exists()
    canli_kalemi_var = (
        _kullanan(Order.deleted_at.is_(None))
        .join(Order, Order.id == LineItem.order_id)
        .exists()
    )
    return or_(~kalemi_var, canli_kalemi_var)
