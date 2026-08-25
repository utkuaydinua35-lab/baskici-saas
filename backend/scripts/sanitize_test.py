"""HTML temizleyici — bilinen XSS atlatma yükleriyle sınama.

sanitize_rich_text ELLE yazılmış (bleach yok). Elle yazılmış temizleyicilerde
hata yapmak kolaydır ve çıktısı vitrinde dangerouslySetInnerHTML ile basılıyor
(storefront/app/urun/[slug]/page.tsx). Bu yüzden ayrı ve kapsamlı sınanıyor.

Ölçüt: çıktıda ÇALIŞTIRILABİLİR hiçbir şey kalmamalı — script/style/iframe
etiketi, on* olay özniteliği, javascript:/data: şemalı href.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.sanitize import sanitize_rich_text  # noqa: E402

GECTI = KALDI = 0

# Çıktıda ASLA bulunmaması gerekenler (ham etiket/öznitelik olarak)
TEHLIKELI = (
    re.compile(r"<\s*script", re.I),
    re.compile(r"<\s*iframe", re.I),
    re.compile(r"<\s*style", re.I),
    re.compile(r"<\s*svg", re.I),
    re.compile(r"<\s*object|<\s*embed|<\s*form|<\s*meta|<\s*link", re.I),
    re.compile(r"\son\w+\s*=", re.I),          # onerror= onload= ...
    re.compile(r"(href|src)\s*=\s*[\"']?\s*javascript:", re.I),
    re.compile(r"(href|src)\s*=\s*[\"']?\s*data:", re.I),
)


def sina(ad: str, yuk: str) -> None:
    global GECTI, KALDI
    cikti = sanitize_rich_text(yuk) or ""
    kalan = [p.pattern for p in TEHLIKELI if p.search(cikti)]
    if not kalan:
        GECTI += 1
        print(f"  ✓ {ad}")
    else:
        KALDI += 1
        print(f"  ✗ {ad}\n      yük   : {yuk[:90]!r}\n      çıktı : {cikti[:120]!r}"
              f"\n      kalan : {kalan}")


print("\n── Temel script enjeksiyonu ──")
sina("script etiketi", "<script>alert(1)</script>")
sina("büyük harf SCRIPT", "<SCRIPT>alert(1)</SCRIPT>")
sina("boşluklu <  script", "<  script>alert(1)</script>")
sina("yeni satırlı", "<script\n>alert(1)</script>")
sina("null bayt", "<scri\x00pt>alert(1)</script>")
sina("iç içe", "<scr<script>ipt>alert(1)</script>")

print("\n── Olay öznitelikleri ──")
sina("img onerror", '<img src=x onerror=alert(1)>')
sina("izinli etikette onclick", '<p onclick="alert(1)">metin</p>')
sina("izinli etikette onmouseover", '<b onmouseover=alert(1)>x</b>')
sina("tırnaksız öznitelik", "<div onload=alert(1)>x</div>")
sina("büyük harf ONERROR", '<img SRC=x ONERROR=alert(1)>')
sina("satır sonlu öznitelik", '<img src=x on\nerror=alert(1)>')
sina("body onload", '<body onload=alert(1)>')
sina("svg onload", '<svg onload=alert(1)>')

print("\n── Link şemaları ──")
sina("javascript: href", '<a href="javascript:alert(1)">tık</a>')
sina("JaVaScRiPt: karışık", '<a href="JaVaScRiPt:alert(1)">tık</a>')
sina("boşluklu javascript:", '<a href=" javascript:alert(1)">tık</a>')
sina("data: href", '<a href="data:text/html,<script>alert(1)</script>">tık</a>')
sina("vbscript:", '<a href="vbscript:msgbox(1)">tık</a>')
sina("entity kaçışlı", '<a href="&#106;avascript:alert(1)">tık</a>')

print("\n── Diğer vektörler ──")
sina("iframe srcdoc", '<iframe srcdoc="<script>alert(1)</script>"></iframe>')
sina("style ifadesi", '<style>body{background:url("javascript:alert(1)")}</style>')
sina("meta refresh", '<meta http-equiv="refresh" content="0;url=javascript:alert(1)">')
sina("form action", '<form action="javascript:alert(1)"><input></form>')
sina("object data", '<object data="javascript:alert(1)"></object>')
sina("yorum kaçışı", '<!--><script>alert(1)</script>-->')
sina("bogus yorum", '<?xml><script>alert(1)</script>')
sina("kapanmamış etiket", '<div><script>alert(1)')
sina("base etiketi", '<base href="javascript:alert(1)//">')

print("\n── looks_like_html kapısını atlatma denemesi ──")
# Etiketsiz görünüp yine de HTML üretebilen bir şey var mı?
sina("< + boşluk + script", "< script>alert(1)</script>")
sina("< + rakam", "<1script>alert(1)</1script>")
sina("yalnızca metin", "5 < 10 ve 20 > 15")

print("\n── Meşru içerik KORUNMALI ──")


def korunmali(ad, giris, beklenen_parcalar):
    global GECTI, KALDI
    c = sanitize_rich_text(giris) or ""
    eksik = [p for p in beklenen_parcalar if p not in c]
    if not eksik:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      çıktı: {c!r}\n      eksik: {eksik}")


korunmali("kalın/italik", "<p><b>Kalın</b> ve <em>italik</em></p>", ["<b>", "<em>", "Kalın"])
korunmali("liste", "<ul><li>bir</li><li>iki</li></ul>", ["<ul>", "<li>", "bir"])
korunmali("güvenli link", '<a href="https://ornek.com">site</a>',
          ['href="https://ornek.com"', "rel=", "site"])
korunmali("göreli link", '<a href="/urunler">ürünler</a>', ['href="/urunler"'])
korunmali("başlık", "<h2>Başlık</h2><h3>Alt</h3>", ["<h2>", "<h3>"])
korunmali("düz metin aynen", "Sadece düz açıklama metni.", ["Sadece düz açıklama metni."])

print(f"\n{'='*46}\nGECTI: {GECTI}   KALDI: {KALDI}\n{'='*46}")
sys.exit(1 if KALDI else 0)
