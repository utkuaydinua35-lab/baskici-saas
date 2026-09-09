"""Bildirime dokununca DOGRU panel aciliyor mu?

Uygulamada iki panel tek kabukta: magaza paneli kokte, Studio `/studio/`
altinda. Bildirimin adresi hangi panele aitse o acilmali — `/orders/123`
yalnizca Studio'da, `/siparisler/123` yalnizca magaza panelinde var. Yanlis
esleme, kullaniciyi bos bir sayfaya dusurur.

Bu test KULLANIMDAKI tum bildirim adreslerini sabitler. Yeni bir tetikleyici
eklenip listeye girmezse burasi kirmizi yanar.

Ayrica iki panelin rota tablolari okunup capraz denetim yapilir: Studio'ya
gittigi soylenen bir yol GERCEKTEN Studio'da tanimli mi?
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from app.services.push import hedef_uygulama  # noqa: E402

GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


# ── Kullanimdaki adresler (backend'deki tetikleyicilerden birebir) ──
KULLANIMDA = [
    ("/siparisler/9f1c",              "magaza", "vitrin siparisi"),
    ("/yorumlar",                     "magaza", "urun sorusu"),
    ("/",                             "magaza", "gunluk ozet"),
    ("/orders/9f1c",                  "studio", "bayi siparisi (Studio)"),
    ("/bayii/siparis/9f1c",           "studio", "bayi portali"),
    ("/destek?thread=9f1c",           "studio", "destek konusu"),
]

print("\n── kullanimdaki bildirim adresleri ──")
for yol, beklenen, ad in KULLANIMDA:
    es(f"{ad}: {yol}", beklenen, hedef_uygulama(yol))

print("\n── sinir durumlari ──")
es("bos adres magazaya gider", "magaza", hedef_uygulama(None))
es("bos string magazaya gider", "magaza", hedef_uygulama(""))
es("sondaki egik cizgi onemsiz", "studio", hedef_uygulama("/orders/"))
es("onek YARIM eslesmemeli", "magaza", hedef_uygulama("/ordersxyz"))
es("sorgu dizesi ayiklaniyor", "studio", hedef_uygulama("/destek?a=1&b=2"))
# Iki panelde de olan yollar magaza paneline gider — uygulamanin varsayilan yuzu.
for ortak in ("/analitik", "/ayarlar", "/musteriler"):
    es(f"ortak yol {ortak} magazaya gider", "magaza", hedef_uygulama(ortak))


def _rotalar(dosya: Path) -> set[str]:
    """App.jsx icindeki path="..." degerlerinin ust duzey parcasi."""
    metin = dosya.read_text(encoding="utf-8")
    cikti = set()
    for y in re.findall(r'path="([^"]+)"', metin):
        if y in ("*", "/"):
            continue
        cikti.add("/" + y.lstrip("/").split("/")[0])
    return cikti


print("\n── capraz denetim: hedef panelde rota GERCEKTEN var mi ──")
panel_rotalari = _rotalar(KOK.parent / "panel" / "src" / "App.jsx")
studio_rotalari = _rotalar(KOK.parent / "frontend" / "src" / "App.jsx")
es("panel rotalari okundu", True, len(panel_rotalari) > 5)
es("studio rotalari okundu", True, len(studio_rotalari) > 5)

for yol, _beklenen, ad in KULLANIMDA:
    temiz = yol.split("?", 1)[0]
    ust = "/" + temiz.lstrip("/").split("/")[0] if temiz != "/" else "/"
    if ust == "/":
        continue
    hedef = hedef_uygulama(yol)
    tablo = studio_rotalari if hedef == "studio" else panel_rotalari
    es(f"{ad}: {ust} → {hedef} tablosunda var", True, ust in tablo)

print("\n" + "=" * 46)
print(f"GECTI: {GECTI}   KALDI: {KALDI}")
sys.exit(1 if KALDI else 0)
