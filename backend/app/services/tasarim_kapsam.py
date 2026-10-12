"""Bir mağazanın GÖREBİLECEĞİ tasarımlar — TEK kaynak.

Aynı işletmenin iki kanalı olabiliyor: eski Shopify mağazası ve kendi vitrini
(BERNZ Commerce). Tasarımlar mağazaya bağlı olduğu için vitrin tarafında
"bu mağazada o kodlu tasarım yok" çıkıyordu; oysa ikisi aynı atölyenin aynı
tasarım havuzu.

KURAL: `stores.tasarim_grubu` aynı ve BOŞ DEĞİLSE mağazalar birbirinin
tasarımlarını görür. Varsayılan boş — bayi mağazalarının kendi katalogları
(bayi önekli kodlar) ana mağazaya karışmasın diye paylaşım OPT-IN.

⚠ NEREDE KULLANILIR: tasarım LİSTELEME ve SEÇME yollarında (panelde tasarım
seç, koda göre ata, kalıba tasarım bağla…). `product_id` üzerinden OTOMATİK
eşleşmede KULLANILMAZ: iki kanalın ürün kimlikleri ayrı uzaylarda ve tahminle
tasarım bağlamak yanlış kılıf bastırır (bkz. services/urun_degisikligi).
"""
from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Design, Store


def paylasilan_idler(db: Session, store_id) -> list[uuid.UUID]:
    """store_id'nin tasarımlarını paylaştığı mağazalar — KENDİSİ DAHİL."""
    if store_id is None:
        return []
    sid = store_id if isinstance(store_id, uuid.UUID) else uuid.UUID(str(store_id))
    st = db.get(Store, sid)
    if st is None:
        return [sid]
    grup = (st.tasarim_grubu or "").strip()
    if not grup:
        return [sid]
    idler = list(db.scalars(select(Store.id).where(
        Store.tenant_id == st.tenant_id, Store.tasarim_grubu == grup)).all())
    return idler or [sid]


def kosul(db: Session, store_id):
    """Sorguya eklenecek koşul: Design.store_id IN (paylaşılanlar)."""
    idler = paylasilan_idler(db, store_id)
    if len(idler) == 1:
        return Design.store_id == idler[0]
    return Design.store_id.in_(idler)


def paylasimli_mi(db: Session, store_id) -> bool:
    return len(paylasilan_idler(db, store_id)) > 1


def grup_magazalari(db: Session, tenant_id, grup: str | None) -> list[Store]:
    """Bir gruptaki mağazalar (ekranda 'kimlerle paylaşıyor' yazmak için)."""
    g = (grup or "").strip()
    if not g:
        return []
    return list(db.scalars(select(Store).where(
        Store.tenant_id == tenant_id, Store.tasarim_grubu == g).order_by(Store.name)).all())
