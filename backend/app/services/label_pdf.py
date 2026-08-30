"""
Kargo etiketi PDF'i — mağaza adı + sipariş no + alıcı adresi + TARANABİLİR
Code 128 barkod.

Barkod eskiden '*KOD*' diye düz metin yazılıyordu (okutulamıyordu); artık
gerçek Code 128-B çubukları çiziliyor. Kendi kargo anlaşmasıyla çalışırken
paketin üzerine yapıştırılan etiket budur.

PyMuPDF base14 fontu Türkçe ş/ğ/İ desteklemediği için METİN ASCII'ye çevrilir;
barkodun kendisi zaten ASCII (Code128-B).
"""
from __future__ import annotations

import io
import os

import fitz  # PyMuPDF

from app.services import barcode128

CM = 28.3464567

_TR = str.maketrans({
    "ş": "s", "Ş": "S", "ğ": "g", "Ğ": "G", "İ": "I", "ı": "i",
    "ö": "o", "Ö": "O", "ü": "u", "Ü": "U", "ç": "c", "Ç": "C",
})


def _a(s) -> str:
    return (s or "").translate(_TR)


# Etiket şablonu — panelden düzenlenir (Tenant.etiket_ayarlari).
# Buradaki değerler VARSAYILAN; kaydedilmemiş her alan buradan gelir.
VARSAYILAN_AYARLAR: dict = {
    "magaza_punto": 13.0,     # üstteki mağaza adı
    "alici_punto": 14.0,      # ALICI adı
    "adres_punto": 11.0,      # sokak satırları (yer darsa otomatik küçülür)
    "ilce_punto": 13.0,       # ilçe / il
    "telefon_punto": 11.0,
    "takip_punto": 17.0,      # barkodun altındaki numara
    "barkod_min_cm": 2.0,
    "barkod_max_cm": 4.2,
    "siparis_no_goster": True,
    "ilce_il_goster": True,
    "telefon_goster": True,
    "kargo_firma_goster": True,
    "gonderici_metni": "",    # opsiyonel: iade adresi / gönderici satırı
    "not_metni": "",          # opsiyonel: "Kırılacak eşya" gibi serbest not
}

_SAYISAL_SINIR = {
    "magaza_punto": (7, 24), "alici_punto": (8, 26), "adres_punto": (7, 18),
    "ilce_punto": (8, 22), "telefon_punto": (7, 18), "takip_punto": (9, 30),
    "barkod_min_cm": (1.0, 5.0), "barkod_max_cm": (1.5, 7.0),
}


def ayarlari_birlestir(kaydedilen: dict | None) -> dict:
    """Kaydedilen ayarları varsayılanların ÜSTÜNE koy ve SINIRLA.

    Sınırlama şart: punto 200 yapılırsa etiket kullanılamaz hale gelir ve bunu
    ancak baskıda fark ederiz. Bilinmeyen anahtarlar atılır.
    """
    out = dict(VARSAYILAN_AYARLAR)
    for k, v in (kaydedilen or {}).items():
        if k not in VARSAYILAN_AYARLAR:
            continue
        if k in _SAYISAL_SINIR:
            try:
                alt, ust = _SAYISAL_SINIR[k]
                out[k] = max(alt, min(ust, float(v)))
            except (TypeError, ValueError):
                pass
        elif isinstance(VARSAYILAN_AYARLAR[k], bool):
            out[k] = bool(v)
        else:
            out[k] = str(v or "")[:120]
    if out["barkod_max_cm"] < out["barkod_min_cm"]:
        out["barkod_max_cm"] = out["barkod_min_cm"]
    return out


def _buyut(s: str) -> str:
    """Türkçe büyük harf. Python'un .upper()'ı 'i' harfini 'I' yapıyor;
    doğrusu 'İ'. Etikette 'YENIMAHALLE'/'IZMIR' gibi yanlış il-ilçe adları
    çıkıyordu — kargo ayrımını yapan bilgi bu, yanlış yazılmamalı.
    """
    return (s or "").replace("i", "İ").replace("ı", "I").upper()


def _font_yollari() -> tuple[str, str] | None:
    """(normal, kalın) TTF yolu. Bulunamazsa None → base14 + ASCII'ye düşülür.

    PyMuPDF'in base14 'helv' fontu ş/ğ/İ/ı basmıyor ('?' çiziyor); Türkçe bir
    kargo etiketinde alıcı adının bozulması kabul edilemez. Sistemde gerçek bir
    TTF varsa gömülür.
    """
    adaylar = [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),          # VPS
        ("/System/Library/Fonts/Supplemental/Arial.ttf",
         "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),             # macOS
        ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ]
    for n, k in adaylar:
        if os.path.exists(n):
            return n, (k if os.path.exists(k) else n)
    return None


def _extract_address(order) -> dict:
    """Adresi PARÇALI döndür: sokak satırları ayrı, ilçe/il ayrı.

    İlçe/il etikette büyük basılır — kargo ayrımını yapan bilgi odur.
    """
    raw = order.raw or {}
    sa = raw.get("shipping_address")
    if sa is None and isinstance(raw.get("order"), dict):
        sa = raw["order"].get("shipping_address")
    out = {"ad": "", "sokak": [], "ilce_il": "", "posta": "", "telefon": ""}
    if isinstance(sa, dict):
        out["ad"] = (sa.get("name") or " ".join(
            filter(None, [sa.get("first_name"), sa.get("last_name")])) or "").strip()
        for k in ("address1", "address2"):
            if (sa.get(k) or "").strip():
                out["sokak"].append(sa[k].strip())
        ilce = (sa.get("city") or "").strip()
        il = (sa.get("province") or "").strip()
        out["ilce_il"] = " / ".join([x for x in (ilce, il) if x]) or il or ilce
        out["posta"] = (sa.get("zip") or "").strip()
        out["telefon"] = str(sa.get("phone") or "").strip()
    elif isinstance(sa, str):
        out["sokak"] = [ln for ln in sa.splitlines() if ln.strip()]
    if not out["ad"]:
        out["ad"] = (getattr(order, "customer_name", "") or "—").strip()
    return out


def _sar(metin: str, font, boyut: float, genislik: float) -> list[str]:
    """Metni ÖLÇEREK satırlara böl.

    Kritik: insert_textbox sığmayan metni kırpmaz, HİÇ YAZMAZ. Eski etikette
    33 karakterden uzun sokak adresleri bu yüzden sessizce kayboluyordu —
    yani paketin üstünde adres yoktu. Artık satırları biz hesaplıyoruz.
    """
    kelimeler = (metin or "").split()
    satirlar: list[str] = []
    simdi = ""
    for k in kelimeler:
        aday = (simdi + " " + k).strip()
        if font.text_length(aday, fontsize=boyut) <= genislik or not simdi:
            simdi = aday
        else:
            satirlar.append(simdi)
            simdi = k
    if simdi:
        satirlar.append(simdi)
    return satirlar or [""]


def render_label_pdf(order, store_name: str | None = None,
                     barkod_kodu: str | None = None,
                     kargo_firma: str | None = None,
                     ayarlar: dict | None = None) -> bytes:
    """10x15 cm kargo etiketi.

    barkod_kodu verilirse siparişin kendi kodu YERİNE o basılır. Sürat DOĞRUDAN
    gönderilerinde Sürat barkod görselini döndürmüyor ama gerçek takip
    numarasını veriyor; o numara Sürat'ın sisteminde KAYITLI olduğu için
    Code128 olarak basıldığında şubede karşılığı vardır.

    Yerleşim: barkod bloğu SAYFANIN ALTINA sabitlenir, adres üstten akar.
    Böylece adres uzunluğu ne olursa olsun etiket dengeli durur ve barkodun
    yeri sabit kalır (okutan kişi her zaman aynı yere bakar).
    """
    A = ayarlari_birlestir(ayarlar)
    W, H = 10 * CM, 15 * CM
    m = 0.55 * CM
    ic = W - 2 * m

    doc = fitz.open()
    pg = doc.new_page(width=W, height=H)

    yollar = _font_yollari()
    if yollar:
        pg.insert_font(fontname="F", fontfile=yollar[0])
        pg.insert_font(fontname="FB", fontfile=yollar[1])
        FN, FK = "F", "FB"
        f_n, f_k = fitz.Font(fontfile=yollar[0]), fitz.Font(fontfile=yollar[1])
        d = lambda t: t or ""                     # noqa: E731  (Türkçe korunur)
    else:
        FN, FK = "helv", "hebo"
        f_n, f_k = fitz.Font("helv"), fitz.Font("hebo")
        d = _a                                     # base14: ASCII'ye düş

    def yaz(metin, boyut, y, *, kalin=False, ortala=False, renk=(0, 0, 0)):
        """Tek satır yaz, YENİ y döndür. Ölçülerek yazılır — sessiz kayıp yok."""
        f = f_k if kalin else f_n
        t = d(metin)
        x = m + (ic - f.text_length(t, fontsize=boyut)) / 2 if ortala else m
        pg.insert_text((x, y + boyut), t, fontsize=boyut,
                       fontname=(FK if kalin else FN), color=renk)
        return y + boyut * 1.32

    a = _extract_address(order)

    kod = str(barkod_kodu or order.barkod_kodu or order.order_number or "").strip()
    # Barkod yüksekliği adres bittikten SONRA hesaplanır: kısa adreste barkod
    # büyür, uzun adreste küçülür. Böylece ortada ölü boşluk kalmaz ve barkod
    # her zaman olabildiğince büyük — okutması kolay — olur.
    firma_var = bool(kargo_firma) and A["kargo_firma_goster"]
    alt_metin_h = A["takip_punto"] * 1.32 + 4 + (10 * 1.32 if firma_var else 0)
    if A["not_metni"]:
        alt_metin_h += 10 * 1.32

    # ── ÜST: gönderici + sipariş no ──────────────────────────────────────
    y = m
    mp = A["magaza_punto"]
    magaza = d(store_name or "BASKICI")
    pg.insert_text((m, y + mp), magaza, fontsize=mp, fontname=FK)
    if A["siparis_no_goster"]:
        sip = d("#" + str(order.order_number or ""))
        pg.insert_text((W - m - f_k.text_length(sip, fontsize=mp), y + mp),
                       sip, fontsize=mp, fontname=FK)
    y += mp * 1.5
    pg.draw_line(fitz.Point(m, y), fitz.Point(W - m, y), width=1.1)
    y += 10

    # ── ALICI ────────────────────────────────────────────────────────────
    pg.insert_text((m, y + 7), "ALICI", fontsize=7, fontname=FN, color=(.45, .45, .45))
    y += 12
    y = yaz(_buyut(a["ad"]) if a["ad"] else "—", A["alici_punto"], y, kalin=True)
    y += 3

    # Sokak satırları — SARILARAK, asla düşmeden. Yer darsa punto küçülür.
    bosluk = (H - m - alt_metin_h - A["barkod_min_cm"] * CM - 14) - y - 46
    _tab = A["adres_punto"]
    for boyut in (_tab, _tab - .5, _tab - 1, _tab - 1.5, _tab - 2, _tab - 2.5, _tab - 3):
        boyut = max(7.0, boyut)
        satirlar = []
        for parca in a["sokak"]:
            satirlar += _sar(d(parca), f_n, boyut, ic)
        if len(satirlar) * boyut * 1.3 <= bosluk or boyut == 8:
            break
    for ln in satirlar:
        y = yaz(ln, boyut, y)

    y += 6
    # İlçe / il — kargo ayrımını yapan bilgi, en görünür olan bu olmalı
    ilce_il = _buyut(a["ilce_il"])
    if a["posta"]:
        ilce_il = f'{ilce_il}  {a["posta"]}'
    if ilce_il.strip() and A["ilce_il_goster"]:
        y = yaz(ilce_il, A["ilce_punto"], y, kalin=True)
    if a["telefon"] and A["telefon_goster"]:
        y = yaz("Tel: " + a["telefon"], A["telefon_punto"], y)
    if A["gonderici_metni"]:
        y += 4
        y = yaz("Gonderici: " + A["gonderici_metni"] if not yollar
                else "Gönderici: " + A["gonderici_metni"], 9, y, renk=(.4, .4, .4))

    # ── ALT BLOK ─────────────────────────────────────────────────────────
    # Kalan dikey alanı barkoda ver (2.0–4.2 cm arası).
    kalan = (H - m - alt_metin_h) - (y + 14)
    bar_h = min(A["barkod_max_cm"] * CM, max(A["barkod_min_cm"] * CM, kalan))
    alt_y = H - m - alt_metin_h - bar_h
    pg.draw_line(fitz.Point(m, alt_y - 10), fitz.Point(W - m, alt_y - 10),
                 width=0.8, color=(.6, .6, .6))
    by = alt_y
    if kod:
        try:
            genislikler = barcode128.pattern_widths(kod)
            sessiz = 10
            modul = ic / (sum(genislikler) + 2 * sessiz)
            x = m + sessiz * modul
            bar = True
            for g in genislikler:
                gen = g * modul
                if bar:
                    pg.draw_rect(fitz.Rect(x, by, x + gen, by + bar_h),
                                 color=(0, 0, 0), fill=(0, 0, 0))
                x += gen
                bar = not bar
            by += bar_h + 4
            by = yaz(kod, A["takip_punto"], by, kalin=True, ortala=True)
        except barcode128.BarcodeError:
            by = yaz("BARKOD URETILEMEDI", 12, by, kalin=True, ortala=True)
    else:
        by = yaz("BARKOD YOK", 12, by, kalin=True, ortala=True)
    if firma_var:
        by = yaz(_buyut(kargo_firma), 10, by, ortala=True, renk=(.35, .35, .35))
    if A["not_metni"]:
        yaz(A["not_metni"], 10, by, ortala=True, kalin=True)

    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()
