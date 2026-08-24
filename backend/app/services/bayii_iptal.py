"""Bayi siparişi iptali — kural TEK kaynak.

Bayi siparişi hangi aşamada nasıl iptal edilir:

  A) Kalıba HİÇ girmemiş
     Bayi kendisi iptal eder. Borç yazıldıysa iade edilir.

  B) Kalıba girmiş, kalıp TAMAMLANMAMIŞ (aşama < 5)
     Bayi TALEP açar. Yönetici onaylayınca:
       • kalemin bulunduğu kalıp(lar) SİLİNİR — kalıp yeniden planlanmalı,
         eksik slotla basılmamalı
       • borç iade edilir
       • sipariş "iptal edildi" olur, paketlemede çıkmaz

  C) Kalıba girmiş, kalıp TAMAMLANMIŞ (aşama = 5)
     Kılıf basıldı, malzeme harcandı: bayi talep AÇAMAZ.
     Talep zaten açıkken kalıp tamamlanırsa (yarış durumu) onayda:
       • kalıp SİLİNMEZ (basılmış)
       • borç İADE EDİLMEZ
       • sipariş yine "iptal edildi" olur ve paketlemede çıkmaz

Bu ayrımın parası var; bu yüzden karar tek fonksiyonda (`durum_belirle`) ve
saf tutuluyor — testi veritabanısız yazılabilsin diye.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

# Kalıbın "tamamlandı" aşaması (molds.MOLD_STAGES)
KALIP_TAMAMLANDI = 5


@dataclass(frozen=True)
class Durum:
    """Bir siparişin iptal açısından durumu."""
    kaliba_girdi: bool
    basilmis_kalip_var: bool      # aşaması 5 olan kalıp var mı

    @property
    def talep_gerekir(self) -> bool:
        """Bayi kendi başına iptal edemez, yöneticiye talep açar."""
        return self.kaliba_girdi

    @property
    def talep_acilabilir(self) -> bool:
        """Basılmış kalıpta iptal talebi açılamaz."""
        return not self.basilmis_kalip_var

    @property
    def iade_edilir(self) -> bool:
        """Basılmış kalıp varsa malzeme harcandı — iade yok."""
        return not self.basilmis_kalip_var

    @property
    def kaliplar_silinir(self) -> bool:
        """Basılmamış kalıp eksik slotla kalmasın diye silinip yeniden planlanır."""
        return self.kaliba_girdi and not self.basilmis_kalip_var


def durum_belirle(kalip_asamalari: list[int]) -> Durum:
    """Siparişin kalemlerinin bulunduğu kalıpların aşamalarından durumu çıkar.

    Saf fonksiyon: veritabanı yok, testi kolay.
    """
    return Durum(
        kaliba_girdi=bool(kalip_asamalari),
        basilmis_kalip_var=any((a or 0) >= KALIP_TAMAMLANDI for a in kalip_asamalari),
    )


def _kaliplari_bul(db: Session, order) -> list:
    """Siparişin kalemlerini içeren kalıplar."""
    from app.models import LineItem, Mold, MoldItem

    kalem_idleri = [li.id for li in (order.line_items or [])]
    kosullar = [MoldItem.order_number == str(order.order_number)]
    if kalem_idleri:
        kosullar.append(MoldItem.line_item_id.in_(kalem_idleri))

    from sqlalchemy import or_
    mold_idleri = set(db.scalars(
        select(MoldItem.mold_id).where(
            MoldItem.tenant_id == order.tenant_id, or_(*kosullar))
    ).all())
    if not mold_idleri:
        return []
    return list(db.scalars(select(Mold).where(Mold.id.in_(mold_idleri))).all())


def durumu_oku(db: Session, order) -> tuple[Durum, list]:
    """Siparişin iptal durumu + ilgili kalıplar."""
    kaliplar = _kaliplari_bul(db, order)
    return durum_belirle([m.current_stage for m in kaliplar]), kaliplar


def uygula(db: Session, order, *, kim: str, sebep: str | None = None) -> dict:
    """İptali GERÇEKTEN uygula. Çağıran, iznin verilip verilmediğini
    (talep_acilabilir) önceden sınamış olmalı.

    Dönüş: yapılanların özeti — çağıran bunu bildirime/geçmişe yazar.
    """
    from datetime import UTC, datetime

    from app.models import LineItem, MoldItem, OrderStatusHistory
    from app.services import dealer_debt

    d, kaliplar = durumu_oku(db, order)

    silinen_kaliplar: list[str] = []
    if d.kaliplar_silinir:
        for m in kaliplar:
            silinen_kaliplar.append(m.kod)
            db.delete(m)      # MoldItem'lar cascade ile gider
    elif d.kaliba_girdi:
        # Basılmış kalıp duruyor; yalnız bu siparişin kalemlerini kalıptan
        # düşürmeyiz (basıldı, fiziksel olarak orada). Paketlemeden düşmesi
        # is_iptal ile olur.
        pass

    ozet = dealer_debt.uygula(db, order, reverse=True) if d.iade_edilir else []

    # Kalemler yeniden planlanmasın diye kalıp bayrağı sıfırlanır
    if d.kaliplar_silinir:
        for li in (order.line_items or []):
            li.is_kaliba_eklendi = False

    order.is_iptal = True
    order.bayii_iptal_talebi = False
    order.bayii_onay_bekliyor = False
    order.kalip_haric = True      # bir daha plana girmesin

    iade_metni = ", ".join(f"{x['delta']:.2f} {x['currency']}" for x in ozet) or "yok"
    parcalar = [f"borç iadesi: {iade_metni}"]
    if silinen_kaliplar:
        parcalar.append(f"silinen kalıp: {', '.join(silinen_kaliplar)}")
    if not d.iade_edilir and d.kaliba_girdi:
        parcalar.append("kalıp basılmış — iade yok")
    if sebep:
        parcalar.append(f"sebep: {sebep}")

    db.add(OrderStatusHistory(
        tenant_id=order.tenant_id, order_id=order.id,
        from_stage=order.current_stage, to_stage=order.current_stage,
        action="iptal_edildi", note=" · ".join(parcalar), created_by=kim,
    ))
    return {
        "iade_edildi": d.iade_edilir,
        "iade": [{"tutar": x["delta"], "para_birimi": x["currency"]} for x in ozet],
        "silinen_kaliplar": silinen_kaliplar,
        "kalip_basilmisti": d.basilmis_kalip_var,
    }
