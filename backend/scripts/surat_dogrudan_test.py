"""Sürat DOĞRUDAN kargo yolu — ağa ÇIKMADAN testler.

surat.create_shipment sahte bir yanıtla değiştirilir; test edilen şey
packaging'in yönlendirmesi, sonuç çevirisi ve etiket yollarıdır.
"""
from __future__ import annotations

import base64
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.routers import packaging as pkg          # noqa: E402
from app.services import basit_kargo, surat       # noqa: E402

GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


class _Sip:
    def __init__(self):
        self.id = uuid.uuid4()
        self.order_number = "T-1001"
        self.raw = {"shipping_address": {
            "first_name": "Ali", "last_name": "Veli", "address1": "Test Cad. No:1",
            "province": "İstanbul", "city": "Kadıköy", "phone": "05001112233"}}


print("\n── 1. handler adlari ──")
es("DIRECT_SURAT adi", "Sürat Kargo (doğrudan)", basit_kargo.handler_name("DIRECT_SURAT"))
es("SELF_SURAT adi bozulmadi", "Sürat Kargo", basit_kargo.handler_name("SELF_SURAT"))
es("sabit dogru", "DIRECT_SURAT", pkg.SURAT_DOGRUDAN)

print("\n── 2. basarili gonderi -> sozlesme cevirisi ──")
SAHTE_PDF = b"%PDF-1.4\n% sahte etiket\n"
_orj = surat.create_shipment
_orj_cfg = surat.is_configured
# Yerelde SURAT_* .env'de yok -> is_configured() False. Bu bolumun konusu
# yonlendirme ve ceviri; kimlik bilgisi eksikligini bolum 5 ayrica sinar.
surat.is_configured = lambda: True
surat.create_shipment = lambda raw, **k: {
    "ok": True, "takip_no": "1234567890",
    "barkod_base64": base64.b64encode(SAHTE_PDF).decode(), "message": "013"}
try:
    o = _Sip()
    r = pkg._surat_gonderi(o, None, None)
    es("ok", True, r["ok"])
    es("takip no aktarildi", "1234567890", r["takip_no"])
    es("provider surat", "surat", r["provider"])
    es("handler kodu", "DIRECT_SURAT", r["handler_code"])
    es("label_svg YOK (PDF yolu)", None, r["label_svg"])
    es("basit kargo id'si YOK", None, r["id"])
    yol = pkg._surat_etiket_yolu(o.id)
    es("etiket diske yazildi", True, yol.exists())
    es("etiket icerigi dogru", SAHTE_PDF, yol.read_bytes())
    es("etiket_var bayragi", True, r["etiket_var"])
    yol.unlink()

    print("\n── 3. il/ilce override iletiliyor ──")
    yakalanan = {}
    surat.create_shipment = lambda raw, **k: (yakalanan.update(k), {
        "ok": True, "takip_no": "9", "barkod_base64": None, "message": "013"})[1]
    pkg._surat_gonderi(_Sip(), "Ankara", "Çankaya")
    es("il_override iletildi", "Ankara", yakalanan.get("il_override"))
    es("ilce_override iletildi", "Çankaya", yakalanan.get("ilce_override"))
    es("ozel takip no = siparis no", "T-1001", yakalanan.get("ozel_kargo_takip_no"))

    print("\n── 4. hata yollari ──")
    surat.create_shipment = lambda raw, **k: {
        "ok": False, "message": "İlçe belirlenemedi", "ilce_eksik": True, "il": "İstanbul"}
    r = pkg._surat_gonderi(_Sip(), None, None)
    es("basarisiz", False, r["ok"])
    es("ilce_eksik bayragi korunuyor", True, r["ilce_eksik"])
    es("il korunuyor", "İstanbul", r["il"])

    surat.create_shipment = lambda raw, **k: {"ok": False, "message": ""}
    es("mesajsiz hatada varsayilan metin",
       "Sürat gönderisi oluşturulamadı", pkg._surat_gonderi(_Sip(), None, None)["message"])

    print("\n── 5. kimlik bilgisi yoksa aga CIKMAZ ──")
    _oi = surat.is_configured
    surat.is_configured = lambda: False
    cagrildi = []
    surat.create_shipment = lambda raw, **k: cagrildi.append(1)
    r = pkg._surat_gonderi(_Sip(), None, None)
    es("ok=False", False, r["ok"])
    es("surat HIC cagrilmadi", [], cagrildi)
    surat.is_configured = lambda: True
finally:
    surat.create_shipment = _orj
    surat.is_configured = _orj_cfg

print("\n── 6. relay tamamen kaldirildi ──")
kaynak = (Path(__file__).resolve().parent.parent / "app/services/surat.py").read_text(encoding="utf-8")
es("relay_url degiskeni yok", False, "relay_url" in kaynak)
es("relay POST yolu yok", False, "/surat\"" in kaynak)

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
