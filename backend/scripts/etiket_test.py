"""Kargo etiketi — yerleşim ve KAYIP METİN testleri.

Eski etikette her satır fontsize*1.9 yüksekliğinde sabit bir kutuya yazılıyordu;
PyMuPDF sığmayan metni kırpmaz, HİÇ YAZMAZ. 33 karakterden uzun sokak adresleri
bu yüzden sessizce kayboluyordu — paketin üstünde adres yoktu.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fitz  # noqa: E402

from app.services import label_pdf  # noqa: E402
from app.services.zpl_label import pdf_to_zpl  # noqa: E402

GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


def _sip(**adres):
    sa = {"first_name": "Ayşe", "last_name": "Yılmaz", "address1": "Test Cad. No:1",
          "city": "Yenimahalle", "province": "Ankara", "phone": "05001112233"}
    sa.update(adres)

    class S:
        name = "#1"; order_number = "11658"; barkod_kodu = None
        customer_name = "Ayşe Yılmaz"
        raw = {"shipping_address": sa}
    return S()


def _metin(pdf: bytes) -> str:
    d = fitz.open(stream=pdf, filetype="pdf")
    return re.sub(r"\s+", " ", "".join(p.get_text() for p in d))


def _uret(order, kod="40105913453122"):
    return label_pdf.render_label_pdf(order, "BERNZ COMPANY", barkod_kodu=kod,
                                      kargo_firma="Sürat Kargo")


UZUN = ("Cumhuriyet Mahallesi Şehit Piyade Onbaşı Mehmet Akif Ersoy Caddesi "
        "Gülbahçe Sitesi B Blok Kat:12 Daire:47 Karşıyaka mevkii")

print("\n── 1. UZUN ADRES KAYBOLMUYOR (asıl hata) ──")
for ad, a1 in (("kısa", "Ataturk Cad. No:5"),
               ("orta 33 krk", "Kentkoop Mah. 1865. Sokak No:19/B"),
               ("uzun 71 krk", "Kentkoop Mah. 1865. Sk. S. Siyasal 92 Yapı Koop No:19/B G1 Blok"),
               ("çok uzun 140 krk", UZUN)):
    t = _metin(_uret(_sip(address1=a1)))
    ilk = " ".join(a1.split()[:4])
    es(f"adres etikette ({ad})", True, ilk in t)

print("\n── 2. Türkçe karakterler ──")
t = _metin(_uret(_sip()))
es("alıcı adı Türkçe", True, "AYŞE YILMAZ" in t)
es("ilçe/il Türkçe büyük harf", True, "YENİMAHALLE" in t)
es("kargo firması", True, "SÜRAT KARGO" in t)
es("İzmir doğru büyüyor", "İZMİR", label_pdf._buyut("İzmir"))
es("Kadıköy doğru büyüyor", "KADIKÖY", label_pdf._buyut("Kadıköy"))

print("\n── 3. barkod ve kod ──")
es("takip no basılı", True, "40105913453122" in t)
es("sipariş no basılı", True, "11658" in t)
es("barkod_kodu boşsa sipariş no'ya düşer", True,
   "11658" in _metin(_uret(_sip(), kod="")))
_bos = _sip(); _bos.order_number = ""; _bos.barkod_kodu = None
es("hiç kod yoksa 'BARKOD YOK'", True, "BARKOD YOK" in _metin(_uret(_bos, kod="")))

print("\n── 4. sayfa ölçüsü ve taşma ──")
d = fitz.open(stream=_uret(_sip(address1=UZUN, address2=UZUN)), filetype="pdf")
sayfa = d[0].rect
es("10x15 cm", (283, 425), (round(sayfa.width), round(sayfa.height)))
tasan = [b for b in d[0].get_text("dict")["blocks"]
         if b.get("bbox", (0, 0, 0, 0))[3] > sayfa.height + 1]
es("sayfa dışına taşan metin yok", 0, len(tasan))

print("\n── 5. eksik alanlarda çökmüyor ──")
for ad, kw in (("telefon yok", {"phone": ""}), ("il/ilçe yok", {"city": "", "province": ""}),
               ("adres yok", {"address1": ""})):
    try:
        _uret(_sip(**kw)); es(ad, True, True)
    except Exception as e:  # noqa: BLE001
        es(ad, True, f"HATA: {e}")

print("\n── 6. Zebra (ZPL) yolu bozulmadı ──")
z = pdf_to_zpl(_uret(_sip()), dpi=203, w_mm=100, h_mm=150)
es("^XA ile başlar", True, z.startswith("^XA"))
es("^XZ ile biter", True, z.rstrip().endswith("^XZ"))
es("boş değil", True, len(z) > 10000)

print("\n── 7. ŞABLON AYARLARI ──")
A = label_pdf.ayarlari_birlestir
es("bilinmeyen anahtar atılır", False, "sacma" in A({"sacma": 1}))
es("punto SINIRLANIR (999 -> 24)", 24.0, A({"magaza_punto": 999})["magaza_punto"])
es("punto alt sınır (1 -> 7)", 7.0, A({"magaza_punto": 1})["magaza_punto"])
es("metin olmayan punto yok sayılır", label_pdf.VARSAYILAN_AYARLAR["alici_punto"],
   A({"alici_punto": "abc"})["alici_punto"])
es("max<min düzeltilir", True,
   A({"barkod_min_cm": 4, "barkod_max_cm": 2})["barkod_max_cm"] >= 4)
es("serbest metin kırpılır (120)", 120, len(A({"not_metni": "x" * 500})["not_metni"]))
es("boş ayar = varsayılan", dict(label_pdf.VARSAYILAN_AYARLAR), A({}))

t = _metin(label_pdf.render_label_pdf(
    _sip(), "BERNZ", barkod_kodu="401059", kargo_firma="Sürat Kargo",
    ayarlar={"telefon_goster": False, "not_metni": "KIRILACAK EŞYA",
             "siparis_no_goster": False}))
es("telefon gizlenebiliyor", True, "Tel:" not in t)
es("sipariş no gizlenebiliyor", True, "11658" not in t)
es("etiket notu basılıyor", True, "KIRILACAK EŞYA" in t)
es("gönderici satırı basılıyor", True, "Iade: BERNZ, Ankara" in _metin(
   label_pdf.render_label_pdf(_sip(), "BERNZ", barkod_kodu="401059",
                              ayarlar={"gonderici_metni": "Iade: BERNZ, Ankara"})))

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
