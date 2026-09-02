"""Beyaz altlık kalıbı — geometri ve renk doğrulaması.

Baskıya giden bir çıktı: yanlış ölçü/renk tüm kalıbı çöpe atar. Bu yüzden
üretilen PDF'in İÇİ okunarak sınanıyor (dosya üretildi demek yetmez).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fitz  # noqa: E402

from app.services import mold_pdf as mp  # noqa: E402

GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


def yakin(ad, beklenen, gercek, tol=0.5):
    global GECTI, KALDI
    if abs(beklenen - gercek) <= tol:
        GECTI += 1; print(f"  ✓ {ad}  ({gercek:.2f})")
    else:
        KALDI += 1; print(f"  ✗ {ad}: beklenen ~{beklenen:.2f}, gercek {gercek:.2f}")


CM = mp.CM_TO_PT
# 3 sutun x 1 satir, her kutu 10x20 cm
SABLON = {
    "page_w_pt": 30 * CM, "page_h_pt": 20 * CM, "cols": 3, "rows": 1,
    "boxes": [{"x0": i * 10 * CM, "y0": 0.0, "w": 10 * CM, "h": 20 * CM} for i in range(3)],
}
# spec = (genislik_cm, yukseklik_cm, radius_cm)
KALEMLER = [
    {"slot_index": 0, "model": "IPHONE-14-PROMAX", "spec": (8.0, 16.25, 1.2),
     "design_file_path": None},
    {"slot_index": 1, "model": "IPHONE-15", "spec": (7.5, 15.5, 1.0),
     "design_file_path": None},
    {"slot_index": 2, "model": "IPHONE-16", "spec": (7.8, 16.0, 1.1),
     "design_file_path": None},
]

def akislar(pdf_bayt: bytes) -> str:
    """PDF'teki TÜM içerik akışlarını açıp birleştir.

    Kaydederken deflate uygulanıyor; ham baytta operatör aranmaz. Rengin
    gerçekten DeviceCMYK olduğunu doğrulamak baskı için kritik — RGB'ye düşerse
    makine beyaz kafayı sürmez.
    """
    d = fitz.open(stream=pdf_bayt, filetype="pdf")
    parcalar = []
    for x in range(1, d.xref_length()):
        try:
            parcalar.append(d.xref_stream(x).decode("latin-1"))
        except Exception:
            continue
    d.close()
    return "\n".join(parcalar)


def bas_alan(pdf_bayt, dpi=72):
    """PDF'te BOYALI alanın sınır kutusu (pt). İçerik XObject içinde olduğu için
    çizim listesi yerine rasterleştirip bakıyoruz — baskıda ne görünüyorsa o."""
    d = fitz.open(stream=pdf_bayt, filetype="pdf")
    pm = d[0].get_pixmap(dpi=dpi, alpha=True)
    en, boy = pm.width, pm.height
    x0 = y0 = None; x1 = y1 = -1
    for y in range(boy):
        for x in range(en):
            if pm.pixel(x, y)[3] > 8:      # saydam değilse boyalı
                if x0 is None or x < x0: x0 = x
                if y0 is None or y < y0: y0 = y
                if x > x1: x1 = x
                if y > y1: y1 = y
    d.close()
    if x0 is None:
        return None
    olcek = 72.0 / dpi
    return (x0 * olcek, y0 * olcek, (x1 + 1) * olcek, (y1 + 1) * olcek)


print("\n── Yalnızca seçili slotlar dolar ──")
veri, rapor = mp.render_beyaz_altlik_pdf(KALEMLER, SABLON, secili_slotlar=[0, 2], k=0.05)
es("2 slot yerlesti", 2, rapor["placed"])
es("atlanan yok", 0, rapor["skipped_count"])
es("secili kayda gecti", [0, 2], rapor["secili"])

_ops = akislar(veri)
import re as _re  # noqa: E402
_k = _re.findall(r"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+k\b", _ops)
es("CMYK 'k' operatoru kullanilmis", True, len(_k) > 0)
es("RGB 'rg' dolgusu YOK", False, bool(_re.search(r"[\d.]+\s+[\d.]+\s+[\d.]+\s+rg\b", _ops)))
es("C=M=Y=0", True, all(float(a) == 0 and float(b) == 0 and float(c) == 0
                        for a, b, c, _d in _k))
es("K=%5", True, any(abs(float(d) - 0.05) < 0.001 for *_x, d in _k))

print("\n── Konum ve ölçü: TASARIM kalıbıyla birebir aynı ──")
# Ayni slot icin once tasarimli kalip (gercek PDF dosyasiyla), sonra altlik uret;
# boyali alanlarin sinir kutusu AYNI olmali.
import io as _io  # noqa: E402
from PIL import Image as _Img  # noqa: E402

_gecici = Path("/tmp/beyaz_test_tasarim.pdf")
_d = fitz.open(); _p = _d.new_page(width=8.0 * CM, height=16.25 * CM)
_p.draw_rect(fitz.Rect(0, 0, 8.0 * CM, 16.25 * CM), color=None, fill=(0, 0, 1))
_d.save(str(_gecici)); _d.close()

_tek = [{"slot_index": 0, "model": "IPHONE-14-PROMAX", "spec": (8.0, 16.25, 1.2),
         "design_file_path": str(_gecici), "design_format": "pdf"}]
_tasarim_pdf, _tr = mp.render_mold_pdf(_tek, SABLON)
_altlik_pdf, _ar = mp.render_beyaz_altlik_pdf(_tek, SABLON, secili_slotlar=[0])
es("tasarim yerlesti", 1, _tr["placed"])
es("altlik yerlesti", 1, _ar["placed"])

_a = bas_alan(_tasarim_pdf)
_b = bas_alan(_altlik_pdf)
es("ikisi de boyali alan uretti", True, _a is not None and _b is not None)
for _n, _ad in enumerate(("sol", "ust", "sag", "alt")):
    yakin(f"{_ad} kenar ayni", _a[_n], _b[_n], tol=1.5)
yakin("genislik 8.0 cm", 8.0, (_b[2] - _b[0]) / CM, tol=0.15)
yakin("yukseklik 16.25 cm", 16.25, (_b[3] - _b[1]) / CM, tol=0.15)

print("\n── Köşeler yuvarlak (keskin dikdörtgen DEĞİL) ──")
# Sol-ust kosede piksel BOS olmali (yuvarlatma varsa)
_dd = fitz.open(stream=_altlik_pdf, filetype="pdf")
_pm = _dd[0].get_pixmap(dpi=72, alpha=True)
_kx, _ky = int(_b[0]) + 1, int(_b[1]) + 1
es("sol-ust kose bos (oval)", True, _pm.pixel(_kx, _ky)[3] <= 8)
_mx = int((_b[0] + _b[2]) / 2)
_my = int((_b[1] + _b[3]) / 2)
es("merkez dolu", True, _pm.pixel(_mx, _my)[3] > 8)
_dd.close()
_gecici.unlink(missing_ok=True)

print("\n── Sınırlar ──")
try:
    mp.render_beyaz_altlik_pdf(KALEMLER, SABLON, secili_slotlar=[])
    es("bos secim reddedilir", True, False)
except ValueError:
    es("bos secim reddedilir", True, True)
try:
    mp.render_beyaz_altlik_pdf(KALEMLER, None, secili_slotlar=[0])
    es("sablonsuz reddedilir", True, False)
except ValueError:
    es("sablonsuz reddedilir", True, True)

# Olcusu bilinmeyen model: yanlis boyda basmaktansa ATLA
_olcusuz = [{"slot_index": 0, "model": "BILINMEYEN", "spec": None,
             "design_file_path": None}]
_v, _r = mp.render_beyaz_altlik_pdf(_olcusuz, SABLON, secili_slotlar=[0])
es("olcusuz model atlanir", "olcu_yok", _r["skipped"][0]["reason"])
es("olcusuz modelde hicbir sey cizilmez", 0, _r["placed"])

# Bos slot secilirse
_v2, _r2 = mp.render_beyaz_altlik_pdf(KALEMLER, SABLON, secili_slotlar=[0, 1, 2])
es("3 slot da dolu", 3, _r2["placed"])

print("\n── K değeri ayarlanabilir ──")
_v3, _r3 = mp.render_beyaz_altlik_pdf(KALEMLER, SABLON, secili_slotlar=[0], k=0.12)
_o3 = akislar(_v3)
_k3 = _re.findall(r"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+k\b", _o3)
es("K=%12 yazildi", True, any(abs(float(d) - 0.12) < 0.001 for *_x, d in _k3))
es("K=%5 ARTIK yok", False, any(abs(float(d) - 0.05) < 0.001 for *_x, d in _k3))

print("\n── Uçlar: seçim kaydı + PDF indirme ──")
import uuid as _uuid  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select as _sel, text as _txt  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app as _app  # noqa: E402
from app.models import (Design as _D, Mold as _M, MoldItem as _MI,  # noqa: E402
                        MoldTemplate as _MT, Store as _S, Tenant as _T, User as _U)

_C = TestClient(_app)
_db = SessionLocal()
_IZ = f"beyaz{_uuid.uuid4().hex[:6]}"
from app.auth.security import verify_password as _vp   # noqa: E402
_adaylar = _db.scalars(_sel(_U).where(
    _U.role.in_(("yonetici", "owner"))).order_by(_U.email)).all()
_admin = next((u for u in _adaylar
               if u.password_hash and _vp("DevAdmin12345!", u.password_hash)), None)
if _admin is None:
    raise SystemExit("Dev sifresiyle girilebilen yonetici YOK — test calisamaz.")
_t = _db.get(_T, _admin.tenant_id)
_r = _C.post("/api/auth/login", json={"email": _admin.email, "password": "DevAdmin12345!"})
if _r.status_code != 200:
    _db.execute(_txt("delete from login_attempts where ip in ('testclient','127.0.0.1')"))
    _db.commit()
    _r = _C.post("/api/auth/login", json={"email": _admin.email, "password": "DevAdmin12345!"})
_H = {"Authorization": f"Bearer {_r.json()['access_token']}"}

# Aktif şablon (dev'de yoksa geçici kur)
_eski_tpl = _db.scalar(_sel(_MT).where(_MT.tenant_id == _t.id, _MT.is_active.is_(True)))
_gecici_tpl = None
if not _eski_tpl:
    _gecici_tpl = _MT(tenant_id=_t.id, name=f"{_IZ}-tpl", file_path="",
                      page_w_pt=SABLON["page_w_pt"], page_h_pt=SABLON["page_h_pt"],
                      cols=3, rows=1, box_count=3, boxes=SABLON["boxes"],
                      is_active=True, beyaz_k=0.05)
    _db.add(_gecici_tpl); _db.commit()

_st = _db.scalar(_sel(_S).where(_S.tenant_id == _t.id).limit(1))
_ds = _D(tenant_id=_t.id, store_id=_st.id, code=f"{_IZ}-D", name="d",
         file_path="", file_format="", file_size_bytes=0)
_db.add(_ds); _db.flush()
_mo = _M(tenant_id=_t.id, store_id=_st.id, kod=f"{_IZ}-U1", variation="BEYAZ",
         kilif_sayisi=2, rows_used=1, current_stage=2)
_db.add(_mo); _db.flush()
for _si in (0, 1):
    _db.add(_MI(tenant_id=_t.id, mold_id=_mo.id, store_id=_st.id, design_id=_ds.id,
                slot_index=_si, kalip_kodu="A1", model="IPHONE-15",
                order_number=f"{_IZ}{_si}"))
_db.commit()

es("secim once bos", [], list(_mo.beyaz_slotlar or []))
_rs = _C.patch(f"/api/molds/{_mo.id}/beyaz-slotlar", headers=_H, json={"slotlar": [0]})
es("secim kaydedildi", 200, _rs.status_code)
es("kaydedilen slot", [0], _rs.json()["slotlar"])

_rs2 = _C.patch(f"/api/molds/{_mo.id}/beyaz-slotlar", headers=_H, json={"slotlar": [0, 99]})
es("dolu OLMAYAN slot yoksayildi", [99], _rs2.json()["yoksayilan"])
es("yalniz dolu slot kaldi", [0], _rs2.json()["slotlar"])

_db.expire_all()
es("secim veritabaninda kalici", [0],
   list(_db.scalar(_sel(_M).where(_M.id == _mo.id)).beyaz_slotlar or []))

_rp = _C.get(f"/api/molds/{_mo.id}/beyaz-pdf", headers=_H)
es("PDF 200", 200, _rp.status_code)
es("PDF tipi", "application/pdf", _rp.headers.get("content-type"))
es("dosya adi -BEYAZ", True, "-BEYAZ.pdf" in (_rp.headers.get("content-disposition") or ""))
es("PDF gercekten PDF", True, _rp.content[:5] == b"%PDF-")

_C.patch(f"/api/molds/{_mo.id}/beyaz-slotlar", headers=_H, json={"slotlar": []})
es("secim yokken 400", 400, _C.get(f"/api/molds/{_mo.id}/beyaz-pdf", headers=_H).status_code)
es("olmayan kalip 404", 404,
   _C.get(f"/api/molds/{_uuid.uuid4()}/beyaz-pdf", headers=_H).status_code)
es("kimliksiz istek reddedilir", 401,
   _C.get(f"/api/molds/{_mo.id}/beyaz-pdf").status_code)

_db.execute(_txt("delete from mold_items where mold_id = :m"), {"m": _mo.id})
_db.execute(_txt("delete from molds where id = :m"), {"m": _mo.id})
_db.execute(_txt("delete from designs where code like :p"), {"p": f"{_IZ}%"})
if _gecici_tpl:
    _db.execute(_txt("delete from mold_templates where name like :p"), {"p": f"{_IZ}%"})
_db.commit()

print(f"\n{'='*46}\nGECTI: {GECTI}   KALDI: {KALDI}\n{'='*46}")
sys.exit(1 if KALDI else 0)
