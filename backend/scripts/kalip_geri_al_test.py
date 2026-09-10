"""Kalıp slotu GERİ AL — dolu slot artık işlemi engellemiyor.

Eski davranış: geri alınacak slot doluysa 400 dönüyordu ve operatörün tek
çıkışı kalıbı silip yeniden kurmaktı. Oysa kalem çıkarıldıktan sonra kalan
slotlar yeniden diziliyor (slot kilidi kapalıyken) ve eski yer HEMEN HER ZAMAN
başkasına geçiyor — yani geri alma pratikte hiç çalışmıyordu.

Yeni davranış burada sınanıyor:
  · eski yer boşsa oraya konur
  · eski yer doluysa oradaki ürün ilk boş slota taşınır, kalem KENDİ yerine döner
  · kalıp BASILMIŞ ya da slot KİLİTLİ ise kimse yerinden oynatılmaz
    (kılıflar fiziksel olarak dizildi; birkaç mm kayma baskıyı bozar)
  · kalıp tamamen doluysa gerçekten yer yok → reddedilir
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.auth.security import verify_password  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Mold, MoldItem, User  # noqa: E402

DEV_SIFRE = "DevAdmin12345!"
GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


C = TestClient(app)
db = SessionLocal()

_adaylar = db.scalars(
    select(User).where(User.role.in_(("yonetici", "owner"))).order_by(User.email)).all()
admin = next((u for u in _adaylar
              if u.password_hash and verify_password(DEV_SIFRE, u.password_hash)), None)
if admin is None:
    raise SystemExit("Dev sifresiyle girilebilen yonetici YOK — test CALISAMAZ, atlanmiyor.")

_r = C.post("/api/auth/login", json={"email": admin.email, "password": DEV_SIFRE})
if _r.status_code != 200:
    db.execute(text("delete from login_attempts where ip in ('testclient','127.0.0.1')"))
    db.commit()
    _r = C.post("/api/auth/login", json={"email": admin.email, "password": DEV_SIFRE})
if _r.status_code != 200:
    raise SystemExit(f"YONETICI GIRISI BASARISIZ ({_r.status_code}) — test durduruldu.")
H = {"Authorization": f"Bearer {_r.json()['access_token']}"}
TID = admin.tenant_id

ETIKET = "GERIAL-TEST"


def kalip_kur(adet: int, *, kilitli: bool = False, basildi: bool = False) -> Mold:
    """Sentetik kalıp. line_item_id YOK: gerçek siparişlere dokunmuyoruz."""
    mo = Mold(tenant_id=TID, kod=f"{ETIKET}-{uuid.uuid4().hex[:8]}",
              variation="PARLAK", kilif_sayisi=adet,
              slot_kilitli=kilitli,
              status="basildi" if basildi else "olusturuldu",
              print_status="basildi" if basildi else "bekliyor")
    db.add(mo); db.flush()
    for i in range(adet):
        db.add(MoldItem(tenant_id=TID, mold_id=mo.id, slot_index=i,
                        kalip_kodu=f"{ETIKET}|PARLAK", design_code=f"{ETIKET}-{i}",
                        model="iPhone 14 Pro", order_number=None))
    db.commit()
    return mo


def slotlar(mold_id) -> dict:
    """{design_code: slot_index}"""
    return {r[0]: r[1] for r in db.execute(
        text("select design_code, slot_index from mold_items where mold_id = :m"),
        {"m": str(mold_id)}).all()}


def cikar_ve_geri_al(mo, hedef_kod: str) -> tuple[int, dict]:
    """hedef_kod'lu slotu çıkarır, sonra geri alır. (undo status, slotlar) döner."""
    _it = db.scalar(select(MoldItem).where(MoldItem.mold_id == mo.id,
                                           MoldItem.design_code == hedef_kod))
    r = C.post(f"/api/molds/{mo.id}/items/{_it.id}/remove", headers=H,
               json={"action": "replan"})
    assert r.status_code == 200, r.text
    return _it, r


try:
    print("\n── eski yer DOLUYKEN: kalem kendi yerine döner, oradaki taşınır ──")
    mo = kalip_kur(3)
    _it, _ = cikar_ve_geri_al(mo, f"{ETIKET}-1")
    db.expire_all()
    _s = slotlar(mo.id)
    es("çıkarma sonrası 2 slot kaldı", 2, len(_s))
    # Slot kilidi kapalı → kalanlar yeniden dizilir ve #1 BAŞKASINA geçer.
    es("eski yer (#1) artık başkasında", True, 1 in _s.values())

    _h = C.get(f"/api/molds/{mo.id}/history", headers=H).json()["items"]
    _undo_id = next(x["id"] for x in _h if x["can_undo"])
    _ru = C.post(f"/api/molds/{mo.id}/history/{_undo_id}/undo", headers=H)
    es("geri alma REDDEDİLMEDİ", 200, _ru.status_code)
    db.expire_all()
    _s2 = slotlar(mo.id)
    es("3 slot geri geldi", 3, len(_s2))
    es("kalem KENDİ eski yerine döndü (#1)", 1, _s2.get(f"{ETIKET}-1"))
    es("işgalci taşındı, çakışma yok", 3, len(set(_s2.values())))
    es("kılıf sayısı güncellendi", 3, db.get(Mold, mo.id).kilif_sayisi)
    es("not taşımayı yazıyor", True, any(
        "taşındı" in (x.get("note") or "")
        for x in C.get(f"/api/molds/{mo.id}/history", headers=H).json()["items"]))
    es("aynı kayıt ikinci kez geri alınamaz", 400,
       C.post(f"/api/molds/{mo.id}/history/{_undo_id}/undo", headers=H).status_code)

    print("\n── BASILMIŞ kalıpta kimse yerinden oynatılmaz ──")
    mo2 = kalip_kur(3, basildi=True)
    _it2, _ = cikar_ve_geri_al(mo2, f"{ETIKET}-1")
    db.expire_all()
    _once = slotlar(mo2.id)
    _h2 = C.get(f"/api/molds/{mo2.id}/history", headers=H).json()["items"]
    _u2 = next(x["id"] for x in _h2 if x["can_undo"])
    es("geri alma yine çalışıyor", 200,
       C.post(f"/api/molds/{mo2.id}/history/{_u2}/undo", headers=H).status_code)
    db.expire_all()
    _sonra = slotlar(mo2.id)
    es("mevcut slotların YERİ DEĞİŞMEDİ", True,
       all(_sonra.get(k) == v for k, v in _once.items()))
    es("geri alınan kalem boş slota indi", 3, len(set(_sonra.values())))

    print("\n── SLOT KİLİTLİ kalıpta da kimse oynatılmaz ──")
    mo3 = kalip_kur(3, kilitli=True)
    _it3, _ = cikar_ve_geri_al(mo3, f"{ETIKET}-0")
    db.expire_all()
    _once3 = slotlar(mo3.id)
    # Kilitliyken kalanlar YERİNDE kalır → eski yer (#0) BOŞ, kalem oraya döner.
    es("kilitliyken kalanlar kaymadı", {1, 2}, set(_once3.values()))
    _h3 = C.get(f"/api/molds/{mo3.id}/history", headers=H).json()["items"]
    _u3 = next(x["id"] for x in _h3 if x["can_undo"])
    es("geri alındı", 200,
       C.post(f"/api/molds/{mo3.id}/history/{_u3}/undo", headers=H).status_code)
    db.expire_all()
    es("boş olan eski yerine döndü", 0, slotlar(mo3.id).get(f"{ETIKET}-0"))

    print("\n── kalıp TAMAMEN doluysa gerçekten yer yok ──")
    mo4 = kalip_kur(27)
    _it4, _ = cikar_ve_geri_al(mo4, f"{ETIKET}-5")
    # Çıkan yerin boşluğunu doldur: kalıp yeniden 27 dolu olsun.
    db.add(MoldItem(tenant_id=TID, mold_id=mo4.id,
                    slot_index=max(slotlar(mo4.id).values()) + 1,
                    kalip_kodu=f"{ETIKET}|PARLAK", design_code=f"{ETIKET}-dolgu",
                    model="iPhone 14 Pro"))
    db.commit(); db.expire_all()
    es("kalıp 27 dolu", 27, len(slotlar(mo4.id)))
    _h4 = C.get(f"/api/molds/{mo4.id}/history", headers=H).json()["items"]
    _u4 = next(x["id"] for x in _h4 if x["can_undo"])
    _r4 = C.post(f"/api/molds/{mo4.id}/history/{_u4}/undo", headers=H)
    es("dolu kalıpta geri alma reddedilir", 400, _r4.status_code)
    es("sebep 'boş slot kalmadı' diyor", True,
       "boş slot" in (_r4.json().get("detail") or ""))

finally:
    db.rollback()
    # ── temizlik ── sentetik kalıpları sil (gerçek siparişe hiç dokunulmadı)
    _ids = [str(x) for x in db.scalars(
        select(Mold.id).distinct().join(MoldItem, MoldItem.mold_id == Mold.id)
        .where(MoldItem.kalip_kodu == f"{ETIKET}|PARLAK")).all()]
    if _ids:
        db.execute(text("delete from mold_status_history where mold_id = any(:i)"),
                   {"i": _ids})
        db.execute(text("delete from mold_items where mold_id = any(:i)"), {"i": _ids})
        db.execute(text("delete from molds where id = any(:i)"), {"i": _ids})
        db.commit()
    print(f"\n  · {len(_ids)} test kalıbı temizlendi")

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
