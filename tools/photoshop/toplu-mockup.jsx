#target photoshop
/**
 * TOPLU MOCKUP — tasarımları mockup PSD'sine oturtur, katalog görseli olarak kaydeder.
 *
 * Photoshop: Dosya → Komut Dosyaları → Gözat… → bu dosyayı seç.
 *
 * NE YAPAR (her tasarım × her şablon için):
 *   1. Şablon PSD'yi açar, içindeki "Design Here" smart object'ini tasarımla değiştirir
 *   2. Filigran/logo katmanlarını GİZLER (katalog görselinde baskının üstü kapanmasın)
 *   3. Ürünü kadrajın ORANI kadarına oturtur (varsayılan %85) — kare kadraj
 *   4. Zemini tek renk yapar (varsayılan #F6F7F9 — beyaz ve şeffaf kılıflar kaybolmasın)
 *   5. Verilen ölçüde JPG/PNG olarak kaydeder, şablonu DEĞİŞTİRMEDEN kapatır
 *
 * Ayarlar aşağıdaki AYAR bloğunda. Klasörleri boş bırakırsan açılışta sorar.
 */


// ══════════════════════════════════════════════════════════════
// AYAR
// ══════════════════════════════════════════════════════════════
var AYAR = {
  // Boş bırakılırsa çalıştırınca klasör seçtirir.
  TASARIM_KLASORU: "",      // ör. "/Users/bernz/Desktop/tasarimlar"
  SABLON_KLASORU: "",       // içindeki TÜM .psd dosyaları şablon sayılır
  CIKTI_KLASORU: "",        // görseller buraya yazılır

  ALT_KLASORLER: true,      // tasarım klasöründeki alt klasörleri de tara
  UZANTILAR: ["png", "jpg", "jpeg", "tif", "tiff", "psd"],  // PDF desteklenmez (önce PNG'ye çevir)

  // ── Kadraj ────────────────────────────────────────────────
  // "sablon" = ŞABLONUN KENDİ kadrajı ve ölçüsü korunur (ör. 4000x3000) —
  //            Photoshop'tan elle kaydetmişsin gibi, kırpma/ölçekleme YOK.
  // "urun"   = ürüne kırpar, kadrajı ORAN'a göre kurar (kılıf kadrajı doldurur).
  KADRAJ: "sablon",
  KARE: true,               // yalnız KADRAJ:"urun" iken: kare kadraj
  ORAN: 0.85,               // yalnız KADRAJ:"urun" iken: ürün kadrajın bu kadarı
  // Uzun kenar. 0 = YENİDEN BOYUTLANDIRMA YOK — şablonun ham çözünürlüğü kalır.
  // ⚠ Küçültmek kılıfı piksel olarak küçültür; 4000x3000'i 2000'e indirince
  //   kılıf yarı boyuta düşüyordu. Katalog için 0 ya da 3000 iyi.
  CIKTI_PX: 0,

  // ── Zemin ─────────────────────────────────────────────────
  ZEMIN_RENK: "F6F7F9",     // "" verirsen zemin rengi hiç eklenmez
  // ⚠ VARSAYILAN: KAPALI. Şablonlarımızda "Background" adlı katman ARKA PLAN
  // DEĞİL, KILIFIN KENDİSİ (kamera modülü, parlama, gölge oradan geliyor);
  // gizlenince çıktı düz bir silüete dönüyordu. Zemin rengi zaten en ALTA
  // eklenen katmandan geliyor — şablonun arkası şeffafsa başka bir şey
  // gerekmiyor. Yalnız gerçekten FOTOĞRAF zeminli şablonlarda true yap.
  ZEMINI_GIZLE: false,
  // Gizlenecek katmanlar (küçük harfe çevrilip ARANIR — parça eşleşme yeter)
  GIZLE: ["filigran", "watermark", "logo", "remove this", "shadow text", "yazı"],

  // ── Çıktı ─────────────────────────────────────────────────
  FORMAT: "png",            // "png" (kayıpsız, şeffaflık korunur) | "jpg"
  JPG_KALITE: 80,           // Web için kaydet kalitesi (0-100)
  AD_SABLONU: "{tasarim}",  // ör. "{tasarim}_{sablon}" — çok şablonda otomatik eklenir
  VARSA_ATLA: true,         // aynı adlı çıktı varsa o tasarımı atla (yarıda kalan işi sürdürür)

  // ── Smart object ──────────────────────────────────────────
  // Tasarımın konacağı katman adları (sırayla aranır, bulunan ilki kullanılır).
  TASARIM_KATMANI: ["Design Here", "Your Work Here", "design", "w1", "bc"],
  YERLESIM: "cover",        // "cover" = kadrajı doldur (taşan kırpılır) | "contain" = sığdır
  // Smart object'in İÇİNDEKİ eski katmanlar gizlensin mi? VARSAYILAN: hayır.
  // Bazı şablonlarda kılıfın dokusu/gölgesi smart object'in içinde duruyor;
  // gizlemek gerçekçiliği siliyor. Eski baskı kenarlardan sızıyorsa true yap.
  PSB_DIGER_KATMANLARI_GIZLE: false,
  // Ürün sınırını belirleyen grup (kırpma bunun sınırına göre yapılır).
  // Bulunamazsa zemin/filigran dışındaki görünür katmanların birleşimi kullanılır.
  URUN_KATMANI: ["Mockup Here", "Mockup", "Product"],
  // Zemin sayılan (kırpmada hesaba KATILMAYAN) katman adları
  ZEMIN_KATMANI: ["background", "arka plan", "arkaplan", "zemin", "bg"]
}

// ══════════════════════════════════════════════════════════════
// Yardımcılar
// ══════════════════════════════════════════════════════════════
function kucuk(s) { return String(s).toLowerCase(); }

function icerir(metin, listesi) {
  var m = kucuk(metin);
  for (var i = 0; i < listesi.length; i++) {
    if (m.indexOf(kucuk(listesi[i])) !== -1) return true;
  }
  return false;
}

function uzanti(ad) {
  var n = String(ad);
  var i = n.lastIndexOf(".");
  return i === -1 ? "" : kucuk(n.substring(i + 1));
}

function adiUzantisiz(dosya) {
  var ad = decodeURI(dosya.name);
  var i = ad.lastIndexOf(".");
  return i === -1 ? ad : ad.substring(0, i);
}

/** Klasördeki dosyaları (istenirse alt klasörlerle) uzantıya göre topla. */
function dosyalariTopla(klasor, uzantilar, altKlasorler) {
  var cikti = [];
  var hepsi = klasor.getFiles();
  for (var i = 0; i < hepsi.length; i++) {
    var f = hepsi[i];
    if (f instanceof Folder) {
      if (altKlasorler) cikti = cikti.concat(dosyalariTopla(f, uzantilar, true));
      continue;
    }
    var u = uzanti(f.name);
    for (var j = 0; j < uzantilar.length; j++) {
      if (u === uzantilar[j]) { cikti.push(f); break; }
    }
  }
  cikti.sort(function (a, b) { return decodeURI(a.name) > decodeURI(b.name) ? 1 : -1; });
  return cikti;
}

/** Belgedeki tüm katmanları (gruplar dahil) düz listeye aç. */
function tumKatmanlar(kap, biriktir) {
  biriktir = biriktir || [];
  for (var i = 0; i < kap.layers.length; i++) {
    var l = kap.layers[i];
    biriktir.push(l);
    if (l.typename === "LayerSet") tumKatmanlar(l, biriktir)
  }
  return biriktir;
}

function katmanBul(doc, adlar) {
  var ks = tumKatmanlar(doc);
  for (var a = 0; a < adlar.length; a++) {
    for (var i = 0; i < ks.length; i++) {
      if (kucuk(ks[i].name) === kucuk(adlar[a])) return ks[i];
    }
  }
  return null;
}

/** Dosyayı AÇIK belgeye yerleştir (Place Embedded) — yeni smart object katmanı döner. */
function yerlestir(dosya) {
  var d = new ActionDescriptor();
  d.putPath(charIDToTypeID("null"), dosya);
  d.putEnumerated(charIDToTypeID("FTcs"), charIDToTypeID("QCSt"), charIDToTypeID("Qcsa"));
  executeAction(charIDToTypeID("Plc "), d, DialogModes.NO);
  return app.activeDocument.activeLayer;
}

/** Katmanı belge kadrajına oturt: cover = doldur, contain = sığdır. */
function kadrajaOturt(doc, katman, mod) {
  var b = katman.bounds;
  var gw = b[2].as("px") - b[0].as("px");
  var gh = b[3].as("px") - b[1].as("px");
  if (gw <= 0 || gh <= 0) return;
  var hw = doc.width.as("px"), hh = doc.height.as("px");
  var olcek = (mod === "contain")
    ? Math.min(hw / gw, hh / gh)
    : Math.max(hw / gw, hh / gh);
  katman.resize(olcek * 100, olcek * 100, AnchorPosition.MIDDLECENTER);
  // ortala
  b = katman.bounds;
  var mx = (b[0].as("px") + b[2].as("px")) / 2;
  var my = (b[1].as("px") + b[3].as("px")) / 2;
  katman.translate(new UnitValue(hw / 2 - mx, "px"), new UnitValue(hh / 2 - my, "px"));
}

/** Smart object'in İÇİNİ aç, tasarımı yerleştir, kaydedip kapat. */
function tasarimiYerlestir(doc, soKatman, tasarimDosyasi, mod, digerleriniGizle) {
  doc.activeLayer = soKatman;
  executeAction(stringIDToTypeID("placedLayerEditContents"), undefined, DialogModes.NO);
  var psb = app.activeDocument;
  if (psb === doc) throw new Error("Smart object açılamadı: " + soKatman.name)
  try {
    var yeni = yerlestir(tasarimDosyasi);
    kadrajaOturt(psb, yeni, mod);
    // Altta kalan eski içerik görünmesin (contain modunda kenarlarda sızabilir)
    for (var i = psb.layers.length - 1; i >= 0; i--) {
      if (psb.layers[i] !== yeni) {
        try { psb.layers[i].visible = false } catch (e) {}
      }
    }
    psb.save();
  } finally {
    psb.close(SaveOptions.SAVECHANGES);
  }
}

/** Katman/grup sınırlarını birleştir → [sol, üst, sağ, alt] (px). */
function sinirBirlestir(mevcut, katman) {
  var b;
  try { b = katman.bounds; } catch (e) { return mevcut; }
  var x1 = b[0].as("px"), y1 = b[1].as("px"), x2 = b[2].as("px"), y2 = b[3].as("px");
  if (x2 - x1 <= 0 || y2 - y1 <= 0) return mevcut;
  if (!mevcut) return [x1, y1, x2, y2];
  return [Math.min(mevcut[0], x1), Math.min(mevcut[1], y1),
          Math.max(mevcut[2], x2), Math.max(mevcut[3], y2)];
}

/** Ürünün kadrajdaki sınırı: GÖRÜNÜR katmanların birleşimi.
 *
 * ⚠ Ada göre eleme YAPILMAZ: şablonlarımızda kılıfın fotoğrafı "Background"
 * adlı katmanda duruyor; adına bakıp elemek kılıfı kadraj dışında bırakıyordu.
 * Gizlenmesi gerekenler bu noktadan ÖNCE zaten gizlenmiş oluyor.
 */
function urunSiniri(doc, ayar) {
  var sinir = null;
  for (var i = 0; i < doc.layers.length; i++) {
    var l = doc.layers[i];
    if (!l.visible) continue;
    sinir = sinirBirlestir(sinir, l);
  }
  if (sinir) return sinir;
  // Hiçbir şey ölçülemezse adı verilen ürün grubuna düş
  var grup = katmanBul(doc, ayar.URUN_KATMANI);
  return grup ? sinirBirlestir(null, grup) : null;
}

function zeminKatmaniEkle(doc, hex) {
  // Kilitli "Background" katmanı varsa normale çevir — altına katman taşınamıyor.
  for (var i = 0; i < doc.layers.length; i++) {
    try {
      if (doc.layers[i].isBackgroundLayer) doc.layers[i].isBackgroundLayer = false;
    } catch (e) {}
  }
  var renk = new SolidColor();
  renk.rgb.hexValue = hex;
  var kat = doc.artLayers.add();
  kat.name = "Zemin";
  doc.selection.selectAll();
  doc.selection.fill(renk);
  doc.selection.deselect();
  kat.move(doc, ElementPlacement.PLACEATEND);
  return kat;
}

function ciktiAdi(ayar, tasarim, sablon, cokSablon) {
  var ad = ayar.AD_SABLONU
    .replace("{tasarim}", adiUzantisiz(tasarim))
    .replace("{sablon}", adiUzantisiz(sablon));
  if (cokSablon && ayar.AD_SABLONU.indexOf("{sablon}") === -1) {
    ad = ad + "_" + adiUzantisiz(sablon);
  }
  return ad;
}

function gorseliKaydet(doc, dosya, ayar) {
  // PNG: "Web için kaydet" yerine normal kaydetme — tam çözünürlük, şeffaflık
  // korunur, büyük tuvalde (4000x3000) ölçek sürprizi yok.
  if (ayar.FORMAT === "png") {
    var po = new PNGSaveOptions();
    po.compression = 6;
    po.interlaced = false;
    doc.saveAs(dosya, po, true, Extension.LOWERCASE);
    return;
  }
  // JPG: Web için kaydet — küçük dosya, katalog/pazar yeri için yeterli
  var o = new ExportOptionsSaveForWeb();
  o.format = SaveDocumentType.JPEG;
  o.quality = ayar.JPG_KALITE;
  o.optimized = true;
  o.includeProfile = false;
  doc.exportDocument(dosya, ExportType.SAVEFORWEB, o);
}

// ══════════════════════════════════════════════════════════════
// Ana akış
// ══════════════════════════════════════════════════════════════
function calistir(ayar) {
  var tKlasor = ayar.TASARIM_KLASORU
    ? new Folder(ayar.TASARIM_KLASORU)
    : Folder.selectDialog("TASARIMLARIN olduğu klasör");
  if (!tKlasor) return null;
  var sKlasor = ayar.SABLON_KLASORU
    ? new Folder(ayar.SABLON_KLASORU)
    : Folder.selectDialog("MOCKUP ŞABLONLARININ (.psd) olduğu klasör");
  if (!sKlasor) return null;
  var cKlasor = ayar.CIKTI_KLASORU
    ? new Folder(ayar.CIKTI_KLASORU)
    : Folder.selectDialog("ÇIKTILARIN kaydedileceği klasör");
  if (!cKlasor) return null;
  if (!cKlasor.exists) cKlasor.create()

  var tasarimlar = dosyalariTopla(tKlasor, ayar.UZANTILAR, ayar.ALT_KLASORLER);
  var sablonlar = dosyalariTopla(sKlasor, ["psd"], false);
  if (!tasarimlar.length) throw new Error("Klasörde tasarım dosyası yok: " + decodeURI(tKlasor.fsName))
  if (!sablonlar.length) throw new Error("Klasörde .psd şablon yok: " + decodeURI(sKlasor.fsName))

  // ⚠ Sessizce "hiçbir şey yapmadım" olmasın: ayar değiştirip tekrar
  // çalıştırıldığında var olan çıktılar atlanıyor ve ekranda sanki iş bitmiş
  // gibi görünüyordu (Yazılan: 0, Atlanan: 35). Artık baştan soruluyor.
  if (ayar.VARSA_ATLA) {
    var varOlan = 0;
    for (var vs = 0; vs < sablonlar.length; vs++) {
      for (var vt = 0; vt < tasarimlar.length; vt++) {
        var vAd = ciktiAdi(ayar, tasarimlar[vt], sablonlar[vs], sablonlar.length > 1);
        if (new File(cKlasor.fsName + "/" + vAd + "." + ayar.FORMAT).exists) varOlan++;
      }
    }
    if (varOlan > 0) {
      var toplam = sablonlar.length * tasarimlar.length;
      ayar.VARSA_ATLA = !confirm(
        "Bu klasörde " + varOlan + " görsel ZATEN VAR (toplam " + toplam + ").\n\n"
        + "Üzerine yazılsın mı?\n\n"
        + "Evet = hepsi yeniden üretilir (ayar değiştirdiysen bunu seç)\n"
        + "Hayır = var olanlar atlanır, yalnız eksikler üretilir",
        false, "Toplu mockup");
    }
  }

  var sonuc = { yazilan: 0, atlanan: 0, hata: 0, satirlar: [] }
  var eskiBirim = app.preferences.rulerUnits;
  var eskiUyari = app.displayDialogs;
  app.preferences.rulerUnits = Units.PIXELS;
  app.displayDialogs = DialogModes.NO;

  try {
    for (var s = 0; s < sablonlar.length; s++) {
      for (var t = 0; t < tasarimlar.length; t++) {
        var tasarim = tasarimlar[t];
        var ad = ciktiAdi(ayar, tasarim, sablonlar[s], sablonlar.length > 1);
        var ciktiDosya = new File(cKlasor.fsName + "/" + ad + "." + ayar.FORMAT);
        if (ayar.VARSA_ATLA && ciktiDosya.exists) {
          sonuc.atlanan++
          sonuc.satirlar.push("ATLANDI (var): " + ad);
          continue;
        }
        var doc = null;
        try {
          doc = app.open(sablonlar[s]);
          var so = katmanBul(doc, ayar.TASARIM_KATMANI);
          if (!so) throw new Error("Tasarım katmanı bulunamadı (" + ayar.TASARIM_KATMANI.join(" / ") + ")")
          tasarimiYerlestir(doc, so, tasarim, ayar.YERLESIM,
                            ayar.PSB_DIGER_KATMANLARI_GIZLE);

          // Filigran/logo gizle — katalog görselinde baskının üstü kapanmasın.
          // Zemin rengi verildiyse şablonun kendi zemini de gizlenir (yoksa yeni
          // renk altta kalır, görsel değişmez).
          var ks = tumKatmanlar(doc);
          for (var i = 0; i < ks.length; i++) {
            var gizle = icerir(ks[i].name, ayar.GIZLE)
              || (ayar.ZEMIN_RENK && ayar.ZEMINI_GIZLE && icerir(ks[i].name, ayar.ZEMIN_KATMANI));
            if (gizle) {
              try { ks[i].visible = false } catch (e) {}
            }
          }

          // Ürünü kadraja oturt (yalnız KADRAJ:"urun"): kırp → kare/oranlı kadraj.
          // KADRAJ:"sablon" iken şablonun kendi kadrajı ve ölçüsü korunur.
          var sinir = (ayar.KADRAJ === "urun") ? urunSiniri(doc, ayar) : null;
          if (sinir) {
            doc.crop([new UnitValue(sinir[0], "px"), new UnitValue(sinir[1], "px"),
                      new UnitValue(sinir[2], "px"), new UnitValue(sinir[3], "px")]);
            var uw = doc.width.as("px"), uh = doc.height.as("px");
            var kenar = Math.max(uw, uh) / ayar.ORAN;
            var yeniW = ayar.KARE ? kenar : uw / ayar.ORAN;
            var yeniH = ayar.KARE ? kenar : uh / ayar.ORAN;
            doc.resizeCanvas(new UnitValue(Math.round(yeniW), "px"),
                             new UnitValue(Math.round(yeniH), "px"),
                             AnchorPosition.MIDDLECENTER);
          }

          if (ayar.ZEMIN_RENK) {
            zeminKatmaniEkle(doc, ayar.ZEMIN_RENK);
            doc.flatten();
          }
          // ⚠ Zemin rengi YOKSA düzleştirme de YOK: flatten şeffaflığı beyazla
          // doldurur, şeffaf PNG isteyen akış bozulurdu.

          // Çıktı ölçüsü (uzun kenar). 0 = DOKUNMA — şablonun ham çözünürlüğü
          // korunur. ⚠ Bu koruma şart: resizeImage(0) Photoshop'ta 1 piksele
          // iniyor ve bütün çıktılar 1x1 olarak kaydediliyordu.
          if (ayar.CIKTI_PX > 0) {
            if (doc.width.as("px") >= doc.height.as("px")) {
              doc.resizeImage(new UnitValue(ayar.CIKTI_PX, "px"), null, 72, ResampleMethod.BICUBICSHARPER);
            } else {
              doc.resizeImage(null, new UnitValue(ayar.CIKTI_PX, "px"), 72, ResampleMethod.BICUBICSHARPER);
            }
          }

          var cw = Math.round(doc.width.as("px")), ch = Math.round(doc.height.as("px"));
          gorseliKaydet(doc, ciktiDosya, ayar);
          sonuc.yazilan++;
          // Ölçü günlüğe yazılır: yanlış ölçekleme (ör. 1x1) sessiz kalmasın
          sonuc.satirlar.push("OK: " + ad + "  (" + cw + "x" + ch + ")");
          if (cw < 200 || ch < 200) {
            sonuc.satirlar.push("   ⚠ ÇOK KÜÇÜK — CIKTI_PX ayarına bak");
          }
        } catch (e) {
          sonuc.hata++
          sonuc.satirlar.push("HATA: " + ad + " → " + e.message);
        } finally {
          // Şablon DEĞİŞMEDEN kapanır — bir sonraki tasarım temiz şablonla başlar
          if (doc) { try { doc.close(SaveOptions.DONOTSAVECHANGES) } catch (e2) {} }
        }
      }
    }
  } finally {
    app.preferences.rulerUnits = eskiBirim;
    app.displayDialogs = eskiUyari;
  }

  // Günlük: ne yazıldı, ne atlandı, ne patladı
  try {
    var log = new File(cKlasor.fsName + "/toplu-mockup-gunluk.txt");
    log.encoding = "UTF-8";
    log.lineFeed = "Unix";       // varsayılan CR: günlük tek satır gibi görünüyordu
    log.open("w");
    log.write("Toplu mockup — " + new Date().toString() + "\n");
    log.write("Yazılan: " + sonuc.yazilan + "  Atlanan: " + sonuc.atlanan + "  Hata: " + sonuc.hata + "\n\n");
    log.write(sonuc.satirlar.join("\n"));
    log.close();
  } catch (e) {}
  return sonuc;
}

try {
  var s = calistir(AYAR);
  if (s) {
    var mesaj = "Bitti.\n\nYazılan: " + s.yazilan + "\nAtlanan: " + s.atlanan + "\nHata: " + s.hata;
    if (s.yazilan === 0 && s.atlanan > 0) {
      mesaj += "\n\n⚠ HİÇBİR GÖRSEL ÜRETİLMEDİ: hepsi zaten vardı ve atlandı."
             + "\nYenilemek için başlangıçtaki soruya 'Evet' de ya da eski çıktıları sil.";
    }
    if (s.hata) mesaj += "\n\nAyrıntı: toplu-mockup-gunluk.txt";
    alert(mesaj);
  }
} catch (e) {
  alert("Çalıştırılamadı:\n" + e.message);
}
