"""'Takip numarası bekleyen gönderiler' listesi neden boş — sipariş sipariş göster.

Son N siparişi alır, bekleyenler filtresinin her kuralını tek tek uygular ve
hangi kuralda elendiğini yazar. Böylece listenin boş olmasının sebebi
tahminle değil veriyle görülür.

Kullanım (VPS, baskici kullanıcısı):
    cd ~/baskici-saas/backend && .venv/bin/python scripts/takip_bekleyen_tani.py [adet]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import desc, func, select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Dealer, Order, OrderShipment  # noqa: E402


def main() -> None:
    adet = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    db = SessionLocal()
    try:
        siparisler = db.scalars(
            select(Order).order_by(desc(Order.created_at)).limit(adet)
        ).all()
        if not siparisler:
            print("Hiç sipariş yok.")
            return
        tid = siparisler[0].tenant_id

        muaf = {
            str(_id) for (_id,) in db.execute(
                select(Dealer.id).where(Dealer.tenant_id == tid,
                                        func.coalesce(Dealer.shipping_fee, 0) == 0)
            ).all()
        }
        gonderiler: dict = {}
        for sh in db.scalars(
            select(OrderShipment).where(OrderShipment.tenant_id == tid)
        ).all():
            gonderiler.setdefault(sh.order_id, []).append(sh)

        print(f"Son {len(siparisler)} sipariş inceleniyor "
              f"(kargo ücreti 0 olan bayii sayısı: {len(muaf)}, "
              f"toplam gönderi kaydı: {sum(len(v) for v in gonderiler.values())})\n")

        sayac: dict = {}
        for o in siparisler:
            shs = gonderiler.get(o.id, [])
            ki = o.kargo_info or {}
            raw = o.raw or {}
            did = str(raw.get("dealer_id") or "") or None

            if o.is_iptal:
                sebep = "iptal"
            elif not ((o.current_stage or 0) >= 8 or shs):
                sebep = f"kargoya verilmemiş (aşama={o.current_stage})"
            elif ki.get("takip_no"):
                sebep = f"takip no VAR (kargo_info: {ki.get('takip_no')})"
            elif any((s.takip_no or "").strip() for s in shs):
                sebep = "takip no VAR (gönderi kaydında)"
            elif did and did in muaf:
                sebep = "kargo ücreti alınmayan bayii"
            else:
                sebep = "★ BEKLEYEN (listede görünmeli)"

            sayac[sebep.split(" (")[0]] = sayac.get(sebep.split(" (")[0], 0) + 1
            print(f"  #{str(o.order_number):>8}  aşama={str(o.current_stage):>2}  "
                  f"gönderi={len(shs)}  bayii={'E' if did else 'H'}  -> {sebep}")

        print("\n── Özet ──")
        for k, v in sorted(sayac.items(), key=lambda x: -x[1]):
            print(f"  {v:>4}  {k}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
