"""Ücretsiz kargo eşiği + yerel sipariş takibi.

BULGU 1 (canlı, 2026-10): 3 al 2 öde ile 1050 TL'lik sepet 700 TL'ye indi;
ücretsiz kargo eşiği 950 TL olduğu hâlde kargo bedava gitti — eşik İNDİRİMSİZ
toplama bakıyordu. Doğrusu (Shopify da böyle): indirimli ürün toplamı.

BULGU 2 (canlı, 2026-10): Shopify kapanınca "Siparişim nerede" (siparistakip)
yeni vitrin siparişlerini bulamıyordu — sorgu Shopify API'sine gidiyordu.
Artık yerel veritabanından; eski Shopify siparişleri de aynı tabloda.
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Order, Store  # noqa: E402
from app.services import checkout as co  # noqa: E402
from app.services import tracker as tk  # noqa: E402

GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


class _Kod:
    def __init__(self, kind="bxgy"):
        self.kind, self.code, self.is_automatic, self.promo_message = kind, "OTO", True, None


class _Magaza:
    config = {"shipping_fee": "89.90", "free_shipping_over": "950"}


print("— kargo eşiği")
m = _Magaza()
uc_al_iki = co.DiscountPlan([(_Kod(), Decimal("350"), False)])
es("1050 → 700 (3 al 2 öde): kargo ÜCRETLİ", Decimal("89.90"),
   co.kargo_ucreti(m, Decimal("1050"), uc_al_iki))
es("1500 → 1000: eşik geçildi, kargo bedava", Decimal("0"),
   co.kargo_ucreti(m, Decimal("1500"), co.DiscountPlan([(_Kod(), Decimal("500"), False)])))
es("indirimsiz 960: bedava", Decimal("0"), co.kargo_ucreti(m, Decimal("960"), co.DiscountPlan([])))
es("indirimsiz 949.99: ücretli", Decimal("89.90"),
   co.kargo_ucreti(m, Decimal("949.99"), co.DiscountPlan([])))
es("kargo kuponu: eşik altında da bedava", Decimal("0"),
   co.kargo_ucreti(m, Decimal("300"), co.DiscountPlan([(_Kod("free_shipping"), Decimal("0"), True)])))

print("— yerel sipariş takibi")
db = SessionLocal()
store = db.scalar(select(Store).where(Store.platform == "storefront"))
if not store:
    print("  · vitrin mağazası yok — takip kısmı atlandı")
else:
    iz = uuid.uuid4().hex[:6]
    no = f"9{uuid.uuid4().int % 10**7}"
    o = Order(tenant_id=store.tenant_id, store_id=store.id, external_id=f"sf_test_{iz}",
              order_number=no, name=f"#{no}", customer_email=f"Takip{iz}@Ornek.com",
              created_at_platform=datetime.now(timezone.utc), current_stage=8,
              kargo_info={"takip_no": "TK123", "takip_url": "https://k.example/TK123",
                          "handler_name": "Sürat"}, raw={})
    db.add(o); db.commit()
    try:
        bulunan = tk.fetch_order_for_tracking(db, store, f"#{no}", f"takip{iz}@ornek.com")
        es("numara (#'li) + e-posta (büyük/küçük harf) ile bulundu", True, bulunan is not None)
        es("yanlış e-posta → bulunamaz", None,
           tk.fetch_order_for_tracking(db, store, no, "baska@ornek.com"))
        es("yanlış numara → bulunamaz", None,
           tk.fetch_order_for_tracking(db, store, "1", f"takip{iz}@ornek.com"))
        yanit = tk.build_track_response(db, bulunan)
        es("aşama: kargoya verildi (panel aşaması 8)", "kargoya_verildi", yanit["active_stage"]["id"])
        es("takip no yanıtta", ["TK123"], yanit["order"]["tracking_numbers"])
        es("kargo firması", "Sürat", yanit["order"]["carrier"])
        o.current_stage = 9; db.commit()
        es("aşama 9 → teslim edildi", "teslim_edildi",
           tk.build_track_response(db, tk.fetch_order_for_tracking(
               db, store, no, f"takip{iz}@ornek.com"))["active_stage"]["id"])
        o.is_iptal = True; db.commit()
        es("iptal → iptal işaretli", True,
           tk.build_track_response(db, tk.fetch_order_for_tracking(
               db, store, no, f"takip{iz}@ornek.com"))["is_cancelled"])
    finally:
        db.delete(o); db.commit()
db.close()

print(f"\n{GECTI} GECTI, {KALDI} KALDI")
sys.exit(1 if KALDI else 0)
