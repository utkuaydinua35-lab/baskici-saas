"""Aksesuar / işleme girmeyen ürünlerin stok eksiği — neden listelendi/listelenmedi.

"Toplam Eksik" ve "Gerekli Modeller" listelerine bu ürünlerin girebilmesi için
İKİ şart var:
  1) ürün Aksesuar olarak işaretli olmalı,
  2) ürün bir Stok Ana Kalemi'ne (StockGroup.linked_products) bağlı olmalı.

İkincisi eksikse ürünün stoğu bilinmiyor demektir; "eksik" denemez ve liste boş
çıkar. Bu betik hangi şartın tutmadığını ürün ürün gösterir.

Kullanım (VPS, baskici kullanıcısı):
    cd ~/baskici-saas/backend && .venv/bin/python scripts/aksesuar_stok_tani.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import AccessoryProduct, Order, StockGroup  # noqa: E402
from app.services import stock as stock_svc  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        tid = db.scalar(select(Order.tenant_id).limit(1))
        if not tid:
            print("Hiç sipariş yok.")
            return

        aksesuarlar = db.scalars(
            select(AccessoryProduct).where(AccessoryProduct.tenant_id == tid)
        ).all()
        print(f"Aksesuar olarak işaretli ürün: {len(aksesuarlar)}")
        if not aksesuarlar:
            print("  → Hiç aksesuar işaretli değil. Ayarlar > Aksesuarlar'dan işaretle.")
            return

        gruplar = db.scalars(
            select(StockGroup).where(StockGroup.tenant_id == tid,
                                     StockGroup.is_active.is_(True))
        ).all()
        pid_to_group = {}
        for g in gruplar:
            for lp in (g.linked_products or []):
                pid = str(lp.get("product_id")) if isinstance(lp, dict) else None
                if pid:
                    pid_to_group[pid] = g.name
        print(f"Stok ana kalemi: {len(gruplar)} · bunlara bağlı ürün: {len(pid_to_group)}\n")

        print("── Aksesuar ürünler ──")
        bagsiz = 0
        for a in aksesuarlar:
            grup = pid_to_group.get(str(a.product_id))
            if grup:
                print(f"  ✓ {(a.product_title or a.product_id)[:48]:<50} → {grup}")
            else:
                bagsiz += 1
                print(f"  ✗ {(a.product_title or a.product_id)[:48]:<50} → STOK GRUBUNA BAĞLI DEĞİL")
        if bagsiz:
            print(f"\n  {bagsiz} ürünün stoğu takip edilmiyor — bunlar eksik listesine GİREMEZ.")
            print("  Stok sayfasında ana kalemi aç, 'Bağlı ürünler'e bu ürünü ekle.")

        eksikler = stock_svc.siparis_stok_eksigi(db, tid)
        print(f"\n── Hesaplanan stok eksiği: {len(eksikler)} satır ──")
        if not eksikler:
            print("  (eksik yok — ya stok yeterli ya da yukarıdaki bağlantılar kurulmamış)")
        for e in eksikler:
            _ek = "  ⚠ alt kalem tanımsız" if e["not_in_system"] else ""
            print(f"  -{e['total_missing']:<4} {e['grup']} · {e['model']}"
                  f"  (ihtiyaç {e['ihtiyac']}, stok {e['mevcut']},"
                  f" {e['siparis_sayisi']} sipariş){_ek}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
