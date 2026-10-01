"""Eski ham kampanya kodu (indirim çarkı + "Gitmeden önce" pop-up'ı) → tema ayarı.

Çark ve çıkış pop-up'ı eskiden panelin "Özel Kod → Hazır ekle" parçacıklarıyla
HAM KOD olarak ekleniyordu. O kodun iki kusuru vardı:
  • çıkış pop-up'ı "gördüm" kaydını yalnız sayfa açılışında kontrol ediyordu →
    kapatınca imleç her yukarı çıktığında YENİDEN açılıyordu (sahada görüldü);
  • çark 260 px'lik canvas'tı → retina ekranda bulanık/pikselli.
Yeni bileşenler (vitrin IndirimCarki / CikisPopup) ikisini de düzgün yapar.

Panel bu kodu algılayıp "Ayarlara aktar / Eski kodu kaldır" öneriyor ama
mağaza bu adımları yapmadıkça canlıda eski kod çalışmaya devam ediyordu. Burada
vitrine GİDEN yanıtta (kayıtlı veriye dokunmadan) eski bloklar çıkarılır;
tema aracı kapalıysa eski koddaki metin/kupon/süreyle yeni araç açılır.
Ayrıştırma kuralları panel lib/snippets.js (kampanyaKodunuAyristir) ile aynı.
"""
from __future__ import annotations

import re

CARK_BASLARI = ("<!-- İndirim çarkı", '<div id="bz-wheel-wrap"')
CIKIS_BASLARI = ("<!-- Çıkış niyeti", '<div id="bz-exit"')
HTML_ALANLARI = ("head_html", "body_html")


def _bloklar(html: str, basliklar) -> list[tuple[int, int]]:
    """[baş, son) — yorum satırı ya da kapsayıcı div → ardından gelen İLK </script>."""
    out, i = [], 0
    while True:
        adaylar = [x for x in (html.find(b, i) for b in basliklar) if x >= 0]
        if not adaylar:
            return out
        bas = min(adaylar)
        son = html.find("</script>", bas)
        if son < 0:
            return out
        out.append((bas, son + len("</script>")))
        i = son + 1


def _bul(desen: str, s: str):
    m = re.search(desen, s)
    return m.group(1) if m else None


def _duz(s) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "", s or "")).strip()


def _sayi(s):
    try:
        return int(s) if s is not None else None
    except ValueError:
        return None


def _cark_oku(k: str) -> dict:
    dilimler = [
        {"yazi": m.group(1), "kod": m.group(2) or ""}
        for m in re.finditer(r"\{\s*yazi:\s*'([^']*)'\s*,\s*kod:\s*(?:'([^']*)'|null)\s*\}", k)
    ]
    d = {
        "enabled": True,
        "baslik": _duz(_bul(r"<h3>([\s\S]*?)</h3>", k)),
        "metin": _duz(_bul(r"<p>([\s\S]*?)</p>", k)),
        "buton": _duz(_bul(r'id="bz-wheel-go">([\s\S]*?)<', k)),
        "gecikme_sn": _sayi(_bul(r"GECIKME_SN\s*=\s*(\d+)", k)),
        "tekrar_gun": _sayi(_bul(r"TEKRAR_GUN\s*=\s*(\d+)", k)),
        "dilimler": dilimler if len(dilimler) >= 2 else None,
    }
    return {a: v for a, v in d.items() if v not in (None, "")}


def _cikis_oku(k: str) -> dict:
    ms = _sayi(_bul(r"setTimeout\(\s*ac\s*,\s*(\d+)\s*\)", k))
    d = {
        "enabled": True,
        "baslik": _duz(_bul(r"<h3>([\s\S]*?)</h3>", k)),
        "metin": _duz(_bul(r"<p>([\s\S]*?)</p>", k)),
        "kupon": _duz(_bul(r'id="bz-exit-code">([\s\S]*?)<', k)),
        "buton": _duz(_bul(r'id="bz-exit-cta">([\s\S]*?)<', k)),
        "vazgec": _duz(_bul(r'id="bz-exit-no">([\s\S]*?)<', k)),
        "tekrar_gun": _sayi(_bul(r"\bGUN\s*=\s*(\d+)", k)),
        "mobil_gecikme_sn": round(ms / 1000) if ms else None,
    }
    return {a: v for a, v in d.items() if v not in (None, "")}


def ayikla(custom_code) -> tuple[dict | None, dict | None, dict | None]:
    """(eski bloklarından arındırılmış özel kod, çark ayarı|None, çıkış ayarı|None).

    Aynı blok birden çok kez yapıştırılmışsa (sahada görüldü) HEPSİ çıkarılır;
    ayar ilk bloktan okunur. Özel kodda eski blok yoksa kod aynen döner.
    """
    if not isinstance(custom_code, dict):
        return custom_code, None, None
    temiz = dict(custom_code)
    cark = cikis = None
    for alan in HTML_ALANLARI:
        html = temiz.get(alan)
        if not isinstance(html, str) or ("bz-wheel" not in html and "bz-exit" not in html):
            continue
        cb, xb = _bloklar(html, CARK_BASLARI), _bloklar(html, CIKIS_BASLARI)
        if cb and cark is None:
            cark = _cark_oku(html[cb[0][0]:cb[0][1]])
        if xb and cikis is None:
            cikis = _cikis_oku(html[xb[0][0]:xb[0][1]])
        for bas, son in sorted(cb + xb, reverse=True):
            html = html[:bas] + html[son:]
        temiz[alan] = re.sub(r"\n{3,}", "\n\n", html).strip()
    if not any((temiz.get(a) or "").strip() for a in ("head_html", "body_html", "css")):
        temiz = None
    return temiz, cark, cikis
