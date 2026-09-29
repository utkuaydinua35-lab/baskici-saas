#!/usr/bin/env python3
"""BERNZ için "Füzyon — BERNZ" TASLAK teması — tasarım dosyasındaki
(bernz-fusion.html) görseller ve metinlerle doldurulmuş hâli.

Genel Füzyon şablonu tüm mağazalar içindir ve görsel alanları boştur (BERNZ'in
ürün fotoğrafları başka mağazada görünmesin). Bu betik BERNZ'e özel kopyayı
kurar:
  • tasarımın görsellerini mağazanın medya kütüphanesine yükler (hero,
    imza seri, Instagram ızgarası, müşteri fotoğrafları — tasarımdaki gibi kırpılmış),
  • tasarımdaki metinleri (kurdele, duyuru, stil önerici, yorumlar…) yazar,
  • stil önerici ürünlerini ve ürün sekmelerini mağazada ADIYLA eşleştirir,
  • mağazanın kendi menüsünü, logosunu, kampanyalarını KORUR (şablon yalnız görünüm).

YAYINA ALMAZ: yalnız taslak oluşturur (vitrin değişmez). Panel → Tema'da
"Füzyon — BERNZ" taslağı görünür; inceleyip "Yayınla" demek sizde.
Koleksiyon kartlarının görseli koleksiyonun kendi görselidir; boş olanlara
tasarımdaki görseli koymak için --koleksiyon-gorselleri (bu CANLIYI etkiler,
yalnız görseli boş koleksiyonlara yazar).

Koşum:  cd backend && .venv/bin/python scripts/fuzyon_bernz_taslak.py [--magaza bernz]
Geri al: ... scripts/fuzyon_bernz_taslak.py --kaldir   (taslağı siler)
"""
import argparse
import copy
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm.attributes import flag_modified  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import CatalogCollection, CatalogProduct, Store  # noqa: E402
from app.services import storage as storage_svc  # noqa: E402
from app.services.theme import THEME_PRESETS, resolve_theme, validate_theme_patch  # noqa: E402

VERI = Path(__file__).resolve().parent / "veri" / "fuzyon_bernz"
TASLAK = "fuzyon-bernz"
# Şablon yalnız görünümü değiştirir — panel TemaPage.sablonuUygula ile aynı liste
KORUNAN = ["logo_url", "favicon_url", "logo_width", "logo_width_mobile", "whatsapp", "footer",
           "nav_links", "cark", "cikis", "cart_messages", "texts", "thankyou", "trust_badges",
           "collection_pages"]


def tr_kucuk(s: str) -> str:
    return (s or "").replace("I", "ı").replace("İ", "i").lower()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--magaza", default="bernz")
    ap.add_argument("--kaldir", action="store_true", help="taslağı sil")
    ap.add_argument("--koleksiyon-gorselleri", action="store_true",
                    help="görseli BOŞ koleksiyonlara tasarım görselini yaz (canlıyı etkiler)")
    a = ap.parse_args()

    db = SessionLocal()
    store = db.query(Store).filter(Store.slug == a.magaza).with_for_update().first()
    if not store:
        print(f"✗ mağaza yok: {a.magaza}")
        return 1
    config = dict(store.config or {})
    taslaklar = dict(config.get("theme_drafts") or {})

    if a.kaldir:
        if taslaklar.pop(TASLAK, None) is None:
            print("Taslak zaten yok.")
            return 0
        config["theme_drafts"] = taslaklar
        store.config = config
        flag_modified(store, "config")
        db.commit()
        print("✓ 'Füzyon — BERNZ' taslağı silindi (yüklenen görseller medya kütüphanesinde kalır).")
        return 0

    if TASLAK not in taslaklar and len(taslaklar) >= 10:
        print("✗ En fazla 10 taslak tutulabiliyor — panelden birini silin.")
        return 1

    yayin = resolve_theme(config)
    t = copy.deepcopy(THEME_PRESETS["fuzyon"]["theme"])
    for alan in KORUNAN:
        if yayin.get(alan) is not None:
            t[alan] = copy.deepcopy(yayin[alan])
    if (yayin.get("popup") or {}).get("baslik"):
        t["popup"] = copy.deepcopy(yayin["popup"])
    if not (t.get("footer") or {}).get("about"):
        t.setdefault("footer", {})["about"] = "Sıra dışı tasarımlar.\nHer gün yanında taşıdığın karakter."

    def yukle(ad: str) -> str:
        yol = VERI / ad
        return storage_svc.save_store_asset(store.tenant_id, store.id, "hero", yol.read_bytes(), yol.name)

    print("Görseller yükleniyor…")
    g = {p.name: yukle(p.name) for p in sorted(VERI.iterdir()) if p.is_file()}
    print(f"  ✓ {len(g)} görsel medya kütüphanesine eklendi")

    # ── Mağaza verisiyle eşleştirme (ürün ve koleksiyon) ──
    urunler = db.query(CatalogProduct).filter(CatalogProduct.store_id == store.id,
                                              CatalogProduct.status == "active").all()
    kolek = db.query(CatalogCollection).filter(CatalogCollection.store_id == store.id,
                                               CatalogCollection.is_active.is_(True)).all()

    def urun_bul(slug: str, *kelimeler: str) -> str:
        for u in urunler:
            if u.slug == slug:
                return u.slug
        for u in urunler:
            if all(k in tr_kucuk(u.title) for k in kelimeler):
                return u.slug
        return ""

    def kolek_bul(*kelimeler: str):
        for c in kolek:
            ad = tr_kucuk(c.title) + " " + c.slug
            if any(k in ad for k in kelimeler):
                return c
        return None

    sec = {s["id"]: s["settings"] for s in t["sections"]}
    t["announcement"]["items"] = [
        {"text": "BERNZ SPECIAL", "url": ""},
        {"text": "KENDİ KILIFINI TASARLA", "url": "/tasarla"},
        {"text": "HER TARZA BİR KOLEKSİYON", "url": "/urunler"},
    ]
    t["style"].update({"ust_link_metin": "Sipariş takibi",
                       "ust_link_url": "https://siparistakip.bernzcompany.com"})

    h = sec["fz-hero"]["slides"]
    h[0]["image"] = g["hero-1.webp"]
    h[1].update({"image": g["hero-2.webp"],
                 "subtitle": "Sanat, F1 ve BERNZ Special serilerinden sana uyan tasarımı seç."})
    editor = urun_bul("editors-choice-tasarim", "editor")
    h[2].update({"image": g["editor-secimi.jpg"], "eyebrow": "SANAT SERİSİ",
                 "subtitle": "Sanat serisinden, sakin tonlarda ve güçlü dokulu bir tasarım.",
                 "cta_url": f"/urun/{editor}" if editor else "/urunler"})

    sec["fz-hizmet"]["items"] = [
        {"icon": "kargo", "title": "Baskı ve kargo süreci", "text": "Siparişin nasıl hazırlanıyor?", "url": ""},
        {"icon": "konum", "title": "Sipariş takibi", "text": "Kargon nerede, anında gör",
         "url": "https://siparistakip.bernzcompany.com"},
        {"icon": "iade", "title": "İade ve değişim", "text": "Koşulları önceden incele", "url": "/iade"},
        {"icon": "eposta", "title": "Destek", "text": "destek@bernzcompany.com",
         "url": "mailto:destek@bernzcompany.com"},
    ]
    # Kategori kartları: görseli olmayan koleksiyonlara tasarımdaki sırayla
    sec["fz-kategori"]["yedek_gorseller"] = [g["kategori-kendi-kilifini-tasarla.png"],
                                             g["kategori-koleksiyon.webp"], g["kategori-android.webp"],
                                             g["anatomic-heart.jpg"]]
    sec["fz-kurdele"]["items"] = [
        {"text": "KENDİ KILIFINI TASARLA", "buyuk": True}, {"text": "BERNZ SPECIAL", "buyuk": False},
        {"text": "Tarzını yanında taşı", "buyuk": False}, {"text": "SIRA DIŞI TASARIMLAR", "buyuk": True},
        {"text": "Art Koleksiyonu", "buyuk": False}, {"text": "F1 Serisi", "buyuk": False},
    ]

    eslesme = {
        0: urun_bul("editors-choice-tasarim", "editor"),
        1: urun_bul("redline-dominance-tasarim-telefon-kilifi-f1-serisi", "redline"),
        2: urun_bul("heart-tasarim-bernz-special-telefon-kilifi", "heart"),
        3: urun_bul("kisiye-ozel-tasarim", "kişiye", "özel"),
    }
    for i, o in enumerate(sec["fz-stil"]["secenekler"]):
        o["urun"] = eslesme.get(i, "")
    sec["fz-stil"]["secenekler"][1]["neden"] = "Yarış ruhunu her gün yanında taşı."

    sekmeler = [c.slug for c in (kolek_bul("special"), kolek_bul("sanat", "art"),
                                 kolek_bul("f1", "yarış"), kolek_bul("kişiye", "kendi")) if c]
    sec["fz-urunler"].update({"sekmeler": list(dict.fromkeys(sekmeler))[:6],
                              "subtitle": "Sanat, F1 ve BERNZ Special serilerinden en çok bakılanlar."})

    special = kolek_bul("special")
    heart = eslesme[2]
    sec["fz-imza"].update({
        "image": g["anatomic-heart.jpg"], "gorsel_notu": "ANATOMIC HEART / BERNZ SPECIAL",
        "eyebrow": "BERNZ SPECIAL", "title": "Anatomic Heart",
        "body": "Anatomik kalp çizimi ve el yazısı notlardan oluşan, BERNZ Special serisinin imza tasarımı.",
        "cta_text": "Special koleksiyonunu keşfet",
        "cta_url": f"/koleksiyon/{special.slug}" if special else (f"/urun/{heart}" if heart else "/urunler"),
    })
    # Gerçek müşteri yorumları (tasarım dosyası, BERNZ sitesinden)
    sec["fz-yorumlar"]["items"] = [
        {"author": "Fatmagül A.", "rating": 5, "image": g["yorum-fatmagul.jpg"],
         "text": "Çok memnunuz hem görüntüsü hem kalitesi sürekli kullanmamıza rağmen hala ilk gün ki gibi."},
        {"author": "Furkan", "rating": 5, "image": g["yorum-furkan.jpg"],
         "text": "Reis kargolar yetişti sonunda çok güzeller elinize emeğinize sağlık hediye içinde teşekkürler"},
        {"author": "Orhan K.", "rating": 5, "image": g["yorum-orhan.jpg"],
         "text": "Ürünüm geldi çok teşekkür ederim"},
    ]
    sec["fz-instagram"].update({
        "title": "@bernzcases’tan", "baglanti": "https://www.instagram.com/bernzcases/",
        "ogeler": [{"url": g[ad], "tip": "gorsel", "link": "https://www.instagram.com/bernzcases/",
                    "etiket": "bernzcases"}
                   for ad in ("kategori-kendi-kilifini-tasarla.png", "anatomic-heart.jpg",
                              "kategori-koleksiyon.webp", "redline-dominance.jpg", "kategori-android.webp")],
    })
    sec["fz-onizleme"]["logo_yazi"] = "BERNZ"
    sec["fz-sss"]["eposta"] = "destek@bernzcompany.com"

    entry = {"name": "Füzyon — BERNZ", "theme": validate_theme_patch(t),
             "updated_at": datetime.now(timezone.utc).isoformat()}
    taslaklar[TASLAK] = entry
    config["theme_drafts"] = taslaklar

    if a.koleksiyon_gorselleri:
        for kelimeler, ad in ((("kendi", "kişiye"), "kategori-kendi-kilifini-tasarla.png"),
                              (("android",), "kategori-android.webp"),
                              (("special",), "anatomic-heart.jpg")):
            c = kolek_bul(*kelimeler)
            if c and not c.image_path:
                c.image_path = g[ad].removeprefix("/storage/")
                print(f"  ✓ koleksiyon görseli: {c.title}")

    store.config = config
    flag_modified(store, "config")
    db.commit()

    print("\n✓ 'Füzyon — BERNZ' taslağı hazır (YAYINDA DEĞİL).")
    print("  Stil önerici ürünleri:", {i: s or "— bulunamadı, panelden seçin" for i, s in eslesme.items()})
    print("  Ürün sekmeleri:", sekmeler or "— eşleşme yok, panelden seçin")
    print("  Kategori kartları koleksiyon görsellerini kullanır",
          "(güncellendi)" if a.koleksiyon_gorselleri else "(--koleksiyon-gorselleri ile boş olanlara yazılır)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
