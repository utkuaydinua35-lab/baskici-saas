"""Baskıya hazır dosya üretimi — müşterinin tasarımından gerçek baskı çıktısı.

İLKE: ekran görüntüsü ASLA baskıya gitmez. Bu modül müşterinin yüklediği
ORİJİNAL dosyaları ve editördekiyle aynı font dosyalarını kullanarak,
şablonda tanımlı fiziksel ölçüde (mm) ve çözünürlükte (DPI) yeniden çizer.

Katman konumları baskı alanına oransal (0-1) olduğundan, müşterinin 380 px
genişlikte gördüğü yerleşim 827×1713 px dosyada bire bir aynı yere düşer.
"""
from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.services.storage import STORAGE_ROOT

log = logging.getLogger("design_render")

FONT_DIR = Path(__file__).resolve().parent.parent / "fonts"
# Editördeki font anahtarı → dosya (storefront/components/studio/fonts.ts ile aynı)
FONT_FILES = {
    "poppins": "Poppins-SemiBold.ttf",
    "montserrat": "Montserrat-Bold.ttf",
    "playfair": "PlayfairDisplay-Bold.ttf",
    "bebas": "BebasNeue-Regular.ttf",
    "oswald": "Oswald-SemiBold.ttf",
    "dancing": "DancingScript-Bold.ttf",
    "lobster": "Lobster-Regular.ttf",
    "mono": "RobotoMono-Medium.ttf",
    "anton": "Anton-Regular.ttf",
    "staatliches": "Staatliches-Regular.ttf",
    "russo": "RussoOne-Regular.ttf",
    "gotik": "UnifrakturCook-Bold.ttf",
    "pirata": "PirataOne-Regular.ttf",
    "bangers": "Bangers-Regular.ttf",
    "marker": "PermanentMarker-Regular.ttf",
    "sprey": "RockSalt-Regular.ttf",
    "bungee": "Bungee-Regular.ttf",
    "alfaslab": "AlfaSlabOne-Regular.ttf",
    "creepster": "Creepster-Regular.ttf",
    "caveat": "Caveat-Regular.ttf",
    "greatvibes": "GreatVibes-Regular.ttf",
    "pacifico": "Pacifico-Regular.ttf",
    "monoton": "Monoton-Regular.ttf",
    "righteous": "Righteous-Regular.ttf",
    "elite": "SpecialElite-Regular.ttf",
    # Kolej/forma: kalın, köşeli, İÇ ÇİZGİLİ (harfin içinde ince boşluk var —
    # kontur rengi o boşluğu doldurur, çift çizgili forma yazısı olur)
    "kolej": "AlumniSansCollegiateOne-Regular.ttf",
}
MAX_PRINT_PX = 8000     # güvenlik tavanı (10.000×10.000 PNG belleği yer)
# "Çerçeveye esnet" açık alanlarda yatay esneme tavanı
ESNET_TAVAN = 2.4
# "Çerçeveyi doldur" açık alanlarda punto, baskı alanı yüksekliğinin bu
# katından büyüyemez — tek harfli metin alanı boydan boya taşırmasın.
# İstemcideki eşi: storefront/components/studio/Canvas.tsx → TAVAN_PUNTO
TAVAN_PUNTO = 0.8


def _kontur(k: dict, boy: float) -> tuple[float, float]:
    """(kontur kalınlığı, harf aralığı) — ikisi de px, puntoya oranlı.

    Kontur harfin DIŞINA doğru büyür; yan yana iki harfin konturu birbirinin
    üstüne binmesin diye harf arası kontur kalınlığının İKİ KATI kadar açılır
    (canlıda "10" yazınca rakamlar üst üste biniyordu). Aynı kural tuvalde,
    önizlemede ve PDF'te de uygulanır."""
    if not k.get("kontur"):
        return 0.0, 0.0
    from app.services.forma import kontur_orani
    t = boy * kontur_orani(k.get("kontur_kalinlik"))
    # Çift kontur (Forma Pro): iç halkanın dışında ikinci, ince bir çizgi —
    # harf arası toplam kalınlığa göre açılır
    if k.get("kontur2"):
        return t, 2 * t * (1 + DIS_KONTUR_ORANI)
    return t, 2 * t


# Çift konturda dış çizginin kalınlığı, iç halkanın bu katı kadar EK
DIS_KONTUR_ORANI = 0.6
# Dikey uzatma tavanı (uzun forma numarası)
DIKEY_TAVAN = 1.6


def _aralikli_genislik(ciz, metin: str, font, aralik: float) -> float:
    if not aralik:
        return ciz.textlength(metin, font=font)
    return sum(ciz.textlength(h, font=font) for h in metin) + aralik * max(0, len(metin) - 1)

# BASKI RENK KURALI (storefront/components/studio/renk.ts ile aynı):
# CMYK bileşenlerinin tamamı ~0 olan renk (saf beyaz) baskı makinesinde
# "mürekkep yok" demektir — o alana hiç baskı yapılmaz. Beyaz her zaman
# CMYK 0,0,0,5 ile basılır. İstemci düzeltmeyi atlarsa burada yakalanır.
BASKI_BEYAZ = "#f2f2f2"


def _basilabilir_renk(ham: str | None) -> str:
    s = (ham or "").strip().lstrip("#").lower()
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    if len(s) != 6 or any(ch not in "0123456789abcdef" for ch in s):
        return "#000000"
    r, g, b = (int(s[i:i + 2], 16) / 255 for i in (0, 2, 4))
    k = 1 - max(r, g, b)
    if k >= 1:
        return f"#{s}"          # saf siyah — sorun yok
    c = (1 - r - k) / (1 - k)
    m = (1 - g - k) / (1 - k)
    y = (1 - b - k) / (1 - k)
    if max(c, m, y, k) < 0.02:
        return BASKI_BEYAZ
    return f"#{s}"


def _font(key: str, size_px: int) -> ImageFont.FreeTypeFont:
    dosya = FONT_FILES.get(key) or FONT_FILES["poppins"]
    yol = FONT_DIR / dosya
    try:
        return ImageFont.truetype(str(yol), max(4, size_px))
    except OSError:
        log.warning("font bulunamadı: %s — varsayılan kullanılıyor", yol)
        return ImageFont.load_default()


def _asset_path(db, asset_id: str) -> Path | None:
    """Katmandaki asset_id → diskteki ORİJİNAL dosya."""
    from sqlalchemy import select

    from app.models import DesignAsset

    try:
        a = db.scalar(select(DesignAsset).where(DesignAsset.id == asset_id))
    except Exception:  # noqa: BLE001 — geçersiz uuid vb.
        return None
    if not a:
        return None
    p = STORAGE_ROOT / a.original_path
    return p if p.exists() else None


def _sar(ciz: ImageDraw.ImageDraw, metin: str, font, max_gen: int) -> list[str]:
    """Satır sarma — editördeki word-break davranışının aynısı."""
    satirlar: list[str] = []
    satir = ""
    for kelime in (metin or "").split():
        deneme = f"{satir} {kelime}".strip()
        if ciz.textlength(deneme, font=font) > max_gen and satir:
            satirlar.append(satir)
            satir = kelime
        else:
            satir = deneme
    if satir:
        satirlar.append(satir)
    return satirlar


def render_print_file(db, design, template) -> bytes:
    """Tasarımdan baskıya hazır PNG üret (saydam zeminli, RGBA).

    Dönüş: PNG bayt dizisi. Çağıran diske yazar (storage.save_design_render).
    """
    W = round(template.print_width_mm / 25.4 * template.print_dpi)
    H = round(template.print_height_mm / 25.4 * template.print_dpi)
    if W > MAX_PRINT_PX or H > MAX_PRINT_PX:
        raise ValueError(f"Baskı ölçüsü çok büyük: {W}×{H} px")

    tuval = _tuval_ciz(db, design.layers or [], W, H, design.id)

    import io

    buf = io.BytesIO()
    tuval.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def render_onizleme(db, katmanlar: list[dict], en_mm: float, boy_mm: float, genislik: int) -> bytes:
    """Stüdyo önizlemesi — BASKI ÇİZİCİSİNİN AYNISI, küçük boyutta (JPEG).

    Forma tasarlayıcının kumaş dokusu, fırça darbesi, kavisli yazı ve parlaması
    tarayıcıda birebir taklit edilemez; önizlemeyi baskıyı üreten kod çizer ki
    müşterinin gördüğü ile basılan aynı olsun."""
    import io

    W = max(120, min(900, int(genislik)))
    H = max(1, round(W * boy_mm / max(1.0, en_mm)))
    tuval = _tuval_ciz(db, katmanlar, W, H, "onizleme")
    zemin = Image.new("RGB", (W, H), (255, 255, 255))
    zemin.paste(tuval, (0, 0), tuval)
    buf = io.BytesIO()
    zemin.save(buf, "JPEG", quality=86)
    return buf.getvalue()


def _tuval_ciz(db, katmanlar: list[dict], W: int, H: int, kimlik) -> Image.Image:
    tuval = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ciz = ImageDraw.Draw(tuval)

    for katman in katmanlar:
        tip = katman.get("type")
        try:
            if tip == "image":
                _ciz_gorsel(db, tuval, katman, W, H)
            elif tip == "overlay":
                _ciz_overlay(db, tuval, katman, W, H)
            elif tip == "text":
                _ciz_metin(tuval, ciz, katman, W, H)
            elif tip == "sekil":
                if katman.get("bicim") == "desen":
                    _ciz_desen(tuval, katman, W, H)
                elif katman.get("bicim") == "amblem":
                    _ciz_amblem(db, tuval, katman, W, H)
                else:
                    _ciz_sekil(ciz, katman, W, H)
        except Exception:  # noqa: BLE001 — tek katman baskıyı tümden bozmasın
            log.exception("katman çizilemedi (design=%s, tip=%s)", kimlik, tip)
    return tuval


# KATMAN SIRASI: dizideki sıra çizim sırasıdır (ilk eleman en altta). Tipe göre
# otomatik sıralama YOK — müşteri hazır şablonu (çerçeveyi) editörde istediği
# katmana taşıyabilir. Storefront karşılığı: components/studio/katmanlar.ts


def _ciz_sekil(ciz: ImageDraw.ImageDraw, k: dict, W: int, H: int) -> None:
    """Kısıtlı şablonun çizilen öğeleri — şimdilik "ilerleme" (Spotify çubuğu).

    Çubuğun dolu kısmı ve noktanın konumu, müşterinin yazdığı geçen/toplam
    süreden hesaplanan orandan gelir (kisitli_sablon.layers_uret).
    """
    if k.get("bicim") != "ilerleme":
        return
    x = float(k.get("x", 0.1)) * W
    y = float(k.get("y", 0.5)) * H
    w = float(k.get("w", 0.8)) * W
    kalinlik = max(1, round(float(k.get("kalinlik", 0.004)) * H))
    yaricap = max(1, round(float(k.get("boyut", 0.012)) * H))
    oran = max(0.0, min(1.0, float(k.get("oran", 0))))
    renk = _basilabilir_renk(k.get("renk"))
    pasif = _basilabilir_renk(k.get("renk_pasif"))

    ciz.rectangle([x, y - kalinlik / 2, x + w, y + kalinlik / 2], fill=pasif)
    if oran > 0:
        ciz.rectangle([x, y - kalinlik / 2, x + w * oran, y + kalinlik / 2], fill=renk)
    nx = x + w * oran
    ciz.ellipse([nx - yaricap, y - yaricap, nx + yaricap, y + yaricap], fill=renk)


def _ciz_desen(tuval: Image.Image, k: dict, W: int, H: int) -> None:
    """Forma zemini — kodla çizilen desen (services/forma.desen_sekilleri).

    4 kat büyük çizilip küçültülür: eğik kenarlar (çapraz desenler) baskıda
    tırtıklı çıkmasın. Dik kenarlı desenlerde fark yaratmaz."""
    from app.services import forma

    renkler = [_basilabilir_renk(r) for r in (k.get("renkler") or [])][:3]
    while len(renkler) < 3:
        renkler.append(BASKI_BEYAZ)
    kat = 2 if max(W, H) * 2 <= MAX_PRINT_PX else 1
    kw, kh = W * kat, H * kat
    g = Image.new("RGBA", (kw, kh), renkler[0])
    gciz = ImageDraw.Draw(g)
    for sira, cokgen in forma.desen_sekilleri(str(k.get("desen") or "duz"),
                                              str(k.get("yogunluk") or "orta")):
        gciz.polygon([(x * kw, y * kh) for x, y in cokgen], fill=renkler[min(sira, 2)])
    if kat > 1:
        g = g.resize((W, H), Image.LANCZOS)
    # Kumaş dokusu / fırça darbeleri (şablon ayarı; müşteri seçmez)
    from app.services import forma_cizim
    if k.get("doku") == "pro":
        merkez = k.get("isik_merkez") or [0.5, 0.55]
        g = forma_cizim.pro_zemin(g, renkler, (float(merkez[0]), float(merkez[1])))
    else:
        g = forma_cizim.zemin_susle(g, renkler, str(k.get("doku") or "yok"), str(k.get("efekt") or "yok"))
    tuval.alpha_composite(g, (0, 0))


def _ciz_amblem(db, tuval: Image.Image, k: dict, W: int, H: int) -> None:
    """Amblem — tek renkli maske, müşterinin seçtiği renge boyanır ve kutusuna
    ORANI BOZULMADAN ortalanır. Dosya şablon kaydından/hazır kütüphaneden
    çözülür; katmandaki url baskıda KULLANILMAZ."""
    from sqlalchemy import select

    from app.models import DesignOverlay
    from app.services import forma

    try:
        o = db.scalar(select(DesignOverlay).where(
            DesignOverlay.id == str(k.get("overlay_id") or "")))
    except Exception:  # noqa: BLE001 — geçersiz uuid
        return
    if not o:
        return
    yol = forma.amblem_dosyasi(getattr(o, "forma", None), str(k.get("amblem") or ""))
    if not yol:
        return
    maske = Image.open(yol)
    maske.load()
    alfa = maske.convert("RGBA").getchannel("A")
    kx, ky = float(k.get("x", 0)) * W, float(k.get("y", 0)) * H
    kw, kh = max(1.0, float(k.get("w", 0.2)) * W), max(1.0, float(k.get("h", 0.1)) * H)
    olcek = min(kw / alfa.width, kh / alfa.height)
    gw, gh = max(1, round(alfa.width * olcek)), max(1, round(alfa.height * olcek))
    alfa = alfa.resize((gw, gh), Image.LANCZOS)
    boya = Image.new("RGBA", (gw, gh), _basilabilir_renk(k.get("renk")))
    boya.putalpha(alfa)
    tuval.alpha_composite(boya, (round(kx + (kw - gw) / 2), round(ky + (kh - gh) / 2)))


def _ciz_overlay(db, tuval: Image.Image, k: dict, W: int, H: int) -> None:
    """Hazır şablon. Katmanda 'field' yoksa şablonun kendi görseli baskı
    alanını tam kaplar; 'field' varsa o ALANIN görseli (kısıtlı şablondaki
    bayrak/logo gibi açılabilir öğe) kendi konumuna çizilir.

    Dosya yolu İSTEMCİDEN DEĞİL veritabanından okunur: müşteri katmana
    istediği url'i yazsa bile sunucu yalnızca kendi kayıtlı dosyasını basar.
    """
    from sqlalchemy import select

    from app.models import DesignOverlay

    try:
        o = db.scalar(select(DesignOverlay).where(
            DesignOverlay.id == str(k.get("overlay_id") or "")))
    except Exception:  # noqa: BLE001 — geçersiz uuid
        return
    if not o:
        return

    alan_key = k.get("field")
    if alan_key:
        alan = next((a for a in (o.alanlar or [])
                     if str(a.get("key")) == str(alan_key) and a.get("tip") == "gorsel"), None)
        if not alan or not alan.get("image_path"):
            return
        yol = STORAGE_ROOT / alan["image_path"]
        kutu = (
            round(float(alan.get("x", 0)) * W), round(float(alan.get("y", 0)) * H),
            max(1, round(float(alan.get("w", 0.1)) * W)),
            max(1, round(float(alan.get("h", 0.1)) * H)),
        )
    else:
        yol = STORAGE_ROOT / o.image_path
        kutu = (0, 0, W, H)

    if not yol.exists():
        log.warning("hazır şablon dosyası yok: %s", yol)
        return
    g = Image.open(yol)
    g.load()
    if g.mode != "RGBA":
        g = g.convert("RGBA")
    if alan_key:
        # Açılabilir öğe kutusuna ORANI BOZULMADAN ortalanır — tuval
        # (object-fit: contain) ve PDF ile aynı. Eskiden kutuya geriliyordu:
        # kutusu logonun oranına uymayan öğe baskıda yassı/uzun çıkıyordu.
        olcek = min(kutu[2] / g.width, kutu[3] / g.height)
        gw, gh = max(1, round(g.width * olcek)), max(1, round(g.height * olcek))
        g = g.resize((gw, gh), Image.LANCZOS)
        tuval.alpha_composite(g, (kutu[0] + (kutu[2] - gw) // 2, kutu[1] + (kutu[3] - gh) // 2))
        return
    g = g.resize((kutu[2], kutu[3]), Image.LANCZOS)
    tuval.alpha_composite(g, (kutu[0], kutu[1]))


def _ciz_gorsel(db, tuval: Image.Image, k: dict, W: int, H: int) -> None:
    yol = _asset_path(db, str(k.get("asset_id") or ""))
    if not yol:
        return
    g = Image.open(yol)
    g.load()
    if g.mode != "RGBA":
        g = g.convert("RGBA")

    # Kırpma: editörde seçilen bölge, ORİJİNAL piksellere uygulanır
    c = k.get("crop")
    if c:
        gw, gh = g.size
        kutu = (
            max(0, int(float(c.get("x", 0)) * gw)),
            max(0, int(float(c.get("y", 0)) * gh)),
            min(gw, int((float(c.get("x", 0)) + float(c.get("w", 1))) * gw)),
            min(gh, int((float(c.get("y", 0)) + float(c.get("h", 1))) * gh)),
        )
        if kutu[2] > kutu[0] and kutu[3] > kutu[1]:
            g = g.crop(kutu)

    hedef_w = max(1, round(float(k.get("w", 1)) * W))
    hedef_h = max(1, round(float(k.get("h", 1)) * H))
    # LANCZOS: büyütmede de küçültmede de en temiz sonuç (baskı için önemli)
    g = g.resize((hedef_w, hedef_h), Image.LANCZOS)

    aci = float(k.get("rot") or 0)
    if aci:
        g = g.rotate(-aci, expand=True, resample=Image.BICUBIC)

    # Konum: döndürme kutuyu büyüttüğü için MERKEZ referans alınır
    mx = round((float(k.get("x", 0)) + float(k.get("w", 1)) / 2) * W)
    my = round((float(k.get("y", 0)) + float(k.get("h", 1)) / 2) * H)
    tuval.alpha_composite(g, (mx - g.width // 2, my - g.height // 2))


def _sayi_yoksa(v, varsayilan: float) -> float:
    """None/boş/geçersiz değerde varsayılana düş."""
    try:
        s = float(v)
    except (TypeError, ValueError):
        return varsayilan
    return s if s > 0 else varsayilan


def _satir_orani(font, boy: int) -> float:
    """Fontun doğal satır yüksekliği / punto. Ascent+descent'ten gelir; ölçüm
    başarısızsa başlık fontlarında güvenli olan 1,3 kullanılır."""
    try:
        a, d = font.getmetrics()
        if boy > 0 and (a + d) > 0:
            return (a + d) / boy
    except Exception:  # noqa: BLE001 — bitmap font/eksik metrik
        pass
    return 1.3


def _isaretli(v) -> float:
    """Sayı (eksi olabilir); geçersizse 0."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def kavis_yerlesimi(genler: list[float], aralik: float, kavis: float) -> tuple[list[tuple[float, float, float]], float, float]:
    """Yay üzerindeki harf konumları — PNG ve PDF AYNI hesabı kullanır.

    kavis: yayın toplam açısı (derece). Artı → ortası YUKARI (kubbe), eksi →
    ortası aşağı. Dönüş: ([(dx, dy, aci_derece)], yaricap, sehim) — dx/dy harf
    ORTASININ yayın tepe noktasına göre konumu (y aşağı artar), aci harfin
    saat yönünde dönüşü.
    """
    import math

    toplam = sum(genler) + aralik * max(0, len(genler) - 1)
    aci = math.radians(abs(kavis))
    if toplam <= 0 or aci <= 0:
        return [], 0.0, 0.0
    R = toplam / aci                                   # yay uzunluğu = yazı genişliği
    yon = 1 if kavis > 0 else -1
    konum, x = [], -toplam / 2
    for gen in genler:
        fi = (x + gen / 2) / R                         # harf ortasının yaydaki açısı
        konum.append((R * math.sin(fi), yon * R * (1 - math.cos(fi)), math.degrees(fi) * yon))
        x += gen + aralik
    return konum, R, R * (1 - math.cos(aci / 2))


def _kavisli_katman(metin: str, font, boy: int, oran: float, kavis: float, aralik: float,
                    kontur_px: int, kontur_renk, dolgu, pay_x: int, pay_y: int,
                    esnet: float = 1.0, kontur2_px: int = 0, kontur2_renk=None) -> Image.Image:
    """Yay üzerine dizilmiş tek satır yazı (forma sırtındaki isim gibi).
    Katmanın ORTASI yazının yay üzerindeki kutusunun ortasıdır: konumlama kutu
    merkezine göre yapıldığı için düz yazıyla aynı yere oturur."""
    import math

    olc = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    genler = [olc.textlength(h, font=font) * esnet for h in metin]
    konumlar, R, sehim = kavis_yerlesimi(genler, aralik * esnet, kavis)
    if not konumlar:
        return Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    yon = 1 if kavis > 0 else -1
    satir = max(1, round(boy * oran))
    kw = int(2 * R * math.sin(math.radians(abs(kavis)) / 2) + 2 * satir + 2 * pay_x)
    kh = int(satir + sehim + 2 * pay_y + satir)
    kat = Image.new("RGBA", (kw, kh), (0, 0, 0, 0))
    ox, oy = kw / 2, kh / 2 - yon * sehim / 2          # yayın tepe/dip noktası

    def harf(h: str, gen: float, renk, cizgi: int) -> Image.Image:
        pay = cizgi + 2
        t = Image.new("RGBA", (int(gen / esnet) + 2 * pay + 2, satir + 2 * pay), (0, 0, 0, 0))
        ImageDraw.Draw(t).text((pay, pay), h, font=font, fill=renk,
                               **({"stroke_width": cizgi, "stroke_fill": renk} if cizgi else {}))
        if esnet > 1:
            t = t.resize((max(1, round(t.width * esnet)), t.height), Image.LANCZOS)
        return t

    gecisler = ([(kontur2_renk, kontur2_px)] if kontur2_px else []) \
        + ([(kontur_renk, kontur_px)] if kontur_px else []) + [(dolgu, 0)]
    for renk, cizgi in gecisler:                       # önce tüm konturlar, sonra dolgular
        for h, gen, (dx, dy, derece) in zip(metin, genler, konumlar):
            if h.isspace():
                continue
            t = harf(h, gen, renk, cizgi).rotate(-derece, expand=True, resample=Image.BICUBIC)
            kat.alpha_composite(t, (round(ox + dx - t.width / 2), round(oy + dy - t.height / 2)))
    return kat


def _ciz_metin(tuval: Image.Image, ciz: ImageDraw.ImageDraw, k: dict, W: int, H: int) -> None:
    metin = (k.get("text") or "").strip()
    if not metin:
        return
    ad = str(k.get("font") or "poppins")
    boy = max(4, round(float(k.get("size", 0.1)) * H))
    kutu_gen = max(1, round(float(k.get("w", 0.8)) * W))
    font = _font(ad, boy)

    # SATIR YÜKSEKLİĞİ fontun KENDİ ölçüsünden gelir (ascent + descent).
    # Sabit 1,15 katsayısı Anton gibi başlık fontlarında gerçek satırdan
    # küçük kalıyordu: "g/y/ğ" kuyrukları ve hatta rakamların altı çerçevenin
    # dışına taşıyordu.
    oran = _satir_orani(font, boy)

    # ÇERÇEVE: alanın kutusu. Yükseklik verilmemişse tanımlı puntonun doğal
    # satır kutusu kabul edilir → o alanda metin BÜYÜMEZ, yalnız küçülür
    # (eski alanlar böyle; taşma yerine tanımlı punto korunur).
    kutu_yuk = max(1, round(_sayi_yoksa(k.get("h"), 0) * H) or round(boy * oran))
    # DİKEY UZATMA: harfler çizildikten sonra boyuna uzatılır (uzun forma
    # numarası). Punto çerçeveye bu pay düşülerek sığdırılır.
    dikey = max(1.0, min(DIKEY_TAVAN, _isaretli(k.get("dikey")) or 1.0))

    # ÇERÇEVEYİ DOLDUR: metin kutuya BİREBİR oturtulur — kısa metin büyür,
    # uzun metin küçülür. Hem GENİŞLİK hem YÜKSEKLİK sınırlar: "1" gibi tek
    # haneli metin genişliği doldurmak için çerçeveden taşacak kadar büyümez.
    # Yalnız KISITLI ŞABLON alanlarında açıktır (katman üreticisi sigdir=True
    # yazar); serbest editörde punto müşterinin kendi ayarıdır, dokunulmaz.
    if k.get("sigdir") is True:
        # Harf aralığı puntoyla orantılı olduğundan oran hesabı aynen geçerli
        gen = _aralikli_genislik(ciz, metin, font, _kontur(k, boy)[1])
        if gen > 0:
            en = boy * kutu_gen / gen               # genişliğe göre punto
            yuk = kutu_yuk / oran / dikey           # yüksekliğe göre punto (uzatma payı)
            boy = max(4, int(min(en, yuk, H * TAVAN_PUNTO)))
            font = _font(ad, boy)
            oran = _satir_orani(font, boy)

    # ÇERÇEVEYE ESNET: dar fontlar (kolej) çerçevenin YÜKSEKLİĞİNE sığınca
    # genişliği dolduramıyor; yazı yatayda esnetilip çerçeveyi kaplar (forma
    # numarası gibi). En çok 2,4 kat — daha fazlası harfi tanınmaz yapar.
    esnet = 1.0
    if k.get("esnet") is True:
        dogal = _aralikli_genislik(ciz, metin, font, _kontur(k, boy)[1])
        if dogal > 0:
            # Tek karakter ("7") tam tavana esnerse şişman ve tanınmaz olur
            tavan = ESNET_TAVAN if len(metin.strip()) > 1 else 1.6
            esnet = max(1.0, min(tavan, kutu_gen / dogal))

    kavis = max(-80.0, min(80.0, _isaretli(k.get("kavis"))))
    # Kavisli yazı TEK satırdır (yay üzerinde satır sarma olmaz)
    satirlar = [metin] if kavis else _sar(ciz, metin, font, kutu_gen)
    satir_yuk = max(1, round(boy * oran))

    # Metni kendi katmanına çiz — döndürme ancak böyle temiz olur.
    # PAYLAR: satır kutusu harfin gerçek mürekkebini tam kapsamayabilir —
    # "g/y/ğ" gibi alt uzantılar satır kutusunun dışına iner. Tuval satır
    # yüksekliğinde olursa bu kuyruklar BASKIDA KESİLİR. Paylar simetrik
    # olduğu için (birleştirme merkeze göre yapılır) konum değişmez.
    kontur = k.get("kontur")
    kalinlik, aralik = _kontur(k, boy)
    kontur_px = max(1, round(kalinlik)) if kontur else 0
    dolgu = _basilabilir_renk(k.get("color"))
    kontur_renk = _basilabilir_renk(kontur) if kontur else None
    kontur2_renk = _basilabilir_renk(k.get("kontur2")) if kontur and k.get("kontur2") else None
    kontur2_px = round(kontur_px * (1 + DIS_KONTUR_ORANI)) if kontur2_renk else 0
    hale_renk = k.get("parlama")
    hale_pay = round(boy * 0.30) if hale_renk else 0
    pay_y = max(1, round(boy * 0.35)) + hale_pay + kontur2_px
    pay_x = max(1, round(boy * 0.15)) + hale_pay + kontur2_px
    hiza = k.get("align") or "left"

    if kavis:
        kat = _kavisli_katman(metin, font, boy, oran, kavis, aralik, kontur_px, kontur_renk, dolgu,
                              pay_x, pay_y, esnet, kontur2_px, kontur2_renk)
    else:
        if esnet > 1:
            # Dar bir katmana ORTALI çiz, sonra yatayda esnet (aşağıda)
            kutu_gen_ciz, hiza = max(1, round(kutu_gen / esnet)), "center"
        else:
            kutu_gen_ciz = kutu_gen
        kat = Image.new(
            "RGBA",
            (kutu_gen_ciz + 2 * pay_x, max(1, satir_yuk * len(satirlar)) + 2 * pay_y),
            (0, 0, 0, 0))
        kciz = ImageDraw.Draw(kat)
        for i, s in enumerate(satirlar):
            gen = _aralikli_genislik(kciz, s, font, aralik)
            x = 0 if hiza == "left" else (kutu_gen_ciz - gen) / 2 if hiza == "center" else kutu_gen_ciz - gen
            y = pay_y + i * satir_yuk
            if not kontur_px:
                kciz.text((x + pay_x, y), s, font=font, fill=dolgu)
                continue
            # Konturlu: harfler tek tek, aralıklı. ÖNCE tüm konturlar, SONRA tüm
            # dolgular — bir harfin konturu komşusunun dolgusunu örtmesin.
            konumlar, cx = [], x + pay_x
            for h in s:
                konumlar.append((cx, h))
                cx += kciz.textlength(h, font=font) + aralik
            if kontur2_px:      # çift kontur: önce dış çizgi
                for hx, h in konumlar:
                    kciz.text((hx, y), h, font=font, fill=kontur2_renk,
                              stroke_width=kontur2_px, stroke_fill=kontur2_renk)
            for hx, h in konumlar:
                kciz.text((hx, y), h, font=font, fill=kontur_renk,
                          stroke_width=kontur_px, stroke_fill=kontur_renk)
            for hx, h in konumlar:
                kciz.text((hx, y), h, font=font, fill=dolgu)

        if esnet > 1:
            # Oran, çizilen MÜREKKEBİN gerçek genişliğinden: ölçülen ilerleme
            # genişliği harfin (ve konturun) kenar taşmasını saymaz, yazı
            # çerçeveden birkaç yüzde taşıyordu.
            murekkep = kat.getchannel("A").getbbox()
            if murekkep:
                esnet = max(1.0, min(ESNET_TAVAN, esnet, (kutu_gen - 2) / max(1, murekkep[2] - murekkep[0])))
            kat = kat.resize((max(1, round(kat.width * esnet)), kat.height), Image.LANCZOS)

    if dikey > 1.0:
        kat = kat.resize((kat.width, max(1, round(kat.height * dikey))), Image.LANCZOS)

    # PARLAMA: yazının çevresinde yumuşak hale (yazının ALTINA konur)
    if hale_renk:
        from app.services import forma_cizim
        kat = Image.alpha_composite(
            forma_cizim.parlama(kat, _basilabilir_renk(hale_renk), boy), kat)

    aci = float(k.get("rot") or 0)
    if aci:
        kat = kat.rotate(-aci, expand=True, resample=Image.BICUBIC)

    # Editörde ÇERÇEVENİN sol-üstü konumlandırılır; metin çerçeveye dikey
    # ORTALANIR (küçülen metin çerçevenin tepesine yapışmasın). Tek satırlık
    # çerçevede iki hesap aynı sonucu verir — eski alanlar aynı yerde kalır.
    sol = float(k.get("x", 0)) * W
    ust = float(k.get("y", 0)) * H
    mx = round(sol + kutu_gen / 2)
    my = round(ust + kutu_yuk / 2)
    tuval.alpha_composite(kat, (mx - kat.width // 2, my - kat.height // 2))
