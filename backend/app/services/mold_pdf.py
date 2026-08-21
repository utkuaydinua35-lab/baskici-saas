"""
Kalıp PDF render motoru v7 — kullanıcının şablon kutularına KALICI vektör clip ile basar.

jsx (bernz_unified_script_v5) mantığı birebir:
- Tasarım, modelin gerçek kılıf ölçüsünde (gizli MODEL_SPECS, -trim), şablon
  kutusunun SAĞ-ALT köşesine yaslanır.
- Köşe yuvarlatma: her tasarım, kendi yuvarlak-dikdörtgen clip path'iyle (W n)
  geçici sayfada hazırlanır, KALICI hale getirilip (tobytes -> tekrar aç) ana
  tablaya gömülür. Böylece çoklu slotta frame-eşleşme kayması OLMAZ; her tasarım
  bağımsız clip'lenir. Köşeler pürüzsüz vektör, modelin radius'u kadar.
- radius=0 modeller (S23/S24 Ultra vb.) keskin kalır.
- Beyaz zemin YOK -> boş alan ve köşe payları şeffaf (basılmaz, boya maliyeti yok).

Gizli ölçü modülü yalnızca burada okunur; ölçüler API'den dışa verilmez.
"""
from __future__ import annotations

import io
import os
from pathlib import Path

import fitz  # PyMuPDF

from app.services._private import case_dimensions as cd
from app.services.storage import STORAGE_ROOT

CM_TO_PT = 28.3464567


def _abs_path(relative_path: str) -> Path:
    return STORAGE_ROOT / relative_path


def _ordered_slots(items, cols, rows):
    """Web önizleme (MoldDetailPage / Baskıcı Paneli) ile BİREBİR aynı yerleşim.
    Web: hücre idx (0=sol-üst .. N-1=sağ-alt) -> slotNo = N - idx -> slot_index = N-1 - idx.
    Yani boxes[idx] kutusuna slot_index == (N-1 - idx) olan item yerleşir.
    Böylece PDF == web == fiziksel kalıp (ters simetri düzeltildi)."""
    n = cols * rows
    # slot_index -> item haritası (slot_index'i olanlar kesin yerine oturur)
    by_si = {}
    no_si = []
    for it in items:
        si = it.get("slot_index")
        if isinstance(si, int) and 0 <= si < n:
            by_si[si] = it
        else:
            no_si.append(it)

    slots = [None] * n
    for idx in range(n):
        want_si = (n - 1) - idx
        if want_si in by_si:
            slots[idx] = by_si[want_si]

    # slot_index'i olmayan (eski/eksik veri) item'lari bos kutulara sirayla koy
    if no_si:
        empties = [i for i in range(n) if slots[i] is None]
        for it, i in zip(no_si, empties):
            slots[i] = it
    return slots


def _placement_rect(box, model, spec=None):
    """Şablon kutusu içinde modelin gerçek kılıf ölçüsünde rect + radius_pt.
    Tasarım kutunun SAĞ-ALT köşesine yaslanır. Dönüş: (fitz.Rect, radius_pt) | None.

    spec: (w_cm, h_cm, r_cm) — çağıran DB'den çözüp geçirir (panelden EKLENEN
    modeller yalnızca DB'de; burada baseline'a bakmak onları göremiyordu ve slot
    sessizce BOŞ basılıyordu). Geçilmezse baseline kataloğa düşülür.
    """
    if spec is None:
        spec = cd.get_spec(model)
    if not spec or spec[0] is None or spec[1] is None:
        return None
    w_cm, h_cm, r_cm = spec
    # TRIM kaldırıldı: gerçek kılıf ölçüsünde basılır (8.0 × 16.25 gibi).
    w_pt = max(0.0, w_cm) * CM_TO_PT
    h_pt = max(0.0, h_cm) * CM_TO_PT
    bw, bh = box["w"], box["h"]
    scale = min(1.0, bw / w_pt if w_pt else 1.0, bh / h_pt if h_pt else 1.0)
    w_pt *= scale
    h_pt *= scale
    r_pt = r_cm * CM_TO_PT * scale
    x1 = box["x0"] + bw
    y1 = box["y0"] + bh
    rect = fitz.Rect(x1 - w_pt, y1 - h_pt, x1, y1)
    return rect, r_pt


# Bu boyutun ustundeki PDF kaynaklar VEKTOR kopyalanmak yerine baski
# cozunurlugunde raster'a cevrilir. Olcum: 6-72 MB'lik saf vektor tasarimlarda
# show_pdf_page slot basina 5-82 sn suruyor (22 slotluk kalip 378 sn -> 524).
# Ayni boyutta ama icinde gomulu GORSEL olan PDF 0.09 sn. 7.9x17 cm alanda
# 300 DPI ustundeki vektor detayi zaten kagida cikmiyor.
RASTER_ESIK_MB = float(os.environ.get("MOLD_PDF_RASTER_MB", "3"))
# Bu boyutun ustunde gomulu gorsel olsa DA rasterlestirilir.
RASTER_ZORUNLU_MB = float(os.environ.get("MOLD_PDF_RASTER_ZORUNLU_MB", "20"))


def _raster_onbellek_yolu(src_path: Path, uzanti: str) -> Path:
    """Tasarım rasterinin önbellek yolu — kaynak dosyanın kimliğine bağlı.

    Anahtar dosya adı + boyut + mtime: tasarım DEĞİŞİRSE anahtar da değişir,
    bayat raster kullanılmaz.
    """
    st = src_path.stat()
    ad = f"{src_path.stem}_{st.st_size}_{int(st.st_mtime)}.{uzanti}"
    return STORAGE_ROOT / "cache" / "tasarim_raster" / ad


def _tasarim_rasteri(src_path: Path) -> Path | None:
    """Tasarımın baskı çözünürlüğündeki rasteri — BİR KEZ üretilir, diske yazılır.

    Neden: bu tasarımlar patolojik derecede karmaşık vektörler (ölçümde slot
    başına 6-19 sn). Maliyet show_pdf_page'e değil, yolların ÇİZİLMESİNE ait —
    get_pixmap de aynı işi yapıyor, o yüzden rasterleştirme tek başına
    yetmedi (378 sn -> 219 sn). Aynı tasarım birden çok slotta ve birden çok
    kalıpta geçtiği için bedeli bir kez ödemek doğru çözüm: ilk üretimden
    sonra her kalıp bu rasteri saniyenin altında gömer.
    """
    try:
        from PIL import Image
    except Exception:  # noqa: BLE001
        return None
    try:
        for uz in ("jpg", "png"):
            hazir = _raster_onbellek_yolu(src_path, uz)
            if hazir.exists():
                return hazir

        src = fitz.open(str(src_path))
        try:
            if src.page_count == 0:
                return None
            sayfa = src[0]
            # Tasarımın KENDİ fiziksel ölçüsünde 300 DPI — slottan bağımsız,
            # böylece tek raster tüm slot ölçülerine yeter.
            olcek = BASKI_DPI / 72.0
            pix = sayfa.get_pixmap(matrix=fitz.Matrix(olcek, olcek), alpha=True)
            im = Image.frombytes("RGBA", (pix.width, pix.height), pix.samples)
        finally:
            src.close()

        saydam = im.getchannel("A").getextrema()[0] != 255
        uz = "png" if saydam else "jpg"
        hedef = _raster_onbellek_yolu(src_path, uz)
        hedef.parent.mkdir(parents=True, exist_ok=True)
        gecici = hedef.with_suffix(hedef.suffix + ".tmp")
        if saydam:
            im.save(gecici, format="PNG", optimize=True)
        else:
            im.convert("RGB").save(gecici, format="JPEG", quality=92, optimize=True)
        gecici.replace(hedef)      # atomik: yarim dosya okunmasin
        return hedef
    except Exception:  # noqa: BLE001
        return None


def onbellek_hazirla(rel_path: str) -> bool:
    """Tasarımın slot rasterini ÖNCEDEN üret (yükleme sonrası arka plan işi).

    Kalıp üretimi sırasında ödenen 6-19 sn'lik çizim maliyeti böylece yüklemeye
    kayar; kalıp PDF'i her zaman hazır rasteri gömer.
    """
    try:
        p = _abs_path(rel_path)
        if not p.exists() or p.suffix.lower() != ".pdf":
            return False
        if p.stat().st_size / 1024 / 1024 <= RASTER_ESIK_MB:
            return False        # küçük vektör zaten hızlı, raster'a çevrilmiyor
        return _tasarim_rasteri(p) is not None
    except Exception:  # noqa: BLE001
        return False


def _gomulu_gorsel_var(src_path) -> bool:
    """Sayfada gomulu raster gorsel var mi. Acma maliyeti olcumde 0.00 sn."""
    try:
        src = fitz.open(str(src_path))
        try:
            return bool(src.page_count and src[0].get_images(full=False))
        finally:
            src.close()
    except Exception:  # noqa: BLE001
        return False


def _raster_sayfa(src_path, w_pt, h_pt) -> bytes | None:
    """Agir PDF'i hedef olcude raster'a cevir. Sikistirilmis bytes ya da None.

    Pixmap'i dogrudan gommek KAYIPSIZ (PNG) oluyor ve slot basina ~2 MB
    uretiyordu. Tamamen opak sayfalar JPEG'e, saydamlik tasiyanlar PNG'ye
    yazilir — saydam tasarimlarin zemini beyaza donmesin.
    """
    try:
        from PIL import Image
    except Exception:  # noqa: BLE001
        return None
    try:
        src = fitz.open(str(src_path))
        try:
            if src.page_count == 0:
                return None
            sayfa = src[0]
            hedef_w = max(1, int(round(w_pt / 72.0 * BASKI_DPI)))
            hedef_h = max(1, int(round(h_pt / 72.0 * BASKI_DPI)))
            # keep_proportion=False ile ayni davranis: tam hedefe esnet
            m = fitz.Matrix(hedef_w / sayfa.rect.width, hedef_h / sayfa.rect.height)
            pix = sayfa.get_pixmap(matrix=m, alpha=True)
            im = Image.frombytes("RGBA", (pix.width, pix.height), pix.samples)
        finally:
            src.close()
        buf = io.BytesIO()
        alfa = im.getchannel("A")
        if alfa.getextrema()[0] == 255:          # hicbir yeri saydam degil
            im.convert("RGB").save(buf, format="JPEG", quality=92, optimize=True)
        else:
            im.save(buf, format="PNG", optimize=True)
        return buf.getvalue()
    except Exception:  # noqa: BLE001
        return None      # rasterlestiremezsek vektor yola dusulur


def _clip_ve_kapat(tmp, pg, w_pt, h_pt, radius):
    """Yuvarlak köşe VEKTÖR clip'i uygula + kalıcı hale getir. Dönüş: pdf bytes.

    Vektör ve raster yol AYNI yuvarlatmayı kullansın diye ayrıldı; iki yerde
    kopya durursa biri düzeltilip diğeri unutulur.
    """
    if radius > 0:
        rr = min(radius, w_pt / 2, h_pt / 2)
        k = 0.5523 * rr  # bezier kappa = matematiksel çeyrek daire
        x0, x1 = 0.0, w_pt
        pb, pt = 0.0, h_pt  # PDF: alt=0, üst=h_pt (bu sayfa için)
        ops = (
            f"{x0+rr:.3f} {pb:.3f} m {x1-rr:.3f} {pb:.3f} l "
            f"{x1-rr+k:.3f} {pb:.3f} {x1:.3f} {pb+rr-k:.3f} {x1:.3f} {pb+rr:.3f} c "
            f"{x1:.3f} {pt-rr:.3f} l {x1:.3f} {pt-rr+k:.3f} {x1-rr+k:.3f} {pt:.3f} {x1-rr:.3f} {pt:.3f} c "
            f"{x0+rr:.3f} {pt:.3f} l {x0+rr-k:.3f} {pt:.3f} {x0:.3f} {pt-rr+k:.3f} {x0:.3f} {pt-rr:.3f} c "
            f"{x0:.3f} {pb+rr:.3f} l {x0:.3f} {pb+rr-k:.3f} {x0+rr-k:.3f} {pb:.3f} {x0+rr:.3f} {pb:.3f} c h W n "
        )
        # Clip'i içerik akışının BAŞINA koy: baştaki "W n" sonraki tüm çizimi kapsar.
        # (Eskiden regex ile aranıp araya sokuluyordu; desen tutmazsa yuvarlatma
        # SESSİZCE atlanıp köşeler keskin kalıyordu.)
        xref = pg.get_contents()[0]
        c = tmp.xref_stream(xref).decode("latin-1")
        tmp.update_stream(xref, (ops + c).encode("latin-1"))

    out = tmp.tobytes(garbage=4, deflate=True)  # clip KALICI
    tmp.close()
    return out


def _make_clipped_design(src_path, w_pt, h_pt, radius):
    """Tasarımı w×h tek sayfaya koy, yuvarlak köşe VEKTÖR clip uygula, KALICI
    hale getir (tobytes). Dönüş: pdf bytes. Köşe payı şeffaf, pürüzsüz."""
    tmp = fitz.open()
    pg = tmp.new_page(width=w_pt, height=h_pt)
    # Rasterlestirme karari OLCUME dayaniyor: yavas kaynaklarin hepsi SAF VEKTOR
    # (13 MB -> 18 sn), hizli olanin icinde gomulu gorsel vardi (10 MB -> 0.09 sn).
    # Yani maliyeti dosya boyutu degil, yol karmasikligi belirliyor. Gomulu
    # gorseli olan PDF vektor yolda kalir; cok buyukse (>ZORUNLU_MB) yine
    # rasterlestirilir, o boyut butun halinde kopyalanmamali.
    _raster = None
    try:
        _mb = src_path.stat().st_size / 1024 / 1024
        if _mb > RASTER_ESIK_MB:
            if _mb > RASTER_ZORUNLU_MB or not _gomulu_gorsel_var(src_path):
                _raster = _tasarim_rasteri(src_path)
    except OSError:
        _raster = None
    if _raster is not None:
        pg.insert_image(pg.rect, filename=str(_raster), keep_proportion=False)
        return _clip_ve_kapat(tmp, pg, w_pt, h_pt, radius)

    src = fitz.open(str(src_path))
    # keep_proportion=False: tasarım rect'i tam doldurur, alt/üst boşluk olmaz
    # (oran sapması olsa bile clip alanını tam kaplar). Aksi halde yuvarlak clip'imiz
    # dış katmanda kalır, tasarım iç katmanda kayıp, "alt birden bitiyor" hatası olur.
    pg.show_pdf_page(pg.rect, src, 0, keep_proportion=False)
    src.close()

    return _clip_ve_kapat(tmp, pg, w_pt, h_pt, radius)


# Baski cozunurlugu. Slotun fiziksel olcusu bunu belirler; uzerindeki her piksel
# kagida ASLA cikmaz ama PDF'i buyutur ve bellegi doldurur.
BASKI_DPI = int(os.environ.get("MOLD_PDF_DPI", "300"))


def _olceklenmis_gorsel(src_path, w_pt, h_pt) -> tuple[bytes, str] | None:
    """Gorseli slotun BASKI cozunurlugune indir. (bytes, uzanti) ya da None.

    Neden: 48 MP'lik bir tasarim 7.9x17 cm'lik slota tam cozunurlukte gomuluyordu.
    O slot 300 DPI'da en fazla ~1.9 MP tasir — fazlasi kagida cikmaz, yalnizca
    dosyayi ve bellegi sisirir. 27 slotluk bir kalip 1.2 GB'a ciktigi icin PDF
    uretimi takasa dusup 524 veriyordu. Kucultme YALNIZCA asagi yonlu; zaten
    kucuk gorseller oldugu gibi birakilir.
    """
    try:
        from PIL import Image
    except Exception:  # noqa: BLE001
        return None
    hedef_w = max(1, int(round(w_pt / 72.0 * BASKI_DPI)))
    hedef_h = max(1, int(round(h_pt / 72.0 * BASKI_DPI)))
    try:
        with Image.open(src_path) as im:
            if im.width <= hedef_w and im.height <= hedef_h:
                return None          # zaten yeterince kucuk — dokunma
            im = im.copy()
            saydam = im.mode in ("RGBA", "LA") or (
                im.mode == "P" and "transparency" in im.info)
            # thumbnail() DEGIL resize(): insert_image zaten keep_proportion=False
            # ile rect'i esnetiyor. Orani korursak esnetme sonrasi bir eksende
            # cozunurluk hedefin altina duser (or. 3:4 tasarim 1:2 slota
            # girerken dikeyde ~186 DPI kalirdi). Dogrudan hedef olcuye
            # getirmek geometriyi degistirmez, iki eksende de tam DPI verir.
            im = im.resize((hedef_w, hedef_h), Image.LANCZOS)
            buf = io.BytesIO()
            if saydam:
                im.convert("RGBA").save(buf, format="PNG", optimize=True)
                return buf.getvalue(), "png"
            im.convert("RGB").save(buf, format="JPEG", quality=92, optimize=True)
            return buf.getvalue(), "jpg"
    except Exception:  # noqa: BLE001
        return None      # kucultemezsek orijinali kullan, baski bozulmasin


def _make_clipped_image(src_path, w_pt, h_pt, radius):
    """Ham gorseli (PNG/JPG) w×h sayfaya tam doldurarak koy + yuvarlak kose VEKTOR
    clip uygula. Kisiye ozel tasarimlar (gorsel) icin — PDF'lerle ayni olcu/ovallik.
    Donus: pdf bytes."""
    tmp = fitz.open()
    pg = tmp.new_page(width=w_pt, height=h_pt)
    # Gorseli rect'i TAM doldur (keep_proportion=False) — sag-alt yaslama + dogru olcu
    _kucuk = _olceklenmis_gorsel(src_path, w_pt, h_pt)
    if _kucuk is not None:
        pg.insert_image(pg.rect, stream=_kucuk[0], keep_proportion=False)
    else:
        pg.insert_image(pg.rect, filename=str(src_path), keep_proportion=False)

    if radius > 0:
        rr = min(radius, w_pt / 2, h_pt / 2)
        k = 0.5523 * rr
        x0, x1 = 0.0, w_pt
        pb, pt = 0.0, h_pt
        ops = (
            f"{x0+rr:.3f} {pb:.3f} m {x1-rr:.3f} {pb:.3f} l "
            f"{x1-rr+k:.3f} {pb:.3f} {x1:.3f} {pb+rr-k:.3f} {x1:.3f} {pb+rr:.3f} c "
            f"{x1:.3f} {pt-rr:.3f} l {x1:.3f} {pt-rr+k:.3f} {x1-rr+k:.3f} {pt:.3f} {x1-rr:.3f} {pt:.3f} c "
            f"{x0+rr:.3f} {pt:.3f} l {x0+rr-k:.3f} {pt:.3f} {x0:.3f} {pt-rr+k:.3f} {x0:.3f} {pt-rr:.3f} c "
            f"{x0:.3f} {pb+rr:.3f} l {x0:.3f} {pb+rr-k:.3f} {x0+rr-k:.3f} {pb:.3f} {x0+rr:.3f} {pb:.3f} c h W n "
        )
        # Clip akışın BAŞINA — görselde akış çoğu zaman boşluksuz "q" ile başladığı
        # için eski " q" regex'i tutmuyor, yuvarlatma sessizce atlanıyordu.
        xref = pg.get_contents()[0]
        c = tmp.xref_stream(xref).decode("latin-1")
        tmp.update_stream(xref, (ops + c).encode("latin-1"))

    out = tmp.tobytes(garbage=4, deflate=True)
    tmp.close()
    return out


def render_mold_pdf(mold_items, template=None):
    """
    Kalıp slotlarından baskıya hazır PDF üret. Kalıcı vektör clip ile pürüzsüz
    yuvarlak köşe (modelin radius'u kadar), şeffaf zemin.
    template: {page_w_pt, page_h_pt, cols, rows, boxes:[...]}.
    """
    if not template or not template.get("boxes"):
        raise ValueError("Kalıp şablonu tanımlı değil — önce şablon yükleyin")

    page_w = template["page_w_pt"]
    page_h = template["page_h_pt"]
    cols = template.get("cols") or 9
    rows = template.get("rows") or 3
    boxes = template["boxes"]

    doc = fitz.open()
    page = doc.new_page(width=page_w, height=page_h)
    # BEYAZ ZEMİN YOK — boş alan şeffaf

    placed = 0
    skipped = []
    slots = _ordered_slots(mold_items, cols, rows)

    # ★ SESSIZ KAYIP KORUMASI ★ — iki item ayni slot_index'i tasiyorsa (bozuk veri)
    # _ordered_slots birini haritadan dusuruyor ve o kalem hic basilmiyordu, uustelik
    # 'skipped' listesine de girmiyordu. Yerlesemeyeni acikca raporla.
    _yerlesen = {id(x) for x in slots if x is not None}
    for _it in mold_items:
        if id(_it) not in _yerlesen:
            skipped.append({
                "slot": _it.get("slot_index"),
                "model": _it.get("model"),
                "reason": "slot_cakismasi",
            })

    for idx, it in enumerate(slots):
        if it is None:
            continue
        if idx >= len(boxes):
            skipped.append({"slot": idx, "reason": "sablon_kutu_yetersiz"})
            continue
        box = boxes[idx]
        model = it.get("model")
        rel = it.get("design_file_path")
        fmt = (it.get("design_format") or "").lower()

        pr = _placement_rect(box, model or "", it.get("spec"))
        if pr is None:
            skipped.append({"slot": idx, "model": model, "reason": "olcu_yok"})
            continue
        rect, radius = pr

        if not rel:
            skipped.append({"slot": idx, "model": model, "reason": "tasarim_dosyasi_yok"})
            continue
        path = _abs_path(rel)
        if not path.exists():
            skipped.append({"slot": idx, "model": model, "reason": "dosya_bulunamadi"})
            continue

        try:
            if fmt == "pdf":
                clipped_bytes = _make_clipped_design(path, rect.width, rect.height, radius)
                clipped = fitz.open(stream=clipped_bytes, filetype="pdf")
                page.show_pdf_page(rect, clipped, 0)
                clipped.close()
            else:
                # Gorsel (PNG/JPG, kisiye ozel) — PDF ile ayni olcu/ovallik/yaslama
                clipped_bytes = _make_clipped_image(path, rect.width, rect.height, radius)
                clipped = fitz.open(stream=clipped_bytes, filetype="pdf")
                page.show_pdf_page(rect, clipped, 0)
                clipped.close()
            placed += 1
        except Exception as e:
            skipped.append({"slot": idx, "model": model, "reason": f"yerlestirme_hatasi: {e}"})

    buf = io.BytesIO()
    doc.save(buf, deflate=True)
    doc.close()
    return buf.getvalue(), {
        "placed": placed,
        "skipped": skipped,
        "skipped_count": len(skipped),
        "total": sum(1 for s in slots if s is not None),
        "page_cm": [round(page_w / CM_TO_PT, 1), round(page_h / CM_TO_PT, 1)],
        "grid": [cols, rows],
    }
