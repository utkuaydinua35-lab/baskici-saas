"""Forma tasarlayıcı — kısıtlı şablonun müşteriye açılan seçenekleri.

Kısıtlı şablonda zemin sabit bir PNG'dir; rengi/deseni değiştirilemez. Forma
tasarlayıcı açıkken zemin KODLA çizilir (desen + renkler), müşteri ayrıca
yazı tipini, yazı rengini/konturunu ve amblemi seçer. Yerleşim yine şablonda
kilitlidir: müşteri hiçbir şeyi taşıyamaz, her kombinasyon baskıya hazırdır.

TELİF: kulüp adı/logosu sunulmaz. Renk takımları renk adıyla anılır, amblemler
geneldir, müşteri kendi görselini yükleyemez; isim alanı yasak kelime
listesinden geçer (services/yasak_kelime).

Yapılandırma `DesignOverlay.forma` (JSONB) — bkz. `yapilandirma_temizle`.
Müşteri seçimleri `alan_degerleri` içinde `_` ile başlayan anahtarlarda gelir
(`_desen`, `_renk1`…); hepsi burada şablonun izin verdikleriyle doğrulanır —
istemciye güvenilmez.

DESEN GEOMETRİSİ üç yerde AYNI olmalı (ekran, önizleme PNG'si, baskı):
  backend/app/services/forma.py            → desen_sekilleri   (baskı, asıl)
  storefront/components/studio/forma.ts    → desenSekilleri    (tuval + önizleme)
  panel/src/lib/formaDesen.js              → desenSekilleri    (panel önizlemesi)
scripts/forma_test.py bu dosyadaki çıktıyı sabit değerlerle karşılaştırır.
"""
from __future__ import annotations

import re
from pathlib import Path

# anahtar → müşteriye görünen ad (sıra = panel/vitrin sırası)
DESENLER: dict[str, str] = {
    "dikey": "Dikey çizgili",
    "yatay": "Yatay çizgili",
    "capraz": "Çapraz çizgili",
    "yari": "Yarı yarıya",
    "kareli": "Kareli",
    "duz": "Tek renk",
    "bant": "Göğüs bandı",
    "orta_serit": "Orta şerit",
    "capraz_bant": "Çapraz bant",
}
YOGUNLUKLAR = ("ince", "orta", "kalin")
# Yazı konturu kalınlığı / punto (harfin DIŞINDA görünen kısım).
# İstemcideki eşi: storefront/components/studio/forma.ts → KONTUR_ORANLARI
KONTUR_ORANLARI = {"ince": 0.018, "orta": 0.032, "kalin": 0.05}


def kontur_orani(anahtar) -> float:
    return KONTUR_ORANLARI.get(str(anahtar or "orta"), KONTUR_ORANLARI["orta"])


def kirp_birim_kare(cokgen: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Çokgeni birim kareye (0-1) kırp (Sutherland–Hodgman). Çapraz desenlerin
    şeritleri karenin dışına uzanır; PNG'de tuval kendiliğinden keser, vektör
    PDF'te ise taşan kısım sayfa dışına çizilmiş olurdu."""
    def kes(noktalar, icinde, kesisim):
        cikti = []
        for i, b in enumerate(noktalar):
            a = noktalar[i - 1]
            if icinde(b):
                if not icinde(a):
                    cikti.append(kesisim(a, b))
                cikti.append(b)
            elif icinde(a):
                cikti.append(kesisim(a, b))
        return cikti

    def x_kes(v):
        return lambda a, b: (v, a[1] + (b[1] - a[1]) * (v - a[0]) / (b[0] - a[0]))

    def y_kes(v):
        return lambda a, b: (a[0] + (b[0] - a[0]) * (v - a[1]) / (b[1] - a[1]), v)

    n = list(cokgen)
    for icinde, kesisim in ((lambda q: q[0] >= 0, x_kes(0.0)), (lambda q: q[0] <= 1, x_kes(1.0)),
                            (lambda q: q[1] >= 0, y_kes(0.0)), (lambda q: q[1] <= 1, y_kes(1.0))):
        if not n:
            break
        n = kes(n, icinde, kesisim)
    return n
# Formaya yakışan, Türkçe harfleri TAM olan fontlar (design_render.FONT_FILES anahtarları)
VARSAYILAN_FONTLAR = ["anton", "bebas", "oswald", "russo", "staatliches", "montserrat",
                      "bungee", "alfaslab"]

# Hazır amblem kütüphanesi — tek renkli maske PNG'leri (scripts/amblem_uret.py üretir).
# Dosyalar app/sablon_gorselleri/amblem/<anahtar>.png; açılışta /storage/sablon/amblem/
# altına kopyalanır (services/storage.sablon_gorsellerini_kur).
AMBLEMLER: dict[str, str] = {
    "kalkan": "Kalkan",
    "yildiz": "Yıldız",
    "yildiz_2": "İki yıldız",
    "yildiz_3": "Üç yıldız (sıra)",
    "yildiz_4": "Dört yıldız",
    "yildiz_5": "Beş yıldız",
    "uc_yildiz": "Üç yıldız (piramit)",
    "tac": "Taç",
    "top": "Top",
    "simsek": "Şimşek",
    "elmas": "Elmas",
    "kalp": "Kalp",
    "rozet": "Rozet",
    "kupa": "Kupa",
}
AMBLEM_DIZIN = Path(__file__).resolve().parent.parent / "sablon_gorselleri" / "amblem"

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_ANAHTAR = re.compile(r"^[a-z0-9_-]{1,30}$")


def _hex(v, varsayilan: str) -> str:
    s = str(v or "").strip()
    if re.fullmatch(r"#[0-9a-fA-F]{3}", s):
        s = "#" + "".join(ch * 2 for ch in s[1:])
    return s.lower() if _HEX.match(s) else varsayilan


def _sayi(v, varsayilan: float, alt: float = 0.0, ust: float = 1.0) -> float:
    try:
        return max(alt, min(ust, float(v)))
    except (TypeError, ValueError):
        return varsayilan


# ─── Desen geometrisi ────────────────────────────────────────

def desen_sekilleri(desen: str, yogunluk: str = "orta") -> list[tuple[int, list[tuple[float, float]]]]:
    """Desen → çokgenler, birim karede (0-1). Dönüş: [(renk_sırası, [(x, y), …])].

    Zemin HER ZAMAN renk 0 ile doldurulur; buradaki çokgenler onun üstüne
    çizilir. renk_sırası: 0, 1 ya da 2 (üçüncü renk = ince kenar çizgisi).
    Sayılar 6 haneye yuvarlanır — üç dildeki kopyalar aynı çıktıyı versin.
    """
    y = {"ince": 0, "orta": 1, "kalin": 2}.get(yogunluk, 1)
    s: list[tuple[int, list[tuple[float, float]]]] = []

    def kutu(renk: int, x0: float, y0: float, x1: float, y1: float) -> None:
        s.append((renk, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]))

    if desen == "dikey":
        n = (11, 7, 5)[y]                       # tek sayı: iki kenar da renk 0
        for i in range(1, n, 2):
            kutu(1, i / n, 0, (i + 1) / n, 1)
    elif desen == "yatay":
        n = (17, 11, 7)[y]
        for i in range(1, n, 2):
            kutu(1, 0, i / n, 1, (i + 1) / n)
    elif desen == "capraz":
        n = (9, 6, 4)[y]                        # bant çifti sayısı
        g = 1 / n                               # bir çiftin x genişliği
        for i in range(-n, n + 1):
            x0 = i * g
            # sol üstten sağ alta eğik bant (x, y birim karede; kayma = 1)
            s.append((1, [(x0, 0), (x0 + g / 2, 0), (x0 + g / 2 + 1, 1), (x0 + 1, 1)]))
    elif desen == "yari":
        kutu(1, 0.5, 0, 1, 1)
    elif desen == "kareli":
        sutun = (6, 4, 2)[y]
        satir = sutun * 2                       # kılıf ~1:2 → kareler kare görünür
        for r in range(satir):
            for c in range(sutun):
                if (r + c) % 2 == 1:
                    kutu(1, c / sutun, r / satir, (c + 1) / sutun, (r + 1) / satir)
    elif desen == "bant":
        h = (0.10, 0.16, 0.24)[y]
        ust = 0.50 - h / 2
        kutu(1, 0, ust, 1, ust + h)
        kutu(2, 0, ust - 0.012, 1, ust)
        kutu(2, 0, ust + h, 1, ust + h + 0.012)
    elif desen == "orta_serit":
        w = (0.18, 0.30, 0.44)[y]
        sol = 0.5 - w / 2
        kutu(1, sol, 0, sol + w, 1)
        kutu(2, sol - 0.024, 0, sol, 1)
        kutu(2, sol + w, 0, sol + w + 0.024, 1)
    elif desen == "capraz_bant":
        w = (0.16, 0.26, 0.38)[y]
        # sol üst köşeden sağ alta tek kuşak
        s.append((2, [(-w / 2 - 0.03, 0), (w / 2 + 0.03, 0), (1 + w / 2 + 0.03, 1), (1 - w / 2 - 0.03, 1)]))
        s.append((1, [(-w / 2, 0), (w / 2, 0), (1 + w / 2, 1), (1 - w / 2, 1)]))
    # "duz": yalnız zemin
    return [(r, [(round(px, 6), round(py, 6)) for px, py in p]) for r, p in s]


# ─── Yapılandırma (panel) ────────────────────────────────────

VARSAYILAN_PALETLER = [
    {"ad": "Sarı-Kırmızı", "renkler": ["#f5a800", "#8f1414", "#ffffff"]},
    {"ad": "Sarı-Lacivert", "renkler": ["#ffd400", "#0b1f5c", "#ffffff"]},
    {"ad": "Siyah-Beyaz", "renkler": ["#111111", "#f2f2f2", "#9a9a9a"]},
    {"ad": "Bordo-Mavi", "renkler": ["#7a1230", "#3aa0dc", "#ffffff"]},
    {"ad": "Yeşil-Beyaz", "renkler": ["#0e7a3b", "#f2f2f2", "#0b0b0b"]},
    {"ad": "Turuncu-Lacivert", "renkler": ["#f26a1b", "#14245c", "#ffffff"]},
]


def yapilandirma_temizle(ham: dict | None, mevcut: dict | None = None) -> dict | None:
    """Panelden gelen forma ayarını doğrula/normalleştir. None → kapalı.

    ozel_amblemler (yüklenen dosyalar) panel gövdesinden DEĞİL mevcut kayıttan
    alınır: dosya yolu yalnız yükleme ucu tarafından yazılır; gövdeden yalnız
    hangilerinin KALDIĞI (anahtar listesi) ve adları okunur.
    """
    if not ham or not ham.get("aktif"):
        return None
    mevcut = mevcut or {}

    desenler = [d for d in (ham.get("desenler") or []) if d in DESENLER] or list(DESENLER)
    fontlar = [str(f) for f in (ham.get("fontlar") or []) if _ANAHTAR.match(str(f))][:12] \
        or list(VARSAYILAN_FONTLAR)

    paletler = []
    for p in (ham.get("paletler") or [])[:12]:
        if not isinstance(p, dict):
            continue
        ad = str(p.get("ad") or "").strip()[:30]
        renkler = [_hex(r, "") for r in (p.get("renkler") or [])][:3]
        if ad and len(renkler) >= 2 and all(renkler):
            while len(renkler) < 3:
                renkler.append("#ffffff")
            paletler.append({"ad": ad, "renkler": renkler})
    if not paletler:
        paletler = [dict(p) for p in VARSAYILAN_PALETLER]

    eski_ozel = {a["key"]: a for a in (mevcut.get("ozel_amblemler") or [])
                 if isinstance(a, dict) and a.get("key") and a.get("image_path")}
    ozel = []
    for a in (ham.get("ozel_amblemler") or [])[:20]:
        k = str((a or {}).get("key") or "")
        if k in eski_ozel:
            ozel.append({"key": k, "image_path": eski_ozel[k]["image_path"],
                         "ad": str(a.get("ad") or eski_ozel[k].get("ad") or "Amblem").strip()[:30]})
    gecerli_amblem = set(AMBLEMLER) | {a["key"] for a in ozel}
    amblemler = [a for a in (ham.get("amblemler") or []) if a in gecerli_amblem]

    k = ham.get("amblem_kutu") or {}
    kutu = {"x": _sayi(k.get("x"), 0.62), "y": _sayi(k.get("y"), 0.30),
            "w": _sayi(k.get("w"), 0.24, 0.03), "h": _sayi(k.get("h"), 0.12, 0.02)}

    v = ham.get("varsayilan") or {}
    renkler = [_hex(r, "") for r in (v.get("renkler") or [])][:3]
    if len(renkler) < 2 or not all(renkler):
        renkler = list(paletler[0]["renkler"])
    while len(renkler) < 3:
        renkler.append("#ffffff")
    amblem = v.get("amblem") if v.get("amblem") in amblemler else (amblemler[0] if amblemler else "")
    varsayilan = {
        "desen": v.get("desen") if v.get("desen") in desenler else desenler[0],
        "yogunluk": v.get("yogunluk") if v.get("yogunluk") in YOGUNLUKLAR else "orta",
        "renkler": renkler,
        "font": v.get("font") if v.get("font") in fontlar else fontlar[0],
        "yazi_renk": _hex(v.get("yazi_renk"), "#ffffff"),
        "kontur": _hex(v.get("kontur"), "") if v.get("kontur") else "",
        "kontur_kalinlik": v.get("kontur_kalinlik") if v.get("kontur_kalinlik") in KONTUR_ORANLARI else "orta",
        "amblem": amblem or "",
        "amblem_renk": _hex(v.get("amblem_renk"), "#ffffff"),
    }

    ek = []
    for kelime in (ham.get("yasak_ek") or [])[:60]:
        t = str(kelime or "").strip()[:40]
        if len(t) >= 2:
            ek.append(t)

    return {
        "aktif": True,
        # kilitli: HAZIR ÜRÜN — müşteri deseni/rengi/yazı tipini/amblemi
        # değiştiremez, yalnız yazı alanlarını (isim, numara) doldurur. Tasarım
        # "başlangıç görünümü"nden çizilir. Aynı forma, renkleri hazır ayrı
        # ürünler olarak satılır ("Sarı-Kırmızı", "Siyah-Beyaz"…).
        "kilitli": bool(ham.get("kilitli")),
        "desenler": desenler,
        "paletler": paletler,
        "serbest_renk": ham.get("serbest_renk", True) is not False,
        "fontlar": fontlar,
        "amblemler": amblemler,
        "ozel_amblemler": ozel,
        "amblem_kutu": kutu,
        "varsayilan": varsayilan,
        "yasak": ham.get("yasak", True) is not False,
        "yasak_ek": ek,
    }


def amblem_listesi(forma: dict) -> list[dict]:
    """Şablonda sunulan amblemler: {key, ad, url} (hazır + mağazanın yükledikleri)."""
    ozel = {a["key"]: a for a in (forma.get("ozel_amblemler") or [])}
    liste = []
    for k in forma.get("amblemler") or []:
        if k in ozel:
            liste.append({"key": k, "ad": ozel[k].get("ad") or "Amblem",
                          "url": f"/storage/{ozel[k]['image_path']}"})
        elif k in AMBLEMLER:
            liste.append({"key": k, "ad": AMBLEMLER[k], "url": f"/storage/sablon/amblem/{k}.png"})
    return liste


def vitrin_ozeti(forma: dict | None) -> dict | None:
    """Vitrine gönderilecek seçenekler (dosya yolları ve yasak listesi sızmaz)."""
    if not forma or not forma.get("aktif"):
        return None
    return {
        "kilitli": bool(forma.get("kilitli")),
        "desenler": [{"key": d, "ad": DESENLER[d]} for d in forma["desenler"] if d in DESENLER],
        "paletler": forma["paletler"],
        "serbest_renk": bool(forma.get("serbest_renk", True)),
        "fontlar": forma["fontlar"],
        "amblemler": amblem_listesi(forma),
        "amblem_kutu": forma["amblem_kutu"],
        "varsayilan": forma["varsayilan"],
        "yasak": bool(forma.get("yasak", True)),
    }


# ─── Müşteri seçimleri ───────────────────────────────────────

def secimleri_coz(forma: dict, degerler: dict | None) -> dict:
    """alan_degerleri içindeki `_…` anahtarlarını şablonun izin verdikleriyle
    doğrula. Geçersiz/eksik her seçim şablonun varsayılanına düşer."""
    # Hazır ürün (kilitli): desen/renk/yazı tipi/amblem seçimleri YOK SAYILIR.
    # KONTUR istisna — hazır üründe de müşterinin tercihidir (aç/kapa, renk,
    # kalınlık): tasarımı değiştirmez, yalnız yazının okunurluğunu.
    d = degerler or {}
    if forma.get("kilitli"):
        d = {k: v for k, v in d.items() if k in ("_kontur", "_kontur_kalinlik")}
    v = forma["varsayilan"]

    desen = d.get("_desen") if d.get("_desen") in forma["desenler"] else v["desen"]
    yogunluk = d.get("_yogunluk") if d.get("_yogunluk") in YOGUNLUKLAR else v["yogunluk"]

    renkler = [_hex(d.get(f"_renk{i + 1}"), v["renkler"][i]) for i in range(3)]
    if not forma.get("serbest_renk", True):
        # Serbest renk kapalı: üçlü, tanımlı takımlardan BİRİ olmalı
        izinli = [[r.lower() for r in p["renkler"]] for p in forma["paletler"]]
        izinli.append([r.lower() for r in v["renkler"]])
        if renkler not in izinli:
            renkler = list(v["renkler"])

    font = d.get("_font") if d.get("_font") in forma["fontlar"] else v["font"]
    yazi_renk = _hex(d.get("_yazi_renk"), v["yazi_renk"])
    kontur_ham = d.get("_kontur")
    kontur = v["kontur"] if kontur_ham is None else (_hex(kontur_ham, "") if kontur_ham else "")

    sunulan = {a["key"]: a for a in amblem_listesi(forma)}
    amblem_ham = d.get("_amblem")
    amblem = v["amblem"] if amblem_ham is None else (amblem_ham if amblem_ham in sunulan else "")
    if amblem not in sunulan:
        amblem = ""
    return {
        "desen": desen, "yogunluk": yogunluk, "renkler": renkler,
        "font": font, "yazi_renk": yazi_renk, "kontur": kontur,
        "kontur_kalinlik": d.get("_kontur_kalinlik") if d.get("_kontur_kalinlik") in KONTUR_ORANLARI
        else v.get("kontur_kalinlik", "orta"),
        "amblem": amblem, "amblem_url": sunulan[amblem]["url"] if amblem else None,
        "amblem_renk": _hex(d.get("_amblem_renk"), v["amblem_renk"]),
    }


def amblem_dosyasi(forma: dict | None, anahtar: str) -> Path | None:
    """Amblem anahtarı → diskteki maske dosyası. Yol İSTEMCİDEN DEĞİL şablon
    kaydından/hazır kütüphaneden çözülür."""
    from app.services.storage import STORAGE_ROOT

    for a in ((forma or {}).get("ozel_amblemler") or []):
        if a.get("key") == anahtar and a.get("image_path"):
            p = STORAGE_ROOT / a["image_path"]
            return p if p.is_file() else None
    if anahtar in AMBLEMLER:
        p = AMBLEM_DIZIN / f"{anahtar}.png"
        return p if p.is_file() else None
    return None
