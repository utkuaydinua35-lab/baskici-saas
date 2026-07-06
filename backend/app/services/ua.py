"""User-Agent -> kısa okunur özet (tarayıcı / OS / cihaz türü).

Tam parse değil; onay ekranında 'Chrome · Windows · masaüstü' gibi bir etiket
üretmek için basit anahtar-kelime eşleşmesi. Kişisel bilgisayar adı ELDE
EDİLEMEZ (tarayıcı vermez) — bu yalnızca UA'dan çıkarılabilen bilgidir.
"""
from __future__ import annotations


def summary(ua: str | None) -> str:
    if not ua:
        return "cihaz bilinmiyor"
    s = ua.lower()

    # OS
    if "windows nt 10" in s or "windows nt 11" in s:
        os = "Windows"
    elif "windows" in s:
        os = "Windows"
    elif "iphone" in s or "ipad" in s or ("cpu os" in s and "mac os" in s):
        os = "iOS"
    elif "android" in s:
        os = "Android"
    elif "mac os x" in s or "macintosh" in s:
        os = "macOS"
    elif "linux" in s:
        os = "Linux"
    else:
        os = "?"

    # Tarayıcı (sıra önemli: Edge/Opera Chrome içerir)
    if "edg/" in s or "edge" in s:
        br = "Edge"
    elif "opr/" in s or "opera" in s:
        br = "Opera"
    elif "samsungbrowser" in s:
        br = "Samsung Internet"
    elif "firefox" in s:
        br = "Firefox"
    elif "chrome" in s or "crios" in s:
        br = "Chrome"
    elif "safari" in s:
        br = "Safari"
    else:
        br = "?"

    # Cihaz türü
    if "mobile" in s or "iphone" in s or "android" in s:
        dev = "mobil"
    elif "ipad" in s or "tablet" in s:
        dev = "tablet"
    else:
        dev = "masaüstü"

    parts = [p for p in (br, os) if p and p != "?"]
    return f"{' · '.join(parts)} · {dev}" if parts else dev
