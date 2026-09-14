"""Geçmişte müşterinin yaptığı ÜRÜN değişikliklerini kaleme işle (tek seferlik).

Yeni sistemden ÖNCE ürün değişikliği yalnız bildirim/geçmiş notuydu; kalemde
iz yok ve kalem eski tasarımla yeniden kalıba girebilir (#11701). Bu betik
uygulanmış model-değişim taleplerinden ürün seçenleri bulur, seçilen ürünü
geçmiş notundan okur ve services/urun_degisikligi ile işler:
tasarım kesinse bağlanır, değilse kalem "tasarım bekliyor" olur.

Varsayılan KURU çalışır (hiçbir şey yazmaz). Yazmak için: --uygula
Yalnız henüz kalıba girmemiş / baskısı tamamlanmamış kalemler işlenir;
kargoya çıkmış sipariş atlanır.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import desc, select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import LineItem, ModelDegisimTalebi, Order, OrderStatusHistory, Store  # noqa: E402
from app.services import urun_degisikligi as uds, urun_katalog  # noqa: E402

UYGULA = "--uygula" in sys.argv
db = SessionLocal()
talepler = db.scalars(select(ModelDegisimTalebi).where(
    ModelDegisimTalebi.durum == "uygulandi", ModelDegisimTalebi.secilen_varyasyon.isnot(None),
    ModelDegisimTalebi.line_item_id.isnot(None)).order_by(ModelDegisimTalebi.uygulandi_at)).all()

islenen = set()
for t in reversed(talepler):            # kalem başına EN SON seçim geçerli
    if t.line_item_id in islenen:
        continue
    islenen.add(t.line_item_id)
    li = db.get(LineItem, t.line_item_id)
    o = db.get(Order, t.order_id)
    if li is None or o is None:
        continue
    if li.urun_degisikligi:
        print(f"#{o.order_number}: zaten işlenmiş ({li.urun_degisikligi.get('durum')})"); continue
    if (o.current_stage or 0) >= 8:
        print(f"#{o.order_number}: kargoya çıkmış — atlandı"); continue
    h = db.scalar(select(OrderStatusHistory).where(
        OrderStatusHistory.order_id == o.id, OrderStatusHistory.action == "musteri_model_degisikligi",
        OrderStatusHistory.note.like("%ürün:%→%")).order_by(desc(OrderStatusHistory.created_at)).limit(1))
    if h is None:
        print(f"#{o.order_number}: geçmişte ürün notu yok — atlandı"); continue
    secilen = h.note.split("ürün:", 1)[1].split("→", 1)[1].split(" · ")[0].strip()
    st = db.get(Store, o.store_id) if o.store_id else None
    urun = next((p for p in urun_katalog.ham_urunler(db, o.tenant_id, st)
                 if (p["baslik"] or "").strip() == secilen), None)
    if urun is None:
        print(f"#{o.order_number}: '{secilen}' katalogda bulunamadı — atlandı"); continue
    kayit = uds.kaydet(db, li, st, urun_id=str(urun["id"]), baslik=urun["baslik"],
                       gorsel=urun.get("gorsel"), kim="Müşteri (geriye dönük)")
    print(f"#{o.order_number} · {li.title[:50]} → {secilen} · {kayit['durum']}"
          + (f" · tasarım {kayit.get('tasarim_kodu')}" if kayit.get("tasarim_kodu") else f" · {kayit.get('sebep')}")
          + ("" if li.is_kaliba_eklendi is False else " · (kalıpta)"))
    if UYGULA:
        db.add(OrderStatusHistory(tenant_id=o.tenant_id, order_id=o.id, action="urun_degisikligi_karar",
                                  note=f"Geriye dönük işlendi: {secilen} · {kayit['durum']}",
                                  created_by="Sistem"))

if UYGULA:
    db.commit(); print("\nYAZILDI.")
else:
    db.rollback(); print("\nKURU ÇALIŞTIRMA — yazmak için --uygula")
