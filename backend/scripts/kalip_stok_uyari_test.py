"""Kalıp planı, BOŞ KILIF STOĞU yetmiyorsa uyarıyor mu?

⚠ NEDEN: stok eksikliği bugüne kadar ancak baskı anında ya da fiziksel olarak
fark ediliyordu — kalem kalıptan çıkarılıyor, müşteriye "ürününüz yok" mesajı
gidiyor, sipariş bekliyor. Canlıda ayda ~113 kalem kalıptan çıkarılıyor,
ağustosta 38'i stok yüzündendi.

Stok verisi ZATEN vardı (255 kalem; baskıda deduct_for_mold ile düşülüyor);
planlayıcı ona hiç bakmıyordu. Artık plan üretilirken bakılıyor.

⚠ UYARIDIR, ENGEL DEĞİL — sayım güncel olmayabilir, operatör "elimde var"
diyip basabilmeli. Bu test de bunu doğruluyor: uyarı çıksa bile plan üretilir.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Order, StockItem  # noqa: E402
from app.services import mold_planner, stock as stok  # noqa: E402

GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


db = SessionLocal()
tid = db.scalar(select(Order.tenant_id).limit(1))

print("\n── plan stok alanlarını döndürüyor ──")
p = mold_planner.plan_molds(db, tenant_id=tid)
es("stok_uyarilar var", True, isinstance(p.get("stok_uyarilar"), list))
es("stok_eksik_toplam var", True, isinstance(p.get("stok_eksik_toplam"), int))
print(f"  · plan: {p['mold_count']} kalıp / {p['total_units']} kılıf")

_birimler = [m for mo in (p.get("molds") or []) for m in (mo.get("items") or [])]
if not _birimler:
    print("\nPlanda kılıf yok — uçtan uca atlandı.")
else:
    _ilk = _birimler[0]
    _model, _var = _ilk.get("model"), _ilk.get("variation")
    print(f"\n── denek: {_var} {_model} ──")
    _si = stok._find_bos_kilif(db, tid, _var, _model)
    # "Stok kaydı YOK" ile "stok BİTMİŞ" farklı şeyler: tanımsız modelde uyarı
    # vermiyoruz, yanlış alarm gerçek alarmı değersizleştirir.
    es("stok kaydı olmayan model uyarı ÜRETMEZ", True,
       _si is not None or all(u["model"] != _model or u["variation"] != _var
                              for u in p["stok_uyarilar"]))

    _gecici = False
    if _si is None:
        # Sınamayı yapabilmek için GEÇİCİ kayıt aç, sonunda sil.
        _si = StockItem(tenant_id=tid, sku=f"TEST-STOK-{_model}-{_var}"[:100],
                        name=f"TEST {_var} {_model}", category="bos_kilif",
                        variation=_var, model=_model, quantity=0, is_active=True)
        db.add(_si); db.flush()
        _gecici = True
        print("  · geçici stok kaydı açıldı (test sonunda silinir)")

    if True:
        _eski = _si.quantity
        try:
            # 1) Bol stok → uyarı YOK
            _si.quantity = 9999
            db.flush()
            _p1 = mold_planner.plan_molds(db, tenant_id=tid)
            es("stok bolken uyarı YOK", True,
               all(not (u["model"] == _model and u["variation"] == _var)
                   for u in _p1["stok_uyarilar"]))

            # 2) Stok SIFIR → uyarı VAR
            _si.quantity = 0
            db.flush()
            _p2 = mold_planner.plan_molds(db, tenant_id=tid)
            _u = next((u for u in _p2["stok_uyarilar"]
                       if u["model"] == _model and u["variation"] == _var), None)
            es("stok bitince uyarı ÇIKIYOR", True, _u is not None)
            if _u:
                es("mevcut 0 yazıyor", 0, _u["mevcut"])
                es("gerekli adet > 0", True, _u["gerekli"] > 0)
                es("eksik = gerekli - mevcut", _u["gerekli"] - _u["mevcut"], _u["eksik"])
                es("hangi siparişler olduğu yazıyor", True, len(_u["siparisler"]) > 0)
                es("toplam eksik sayacı tutuyor",
                   sum(x["eksik"] for x in _p2["stok_uyarilar"]), _p2["stok_eksik_toplam"])

            # ⚠ EN ÖNEMLİSİ: uyarı planı ENGELLEMEZ.
            es("uyarıya rağmen plan ÜRETİLİYOR", True, _p2["mold_count"] > 0)
            es("kılıf sayısı değişmedi", _p1["total_units"], _p2["total_units"])

            # 3) Kısmi stok → eksik doğru hesaplanıyor
            if _u and _u["gerekli"] > 1:
                _si.quantity = _u["gerekli"] - 1
                db.flush()
                _p3 = mold_planner.plan_molds(db, tenant_id=tid)
                _u3 = next((x for x in _p3["stok_uyarilar"]
                            if x["model"] == _model and x["variation"] == _var), None)
                es("kısmi stokta eksik 1", 1, _u3["eksik"] if _u3 else None)
        finally:
            if _gecici:
                db.delete(_si)
                print("  · geçici stok kaydı silindi")
            else:
                _si.quantity = _eski
                print("  · stok eski değerine döndürüldü")
            db.commit()

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
