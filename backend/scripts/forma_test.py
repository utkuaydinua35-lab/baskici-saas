"""Forma tasarlayıcı — desen, seçim doğrulama, baskı çıktısı, kulüp adı engeli.

Sınananlar:
  1. Desen geometrisi sabit değerlerle (üç dildeki kopya aynı kalsın diye:
     storefront/components/studio/forma.ts, panel/src/lib/formaDesen.js).
  2. Panel ayarı temizlenir; müşteri seçimi şablonun izin verdiğinin DIŞINA
     çıkamaz (istemciye güvenilmez).
  3. Baskı dosyası gerçekten o renk/desenle çıkar; saf beyaz #f2f2f2'ye döner;
     amblem seçilen renge boyanır; dosya yolu istemciden alınmaz.
  4. Kulüp adı engeli: kaçamaklar yakalanır, sıradan adlar geçer.
"""
from __future__ import annotations

import io
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import DesignOverlay, Store  # noqa: E402
from app.services import design_render, forma, kisitli_sablon, yasak_kelime  # noqa: E402

GECTI = KALDI = 0


def es(ad, beklenen, gercek):
    global GECTI, KALDI
    if beklenen == gercek:
        GECTI += 1; print(f"  ✓ {ad}")
    else:
        KALDI += 1; print(f"  ✗ {ad}\n      beklenen {beklenen!r}\n      gercek   {gercek!r}")


print("— desen geometrisi")
es("dikey/orta: 3 şerit, ilki 1/7–2/7",
   (3, [(0.142857, 0), (0.285714, 0), (0.285714, 1), (0.142857, 1)]),
   (len(forma.desen_sekilleri("dikey", "orta")), forma.desen_sekilleri("dikey", "orta")[0][1]))
es("kareli/ince: 36 kare", 36, len(forma.desen_sekilleri("kareli", "ince")))
es("çapraz bant: kenar çizgisi (renk 2) önce, bant (renk 1) üstte",
   [(2, [(-0.16, 0), (0.16, 0), (1.16, 1), (0.84, 1)]), (1, [(-0.13, 0), (0.13, 0), (1.13, 1), (0.87, 1)])],
   forma.desen_sekilleri("capraz_bant", "orta"))
es("tek renk: çokgen yok", [], forma.desen_sekilleri("duz"))
es("bilinmeyen desen: çokgen yok (zemin kalır)", [], forma.desen_sekilleri("uydurma"))
es("her desenin her yoğunluğu çiziliyor", True,
   all(isinstance(forma.desen_sekilleri(d, y), list) for d in forma.DESENLER for y in forma.YOGUNLUKLAR))

print("— panel ayarı")
es("kapalı → None", None, forma.yapilandirma_temizle({"aktif": False}))
f = forma.yapilandirma_temizle({
    "aktif": True, "desenler": ["dikey", "uydurma", "yari"],
    "paletler": [{"ad": "Mavi-Beyaz", "renkler": ["#00F", "#ffffff"]}, {"ad": "", "renkler": ["#000000", "#111111"]}],
    "fontlar": ["anton", "bebas"], "amblemler": ["kalkan", "yok-boyle", "ozel-sahte"],
    "ozel_amblemler": [{"key": "ozel-sahte", "ad": "x", "image_path": "../../etc/passwd"}],
    "varsayilan": {"desen": "kareli", "font": "comic", "renkler": ["#123456", "kirmizi"], "amblem": "tac"},
    "yasak_ek": ["Bizim Takım", "x"],
})
es("geçersiz desen atıldı", ["dikey", "yari"], f["desenler"])
es("3 haneli renk açıldı, 3. renk tamamlandı", [{"ad": "Mavi-Beyaz", "renkler": ["#0000ff", "#ffffff", "#ffffff"]}], f["paletler"])
es("gövdeyle gelen sahte amblem dosyası KABUL EDİLMEDİ", ([], ["kalkan"]), (f["ozel_amblemler"], f["amblemler"]))
es("varsayılan desen izinli olana düştü", "dikey", f["varsayilan"]["desen"])
es("varsayılan font izinli olana düştü", "anton", f["varsayilan"]["font"])
es("bozuk varsayılan renk → ilk takım", ["#0000ff", "#ffffff", "#ffffff"], f["varsayilan"]["renkler"])
es("sunulmayan amblem varsayılan olamaz", "kalkan", f["varsayilan"]["amblem"])
es("ek yasak kelime (1 harfli atılır)", ["Bizim Takım"], f["yasak_ek"])

print("— müşteri seçimi (sunucuda doğrulanır)")
s = forma.secimleri_coz(f, {"_desen": "kareli", "_renk1": "#ff0000", "_renk2": "javascript:1",
                            "_font": "gotik", "_amblem": "tac", "_kontur": "#000000", "_yogunluk": "kalin"})
es("izinsiz desen → varsayılan", "dikey", s["desen"])
es("geçerli renk alındı, bozuk renk varsayılana döndü", ["#ff0000", "#ffffff", "#ffffff"], s["renkler"])
es("izinsiz font → varsayılan", "anton", s["font"])
es("sunulmayan amblem → amblemsiz", "", s["amblem"])
es("kontur ve yoğunluk alındı", ("#000000", "kalin"), (s["kontur"], s["yogunluk"]))
es("seçim yok → şablon varsayılanı", ("dikey", "kalkan"),
   (forma.secimleri_coz(f, {})["desen"], forma.secimleri_coz(f, None)["amblem"]))
kilitli = {**f, "serbest_renk": False}
es("serbest renk kapalı: takım dışı renk → varsayılan", f["varsayilan"]["renkler"],
   forma.secimleri_coz(kilitli, {"_renk1": "#ff0000", "_renk2": "#00ff00", "_renk3": "#0000ff"})["renkler"])
es("serbest renk kapalı: tanımlı takım geçer", ["#0000ff", "#ffffff", "#ffffff"],
   forma.secimleri_coz(kilitli, {"_renk1": "#0000FF", "_renk2": "#ffffff", "_renk3": "#ffffff"})["renkler"])
hazir = {**f, "kilitli": True}
es("hazır ürün (kilitli): müşterinin desen/renk/font seçimi YOK SAYILIR",
   (f["varsayilan"]["desen"], f["varsayilan"]["renkler"], f["varsayilan"]["font"]),
   (lambda z: (z["desen"], z["renkler"], z["font"]))(forma.secimleri_coz(
       hazir, {"_desen": "yari", "_renk1": "#ff0000", "_font": "bebas"})))
es("hazır üründe KONTUR müşterinin seçimi olarak kalır", ("#123456", "kalin"),
   (lambda z: (z["kontur"], z["kontur_kalinlik"]))(forma.secimleri_coz(
       hazir, {"_kontur": "#123456", "_kontur_kalinlik": "kalin", "_desen": "yari"})))
es("kilitli bayrağı panel ayarından geçer ve vitrine bildirilir", (True, True),
   (forma.yapilandirma_temizle({"aktif": True, "kilitli": True})["kilitli"],
    forma.vitrin_ozeti(hazir)["kilitli"]))
ozet = forma.vitrin_ozeti({**f, "yasak_ek": ["gizli"]})
es("vitrine dosya yolu ve yasak listesi sızmıyor", False, "yasak_ek" in ozet or "ozel_amblemler" in ozet)

print("— kulüp adı engeli")
for metin in ["Galatasaray", "GALATA SARAY", "g.a.l.a.t.a.s.a.r.a.y", "Fenerbahçeli Ali", "BEŞİKTAŞ",
              "G4L4T4S4R4Y", "GS", "g.s.", " FB ", "bjk", "Real Madrid", "cimbom 1905"]:
    es(f"engellenir: {metin!r}", True, yasak_kelime.yasak_mi(metin))
for metin in ["Utku", "Altay", "Aslan", "Gökhan S.", "10", "Kartal Yılmaz", "Efe 7", "TSubasa", "Gs Yılmaz", ""]:
    es(f"geçer: {metin!r}", False, yasak_kelime.yasak_mi(metin))
es("mağazanın eklediği kelime", True, yasak_kelime.yasak_mi("BİZİM  takım forever", ["Bizim Takım"]))
es("desen/renk seçimleri metin sayılmaz", None,
   yasak_kelime.ilk_yasak({"_desen": "gs", "_font": "fb", "isim": "Utku", "bayrak": True}))
es("yasak alan değeri bulunur", "Cimbom", yasak_kelime.ilk_yasak({"numara": "10", "isim": "Cimbom"}))

print("— katmanlar ve baskı")
db = SessionLocal()
store = db.scalar(select(Store).where(Store.platform == "storefront"))
if not store:
    print("  · vitrin mağazası yok — baskı kısmı atlandı")
else:
    ayar = forma.yapilandirma_temizle({"aktif": True, "amblemler": ["yildiz"], "varsayilan": {
        "desen": "yari", "renkler": ["#ffffff", "#aa0000", "#000000"], "amblem": "yildiz"}})
    ov = DesignOverlay(
        tenant_id=store.tenant_id, store_id=store.id, label=f"forma-test-{uuid.uuid4().hex[:6]}",
        image_path="yok/olmayan.png", mod="kisitli", forma=ayar,
        # Açılabilir öğe (logo/bayrak) BİLEREK var: katman üreticisindeki
        # "gorsel" dalı bir kez forma seçimini ezmiş, kaydedilen tasarım eski
        # sabit zeminle basılacak hâle gelmişti (ekranda doğru görünürken).
        alanlar=[{"key": "logo", "tip": "gorsel", "etiket": "Logo", "image_path": "yok/logo.png",
                  "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.05, "varsayilan": True},
                 {"key": "numara", "tip": "yazi", "etiket": "Numara", "varsayilan": "10",
                  "x": 0.2, "y": 0.6, "w": 0.6, "h": 0.2, "size": 0.2, "font": "anton", "renk": "#ffffff"}])
    db.add(ov); db.commit()
    try:
        katmanlar = kisitli_sablon.layers_uret(ov, {
            "numara": "7", "_renk1": "#ffffff", "_renk2": "#aa0000", "_kontur": "#00ff00",
            "_amblem": "yildiz", "_amblem_renk": "#0000ff"})
        es("zemin: sabit görsel yerine desen katmanı", ("sekil", "desen"),
           (katmanlar[0]["type"], katmanlar[0].get("bicim")))
        es("sıra: desen → amblem → logo → yazı", ["taban", "amblem", "alan-logo", "alan-numara"],
           [k["id"] for k in katmanlar])
        es("yazıya kontur işlendi", "#00ff00", katmanlar[-1].get("kontur"))

        tasarim = SimpleNamespace(id="test", layers=katmanlar)
        sablon = SimpleNamespace(print_width_mm=40, print_height_mm=80, print_dpi=100)
        g = Image.open(io.BytesIO(design_render.render_print_file(db, tasarim, sablon))).convert("RGBA")
        W, H = g.size
        es("sol yarı: saf beyaz BASKI BEYAZINA döndü (#f2f2f2)", (242, 242, 242, 255), g.getpixel((W // 8, H // 10)))
        es("sağ yarı: desen rengi", (170, 0, 0, 255), g.getpixel((W - W // 8, H // 10)))
        k = ayar["amblem_kutu"]
        ax, ay = round((k["x"] + k["w"] / 2) * W), round((k["y"] + k["h"] * 0.55) * H)
        es("amblem müşterinin seçtiği renkte basıldı", (0, 0, 255, 255), g.getpixel((ax, ay)))
        kirpik = g.crop((round(0.2 * W), round(0.6 * H), round(0.8 * W), round(0.8 * H)))
        renkler = {c[:3] for _, c in kirpik.getcolors(maxcolors=100000)}
        es("yazı konturu basıldı (yeşil var)", True, (0, 255, 0) in renkler)

        # KONTUR: harf arası açılır — yan yana iki rakamın konturu üst üste binmez
        def satir_genisligi(deg):
            kt = kisitli_sablon.layers_uret(ov, {"numara": "11", "_amblem": "", **deg})
            gg = Image.open(io.BytesIO(design_render.render_print_file(
                db, SimpleNamespace(id="k", layers=[x for x in kt if x["type"] == "text"]), sablon)))
            kutu = gg.getchannel("A").getbbox()
            # iki "1" arasında TAM saydam sütun var mı (konturlar ayrık mı)
            orta = gg.crop(kutu).getchannel("A")
            bos = [x for x in range(orta.width) if orta.crop((x, 0, x + 1, orta.height)).getextrema()[1] == 0]
            return bool(bos)
        es("kalın konturda rakamlar birbirine DEĞMİYOR", True,
           satir_genisligi({"_kontur": "#000000", "_kontur_kalinlik": "kalin"}))
        es("kontur kalınlığı katmana işlendi", "ince", kisitli_sablon.layers_uret(
            ov, {"_kontur": "#000000", "_kontur_kalinlik": "ince"})[-1].get("kontur_kalinlik"))
        es("geçersiz kalınlık → şablon varsayılanı", "orta", kisitli_sablon.layers_uret(
            ov, {"_kontur": "#000000", "_kontur_kalinlik": "devasa"})[-1].get("kontur_kalinlik"))

        # PDF: vektör desen + gömülü font + gerçek mm + saf beyaz yok
        import pymupdf

        from app.services import design_pdf
        pdf = design_pdf.render_print_pdf(db, tasarim, sablon)
        sayfa = pymupdf.open("pdf", pdf)[0]
        es("PDF sayfası gerçek ölçüde (40×80 mm)", (40.0, 80.0),
           (round(sayfa.rect.width / 72 * 25.4, 1), round(sayfa.rect.height / 72 * 25.4, 1)))
        cizimler = sayfa.get_drawings()
        es("PDF'te desen VEKTÖR (zemin + sağ yarı)", 2, len(cizimler))
        dolgular = {tuple(round(c, 3) for c in (d.get("fill") or ())) for d in cizimler}
        es("PDF'te saf beyaz (mürekkepsiz) dolgu YOK — beyaz 0.949'a döndü", True,
           (1.0, 1.0, 1.0) not in dolgular and (0.949, 0.949, 0.949) in dolgular)
        es("PDF'te yazı VEKTÖR, font gömülü", True,
           any("Anton" in f[3] for f in sayfa.get_fonts()) and "7" in sayfa.get_text())
        es("PDF'te amblem gömülü (maskeyle, beyaz kutu değil)", True,
           any(g[1] > 0 for g in sayfa.get_images()))     # g[1] = smask xref
        pix = sayfa.get_pixmap(dpi=100)
        px = pix.pixel(round(ax * pix.width / W), round(ay * pix.height / H))
        es("PDF'te amblem seçilen renkte", True, px[2] > 200 and px[0] < 60 and px[1] < 60)

        # İstemci katmana kendi adresini yazsa da dosya şablon kaydından çözülür
        sahte = [dict(k2, url="https://kotu.example/logo.png", amblem="../../etc/passwd")
                 if k2.get("bicim") == "amblem" else k2 for k2 in katmanlar]
        g2 = Image.open(io.BytesIO(design_render.render_print_file(
            db, SimpleNamespace(id="t2", layers=sahte), sablon))).convert("RGBA")
        es("sahte amblem anahtarı/adresi basılmaz", (170, 0, 0, 255), g2.getpixel((ax, ay)))
    finally:
        db.delete(ov); db.commit()
db.close()

print(f"\n{GECTI} GECTI, {KALDI} KALDI")
sys.exit(1 if KALDI else 0)
