#!/usr/bin/env python3
"""Füzyon teması — şema temizliği (services/theme.py).

Hazır şablon kaydet → oku turunda bozulmadan kalmalı; panelden ya da elle
düzenlenmiş config'ten gelen tehlikeli/bozuk değerler (javascript: bağlantı,
geçersiz renk, tanımsız seçenek) vitrine ULAŞMAMALI. Veritabanı gerekmez.

Koşum: cd backend && .venv/bin/python scripts/tema_fuzyon_test.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.theme import (  # noqa: E402
    MAX_SECTIONS, THEME_PRESETS, resolve_theme, validate_theme_patch,
)

GECTI = KALDI = 0


def kontrol(ad, gercek, beklenen):
    global GECTI, KALDI
    if gercek == beklenen:
        GECTI += 1
        print(f"  ✓ {ad}")
    else:
        KALDI += 1
        print(f"  ✗ {ad}: beklenen {beklenen!r}, gelen {gercek!r}")


def tur(tema: dict) -> dict:
    """Panel kaydı + vitrin okuması."""
    return resolve_theme({"theme": validate_theme_patch(tema)})


def bolum(tip: str, ayar: dict, **meta) -> dict:
    return tur({"sections": [{"id": "x", "type": tip, "settings": ayar, **meta}]})["sections"][0]


def main() -> int:
    print("Füzyon şablonu")
    t = tur(THEME_PRESETS["fuzyon"]["theme"])
    tipler = [s["type"] for s in t["sections"]]
    kontrol("13 bölüm korunur", len(tipler), 13)
    kontrol("yeni bölüm tipleri", [x for x in tipler if x in ("kurdele", "stil_onerici", "adimlar", "kilif_onizleme")],
            ["kurdele", "stil_onerici", "adimlar", "kilif_onizleme"])
    kontrol("akış çizgisi işaretleri", [s["id"] for s in t["sections"] if s["akis"]],
            ["fz-urunler", "fz-imza", "fz-adimlar"])
    kontrol("editoryal yazı tipi", t["font"], "editoryal")
    kontrol("görünüm", {k: t["style"][k] for k in ("header_layout", "card_style", "heading_style", "footer_stil")},
            {"header_layout": "vitrin", "card_style": "yumusak", "heading_style": "editoryal", "footer_stil": "genis"})
    kontrol("hero bölünmüş + başlık satır sonu", (t["sections"][0]["settings"]["stil"],
            t["sections"][0]["settings"]["slides"][0]["title"]), ("bolunmus", "Fotoğrafın,\nkılıfın olsun."))
    kontrol("uydurma müşteri yorumu yok", t["sections"][7]["settings"]["items"], [])
    kontrol("son bakılanlar SSS'den önce", tipler[-2:], ["son_bakilanlar", "faq"])
    kontrol("sepete uçuş açık (şablon) / kapalı (varsayılan)",
            (t["animations"]["sepete_ucus"], tur({})["animations"]["sepete_ucus"]), (True, False))
    kontrol("mağaza adı yer tutucusu (vitrin doldurur)",
            any(i["text"] == "{magaza}" for i in t["sections"][3]["settings"]["items"]), True)
    kontrol("bölüm sınırı 16", MAX_SECTIONS, 16)

    print("Temizlik")
    s = bolum("icon_bar", {"stil": "serit", "items": [
        {"icon": "kargo", "title": "A", "url": "javascript:alert(1)"},
        {"icon": "iade", "title": "B", "url": "/iade"},
        {"icon": "eposta", "title": "C", "url": "mailto:a@b.co"},
        {"icon": "x", "title": "D", "url": "//kotu.site"}]})["settings"]
    kontrol("ikon bağlantıları güvenli", [i["url"] for i in s["items"]], ["", "/iade", "mailto:a@b.co", ""])
    kontrol("tanımsız stil → varsayılan", bolum("icon_bar", {"stil": "bilinmez"})["settings"]["stil"], "kart")
    s = bolum("stil_onerici", {"secenekler": [
        {"etiket": "Sakin", "renk": "red", "zemin": "#e5e8ed", "urun": "u1", "kelime": "SANAT.UZUN.KELIME.X"},
        {"etiket": "", "urun": "u2"}]})["settings"]["secenekler"]
    kontrol("etiketsiz seçenek atılır, geçersiz renk varsayılana", (len(s), s[0]["renk"], s[0]["zemin"]),
            (1, "#888888", "#e5e8ed"))
    kontrol("büyük kelime kısaltılır", len(s[0]["kelime"]), 14)
    s = bolum("kurdele", {"palet": "gokkusagi", "sembol": "", "items": [{"text": "A", "buyuk": 1}, {"text": " "}]})["settings"]
    kontrol("kurdele temizliği", (s["palet"], s["sembol"], s["items"]), ("neon", "✦", [{"text": "A", "buyuk": True}]))
    s = bolum("testimonials", {"stil": "fotografli", "items": [
        {"text": "iyi", "image": "javascript:x"}, {"text": "güzel", "image": "/storage/a.jpg"}]})["settings"]["items"]
    kontrol("yorum fotoğrafı yalnız depo/https", [i["image"] for i in s], ["", "/storage/a.jpg"])
    s = bolum("adimlar", {"items": [{"title": "Bir", "url": "javascript:x"}, {"title": ""}]})["settings"]["items"]
    kontrol("adım bağlantısı temizlenir, başlıksız adım atılır", s, [{"title": "Bir", "text": "", "url": ""}])
    kontrol("önizleme hedefi boşsa /tasarla",
            bolum("kilif_onizleme", {"cta_url": "javascript:x"})["settings"]["cta_url"], "/tasarla")
    kontrol("hero pano rengi doğrulanır", bolum("hero_slider", {"panel_renk": "url(x)"})["settings"]["panel_renk"], "#efefef")
    kontrol("slayt görsel kipi", bolum("hero_slider", {"slides": [{"title": "a", "gorsel_kip": "x"}]})
            ["settings"]["slides"][0]["gorsel_kip"], "sigdir")
    kontrol("sekmeler en fazla 6", len(bolum("products_grid", {"sekmeler": [f"k{i}" for i in range(9)]})
                                      ["settings"]["sekmeler"]), 6)
    kontrol("galeri bağlantısı güvenli", bolum("gallery", {"baglanti": "javascript:x"})["settings"]["baglanti"], "")
    st = tur({"style": {"ust_link_url": "javascript:x", "ust_not": "x" * 90, "mobil_dock": "evet",
                        "footer_stil": "dev"}})["style"]
    kontrol("üst menü bağlantısı + sınırlar", (st["ust_link_url"], len(st["ust_not"]), st["mobil_dock"], st["footer_stil"]),
            ("", 40, True, "sade"))
    kontrol("eski tema: yeni ayarlar varsayılanla gelir",
            {k: tur({})["style"][k] for k in ("akis_cizgisi", "ilerleme", "mobil_dock")},
            {"akis_cizgisi": False, "ilerleme": False, "mobil_dock": False})

    print(f"\nGECTI: {GECTI}   KALDI: {KALDI}")
    return 1 if KALDI else 0


if __name__ == "__main__":
    sys.exit(main())
