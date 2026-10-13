"""Forma tasarlayıcının HAZIR amblem kütüphanesini üretir.

Çıktı: app/sablon_gorselleri/amblem/<anahtar>.png — beyaz, saydam zeminli
MASKE (512 px). Müşteri rengi seçer; baskıda maske o renge boyanır
(design_render._ciz_amblem), tuvalde CSS maskesi olarak kullanılır.

Şekiller bilerek GENEL ve telifsiz: hepsi burada, koddan çizilir — hiçbir
kulübün ya da markanın armasına benzetilmemiştir. Yeni amblem eklemek için
bir çizim fonksiyonu yazıp AMBLEMLER'e ve services/forma.AMBLEMLER'e ekleyin;
mağaza sahibi ayrıca panelden kendi görselini yükleyebilir.

Kullanım:  python scripts/amblem_uret.py     (dosyalar depoya commit'lenir)
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402

B = 2048            # çizim boyu (4 kat) → 512'ye küçültülür: pürüzsüz kenar
CIKTI = 512
BEYAZ = (255, 255, 255, 255)
YOK = (0, 0, 0, 0)
HEDEF = Path(__file__).resolve().parent.parent / "app" / "sablon_gorselleri" / "amblem"


def p(x: float, y: float) -> tuple[float, float]:
    return (x * B, y * B)


def yildiz_noktalari(cx, cy, r_dis, r_ic=None, uc=5, aci=-90.0):
    r_ic = r_ic if r_ic is not None else r_dis * 0.40
    nokta = []
    for i in range(uc * 2):
        r = r_dis if i % 2 == 0 else r_ic
        a = math.radians(aci + i * 180 / uc)
        nokta.append(p(cx + r * math.cos(a), cy + r * math.sin(a)))
    return nokta


def egri(p0, p1, p2, adim=40):
    """İkinci derece Bézier — yumuşak kenarlar için nokta dizisi."""
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1])
            for t in (i / adim for i in range(adim + 1))]


def kalkan(c: ImageDraw.ImageDraw) -> None:
    ust = egri((0.14, 0.12), (0.5, 0.02), (0.86, 0.12))
    sag = egri((0.86, 0.12), (0.90, 0.62), (0.5, 0.97))
    sol = egri((0.5, 0.97), (0.10, 0.62), (0.14, 0.12))
    c.polygon([p(*n) for n in ust + sag + sol], fill=BEYAZ)
    # iç çizgi: kalkana derinlik verir (maskede delik)
    ic_ust = egri((0.22, 0.19), (0.5, 0.11), (0.78, 0.19))
    ic_sag = egri((0.78, 0.19), (0.81, 0.60), (0.5, 0.87))
    ic_sol = egri((0.5, 0.87), (0.19, 0.60), (0.22, 0.19))
    c.line([p(*n) for n in ic_ust + ic_sag + ic_sol], fill=YOK, width=int(B * 0.022), joint="curve")


def yildiz(c) -> None:
    c.polygon(yildiz_noktalari(0.5, 0.53, 0.47), fill=BEYAZ)


def uc_yildiz(c) -> None:
    c.polygon(yildiz_noktalari(0.5, 0.40, 0.24), fill=BEYAZ)
    c.polygon(yildiz_noktalari(0.19, 0.60, 0.17), fill=BEYAZ)
    c.polygon(yildiz_noktalari(0.81, 0.60, 0.17), fill=BEYAZ)


def yildiz_sirasi(n: int):
    """n yıldız yan yana, hafif yay üzerinde (ortadakiler biraz yukarıda)."""
    def ciz(c) -> None:
        r = min(0.46, 0.92 / (n * 1.9))            # yıldız yarıçapı: sıraya sığsın
        adim = 0.92 / n
        for i in range(n):
            x = 0.04 + adim * (i + 0.5)
            uzak = abs(i - (n - 1) / 2) / max(1, (n - 1) / 2)     # 0 orta, 1 kenar
            y = 0.50 + 0.10 * uzak * uzak - 0.03
            c.polygon(yildiz_noktalari(x, y, r), fill=BEYAZ)
    return ciz


def tac(c) -> None:
    c.polygon([p(0.10, 0.74), p(0.06, 0.30), p(0.29, 0.52), p(0.50, 0.18),
               p(0.71, 0.52), p(0.94, 0.30), p(0.90, 0.74)], fill=BEYAZ)
    c.rounded_rectangle([p(0.10, 0.79), p(0.90, 0.90)], radius=int(B * 0.025), fill=BEYAZ)
    for x, y in ((0.06, 0.27), (0.50, 0.15), (0.94, 0.27)):
        r = 0.055
        c.ellipse([p(x - r, y - r), p(x + r, y + r)], fill=BEYAZ)


def top(c) -> None:
    c.ellipse([p(0.04, 0.04), p(0.96, 0.96)], fill=BEYAZ)
    cizgi = int(B * 0.028)
    orta = [(0.5 + 0.17 * math.cos(math.radians(-90 + i * 72)),
             0.5 + 0.17 * math.sin(math.radians(-90 + i * 72))) for i in range(5)]
    c.polygon([p(*n) for n in orta], fill=YOK)
    for i, (x, y) in enumerate(orta):
        a = math.radians(-90 + i * 72)
        dx, dy = 0.5 + 0.34 * math.cos(a), 0.5 + 0.34 * math.sin(a)
        c.line([p(x, y), p(dx, dy)], fill=YOK, width=cizgi)
        # kenar beşgenlerinin iç kenarı (iki yana açılan kısa çizgiler)
        for yon in (-1, 1):
            b = a + yon * math.radians(34)
            c.line([p(dx, dy), p(0.5 + 0.47 * math.cos(b), 0.5 + 0.47 * math.sin(b))],
                   fill=YOK, width=cizgi)


def simsek(c) -> None:
    c.polygon([p(0.60, 0.03), p(0.17, 0.56), p(0.45, 0.56), p(0.36, 0.97),
               p(0.83, 0.40), p(0.54, 0.40)], fill=BEYAZ)


def elmas(c) -> None:
    c.polygon([p(0.24, 0.12), p(0.76, 0.12), p(0.97, 0.38), p(0.50, 0.94), p(0.03, 0.38)], fill=BEYAZ)
    w = int(B * 0.02)
    c.line([p(0.03, 0.38), p(0.97, 0.38)], fill=YOK, width=w)
    for x in (0.24, 0.50, 0.76):
        c.line([p(x, 0.12), p({0.24: 0.33, 0.50: 0.50, 0.76: 0.67}[x], 0.38)], fill=YOK, width=w)
    for x in (0.33, 0.67):
        c.line([p(x, 0.38), p(0.50, 0.94)], fill=YOK, width=w)
        c.line([p(x, 0.38), p(0.50, 0.12)], fill=YOK, width=w)


def kalp(c) -> None:
    nokta = []
    for i in range(361):
        t = math.radians(i)
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        nokta.append(p(0.5 + x / 35, 0.47 - y / 35))
    c.polygon(nokta, fill=BEYAZ)


def rozet(c) -> None:
    c.ellipse([p(0.03, 0.03), p(0.97, 0.97)], fill=BEYAZ)
    c.ellipse([p(0.10, 0.10), p(0.90, 0.90)], fill=YOK)
    c.ellipse([p(0.14, 0.14), p(0.86, 0.86)], fill=BEYAZ)
    c.polygon(yildiz_noktalari(0.5, 0.52, 0.27), fill=YOK)


def kupa(c) -> None:
    # kulplar (halka) — önce çizilir, gövde üstüne biner
    w = int(B * 0.055)
    c.ellipse([p(0.06, 0.12), p(0.40, 0.46)], outline=BEYAZ, width=w)
    c.ellipse([p(0.60, 0.12), p(0.94, 0.46)], outline=BEYAZ, width=w)
    govde = [(0.24, 0.08), (0.76, 0.08)] + egri((0.76, 0.08), (0.76, 0.56), (0.50, 0.60)) \
        + egri((0.50, 0.60), (0.24, 0.56), (0.24, 0.08))
    c.polygon([p(*n) for n in govde], fill=BEYAZ)
    c.rectangle([p(0.45, 0.58), p(0.55, 0.76)], fill=BEYAZ)
    c.rounded_rectangle([p(0.30, 0.76), p(0.70, 0.84)], radius=int(B * 0.02), fill=BEYAZ)
    c.rounded_rectangle([p(0.22, 0.84), p(0.78, 0.94)], radius=int(B * 0.02), fill=BEYAZ)


AMBLEMLER = {
    "kalkan": kalkan, "yildiz": yildiz, "yildiz_2": yildiz_sirasi(2), "yildiz_3": yildiz_sirasi(3),
    "yildiz_4": yildiz_sirasi(4), "yildiz_5": yildiz_sirasi(5),
    "uc_yildiz": uc_yildiz, "tac": tac, "top": top,
    "simsek": simsek, "elmas": elmas, "kalp": kalp, "rozet": rozet, "kupa": kupa,
}


def uret() -> None:
    from app.services import forma

    eksik = set(forma.AMBLEMLER) ^ set(AMBLEMLER)
    if eksik:
        raise SystemExit(f"services/forma.AMBLEMLER ile uyuşmuyor: {sorted(eksik)}")
    HEDEF.mkdir(parents=True, exist_ok=True)
    for ad, ciz in AMBLEMLER.items():
        g = Image.new("RGBA", (B, B), YOK)
        ciz(ImageDraw.Draw(g))
        g = g.resize((CIKTI, CIKTI), Image.LANCZOS)
        kutu = g.getchannel("A").getbbox()
        g = g.crop(kutu)            # boşlukları at: kutuya tam otursun
        g.save(HEDEF / f"{ad}.png", "PNG", optimize=True)
        print(f"  {ad:<10} {g.size[0]}×{g.size[1]}")


if __name__ == "__main__":
    uret()
