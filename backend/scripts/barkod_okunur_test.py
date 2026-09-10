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

# ─────────────────────────────────────────────────────────────────────────
# ZPL yolu: barkod RASTER DEĞİL, yazıcının kendi ^BC komutu
# ─────────────────────────────────────────────────────────────────────────
print("\n── 6. rasterleştirmenin ÇUBUK GENİŞLİĞİ HATASI ──")
# Ölçüm: barkod etiketle birlikte rasterleştirilince her çubuk kenarı en yakın
# noktaya yuvarlanıyor. Code128'in okuma toleransı modülün ~%25'i; ölçülen
# sapma buna DAYANIYOR ve termal baskının çubuk şişmesi eklenince okunmuyor.
# Bu bölüm hatayı ölçer ve ^BC yolunun onu SIFIRLADIĞINI gösterir.
import re  # noqa: E402


def _bitmap(zpl):
    m = re.search(r"\^GFA,(\d+),\d+,(\d+),([0-9A-F]+)\^FS", zpl)
    ham, sb = bytes.fromhex(m.group(3)), int(m.group(2))
    return ham, sb, int(re.search(r"\^PW(\d+)", zpl).group(1)), int(m.group(1)) // sb


def _kosu(ham, sb, w, y):
    out, son, n = [], None, 0
    for x in range(w):
        s = bool((ham[y * sb + (x >> 3)] >> (7 - (x & 7))) & 1)
        if s == son:
            n += 1
        else:
            if son is not None:
                out.append(n)
            son, n = s, 1
    out.append(n)
    return out


def raster_sapmasi(kod, w_mm, h_mm, dpi=203):
    """Rasterleşmiş çubukların ideal genişlikten EN BÜYÜK sapması (modül oranı)."""
    from app.services import zpl_label
    pdf = label_pdf.render_label_pdf(_Sip(), "BERNZ", barkod_kodu=kod,
                                     kargo_firma="Sürat Kargo")
    z = zpl_label.pdf_to_zpl(pdf, dpi=dpi, w_mm=w_mm, h_mm=h_mm, doldur=True)
    ham, sb, w, h = _bitmap(z)
    ideal = bc.pattern_widths(kod)
    en_iyi, en_cok = None, 0
    for y in range(int(h * 0.5), h - 3):
        k = _kosu(ham, sb, w, y)
        if len(k) > en_cok:
            en_cok, en_iyi = len(k), y
    k = _kosu(ham, sb, w, en_iyi)
    g = k[1:-1] if len(k) == len(ideal) + 2 else k
    if len(g) != len(ideal):
        return None
    modul = sum(g) / sum(ideal)
    return max(abs(gi - ii * modul) / modul for gi, ii in zip(g, ideal))


_sapma = raster_sapmasi(KOD, 100, 150)
es("raster sapması ölçülebildi", True, _sapma is not None)
print(f"      · rasterde en büyük çubuk sapması: %{_sapma * 100:.0f} "
      f"(Code128 toleransı ~%25)")
es("raster sapması TOLERANSA DAYANIYOR (bu yüzden ^BC'ye geçildi)", True,
   _sapma > 0.15)

print("\n── 7. ^BC: modül TAM SAYI nokta, sapma yok ──")
from app.services import zpl_label as _zl  # noqa: E402

_BC = re.compile(r"\^BY(\d+)\^FO(\d+),(\d+)\^BCN,(\d+),N,N,N,N\^FD(.+?)\^FS")


def _bc_zpl(kod, w_mm, h_mm, dpi=203):
    yer = {}
    pdf = label_pdf.render_label_pdf(_Sip(), "BERNZ", barkod_kodu=kod,
                                     barkod_yerlesim=yer, kargo_firma="Sürat Kargo")
    return _zl.pdf_to_zpl(pdf, dpi=dpi, w_mm=w_mm, h_mm=h_mm, doldur=True,
                          barkod=yer or None), yer


for _w, _h, _dpi in ((100, 150, 203), (80, 100, 203), (67, 100, 203), (100, 150, 300)):
    _z, _yer = _bc_zpl(KOD, _w, _h, _dpi)
    _m = _BC.search(_z)
    _ad = f"{_w}x{_h}mm@{_dpi}"
    if not _m:
        es(f"{_ad} ^BC üretildi", True, False)
        continue
    _by, _x, _y, _yuk, _veri = (int(_m.group(1)), int(_m.group(2)), int(_m.group(3)),
                                int(_m.group(4)), _m.group(5))
    _pw = int(re.search(r"\^PW(\d+)", _z).group(1))
    _ll = int(re.search(r"\^LL(\d+)", _z).group(1))
    _gen = _by * bc.toplam_modul(KOD)
    es(f"{_ad}: veri = alt küme C + kod", ">;" + KOD, _veri)
    es(f"{_ad}: modül ≥ 0.25 mm (okuyucu alt sınırı)", True, _by / _dpi * 25.4 >= 0.25)
    es(f"{_ad}: etikete sığıyor", True, _x >= 0 and _x + _gen <= _pw and _y + _yuk <= _ll)
    # Çubuklar rasterde OLMAMALI: iki kez basılırsa üst üste biner.
    _ham, _sb, _bw, _bh = _bitmap(_z)
    _satir = _y + _yuk // 2
    _siyah = sum(bin(_ham[_satir * _sb + i]).count("1") for i in range(_sb))
    es(f"{_ad}: rasterde çubuk YOK (çift baskı olmaz)", 0, _siyah)

print("\n── 8. alt küme seçimi ^BC ile barcode128 AYNI ──")
for _k, _beklenen in (("40105913453122", ">;"), ("4010591345312", ">:"), ("A1-B2", ">:")):
    _z, _ = _bc_zpl(_k, 100, 150)
    _m = _BC.search(_z)
    es(f"{_k} → {_beklenen}", _beklenen + _k, _m.group(5) if _m else None)

print("\n── 9. ZPL'i bozacak karakter reddediliyor ──")
for _kotu in ("12^XA34", "12~DG34", "12>;34"):
    try:
        _bc_zpl(_kotu, 100, 150)
        _sonuc = "GECTI"
    except _zl.ZplError:
        _sonuc = "REDDEDILDI"
    es(f"{_kotu!r} reddedildi", "REDDEDILDI", _sonuc)

print("\n── 10. barkod kodundaki boşluklar temizleniyor ──")
# Elle "4010 5913 4531 22" girilirse kod rakam sayılmaz, Code128-B'ye düşer ve
# okuyucu boşluklu metin verir; karşı sistem bunu SAYI kabul etmez.
_z, _yer = _bc_zpl("4010 5913 4531 22", 100, 150)
es("boşluklar atıldı", "40105913453122", _yer.get("kod"))
es("boşluksuz kod alt küme C'ye düştü", ">;40105913453122", _BC.search(_z).group(5))

print("\n── 11. 300 dpi etiket artık reddedilmiyor ──")
# AZAMI_NOKTA 203 dpi'ya göre sabitti; 300 dpi'lık GX430t'de geçerli etiketler
# "çok geniş" diye reddediliyordu.
es("300 dpi azami nokta 4 inç karşılığı", True, _zl.azami_nokta(300) >= 1200)
es("203 dpi eski sınır korunuyor", True, _zl.azami_nokta(203) >= 832)

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
