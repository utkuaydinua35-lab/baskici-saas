"""ÖNİZLEME görseli — BASKIYA ASLA GİRMEMELİ.

Önizleme, tasarımın kılıf üzerinde nasıl duracağını gösterir. Kalıba yanlışlıkla
önizleme girerse kılıflar çöp olur. Testlerin ağırlığı bilerek bu ayrımda.
"""
from __future__ import annotations

import io
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import UploadFile  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Dealer, Design, Store, Tenant  # noqa: E402
from app.routers import bayii_portal as bp  # noqa: E402
from app.services import storage  # noqa: E402

GECTI = KALDI = 0
IZ = uuid.uuid4().hex[:6]
TASARIM = b"\xff\xd8\xff\xe0" + b"TASARIM!" * 60 + b"\xff\xd9"
ONIZLEME = b"\xff\xd8\xff\xe0" + b"ONIZLEME" * 60 + b"\xff\xd9"


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


def _yuk(veri, ad="x.jpg"):
    return UploadFile(filename=ad, file=io.BytesIO(veri))


db = SessionLocal()
from app.auth.security import verify_password as _vp  # noqa: E402
from app.models import User as _U  # noqa: E402

_adaylar = db.scalars(select(_U).where(
    _U.role.in_(("yonetici", "owner"))).order_by(_U.email)).all()
_admin = next((u for u in _adaylar
               if u.password_hash and _vp("DevAdmin12345!", u.password_hash)), None)
if _admin is None:
    raise SystemExit("Dev sifresiyle girilebilen yonetici YOK — test calisamaz.")
tenant = db.get(Tenant, _admin.tenant_id)
store = Store(tenant_id=tenant.id, slug=f"{IZ}-o", name="Onizleme Test",
              platform="bayii", is_active=True)
db.add(store); db.flush()
dealer = Dealer(tenant_id=tenant.id, store_id=store.id, name=f"ONZ-{IZ}", is_active=True)
db.add(dealer); db.commit()

print("\n── 1. önizleme AYRI dosyaya yazılır ──")
ds = bp._tasarim_kaydet(db, dealer, _yuk(TASARIM), "test"); db.commit()
es("tasarım dosyası kaydedildi", TASARIM, storage.read_design_file(ds.file_path))
es("önizleme henüz yok", None, ds.onizleme_path)

bp._onizleme_kaydet(db, dealer, ds, _yuk(ONIZLEME, "onz.jpg")); db.commit()
db.expire_all(); ds = db.get(Design, ds.id)
es("önizleme yolu yazıldı", True, bool(ds.onizleme_path))
es("önizleme AYRI klasörde", True, "/onizleme/" in ds.onizleme_path.replace("\\", "/"))

print("\n── 2. TASARIM dosyası DEĞİŞMEDİ (asıl sınama) ──")
es("baskıya giden dosya hâlâ TASARIM", TASARIM, storage.read_design_file(ds.file_path))
es("tasarım yolu önizleme yolu DEĞİL", True, ds.file_path != ds.onizleme_path)
_onz = (storage.STORAGE_ROOT / ds.onizleme_path).read_bytes()
es("önizleme dosyası gerçekten önizleme", ONIZLEME, _onz)
es("önizleme ≠ tasarım", True, _onz != TASARIM)

print("\n── 3. KALIP girdisi önizlemeyi HİÇ görmüyor ──")
# _pdf_girdi tasarımın file_path'ini kullanır; önizleme alanı hiç okunmaz.
kaynak = (Path(__file__).resolve().parent.parent / "app/routers/molds.py").read_text(encoding="utf-8")
es("molds.py 'onizleme' kelimesini geçirmiyor", False, "onizleme_path" in kaynak)
mp = (Path(__file__).resolve().parent.parent / "app/services/mold_pdf.py").read_text(encoding="utf-8")
es("mold_pdf.py önizleme okumuyor", False, "onizleme" in mp)

print("\n── 4. katalog: önizleme GÖSTERİR, tasarımı SEÇTİRİR ──")
sonuc = bp.tasarimlar(d=dealer, db=db)
kayit = next(x for x in sonuc["items"] if x["id"] == str(ds.id))
es("listede önizleme gösteriliyor", True, "/onizleme/" in (kayit["gorsel"] or ""))
es("seçilecek id TASARIMIN id'si", str(ds.id), kayit["id"])
es("tasarım görseli ayrıca veriliyor", True,
   bool(kayit["tasarim_gorseli"]) and "/onizleme/" not in kayit["tasarim_gorseli"])
es("önizleme_var bayrağı", True, kayit["onizleme_var"])

print("\n── 5. katalogdan seçim TASARIM dosyasını bağlar ──")
secilen = bp._katalogdan_tasarim(db, dealer, str(ds.id))
es("aynı tasarım", ds.id, secilen.id)
es("bağlanan dosya TASARIM", TASARIM, storage.read_design_file(secilen.file_path))

print("\n── 6. sonuncu önizleme geçerli (kullanıcı kararı) ──")
YENI_ONZ = b"\xff\xd8\xff\xe0" + b"YENIONZ!" * 60 + b"\xff\xd9"
eski_yol = ds.onizleme_path
bp._onizleme_kaydet(db, dealer, ds, _yuk(YENI_ONZ, "yeni.png")); db.commit()
db.expire_all(); ds = db.get(Design, ds.id)
es("yeni önizleme geçerli", YENI_ONZ, (storage.STORAGE_ROOT / ds.onizleme_path).read_bytes())
es("eski önizleme dosyası silindi", False,
   eski_yol != ds.onizleme_path and (storage.STORAGE_ROOT / eski_yol).exists())
es("TASARIM yine değişmedi", TASARIM, storage.read_design_file(ds.file_path))

print("\n── 7. /onizleme UCU GERÇEKTEN ÇAĞRILIYOR ──")
# Bu uç canlıda 500 verdi: Response import edilmemişti ve testler ucu hiç
# çağırmadığı için (tarayıcıda sahte fetch kullanılmıştı) kaçtı.
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app as _app  # noqa: E402

_C = TestClient(_app)
db.execute(text("delete from login_attempts where ip in ('testclient','127.0.0.1')"))
db.commit()
_r = _C.post("/api/auth/login", json={"email": _admin.email, "password": "DevAdmin12345!"})
if _r.status_code != 200:
    raise SystemExit(f"Giris basarisiz ({_r.status_code})")
_H = {"Authorization": f"Bearer {_r.json()['access_token']}"}

# Bu tasarim ADMIN'in tenant'inda olmali; test magazasi zaten oradan olusturuldu
_u = f"/api/designs/{ds.id}/onizleme?dpi=200"
_res = _C.get(_u, headers=_H)
es("JPG tasarımda 200", 200, _res.status_code)
es("görsel döndü", True, _res.headers.get("content-type", "").startswith("image/"))
es("gövde boş değil", True, len(_res.content) > 100)
es("kimliksiz istek reddedilir", 401, _C.get(_u).status_code)
es("olmayan tasarım 404", 404,
   _C.get(f"/api/designs/{uuid.uuid4()}/onizleme", headers=_H).status_code)

# PDF tasarımda gerçekten PNG'ye çeviriyor mu?
_pdf_ds = Design(tenant_id=tenant.id, store_id=store.id, code=f"{IZ}-PDFT",
                 name="pdf", file_path="", file_format="pdf", file_size_bytes=0)
db.add(_pdf_ds); db.flush()
import fitz  # noqa: E402
_d = fitz.open(); _d.new_page(width=200, height=200)
_pdf_ds.file_path = storage.save_design_file(
    tenant_id=tenant.id, design_id=_pdf_ds.id, file_data=_d.tobytes(),
    original_filename="x.pdf", skip_thumbnail=True)["relative_path"]
db.commit()
_r2 = _C.get(f"/api/designs/{_pdf_ds.id}/onizleme?dpi=200", headers=_H)
es("PDF tasarımda 200", 200, _r2.status_code)
es("PNG'ye çevrildi", "image/png", _r2.headers.get("content-type"))
storage.delete_design_file(_pdf_ds.file_path)

print("\n── 8. dosyası silinmiş tasarım katalogda GÖRÜNMEZ ──")
from datetime import UTC, datetime  # noqa: E402
ds.dosya_silindi_at = datetime.now(UTC); db.commit()
es("listeden düştü", False,
   any(x["id"] == str(ds.id) for x in bp.tasarimlar(d=dealer, db=db)["items"]))

# temizlik
storage.delete_design_file(ds.file_path)
storage.delete_onizleme(ds.onizleme_path)
db.execute(text("delete from designs where store_id=:s"), {"s": str(store.id)})
db.execute(text("delete from dealers where store_id=:s"), {"s": str(store.id)})
db.execute(text("delete from stores where id=:s"), {"s": str(store.id)})
db.commit()

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
