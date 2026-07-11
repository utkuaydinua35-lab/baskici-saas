"""
Zengin metin sanitizasyonu — ürün açıklaması gibi panelden gelen sınırlı
HTML'i beyaz listeyle temizler. Kural: vitrine giden hiçbir HTML sunucuda
temizlenmeden saklanmaz (XSS: script/style/on* olayları/javascript: linkleri).

Bilinçli olarak bağımlılıksız (bleach yok) — stdlib HTMLParser yeterli:
yalnızca izinli etiketler ve izinli öznitelikler geçer, gerisi metne düşer.
"""
from __future__ import annotations

import html
import re
from html.parser import HTMLParser

# Panel editörünün üretebildiği etiketler
ALLOWED_TAGS = {
    "b", "strong", "i", "em", "u", "s", "strike",
    "p", "br", "ul", "ol", "li", "h2", "h3", "a", "div",
}
VOID_TAGS = {"br"}
# href yalnız güvenli şemalar / göreli yollar
SAFE_HREF_PREFIXES = ("http://", "https://", "mailto:", "/", "#")

MAX_LEN = 20000


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self._open: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag not in ALLOWED_TAGS:
            return
        if tag == "a":
            href = next((v or "" for k, v in attrs if k == "href"), "")
            href = href.strip()
            if not href.lower().startswith(SAFE_HREF_PREFIXES):
                href = "#"
            self.out.append(
                f'<a href="{html.escape(href, quote=True)}" rel="noopener nofollow" target="_blank">'
            )
        else:
            self.out.append(f"<{tag}>")
        if tag not in VOID_TAGS:
            self._open.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag not in ALLOWED_TAGS or tag in VOID_TAGS:
            return
        if tag in self._open:
            # Aradaki kapanmamış etiketleri de kapat (dengeli çıktı)
            while self._open:
                t = self._open.pop()
                self.out.append(f"</{t}>")
                if t == tag:
                    break

    def handle_data(self, data: str) -> None:
        self.out.append(html.escape(data))

    def close_all(self) -> None:
        while self._open:
            self.out.append(f"</{self._open.pop()}>")


def looks_like_html(value: str) -> bool:
    return bool(re.search(r"<[a-zA-Z/!]", value))


def sanitize_rich_text(value: str | None) -> str | None:
    """İzinli etiketler dışındaki her şeyi metne indirger; None/boş korunur.

    Düz metin (etiketsiz) olduğu gibi bırakılır — eski açıklamalar ve CSV
    içe aktarımları entity'lenmez; vitrin de aynı ayrımla render eder.
    """
    if not value:
        return value
    if not looks_like_html(value):
        return value
    p = _Sanitizer()
    p.feed(value[:MAX_LEN])
    p.close()
    p.close_all()
    return "".join(p.out).strip() or None
