"""Kişiye özel ürün — görsel alanı kırpma ayarı ve sipariş güvenliği.

  • panelde görsel alanına oran (1:1, 9:16…) ya da piksel ölçüsü verilir;
    geçersiz değer kırpmasız (serbest) sayılır
  • siparişte görsel alanı YALNIZ kendi depomuza yüklenmiş dosya olabilir
  • müşterinin yüklediği görsel Kişiye Özel ekranında görsel olarak görünür
  • yüklemede çözünürlük 2560'a düşürülmez (baskı için istenen piksel korunur)
"""
from __future__ import annotations

import io
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402

from app.routers.catalog import _clean_custom_fields  # noqa: E402
from app.routers.kisiye_ozel import _serialize_line_item  # noqa: E402
from app.services import checkout, storage  # noqa: E402

GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


print("\n── Kırpma ayarı ──")
temiz = _clean_custom_fields([
    {"label": "Fotoğrafın", "type": "image", "kirp": {"oran": "9:16"}},
    {"label": "Kapak", "type": "image", "kirp": {"oran": "px", "px_w": "3000", "px_h": 3000}},
    {"label": "Serbest", "type": "image", "kirp": {"oran": "7:3"}},
    {"label": "Küçük px", "type": "image", "kirp": {"oran": "px", "px_w": 50, "px_h": 50}},
    {"label": "İsim", "type": "text", "kirp": {"oran": "1:1"}},
])
es("oran korunur", {"oran": "9:16"}, temiz[0].get("kirp"))
es("piksel ölçüsü sayıya çevrilir", {"oran": "px", "px_w": 3000, "px_h": 3000}, temiz[1].get("kirp"))
es("geçersiz oran → kırpma yok", None, temiz[2].get("kirp"))
es("çok küçük piksel → kırpma yok", None, temiz[3].get("kirp"))
es("yazı alanına kırpma eklenmez", None, temiz[4].get("kirp"))

print("\n── Sipariş: yalnız kendi depomuz ──")
st = SimpleNamespace(tenant_id=uuid.uuid4(), id=uuid.uuid4())
dogru = f"/storage/tenants/{st.tenant_id}/store-assets/{st.id}/musteri-1700000000-abc123.jpg"
es("kendi depomuzdaki müşteri görseli kabul", True, checkout._depo_gorseli(dogru, st))
es("dış adres reddedilir", False, checkout._depo_gorseli("https://kotu.example/x.jpg", st))
es("başka mağazanın deposu reddedilir", False, checkout._depo_gorseli(
    f"/storage/tenants/{st.tenant_id}/store-assets/{uuid.uuid4()}/musteri-1.jpg", st))
es("üst klasöre çıkma reddedilir", False, checkout._depo_gorseli(dogru.replace("musteri-", "musteri-/../../"), st))

print("\n── Kişiye Özel ekranı ──")
from app.models import LineItem  # noqa: E402
li = LineItem(id=uuid.uuid4(), tenant_id=st.tenant_id, title="Kişiye özel kılıf", quantity=1, product_id="x",
              properties=[{"name": "Telefon Modeli", "value": "iPhone 15"},
                          {"name": "Fotoğrafın", "value": dogru}])
try:
    s = _serialize_line_item(li, set(), set())
    es("depodaki görsel ekranda GÖRSEL olarak görünür (metin değil)", dogru, s["customer_image_url"])
except Exception as e:  # noqa: BLE001 — sahte satır modelin tüm alanlarını taşımayabilir
    es("depodaki görsel ekranda GÖRSEL olarak görünür (metin değil)", "çalıştı", f"hata: {e}")

print("\n── Çözünürlük korunur ──")
buf = io.BytesIO()
Image.new("RGB", (3000, 3000), (200, 30, 30)).save(buf, "JPEG", quality=90)
tid, sid = uuid.uuid4(), uuid.uuid4()
url = storage.save_store_asset(tid, sid, "musteri", buf.getvalue(), "kirpik.jpg")
yol = storage.STORAGE_ROOT / url.removeprefix("/storage/")
try:
    es("3000×3000 müşteri görseli küçültülmez", (3000, 3000), Image.open(yol).size)
finally:
    import shutil
    shutil.rmtree(storage.STORAGE_ROOT / "tenants" / str(tid), ignore_errors=True)

print("\n── Saydam ürün görseli: dolu kutu ──")
import tempfile  # noqa: E402

from app.services.images import dolu_kutu  # noqa: E402
with tempfile.TemporaryDirectory() as td:
    seffaf = Path(td) / "kilif.png"
    g = Image.new("RGBA", (1000, 1000), (0, 0, 0, 0))
    g.paste((120, 120, 200, 255), (300, 200, 700, 800))
    g.save(seffaf)
    k = dolu_kutu(seffaf)
    es("saydam PNG'de ürünün kutusu ölçülür", True,
       bool(k) and abs(k["x0"] - 0.3) < 0.01 and abs(k["y1"] - 0.8) < 0.01)
    dolu = Path(td) / "dolu.png"
    Image.new("RGBA", (500, 500), (10, 10, 10, 255)).save(dolu)
    es("zaten dolu görselde büyütme yok", None, dolu_kutu(dolu))
    jpg = Path(td) / "foto.jpg"
    Image.new("RGB", (500, 500), (10, 10, 10)).save(jpg)
    es("saydam olmayan görselde büyütme yok", None, dolu_kutu(jpg))

print(f"\n{GECTI} GECTI, {KALDI} KALDI")
sys.exit(1 if KALDI else 0)
