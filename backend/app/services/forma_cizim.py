"""Forma zemininin "zengin" görünümü — kumaş dokusu ve fırça darbeleri.

Düz renkli çizgiler ekranda sade duruyordu; gerçek forma kumaşı dokuludur ve
ışık alır. Bu modül kodla çizilen desenin (services/forma.desen_sekilleri)
üstüne iki katman ekler:
  • doku "kumas": ince çapraz dokuma + hafif yıpranma + kenarlara doğru gölge
  • efekt "firca": deseni çapraz kesen, kenarı tırtıklı fırça darbeleri
    (iki renkte: desen rengi ve zemin rengi)

TEK ÇİZİCİ: aynı fonksiyon stüdyo önizlemesini (düşük çözünürlük), baskı
PNG'sini ve PDF'in zeminini üretir — müşterinin gördüğü ile basılan AYNI
koddan çıkar. Doku/efekt sabit bir referans boyutta ve SABİT tohumla üretilip
hedef boyuta ölçeklenir: önizlemede ve baskıda aynı yerde aynı darbe durur.
Yalnız Pillow kullanır (numpy yok — CI ve yeni sunucuda ek bağımlılık olmasın).
"""
from __future__ import annotations

import functools
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter

DOKULAR = {"yok": "Düz", "kumas": "Kumaş dokusu", "pro": "Forma Pro (örgü + fırça + ışık)"}
EFEKTLER = {"yok": "Yok", "firca": "Fırça darbeleri"}

REF_W = 900          # doku/efekt bu genişlikte üretilir, sonra ölçeklenir


def _gurultu(boyut: tuple[int, int], tohum: int) -> Image.Image:
    """TOHUMLU gürültü ('L', 0-255 düzgün dağılım). Pillow'un effect_noise'ı
    tohumlanamıyor: iki ayrı süreçte (önizlemeyi çizen ile baskıyı çizen
    worker) farklı desen üretirdi."""
    w, h = boyut
    return Image.frombytes("L", (w, h), random.Random(tohum).randbytes(w * h))


def _ref_boyut(W: int, H: int) -> tuple[int, int]:
    return REF_W, max(1, round(REF_W * H / max(1, W)))


@functools.lru_cache(maxsize=8)
def _kumas_katmanlari(rw: int, rh: int) -> tuple[Image.Image, Image.Image]:
    """(koyulaştırma, aydınlatma) alfa maskeleri — 'L' kipinde, ref boyutta."""
    # 1) Dokuma: iki yöne ince çapraz çizgiler (8 px'lik karo döşenir)
    karo = Image.new("L", (8, 8), 0)
    c = ImageDraw.Draw(karo)
    for k in (-8, 0, 8):
        c.line([(k, 0), (k + 8, 8)], fill=120, width=1)
        c.line([(k + 8, 0), (k, 8)], fill=70, width=1)
    dokuma = Image.new("L", (rw, rh), 0)
    for y in range(0, rh, 8):
        for x in range(0, rw, 8):
            dokuma.paste(karo, (x, y))
    # 2) Yıpranma: iri, yumuşak gürültü lekeleri
    kucuk = _gurultu((max(2, rw // 110), max(2, rh // 110)), 1907)
    leke = kucuk.resize((rw, rh), Image.BICUBIC).filter(ImageFilter.GaussianBlur(22))
    # 3) Işık: ortası aydınlık, kenarlar koyu (kılıfın kıvrımı hissi)
    golge = Image.new("L", (rw, rh), 0)
    gc = ImageDraw.Draw(golge)
    pay = rw * 0.22
    gc.rectangle([0, 0, rw, rh], fill=150)
    gc.rounded_rectangle([pay * 0.35, pay * 0.3, rw - pay * 0.35, rh - pay * 0.3],
                         radius=int(pay), fill=0)
    golge = golge.filter(ImageFilter.GaussianBlur(pay * 0.45))

    # Koyulaştırma = dokuma çizgileri + lekenin koyu yarısı + kenar gölgesi
    koyu_leke = leke.point(lambda v: max(0, 128 - v) * 2)
    koyu = ImageChops.add(ImageChops.add(dokuma.point(lambda v: v // 3),
                                         koyu_leke.point(lambda v: v // 9)),
                          golge.point(lambda v: int(v / 2.2)))
    # Aydınlatma = lekenin açık yarısı + ince tanecik
    tanecik = _gurultu((rw, rh), 1908).point(lambda v: max(0, v - 190))
    acik = ImageChops.add(leke.point(lambda v: max(0, v - 128) // 7), tanecik.point(lambda v: v // 4))
    return koyu, acik


@functools.lru_cache(maxsize=8)
def _firca_maskeleri(rw: int, rh: int) -> tuple[Image.Image, Image.Image]:
    """İki fırça darbesi maskesi ('L', ref boyut) — biri desen rengiyle, diğeri
    zemin rengiyle boyanır. Darbeler sağ üstten sol alta çapraz iner."""
    def maske(tohum: int, yogunluk: int, esik: int) -> Image.Image:
        rnd = random.Random(tohum)
        kose = int((rw ** 2 + rh ** 2) ** 0.5) + 40          # döndürünce her yeri kaplasın
        m = Image.new("L", (kose, kose), 0)
        c = ImageDraw.Draw(m)
        for _ in range(yogunluk):
            x = rnd.uniform(0, kose)
            y = rnd.uniform(0, kose)
            uzun = rnd.uniform(kose * 0.10, kose * 0.36)
            # Çoğu ince çizik, arada geniş kuru-fırça darbesi
            kalin = rnd.uniform(14, 44) if rnd.random() < 0.22 else rnd.uniform(2, 11)
            # Fırça izi: incelerek biten uzun damla
            c.polygon([(x, y - kalin / 2), (x + uzun * 0.7, y - kalin * 0.35),
                       (x + uzun, y), (x + uzun * 0.7, y + kalin * 0.35), (x, y + kalin / 2)],
                      fill=rnd.randint(150, 255))
        # Kenarı tırtıkla: gürültüyle çarpıp eşikle (kuru fırça görünümü)
        gurultu = _gurultu((kose, kose), tohum + 7).filter(ImageFilter.GaussianBlur(0.6))
        m = ImageChops.multiply(m, gurultu.point(lambda v: 255 if v > esik else int(v * 1.2)))
        m = m.rotate(58, resample=Image.BICUBIC)             # çapraz yön
        sol, ust = (kose - rw) // 2, (kose - rh) // 2
        m = m.crop((sol, ust, sol + rw, ust + rh))
        # Ortayı (isim/numara bölgesi) seyrelt: yazı okunur kalsın
        orta = Image.new("L", (rw, rh), 255)
        oc = ImageDraw.Draw(orta)
        oc.ellipse([rw * 0.12, rh * 0.30, rw * 0.88, rh * 0.80], fill=70)
        orta = orta.filter(ImageFilter.GaussianBlur(rw * 0.10))
        return ImageChops.multiply(m, orta)

    return maske(1905, 120, 120), maske(1923, 85, 130)


def _hex_rgb(h: str) -> tuple[int, int, int]:
    s = h.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def zemin_susle(g: Image.Image, renkler: list[str], doku: str, efekt: str) -> Image.Image:
    """Düz desen görselinin (RGBA, W×H) üstüne efekt ve dokuyu uygula."""
    if doku not in DOKULAR:
        doku = "yok"
    if efekt not in EFEKTLER:
        efekt = "yok"
    if doku == "yok" and efekt == "yok":
        return g
    W, H = g.size
    rw, rh = _ref_boyut(W, H)

    def hedefe(m: Image.Image) -> Image.Image:
        return m if (rw, rh) == (W, H) else m.resize((W, H), Image.LANCZOS)

    if efekt == "firca":
        m1, m2 = _firca_maskeleri(rw, rh)
        for maske, renk in ((m1, renkler[1]), (m2, renkler[0])):
            boya = Image.new("RGBA", (W, H), _hex_rgb(renk) + (255,))
            boya.putalpha(hedefe(maske))
            g = Image.alpha_composite(g, boya)
    if doku == "kumas":
        koyu, acik = _kumas_katmanlari(rw, rh)
        siyah = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        siyah.putalpha(hedefe(koyu))
        beyaz = Image.new("RGBA", (W, H), (255, 255, 255, 255))
        beyaz.putalpha(hedefe(acik))
        g = Image.alpha_composite(Image.alpha_composite(g, siyah), beyaz)
    return g


def parlama(katman: Image.Image, renk: str, punto: float) -> Image.Image:
    """Yazı katmanının (RGBA) çevresinde yumuşak hale. Dönüş: katmanla aynı
    boyutta, YALNIZ haleyi içeren RGBA (yazının altına konur)."""
    alfa = katman.getchannel("A")
    yay = max(1.0, punto * 0.07)
    # Bulanıklaştır, sonra güçlendir: hale harfin kenarından dolgun başlar.
    # (Genişletme filtresi 600 DPI'da saniyeler sürüyordu; bu aynı görünümü
    # tek bulanıklaştırmayla verir.) Yarı çözünürlükte hesaplanır — hale
    # zaten yumuşak, fark görünmez, süre dörtte bire iner.
    kucuk = alfa.resize((max(1, alfa.width // 2), max(1, alfa.height // 2)), Image.BILINEAR)
    hale = kucuk.filter(ImageFilter.GaussianBlur(yay / 2)).point(lambda v: min(255, int(v * 2.4)))
    hale = hale.resize(alfa.size, Image.BILINEAR)
    cikti = Image.new("RGBA", katman.size, _hex_rgb(renk) + (255,))
    cikti.putalpha(hale)
    return cikti


# ─── "Forma Pro" zemini ─────────────────────────────────────────────────
# Referans: parlak, dokulu maç forması — belirgin örgü (elmas desenli
# file), kenarlara yığılan çapraz kuru fırça darbeleri, yazının arkasında
# sıcak bir ışık ve kenarlara doğru koyulaşma. Renkler değişse de efekt
# AYNI kalır: hepsi zeminin kendi renklerinden türetilir (sabit renk yok).

def _acik(rgb: tuple[int, int, int], oran: float) -> tuple[int, int, int]:
    return tuple(min(255, round(c + (255 - c) * oran)) for c in rgb)  # type: ignore[return-value]


@functools.lru_cache(maxsize=8)
def _orgu(rw: int, rh: int) -> tuple[Image.Image, Image.Image]:
    """Elmas örgü: (gölge, ışık) maskeleri. Karo ~ genişliğin 1/75'i."""
    s = max(7, rw // 62)
    karo_g = Image.new("L", (s, s), 0)
    karo_i = Image.new("L", (s, s), 0)
    cg, ci = ImageDraw.Draw(karo_g), ImageDraw.Draw(karo_i)
    for k in (-s, 0, s):
        cg.line([(k, 0), (k + s, s)], fill=150, width=max(1, s // 6))
        cg.line([(k + s, 0), (k, s)], fill=150, width=max(1, s // 6))
        ci.line([(k + 1, 0), (k + s + 1, s)], fill=120, width=1)
    golge = Image.new("L", (rw, rh), 0)
    isik = Image.new("L", (rw, rh), 0)
    for y in range(0, rh, s):
        for x in range(0, rw, s):
            golge.paste(karo_g, (x, y))
            isik.paste(karo_i, (x, y))
    # Örgü düzgün tekrar etmesin: hafif dalgalı yoğunluk
    leke = _gurultu((max(2, rw // 60), max(2, rh // 60)), 3101).resize((rw, rh), Image.BICUBIC) \
        .filter(ImageFilter.GaussianBlur(rw / 40))
    golge = ImageChops.multiply(golge, leke.point(lambda v: 110 + v // 2))
    return golge.point(lambda v: v * 50 // 100), isik.point(lambda v: v * 34 // 100)


@functools.lru_cache(maxsize=8)
def _kenar_agirligi(rw: int, rh: int) -> Image.Image:
    """Fırça darbeleri KENARLARDA (sol/sağ şerit ve köşeler) yoğun; ortadaki
    yazı bölgesi temiz kalır (referansta isim/numara çevresi lekesiz)."""
    m = Image.new("L", (rw, rh), 0)
    c = ImageDraw.Draw(m)
    c.rectangle([0, 0, rw * 0.26, rh], fill=255)                 # sol kenar
    c.rectangle([rw * 0.74, 0, rw, rh], fill=255)                # sağ kenar
    c.rectangle([0, 0, rw, rh * 0.16], fill=200)                 # üst
    c.rectangle([0, rh * 0.80, rw, rh], fill=220)                # alt
    return m.filter(ImageFilter.GaussianBlur(rw * 0.07))


@functools.lru_cache(maxsize=8)
def _pro_firca(rw: int, rh: int) -> tuple[Image.Image, Image.Image]:
    """Kuru fırça vuruşları: '/' yönünde, kalın-ince karışık, tırtıklı kenarlı
    kümeler (tek tek çizgi değil, aynı darbeden çıkmış birkaç iz)."""
    def maske(tohum: int, kume: int) -> Image.Image:
        rnd = random.Random(tohum)
        kose = int((rw ** 2 + rh ** 2) ** 0.5) + 40
        m = Image.new("L", (kose, kose), 0)
        c = ImageDraw.Draw(m)
        for _ in range(kume):
            x, y = rnd.uniform(0, kose), rnd.uniform(0, kose)
            uzun = rnd.uniform(kose * 0.06, kose * 0.20)
            for _iz in range(rnd.randint(2, 6)):                  # bir darbenin kılları
                dy = rnd.uniform(-14, 14)
                dx = rnd.uniform(-uzun * 0.1, uzun * 0.1)
                kalin = rnd.uniform(2, 9) if rnd.random() < 0.7 else rnd.uniform(10, 20)
                bas, son = x + dx, x + dx + uzun * rnd.uniform(0.5, 1.0)
                c.polygon([(bas, y + dy - kalin / 2), (son - kalin, y + dy - kalin * 0.15),
                           (son, y + dy), (son - kalin, y + dy + kalin * 0.15), (bas, y + dy + kalin / 2)],
                          fill=rnd.randint(200, 255))
        grn = _gurultu((kose, kose), tohum + 11).filter(ImageFilter.GaussianBlur(0.8))
        m = ImageChops.multiply(m, grn.point(lambda v: 255 if v > 85 else 0))   # kuru fırça boşlukları
        m = m.rotate(58, resample=Image.BICUBIC)
        sol, ust = (kose - rw) // 2, (kose - rh) // 2
        return ImageChops.multiply(m.crop((sol, ust, sol + rw, ust + rh)), _kenar_agirligi(rw, rh))
    return maske(4401, 360), maske(4423, 270)


def pro_zemin(g: Image.Image, renkler: list[str], merkez: tuple[float, float] = (0.5, 0.55),
              isik_renk: str | None = None) -> Image.Image:
    """Forma Pro zemini — düz desen görselinin (RGBA, W×H) üstüne.

    Renkler BOZULMAZ: fırça yalnız kenarlarda, ışık zeminin parlak renginin
    doygun hâli (beyaza çekilmez), örgü her yerde ince. merkez: yazı bloğu."""
    W, H = g.size
    rw, rh = _ref_boyut(W, H)

    def hedefe(m: Image.Image) -> Image.Image:
        return m if (rw, rh) == (W, H) else m.resize((W, H), Image.LANCZOS)

    def boya(maske: Image.Image, renk) -> None:
        nonlocal g
        k = Image.new("RGBA", (W, H), (renk if isinstance(renk, tuple) else _hex_rgb(renk)) + (255,))
        k.putalpha(hedefe(maske))
        g = Image.alpha_composite(g, k)

    r1, r2 = _hex_rgb(renkler[0]), _hex_rgb(renkler[1])
    parlak = max((r1, r2), key=lambda c: 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2])
    koyu = r2 if parlak == r1 else r1
    # 1) Fırça: koyu renk açık şeritlere, açık renk koyu şeritlere (kenarlarda)
    f1, f2 = _pro_firca(rw, rh)
    boya(f1, koyu)
    boya(f2, parlak)
    # 2) Yazının arkasında ılık parlaklık — doygun, beyaza kaçmaz
    isik = _hex_rgb(isik_renk) if isik_renk else _acik(parlak, 0.12)
    mx, my = merkez
    hale = Image.new("L", (rw, rh), 0)
    hd = ImageDraw.Draw(hale)
    hd.ellipse([rw * (mx - 0.40), rh * (my - 0.20), rw * (mx + 0.40), rh * (my + 0.20)], fill=120)
    hd.ellipse([rw * (mx - 0.30), rh * (my - 0.14), rw * (mx + 0.30), rh * (my + 0.14)], fill=190)
    boya(hale.filter(ImageFilter.GaussianBlur(rw * 0.08)), isik)
    # 3) Örgü dokusu
    golge, parilti = _orgu(rw, rh)
    boya(golge, (0, 0, 0))
    boya(parilti, (255, 255, 255))
    # 4) Çok hafif kenar koyulaşması (renkleri öldürmeden derinlik)
    kenar = Image.new("L", (rw, rh), 45)
    ImageDraw.Draw(kenar).rounded_rectangle([rw * 0.05, rh * 0.03, rw * 0.95, rh * 0.97], radius=int(rw * 0.2), fill=0)
    boya(kenar.filter(ImageFilter.GaussianBlur(rw * 0.06)), (0, 0, 0))
    return g
