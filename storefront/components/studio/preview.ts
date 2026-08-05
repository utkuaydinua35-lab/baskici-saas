// Tuvalin küçük PNG önizlemesi — "Tasarımlarım" listesinde ve panelde görünür.
//
// Bu SADECE önizlemedir. Baskıya giden dosya sunucuda, müşterinin yüklediği
// ORİJİNAL görsellerden ve aynı font dosyalarından üretilir; ekran görüntüsü
// asla baskıya gitmez.
import { fontByKey } from "./fonts";
import type { CaseTemplate, ImageLayer, Layer, OverlayLayer, TextLayer } from "./types";

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
        const boy = Math.max(6, tx.size * ah);
        ctx.save();
        ctx.font = `${boy}px '${f.css}', sans-serif`;
        ctx.fillStyle = tx.color;
        ctx.textBaseline = "top";
        ctx.textAlign = tx.align === "center" ? "center" : tx.align === "right" ? "right" : "left";
        const x = ax + tx.x * aw;
        const y = ay + tx.y * ah;
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
            ctx.fillText(satir, 0, dy);
            satir = k;
            dy += boy * 1.15;
          } else {
            satir = deneme;
          }
        }
        if (satir) ctx.fillText(satir, 0, dy);
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
