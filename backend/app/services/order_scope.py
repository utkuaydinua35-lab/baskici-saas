"""'Açık sipariş' tanımı — TEK kaynak.

Bu ölçüt paketleme kuyruğunda yıllardır kullanılıyordu ama kopyası çıkarılmadan
başka yerlerde yeniden yazılınca ayrışıyordu. Örneğin aksesuar stok ihtiyacı
yalnızca `is_iptal` ve `current_stage < 8` bakıyordu; Shopify'da FULFILL edilmiş,
arşivlenmiş ya da iade edilmiş siparişler hâlâ "açık" sayılıp ihtiyaç listesini
kat kat şişiriyordu (78 açık siparişte 71 aksesuar gibi imkânsız bir oran).

Açık sipariş sayılmama sebepleri:
  is_iptal              — panelde iptal edildi
  fulfillment_status    — Shopify'da gönderildi
  cancelled_at          — Shopify'da iptal edildi
  closed_at             — Shopify'da arşivlendi (= tamamlandı)
  financial_status      — iade edildi
  current_stage >= 8    — kargoya verildi / teslim edildi
"""
from __future__ import annotations

from sqlalchemy import or_

from app.models import Order


def acik_siparis_filtresi(tenant_id):
    """Açık (gönderilmemiş, iptal olmayan, tamamlanmamış) siparişler için WHERE.

    current_stage NULL olan siparişler AÇIK sayılır — aşaması hiç işlenmemiş
    yeni kayıtlar kuyruktan düşmemeli.
    """
    return (
        (Order.tenant_id == tenant_id)
        & (Order.is_iptal == False)  # noqa: E712
        & (or_(Order.fulfillment_status.is_(None), Order.fulfillment_status != "fulfilled"))
        & (Order.cancelled_at.is_(None))
        & (Order.closed_at.is_(None))   # Shopify'da arşivlenmiş = tamamlanmış
        & (or_(Order.financial_status.is_(None), Order.financial_status != "refunded"))
        # Kargoya verilmiş/teslim (8 Kargoda, 9 Teslim) = tamamlanmış
        & (or_(Order.current_stage.is_(None), Order.current_stage < 8))
    )
