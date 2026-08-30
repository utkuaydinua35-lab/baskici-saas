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

print("\n── 6. ETIKET YEDEGI: Surat barkod vermezse kendi etiketimiz ──")
# Surat bu hesapta Message=013 + gercek takip no veriyor ama Barcode BOS.
# O durumda gercek takip nosu Code128 olarak kendi etiketimize basilmali.
import fitz  # noqa: E402


class _SahteStore:
    name = "BERNZ"


class _SahteDb:
    def scalar(self, *a, **k):
        return _SahteStore()


class _SipEtiket(_Sip):
    def __init__(self):
        super().__init__()
        self.store_id = uuid.uuid4()
        self.tenant_id = uuid.uuid4()   # etiket ayarları tenant'tan okunuyor
        self.name = "#T-1001"
        self.customer_name = "Ali Veli"
        self.barkod_kodu = "KENDI-KODUMUZ"


o = _SipEtiket()
ki = {"provider": "surat", "takip_no": "40105913453122", "barkod_no": None,
      "etiket_var": False}
pdf = pkg._surat_etiket_pdf(_SahteDb(), o, ki)
es("PDF uretildi", True, pdf.startswith(b"%PDF"))
_metin = "".join(pg.get_text() for pg in fitz.open(stream=pdf, filetype="pdf"))
es("SURAT takip nosu etikette", True, "40105913453122" in _metin)
es("kendi kodumuz BASILMADI", False, "KENDI-KODUMUZ" in _metin)

# barkod_no varsa O tercih edilir
ki2 = dict(ki, barkod_no="9998887776665")
_m2 = "".join(pg.get_text() for pg in fitz.open(
    stream=pkg._surat_etiket_pdf(_SahteDb(), o, ki2), filetype="pdf"))
es("barkod_no takip_no'ya TERCIH edilir", True, "9998887776665" in _m2)
es("barkod_no varken takip_no basilmaz", False, "40105913453122" in _m2)

# Surat GERCEKTEN PDF verirse o kullanilir (kendi etiketimiz degil)
yol = pkg._surat_etiket_yolu(o.id)
yol.write_bytes(b"%PDF-1.4\n% surat etiketi\n")
es("Surat PDF'i varsa O kullanilir", True,
   pkg._surat_etiket_pdf(_SahteDb(), o, ki).endswith(b"% surat etiketi\n"))
yol.unlink()

print("\n── 7. YENIDEN DENEME: barkodsuz basarida TEKRAR CAGIRMA ──")
# Bu hesapta barkod hic gelmiyor. Eski kosul her gonderide 3 cagri yapiyordu
# -> Surat idempotent degilse mukerrer gonderi. Sayaci gercekten olcelim.
import app.services.surat as _sr  # noqa: E402

_cagri = {"n": 0}


class _SahteYanit:
    status_code = 200

    def __init__(self, govde): self._g = govde
    def json(self): return self._g


def _sahte_post(url, json=None, timeout=None):
    _cagri["n"] += 1
    return _SahteYanit({"isError": False, "Message": "013",
                        "KargoTakipNo": "40105913453122",
                        "Barcode": [], "BarcodeNo": [], "Value": None})


_orj_req = _sr.requests.post
_orj_cfg2 = _sr.is_configured
_sr.requests.post = _sahte_post
try:
    r = _sr.create_shipment(
        {"shipping_address": {"first_name": "Ali", "last_name": "Veli",
                              "address1": "Test Cad. No:1", "province": "İstanbul",
                              "city": "Kadıköy", "phone": "05001112233"}},
        ozel_kargo_takip_no="T-1001", kullanici_adi="x", sifre="y")
    es("gonderi basarili", True, r["ok"])
    es("gercek takip no dondu", "40105913453122", r["takip_no"])
    es("barkod yok (beklenen)", None, r["barkod_base64"])
    es("SURAT'A TEK CAGRI yapildi", 1, _cagri["n"])
finally:
    _sr.requests.post = _orj_req
    _sr.is_configured = _orj_cfg2

print("\n── 8. relay tamamen kaldirildi ──")
kaynak = (Path(__file__).resolve().parent.parent / "app/services/surat.py").read_text(encoding="utf-8")
es("relay_url degiskeni yok", False, "relay_url" in kaynak)
es("relay POST yolu yok", False, "/surat\"" in kaynak)

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
