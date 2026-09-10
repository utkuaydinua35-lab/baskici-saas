"""BERNZ Special (PARLAK) stok listesi.

Special yalnız birkaç modelde stok bulunduruyor. Müşteriye kalıp motorunun
tanıdığı 300+ modelin tamamını sunmak, karşılanamayacak bir siparişe dönüşür;
bu yüzden model değişikliği bağlantısında PARLAK ürünler için YALNIZ buradaki
liste gösterilir.

`stokta=False` model listede GÖRÜNÜR ama seçilemez. Amaç bilinçli: müşteri
"bu model var, şu an stokta değil" ile "bu model hiç yok" arasındaki farkı
görsün. Stok gelince panelden işaretlenir, bağlantıdaki liste anında güncellenir.

Liste tenant başına tutulur ve ilk okumada aşağıdaki varsayılanla doldurulur —
böylece migration'ın hangi tenant'a yazacağını bilmesi gerekmez ve sonradan
açılan atölyeler de çalışır durumda başlar.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import OzelSeriStok

# (model, stokta) — sıra listede göründüğü sıradır.
# İşletmenin 2026-09-10'da verdiği başlangıç durumu; buradan sonrası panelden
# yönetilir, bu sabit yalnız İLK doldurma için kullanılır.
VARSAYILAN: list[tuple[str, bool]] = [
    ("iPhone 16 Pro Max", True),
    ("iPhone 16 Pro", True),
    ("iPhone 16", True),
    ("iPhone 15 Pro Max", True),
    ("iPhone 15 Pro", True),
    ("iPhone 15 Plus", True),
    ("iPhone 15", False),
    ("iPhone 14 Pro Max", False),
    ("iPhone 14 Pro", True),
    ("iPhone 14 Plus", True),
    ("iPhone 14", False),
    ("iPhone 13 Pro Max", True),
    ("iPhone 13 Pro", True),
    ("iPhone 13", False),
    ("iPhone 11", True),
    ("Samsung S25 Ultra", True),
    ("Samsung S24 FE", True),
    ("Samsung S24 Plus", True),
    ("Samsung S24", True),
    ("Samsung S23 Ultra", True),
    ("Samsung S23", True),
]


def liste(db: Session, tenant_id) -> list[OzelSeriStok]:
    """Tenant'ın Special stok listesi; boşsa varsayılanla doldurulur."""
    rows = db.scalars(
        select(OzelSeriStok).where(OzelSeriStok.tenant_id == tenant_id)
        .order_by(OzelSeriStok.sira)
    ).all()
    if rows:
        return list(rows)

    for i, (model, stokta) in enumerate(VARSAYILAN):
        db.add(OzelSeriStok(tenant_id=tenant_id, model=model, sira=i, stokta=stokta))
    db.commit()
    return list(db.scalars(
        select(OzelSeriStok).where(OzelSeriStok.tenant_id == tenant_id)
        .order_by(OzelSeriStok.sira)
    ).all())


def secenekler(db: Session, tenant_id) -> list[dict]:
    """Müşteri sayfası için: [{deger, etiket, stokta}] — sırası korunur."""
    return [{"deger": r.model, "etiket": r.model, "stokta": bool(r.stokta)}
            for r in liste(db, tenant_id)]


def stokta_mi(db: Session, tenant_id, model: str) -> bool:
    """Bu model Special'da seçilebilir mi? (listede VE stokta)"""
    m = (model or "").strip()
    if not m:
        return False
    r = db.scalar(select(OzelSeriStok).where(
        OzelSeriStok.tenant_id == tenant_id, OzelSeriStok.model == m))
    return bool(r and r.stokta)
