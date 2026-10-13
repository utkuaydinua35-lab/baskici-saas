// Tuvalin küçük PNG önizlemesi — "Tasarımlarım" listesinde ve panelde görünür.
//
// Bu SADECE önizlemedir. Baskıya giden dosya sunucuda, müşterinin yüklediği
// ORİJİNAL görsellerden ve aynı font dosyalarından üretilir; ekran görüntüsü
// asla baskıya gitmez.
import { fontByKey } from "./fonts";
import { KONTUR_ORAN, desenSekilleri } from "./forma";
import { TAVAN_PUNTO } from "./types";
import type {
  CaseTemplate, ImageLayer, Layer, OverlayLayer, ShapeLayer, TextLayer,
} from "./types";

/** Tasarımda kullanılan yazı tipleri yüklenene kadar bekle (en fazla 3 sn). */
async function fontlariBekle(layers: Layer[]): Promise<void> {
  if (typeof document === "undefined" || !document.fonts) return;
  const yazilar = layers.filter((l) => l.type === "text") as TextLayer[];
  if (!yazilar.length) return;
  const isler = yazilar.map((t) => {
    const f = fontByKey(t.font);
    return document.fonts.load(`16px '${f.css}'`).catch(() => undefined);
  });
  await Promise.race([
    Promise.all(isler),
    new Promise((r) => setTimeout(r, 3000)),
  ]);
}

const gorselYukle = (src: string): Promise<HTMLImageElement> =>
  new Promise((cozumle, reddet) => {
    const im = new Image();
    im.crossOrigin = "anonymous";
    im.onload = () => cozumle(im);
    im.onerror = () => reddet(new Error(src));
    im.src = src;
  });

export async function onizlemeUret(
  template: CaseTemplate, layers: Layer[], genislik = 420,
): Promise<string | null> {
  try {
    // Özel fontlar yüklenmeden ölçüm/çizim yapılırsa yedek font kullanılır:
    // metin genişliği yanlış çıkar, "çerçeveye sığdır" hesabı şaşar.
    await fontlariBekle(layers);
    const kilif = await gorselYukle(template.image_url);
    const oran = kilif.naturalHeight / kilif.naturalWidth;
    const W = genislik;
    const H = Math.round(W * oran);
    const cv = document.createElement("canvas");
    cv.width = W; cv.height = H;
    const ctx = cv.getContext("2d");
    if (!ctx) return null;

    const a = template.area;
    const ax = a.x * W, ay = a.y * H, aw = a.w * W, ah = a.h * H;

    // Sıra tuvaldekiyle BİREBİR: kılıf zemin, tasarım üstünde, kamera adası
    // en üstte. (Eskiden kılıf en üste çiziliyordu — opak kılıf şablonunda
    // tasarımı tamamen örtüyor, önizleme boş kılıf gibi görünüyordu.)
    ctx.drawImage(kilif, 0, 0, W, H);

    ctx.save();
    ctx.beginPath();
    const r = Math.min(aw, ah) * (a.radius || 0);
    if (typeof ctx.roundRect === "function") ctx.roundRect(ax, ay, aw, ah, r);
    else ctx.rect(ax, ay, aw, ah);
    ctx.clip();

    // Dizideki sıra = çizim sırası (ilk eleman en altta). Tipe göre otomatik
    // sıralama yok; müşteri hazır şablonu istediği katmana taşıyabilir.
    for (const l of layers) {
      if (l.type === "overlay") {
        // Şablon zemini tam alanı kaplar; kısıtlı şablonun açılabilir öğesi
        // (kutu'su olan) kendi konumuna çizilir
        const o = l as OverlayLayer;
        try {
          const ov = await gorselYukle(o.url);
          if (o.kutu) {
            ctx.drawImage(ov, ax + o.kutu.x * aw, ay + o.kutu.y * ah,
              o.kutu.w * aw, o.kutu.h * ah);
          } else {
            ctx.drawImage(ov, ax, ay, aw, ah);
          }
        } catch { /* şablon yüklenemezse önizleme yine üretilir */ }
      } else if (l.type === "sekil" && l.bicim === "desen") {
        // Forma zemini — tuvaldeki SVG ile aynı çokgenler
        const renk = (i: number) => l.renkler[Math.min(i, l.renkler.length - 1)] || "#ffffff";
        ctx.fillStyle = renk(0);
        ctx.fillRect(ax, ay, aw, ah);
        for (const c of desenSekilleri(l.desen, l.yogunluk)) {
          ctx.fillStyle = renk(c.renk);
          ctx.beginPath();
          c.nokta.forEach(([x, y], i) => {
            if (i === 0) ctx.moveTo(ax + x * aw, ay + y * ah);
            else ctx.lineTo(ax + x * aw, ay + y * ah);
          });
          ctx.closePath();
          ctx.fill();
        }
      } else if (l.type === "sekil" && l.bicim === "amblem") {
        try {
          const g = await gorselYukle(l.url);
          const kw = l.w * aw, kh = l.h * ah;
          const olcek = Math.min(kw / g.naturalWidth, kh / g.naturalHeight);
          const gw = Math.max(1, g.naturalWidth * olcek), gh = Math.max(1, g.naturalHeight * olcek);
          // Maskeyi ayrı tuvalde seçilen renge boya, sonra yerine çiz
          const m = document.createElement("canvas");
          m.width = Math.ceil(gw); m.height = Math.ceil(gh);
          const mc = m.getContext("2d");
          if (mc) {
            mc.drawImage(g, 0, 0, m.width, m.height);
            mc.globalCompositeOperation = "source-in";
            mc.fillStyle = l.renk;
            mc.fillRect(0, 0, m.width, m.height);
            ctx.drawImage(m, ax + l.x * aw + (kw - gw) / 2, ay + l.y * ah + (kh - gh) / 2, gw, gh);
          }
        } catch { /* amblem yüklenemezse önizleme yine üretilir */ }
      } else if (l.type === "sekil") {
        const sk = l as ShapeLayer;
        const bx = ax + sk.x * aw, by = ay + sk.y * ah, bw = sk.w * aw;
        const kal = Math.max(1, sk.kalinlik * ah);
        ctx.fillStyle = sk.renk_pasif;
        ctx.fillRect(bx, by - kal / 2, bw, kal);
        ctx.fillStyle = sk.renk;
        ctx.fillRect(bx, by - kal / 2, bw * sk.oran, kal);
        ctx.beginPath();
        ctx.arc(bx + bw * sk.oran, by, Math.max(1, sk.boyut * ah), 0, Math.PI * 2);
        ctx.fill();
      } else if (l.type === "image") {
        const im = l as ImageLayer;
        try {
          const g = await gorselYukle(im.url);
          const x = ax + im.x * aw, y = ay + im.y * ah;
          const w = im.w * aw, h = im.h * ah;
          ctx.save();
          ctx.translate(x + w / 2, y + h / 2);
          ctx.rotate(((im.rot || 0) * Math.PI) / 180);
          const c = im.crop;
          if (c) {
            ctx.drawImage(
              g, c.x * g.naturalWidth, c.y * g.naturalHeight,
              c.w * g.naturalWidth, c.h * g.naturalHeight,
              -w / 2, -h / 2, w, h);
          } else {
            ctx.drawImage(g, -w / 2, -h / 2, w, h);
          }
          ctx.restore();
        } catch { /* tek görsel yüklenemezse önizleme yine üretilir */ }
      } else {
        const tx = l as TextLayer;
        const f = fontByKey(tx.font);
        let boy = Math.max(6, tx.size * ah);
        const cerceveYuk = (tx.h ?? 0) * ah;   // 0 → metin büyümez
        ctx.save();
        ctx.font = `${boy}px '${f.css}', sans-serif`;
        // Satır yüksekliği fontun KENDİ ölçüsünden (sabit katsayı, Anton gibi
        // başlık fontlarında gerçek satırdan küçük kalıp taşmaya yol açıyordu)
        const olcuBir = ctx.measureText(tx.text || "M");
        const satirOran = Math.max(0.5,
          ((olcuBir.fontBoundingBoxAscent ?? 0) + (olcuBir.fontBoundingBoxDescent ?? 0))
          / boy) || 1.3;
        // ÇERÇEVEYİ DOLDUR — tuval ve baskıdaki kuralın aynısı: kısa metin
        // büyür, uzun metin küçülür; genişlik VE yükseklik birlikte sınırlar
        if (tx.sigdir === true) {
          const olcu = ctx.measureText(tx.text || "").width;
          const kutu = tx.w * aw;
          if (olcu > 0) {
            const yukSiniri = cerceveYuk > 0 ? cerceveYuk / satirOran : boy;
            boy = Math.max(4, Math.min((boy * kutu) / olcu, yukSiniri,
              ah * TAVAN_PUNTO));
            ctx.font = `${boy}px '${f.css}', sans-serif`;
          }
        }
        ctx.fillStyle = tx.color;
        if (tx.kontur) {
          // Çizgi harf kenarına ortalanır; dolgu üstüne bindiği için dışarıda
          // KONTUR_ORAN kadarı görünür (tuval ve baskıyla aynı)
          ctx.strokeStyle = tx.kontur;
          ctx.lineWidth = boy * KONTUR_ORAN * 2;
          ctx.lineJoin = "round";
        }
        ctx.textBaseline = "top";
        ctx.textAlign = tx.align === "center" ? "center" : tx.align === "right" ? "right" : "left";
        const x = ax + tx.x * aw;
        // Metin çerçeveye dikey ortalanır (tuval ve baskıyla aynı)
        const y = ay + tx.y * ah + Math.max(0, (cerceveYuk - boy * satirOran) / 2);
        const kutuG = tx.w * aw;
        const hizaX = tx.align === "center" ? x + kutuG / 2 : tx.align === "right" ? x + kutuG : x;
        ctx.translate(hizaX, y);
        ctx.rotate(((tx.rot || 0) * Math.PI) / 180);
        // Basit satır sarma — tuvaldeki word-break davranışına yakın
        const kelimeler = (tx.text || "").split(/\s+/);
        let satir = "";
        let dy = 0;
        for (const k of kelimeler) {
          const deneme = satir ? `${satir} ${k}` : k;
          if (ctx.measureText(deneme).width > kutuG && satir) {
            if (tx.kontur) ctx.strokeText(satir, 0, dy);
            ctx.fillText(satir, 0, dy);
            satir = k;
            dy += boy * 1.15;
          } else {
            satir = deneme;
          }
        }
        if (satir) {
          if (tx.kontur) ctx.strokeText(satir, 0, dy);
          ctx.fillText(satir, 0, dy);
        }
        ctx.restore();
      }
    }
    ctx.restore();

    // Kamera/kesik bölgeleri: kılıf görselinin o parçası tasarımın üstüne
    // döner — tuvaldeki görünümün aynısı (blur/maske değil, gerçek kamera adası)
    for (const c of template.cutouts || []) {
      const cx = c.x * W, cy = c.y * H, cw = c.w * W, ch = c.h * H;
      ctx.save();
      ctx.beginPath();
      const cr = Math.min(cw, ch) * (c.radius || 0);
      if (typeof ctx.roundRect === "function") ctx.roundRect(cx, cy, cw, ch, cr);
      else ctx.rect(cx, cy, cw, ch);
      ctx.clip();
      ctx.drawImage(kilif, 0, 0, W, H);
      ctx.restore();
    }
    return cv.toDataURL("image/png");
  } catch {
    return null;
  }
}
