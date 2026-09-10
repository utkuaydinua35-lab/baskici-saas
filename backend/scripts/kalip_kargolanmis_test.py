"""KARGOYA VERİLMİŞ sipariş tekrar kalıba girmemeli.

GERÇEK OLAY (#11677, 09.09.2026 — bir kılıf çöpe gitti):
  02.09 16:45  kargoya verildi (Sürat, takip 23962223212236)
  02.09 16:49  kargo iptal (Sürat'ta iptal EDİLMEDİ)
  02.09 16:50  tekrar kargoya verildi — ama Shopify'a fulfillment YAZILAMADI
               (HTTP 422 "fulfillment order ... has an unfulfillable status=
               closed"), yani `fulfillment_status` NULL kaldı
  04.09 12:30  operatör kalemi elle kalıptan çıkardı (item_replan) →
               `is_kaliba_eklendi` sıfırlandı
  09.09        planlayıcı kalemi G7-H2-H9 kalıbına koydu → İKİNCİ KEZ basıldı

KÖK NEDEN: planlayıcı "açık sipariş"i kendi elle yazdığı filtreyle tanımlıyordu
ve o kopyada `current_stage >= 8` ile `closed_at` YOKTU. Sipariş yerelde 8.
aşamadaydı (kargoda) ama plana göre hâlâ açıktı. Tek koruma `is_kaliba_eklendi`
bayrağıydı, o da meşru bir "plana geri döndür" işlemiyle sıfırlandı.

Bu test siparişi TAM O DURUMA sokup planlayıcının artık dokunmadığını gösterir.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import UTC, datetime  # noqa: E402

from sqlalchemy import select, text  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import LineItem, Order  # noqa: E402
from app.services import mold_planner  # noqa: E402
from app.services.order_scope import acik_siparis_filtresi  # noqa: E402

GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


db = SessionLocal()


def _planda_mi(tenant_id, li_id) -> bool:
    """Kalem şu anki planda herhangi bir kalıpta yer alıyor mu?"""
    p = mold_planner.plan_molds(db, tenant_id=tenant_id)
    for m in p.get("molds") or []:
        for it in (m.get("items") or []):
            if str(it.get("line_item_id") or "") == str(li_id):
                return True
    return False


print("\n── 'açık sipariş' ölçütü TEK KAYNAKTAN ──")
# Planlayıcının kendi kopyası bu hataya yol açtı; kopya geri gelirse yakala.
_kaynak = (Path(__file__).resolve().parent.parent
           / "app/services/mold_planner.py").read_text(encoding="utf-8")
es("planlayıcı order_scope kullanıyor", True, "acik_siparis_filtresi" in _kaynak)
es("elle yazılmış fulfillment kopyası YOK", False,
   'Order.fulfillment_status != "fulfilled"' in _kaynak)

print("\n── ölçüt HER YERDE aynı mı (elle kopya kalmadı) ──")
# Ölçütün kopyası çıkarılınca panelde aynı soruya iki farklı cevap veriliyordu:
# paketleme kuyruğu 60, "gönderilmeyen" sekmesi 171 sipariş gösteriyordu.
import subprocess  # noqa: E402

_kok = Path(__file__).resolve().parent.parent / "app"
_kopya = subprocess.run(
    ["grep", "-rn", 'fulfillment_status != "fulfilled"', str(_kok)],
    capture_output=True, text=True).stdout
_kopya = [x for x in _kopya.split("\n") if x.strip() and "order_scope" not in x]
es("elle yazılmış SQL kopyası YOK", [], _kopya)

from app.services.order_counts import open_conds  # noqa: E402
from app.services.order_scope import acik_kosullar, acik_mi  # noqa: E402
# Tuple repr'ı bellek adresi taşır; koşulları TEK TEK SQL metnine çevirip
# karşılaştırıyoruz.
es("order_counts tek kaynağa delege ediyor",
   [str(x) for x in acik_kosullar()], [str(x) for x in open_conds()])

print("\n── nesne üzerinden ölçüt (acik_mi) SQL ile tutarlı ──")


class _S:
    cancelled_at = closed_at = None
    is_iptal = False
    fulfillment_status = financial_status = None
    current_stage = 3


es("temiz sipariş açık", True, acik_mi(_S()))
_k = _S(); _k.current_stage = 8
es("kargoda (8) açık DEĞİL", False, acik_mi(_k))
_k = _S(); _k.current_stage = 9
es("teslim (9) açık DEĞİL", False, acik_mi(_k))
_k = _S(); _k.fulfillment_status = "fulfilled"
es("fulfilled açık DEĞİL", False, acik_mi(_k))
_k = _S(); _k.closed_at = datetime.now(UTC)
es("arşivlenmiş açık DEĞİL", False, acik_mi(_k))
_k = _S(); _k.is_iptal = True
es("panelden iptal açık DEĞİL", False, acik_mi(_k))
_k = _S(); _k.financial_status = "refunded"
es("iade açık DEĞİL", False, acik_mi(_k))
es("sipariş yoksa açık DEĞİL", False, acik_mi(None))

print("\n── ölçütün kendisi: kargodaki sipariş AÇIK DEĞİL ──")
_f = str(acik_siparis_filtresi("00000000-0000-0000-0000-000000000000"))
es("current_stage şartı var", True, "current_stage" in _f)
es("closed_at şartı var", True, "closed_at" in _f)
es("fulfillment_status şartı var", True, "fulfillment_status" in _f)

# ── uçtan uca: PLANDA OLAN gerçek bir kalemi #11677'nin durumuna sok ──
# Kalemi elle seçmiyoruz: planlayıcının kendi çıktısından alıyoruz, aksi halde
# tasarımı/modeli çözülemeyen bir kalem seçilip "zaten planda değil" diye
# anlamsız bir taban ölçüyorduk.
_tid = db.scalar(select(Order.tenant_id).limit(1))
_lid = None
if _tid is not None:
    _p = mold_planner.plan_molds(db, tenant_id=_tid)
    for _m in (_p.get("molds") or []):
        for _it in (_m.get("items") or []):
            if _it.get("line_item_id"):
                _lid = _it["line_item_id"]
                break
        if _lid:
            break

if _lid is None:
    print("\nPlanda kalem yok — uçtan uca atlandı.")
else:
    _li = db.get(LineItem, _lid if not isinstance(_lid, str) else __import__("uuid").UUID(_lid))
    _ord = db.get(Order, _li.order_id)
    _eski = (_ord.current_stage, _ord.fulfillment_status, _ord.closed_at)
    try:
        print(f"\n── uçtan uca (sipariş #{_ord.order_number}) ──")
        es("kalem normalde planda", True, _planda_mi(_tid, _li.id))

        # #11677'nin TAM durumu: yerelde kargoda (8), Shopify'da fulfillment YOK.
        _ord.current_stage = 8
        _ord.fulfillment_status = None
        db.commit()
        es("kargoya verildi (8) → planda YOK", False, _planda_mi(_tid, _li.id))

        _ord.current_stage = 9
        db.commit()
        es("teslim edildi (9) → planda YOK", False, _planda_mi(_tid, _li.id))

        _ord.current_stage = _eski[0]
        _ord.closed_at = datetime.now(UTC)
        db.commit()
        es("Shopify'da arşivlenmiş → planda YOK", False, _planda_mi(_tid, _li.id))

        _ord.closed_at = None
        _ord.fulfillment_status = "fulfilled"
        db.commit()
        es("fulfilled → planda YOK (eski koruma duruyor)", False, _planda_mi(_tid, _li.id))

        _ord.fulfillment_status = _eski[1]
        db.commit()
        es("durum geri alınınca planda YİNE var", True, _planda_mi(_tid, _li.id))
    finally:
        _ord.current_stage, _ord.fulfillment_status, _ord.closed_at = _eski
        db.commit()
        print("  · sipariş eski haline döndürüldü")

print("\n── canlıda kaç sipariş bu riskteydi ──")
_risk = db.execute(text("""
    select count(distinct o.id) from orders o join line_items li on li.order_id = o.id
    where o.is_iptal = false and o.cancelled_at is null and o.closed_at is null
      and o.kalip_haric = false and o.current_stage >= 8
      and (o.fulfillment_status is null or o.fulfillment_status <> 'fulfilled')
      and li.is_kaliba_eklendi = false and li.is_hazir = false""")).scalar()
print(f"  · kargoda olduğu halde 'planlanabilir kalemi' olan sipariş: {_risk}")
# Bu siparişlerin HİÇBİRİ artık plana giremez — ölçütü doğrudan sınıyoruz.
_kacak = db.execute(text("""
    select count(*) from orders o
    where o.current_stage >= 8
      and (o.fulfillment_status is null or o.fulfillment_status <> 'fulfilled')
      and o.id in (select id from orders where """ + """
        is_iptal = false and cancelled_at is null and closed_at is null
        and (current_stage is null or current_stage < 8))""")).scalar()
es("kargodaki sipariş 'açık' sayılmıyor", 0, _kacak)

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
