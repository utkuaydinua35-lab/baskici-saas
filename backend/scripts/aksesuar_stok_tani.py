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

        # Açık sipariş sayımı — Shopify'daki açık sipariş sayısıyla karşılaştır.
        # Tutmuyorsa ihtiyaç hesabı da tutmaz; hangi kuralın kaç sipariş elediği
        # burada görünür.
        from app.services.order_scope import acik_siparis_filtresi
        _acik = db.scalars(select(Order).where(acik_siparis_filtresi(tid))).all()
        _gevsek = db.scalars(select(Order).where(
            Order.tenant_id == tid, Order.is_iptal == False,  # noqa: E712
            Order.current_stage < 8)).all()
        print(f"\n── Açık sipariş ──")
        print(f"  Paketleme ölçütü (doğru) : {len(_acik)}")
        print(f"  Yalnız aşama < 8         : {len(_gevsek)}")
        _sebep: dict = {}
        for o in _gevsek:
            if o in _acik:
                continue
            if (o.fulfillment_status or "") == "fulfilled":
                k = "Shopify'da gönderilmiş (fulfilled)"
            elif o.closed_at is not None:
                k = "Shopify'da arşivlenmiş (closed)"
            elif o.cancelled_at is not None:
                k = "Shopify'da iptal"
            elif (o.financial_status or "") == "refunded":
                k = "iade edilmiş"
            else:
                k = "diğer"
            _sebep[k] = _sebep.get(k, 0) + 1
        for k, v in sorted(_sebep.items(), key=lambda x: -x[1]):
            print(f"    -{v:<5} {k}")

        eksikler = stock_svc.siparis_stok_eksigi(db, tid)
        print(f"\n── Hesaplanan stok eksiği: {len(eksikler)} satır ──")
        if not eksikler:
            print("  (eksik yok — ya stok yeterli ya da yukarıdaki bağlantılar kurulmamış)")
        for e in eksikler[:15]:
            _ek = ("  ⚠ alt kalem tanımsız" if e["not_in_system"] else "")
            print(f"  -{e['total_missing']:<4} {e['grup']} · {e['model']}"
                  f"  (ihtiyaç {e['ihtiyac']}, stok {e['mevcut']},"
                  f" {e['siparis_sayisi']} sipariş){_ek}")
        if len(eksikler) > 15:
            print(f"  … {len(eksikler) - 15} satır daha")

        # "Alt kalem tanımsız" iki sebepten olur: ya grupta hiç alt kalem yok,
        # ya da var ama model adı eşleşmiyor. Ayrımı gösterip KARARI da veriyoruz;
        # bu bölüm EN SONDA duruyor çünkü terminal kaydırınca sadece son ekran
        # okunabiliyor ve asıl cevap burada.
        from app.models import StockItem
        print("\n── Stok ana kalemlerinin alt kalemleri ──")
        toplam_alt = 0
        ornek_anahtar: list[str] = []
        for g in gruplar:
            alt = db.scalars(
                select(StockItem).where(StockItem.group_id == g.id,
                                        StockItem.is_active.is_(True))
            ).all()
            toplam_alt += len(alt)
            print(f"  {g.name}: {len(alt)} alt kalem")
            if not alt:
                print("    → hiç alt kalem yok; model bazlı stok girilmemiş.")
                continue
            for si in alt[:8]:
                _modeller = si.models if si.models else ([si.model] if si.model else [])
                _anahtarlar = [stock_svc._norm_model(m) for m in _modeller]
                ornek_anahtar.extend(_anahtarlar)
                print(f"    - {(si.name or '')[:30]:<32} adet={si.quantity:<5}"
                      f" model={_modeller} → anahtar{_anahtarlar}")
            if len(alt) > 8:
                print(f"    … {len(alt) - 8} alt kalem daha")

        aranan = {stock_svc._norm_model(e["model"]) for e in eksikler}
        kesisim = aranan & set(ornek_anahtar)
        print("\n" + "═" * 62)
        print("KARAR")
        if toplam_alt == 0:
            print("  Gruplarda HİÇ alt kalem yok → model bazlı stok girilmemiş.")
            print("  Yapılacak: Stok sayfasında ana kalemi aç, her model için alt")
            print("  kalem ekle. Eşleştirme kodu doğru çalışıyor, veri eksik.")
        elif not ornek_anahtar:
            print("  Alt kalemler var ama hiçbirinde model tanımlı değil.")
            print("  Yapılacak: alt kalemlere model adı gir.")
        elif kesisim:
            print(f"  Eşleşme çalışıyor ({len(kesisim)} anahtar tuttu). Kalan")
            print("  'alt kalem tanımsız' satırları gerçekten girilmemiş modeller.")
        else:
            print("  Alt kalemler VAR ama hiçbir anahtar tutmuyor → EŞLEŞTİRME HATASI.")
            print(f"  Aranan örnek : {sorted(aranan)[:4]}")
            print(f"  Stokta olan  : {sorted(set(ornek_anahtar))[:4]}")
            print("  Bu çıktıyı ilet — normalize eşleştirmesi düzeltilecek.")
        print("═" * 62)
    finally:
        db.close()


if __name__ == "__main__":
    main()
