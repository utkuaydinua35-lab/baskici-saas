"""Basılan etiketteki barkod GERİ OKUNABİLİYOR mu?

Sürat şubesinde okunmadı: sebep çubukların çerçeveli çizilmesiydi (PyMuPDF'te
`color=` çerçeve demek, varsayılan kalınlık 1 punto). Modül ~1.2 punto olduğu
için çubuklar iki yandan şişip birbirine yapışıyordu — 103 çubukluk barkod 85
çubuk basılıyordu.

Bu test etiketi GERÇEKTEN rasterleştirip (yazıcıya giden yolun aynısı) barkodu
görüntüden çözer. Fiziksel okutmanın yerini tutmaz ama yapısal bozulmayı
kesin yakalar.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fitz  # noqa: E402

from app.services import barcode128 as bc, label_pdf  # noqa: E402

GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


class _Sip:
    order_number = "11658"; name = "#11658"; barkod_kodu = None
    customer_name = "Ayşe Yılmaz"
    raw = {"shipping_address": {"first_name": "Ayşe", "last_name": "Yılmaz",
           "address1": "Test Cad. No:1", "city": "Yenimahalle",
           "province": "Ankara", "phone": "05001112233"}}


_DESEN = {p: i for i, p in enumerate(bc._PATTERNS)}


def _rasterle(kod: str, dpi: int = 203) -> tuple[bytes, int, int]:
    """Etiketi ZPL yolunun YAPTIĞININ AYNISIYLA rasterleştir (100x150 mm)."""
    pdf = label_pdf.render_label_pdf(_Sip(), "BERNZ", barkod_kodu=kod,
                                     kargo_firma="Sürat Kargo")
    sayfa = fitz.open(stream=pdf, filetype="pdf")[0]
    ox = (100 / 25.4 * dpi) / sayfa.rect.width
    oy = (150 / 25.4 * dpi) / sayfa.rect.height
    pix = fitz.Pixmap(fitz.csGRAY, sayfa.get_pixmap(matrix=fitz.Matrix(ox, oy), alpha=False))
    return pix.samples, pix.width, pix.height


def _koşular(ham, w, y):
    out, son, n = [], None, 0
    for x in range(w):
        siyah = ham[y * w + x] < 128
        if siyah == son:
            n += 1
        else:
            if son is not None:
                out.append((son, n))
            son, n = siyah, 1
    out.append((son, n))
    return out


def coz(kod: str, dpi: int = 203) -> str | None:
    """Rasterleşmiş etiketten barkodu ÇÖZ. Başarısızsa None."""
    ham, w, h = _rasterle(kod, dpi)
    # En çok geçiş olan satır = barkodun içi
    en_iyi, en_cok = None, 0
    for y in range(int(h * 0.5), h - 3):
        k = len(_koşular(ham, w, y))
        if k > en_cok:
            en_cok, en_iyi = k, y
    if en_iyi is None:
        return None
    kos = _koşular(ham, w, en_iyi)
    while kos and not kos[0][0]:
        kos.pop(0)
    while kos and not kos[-1][0]:
        kos.pop()
    genisler = [n for _, n in kos]
    if len(genisler) < 20:
        return None
    modul = sum(genisler) / bc.toplam_modul(kod)
    # Sembollere böl: stop 7 eleman, diğerleri 6
    semboller, i = [], 0
    while i < len(genisler):
        uzunluk = 7 if len(genisler) - i == 7 else 6
        if len(genisler) - i < uzunluk:
            return None
        parca = "".join(str(max(1, round(g / modul))) for g in genisler[i:i + uzunluk])
        if parca not in _DESEN:
            return None
        semboller.append(_DESEN[parca])
        i += uzunluk
    if len(semboller) < 4 or semboller[-1] != bc.STOP:
        return None
    start, veri, kontrol = semboller[0], semboller[1:-2], semboller[-2]
    if (start + sum(i * d for i, d in enumerate(veri, 1))) % 103 != kontrol:
        return None   # kontrol basamağı tutmuyor
    if start == bc.START_C:
        return "".join(f"{d:02d}" for d in veri)
    return "".join(chr(d + 32) for d in veri)


print("\n── 1. gerçek takip numarası (14 hane) ──")
KOD = "40105913453122"
es("çözülen kod = basılan kod", KOD, coz(KOD))
es("Code128-C seçildi", bc.START_C, bc.kodlari_uret(KOD)[0])

print("\n── 2. farklı numaralar ──")
for k in ("33183188161612", "20823610230551", "79348435213106"):
    es(f"{k} çözüldü", k, coz(k))

print("\n── 3. sipariş numarası gibi harfli kod (Code128-B) ──")
es("A1-B2 çözüldü", "A1-B2", coz("A1-B2"))
es("Code128-B seçildi", bc.START_B, bc.kodlari_uret("A1-B2")[0])

print("\n── 4. yazıcı çözünürlüğünde bozulmuyor ──")
for dpi in (203, 300, 600):
    es(f"{dpi} dpi'da çözülüyor", KOD, coz(KOD, dpi))

print("\n── 5. çubuk ÇERÇEVESİ geri gelirse test yakalar ──")
kaynak = (Path(__file__).resolve().parent.parent
          / "app/services/label_pdf.py").read_text(encoding="utf-8")
es("barkod çubuğu çerçevesiz çiziliyor", True,
   "color=None, fill=(0, 0, 0), width=0" in kaynak)

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
