"""Bayi siparişinin etiketinde BAYİNİN adı yazmalı.

Paketi alan müşteri bayinin müşterisi; etikette BERNZ değil bayi görünmeli.
Ayrıca bayi mağazaları "Bayii: X" diye kayıtlı — o önek etikete basılmamalı.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Dealer, Order, Store, Tenant  # noqa: E402
from app.routers import packaging as pkg  # noqa: E402

GECTI = KALDI = 0
IZ = uuid.uuid4().hex[:6]


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


db = SessionLocal()
tenant = db.scalar(select(Tenant).order_by(Tenant.created_at).limit(1))

bayi_store = Store(tenant_id=tenant.id, slug=f"{IZ}-b", name=f"Bayii: KE-MARKET-{IZ}",
                   platform="bayii", is_active=True)
normal_store = Store(tenant_id=tenant.id, slug=f"{IZ}-n", name="BERNZ COMPANY",
                     platform="shopify", is_active=True)
db.add_all([bayi_store, normal_store]); db.flush()
dealer = Dealer(tenant_id=tenant.id, store_id=bayi_store.id, name=f"KE-MARKET-{IZ}",
                is_active=True)
db.add(dealer); db.flush()

o_bayi = Order(tenant_id=tenant.id, store_id=bayi_store.id,
               order_number=f"{IZ}-B", external_id=f"{IZ}-B", customer_name="T",
               current_stage=1, raw={"dealer_id": str(dealer.id)})
o_normal = Order(tenant_id=tenant.id, store_id=normal_store.id,
                 order_number=f"{IZ}-N", external_id=f"{IZ}-N", customer_name="T",
                 current_stage=1, raw={})
# Bayi kaydi SILINMIS ama magaza adi "Bayii: ..." kalmis hali
o_kopuk = Order(tenant_id=tenant.id, store_id=bayi_store.id,
                order_number=f"{IZ}-K", external_id=f"{IZ}-K", customer_name="T",
                current_stage=1, raw={})
db.add_all([o_bayi, o_normal, o_kopuk]); db.commit()

print("\n── 1. bayi siparişi → BAYİNİN adı ──")
es("bayi adı yazılıyor", f"KE-MARKET-{IZ}", pkg._etiket_magaza_adi(db, o_bayi))
es("'Bayii:' öneki YOK", False,
   (pkg._etiket_magaza_adi(db, o_bayi) or "").lower().startswith("bayii"))

print("\n── 2. normal sipariş → mağaza adı (değişmedi) ──")
es("mağaza adı", "BERNZ COMPANY", pkg._etiket_magaza_adi(db, o_normal))

print("\n── 3. bayi kaydı bulunamazsa önek yine temizlenir ──")
es("önek temizlendi", f"KE-MARKET-{IZ}", pkg._etiket_magaza_adi(db, o_kopuk))

print("\n── 4. mağazası olmayan sipariş çökmüyor (koddaki koruma) ──")


class _Bos:
    store_id = None
    raw = {}


es("None döner", None, pkg._etiket_magaza_adi(db, _Bos()))

print("\n── 5. etikette gerçekten basılıyor ──")
import re  # noqa: E402
import fitz  # noqa: E402
from app.services import label_pdf  # noqa: E402
pdf = label_pdf.render_label_pdf(o_bayi, pkg._etiket_magaza_adi(db, o_bayi),
                                 barkod_kodu="401059")
metin = re.sub(r"\s+", " ", fitz.open(stream=pdf, filetype="pdf")[0].get_text())
metin = metin.replace("\u00ad", "-").replace("\u2010", "-").replace("\u2011", "-")
es("etikette bayi adı var", True, f"KE-MARKET-{IZ}".upper() in metin.upper())
es("etikette 'BAYII' yok", False, "BAYII" in metin.upper())

for sql in ("delete from orders where tenant_id=:t and order_number like :p",
            "delete from dealers where store_id=:b",
            "delete from stores where id in (:b,:n)"):
    db.execute(text(sql), {"t": str(tenant.id), "p": f"{IZ}-%",
                           "b": str(bayi_store.id), "n": str(normal_store.id)})
db.commit()

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
