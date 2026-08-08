"use client";

// Tasarım tuvali — kılıf görseli + baskı alanı içindeki katmanlar.
//
// Katmanlar DOM elemanıdır (canvas değil): metin gerçek font'la render olur,
// dokunmatik tutamaklar kolay, kırpma CSS ile yapılır. Önizleme PNG'si ayrıca
// canvas'a çizilir (Preview.ts), baskı dosyası ise sunucuda üretilir.
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { fontByKey } from "./fonts";
import { TAVAN_PUNTO } from "./types";
import type {
  CaseTemplate, ImageLayer, Layer, LayerPatch, OverlayLayer, ShapeLayer, TextLayer,
} from "./types";

interface Props {
  template: CaseTemplate;
  layers: Layer[];
  selected: string | null;
  onSelect: (id: string | null) => void;
  onChange: (id: string, patch: LayerPatch) => void;
  maxHeight?: number;
  /** Kırpma modu: görsel tutamakları ÖLÇEKLEMEZ, kenardan KIRPAR
      (en/boy oranı bozulmaz, görüntü ezilmez). */
  kirpma?: boolean;
  /** Kısıtlı şablon: yerleşim panelde belirlenmiştir — müşteri hiçbir
      katmanı taşıyamaz, ölçekleyemez, döndüremez. */
  kilitli?: boolean;
}

/** Metni kutu genişliğine BİREBİR oturtan katman: kısa metin büyür, uzun
 *  metin küçülür — "10" ile "100" aynı genişlikte çıkar.
 *
 *  Ölçüm, tanımlı puntoda duran GİZLİ bir kopya üzerinden yapılır; canvas
 *  measureText ile ölçmek, özel font henüz yüklenmemişse yedek fontu ölçüyor
 *  ve "100" gibi metinler ekranda çerçeveyi taşırıyordu.
 *
 *  Sunucudaki karşılığı: design_render._ciz_metin / design_pdf._yazi. */
function SigdirilanYazi({ metin, punto, sigdir, cerceveYuk, tavan, stil }: {
  metin: string; punto: number; sigdir: boolean;
  /** Çerçeve yüksekliği (px). 0 → yükseklik serbest, metin BÜYÜMEZ. */
  cerceveYuk: number;
  tavan: number;
  stil: React.CSSProperties;
}) {
  // Ölçüm, GÖRÜNEN metnin değil hep TANIMLI puntodaki gizli kopyanın üzerinden
  // yapılır. Görünen metni ölçmek geri besleme yaratıyordu: bir kez ölçekledikten
  // sonraki ölçüm zaten büyümüş/küçülmüş metni okuyup yanlış oran çıkarıyor,
  // ölçek tek geçişte doğru değere yakınsamıyordu.
  const olcRef = useRef<HTMLSpanElement>(null);
  const [olcek, setOlcek] = useState(1);

  useLayoutEffect(() => {
    const el = olcRef.current;
    const kap = el?.parentElement;
    if (!sigdir || !el || !kap) { setOlcek(1); return; }
    const olc = () => {
      const kutu = kap.clientWidth;
      const kut = el.getBoundingClientRect();
      const gen = kut.width;      // ölçeksiz genişlik
      const yuk = kut.height;     // ölçeksiz SATIR yüksekliği (fontun kendi ölçüsü)
      if (!kutu || !gen || !yuk) return;
      // Kutuyu doldur: hem GENİŞLİK hem YÜKSEKLİK sınırlar. Çerçeve yüksekliği
      // verilmemişse metin büyümez (yalnız küçülür) — tek harfli metin,
      // genişliği doldurayım derken çerçevenin dışına taşmasın.
      const enBuyukH = cerceveYuk > 0 ? cerceveYuk / yuk : 1;
      const tavanOlcek = punto > 0 ? Math.max(1, tavan / punto) : 1;
      const yeni = Math.max(0.15, Math.min(kutu / gen, enBuyukH, tavanOlcek));
      setOlcek((eski) => (Math.abs(yeni - eski) > 0.005 ? yeni : eski));
    };
    olc();
    // Özel font GEÇ yüklenirse İLK ölçüm yedek fontu okur ve metin kutuyu
    // doldurmaz. Tek bir "font hazır" sinyaline güvenmek yetmiyor:
    // document.fonts.ready tek seferliktir, fonts.load bazı tarayıcılarda
    // yazı tipi uygulanmadan çözülüyor, ResizeObserver ise her ortamda
    // tetiklenmiyor. Bu yüzden kısa bir pencere boyunca yeniden ölçülür —
    // ölçü değişmediği anda durulur (setOlcek zaten aynı değeri yazmaz).
    let ro: ResizeObserver | null = null;
    try {
      ro = new ResizeObserver(olc);
      ro.observe(el);
      ro.observe(kap);
    } catch { /* eski tarayıcı — zamanlayıcılar yine ölçer */ }
    const zamanlar = [120, 350, 800, 1600].map((ms) => window.setTimeout(olc, ms));
    return () => { ro?.disconnect(); zamanlar.forEach(window.clearTimeout); };
  }, [metin, punto, sigdir, cerceveYuk, tavan, stil.fontFamily]);

  return (
    <>
      {sigdir && (
        <span ref={olcRef} aria-hidden="true" style={{
          position: "absolute", visibility: "hidden", pointerEvents: "none",
          left: 0, top: 0, whiteSpace: "nowrap", fontSize: `${punto}px`,
          lineHeight: "normal",
        }}>
          {metin}
        </span>
      )}
      <span style={{
        display: "inline-block",
        whiteSpace: sigdir ? "nowrap" : "normal",
        fontSize: `${punto * olcek}px`,
        lineHeight: sigdir ? "normal" : undefined,
        width: sigdir ? "auto" : "100%",
      }}>
        {metin}
      </span>
    </>
  );
}

// Boyutlandırma yönleri: köşeler oranı korur, kenarlar tek eksende esner
type Yon = "nw" | "n" | "ne" | "e" | "se" | "s" | "sw" | "w";
type DragMode = "move" | "rotate" | Yon;
const YONLER: [Yon, number, number, string][] = [
  ["nw", 0, 0, "nwse-resize"], ["n", 50, 0, "ns-resize"], ["ne", 100, 0, "nesw-resize"],
  ["e", 100, 50, "ew-resize"], ["se", 100, 100, "nwse-resize"], ["s", 50, 100, "ns-resize"],
  ["sw", 0, 100, "nesw-resize"], ["w", 0, 50, "ew-resize"],
];

export default function Canvas({
  template, layers, selected, onSelect, onChange, maxHeight = 560, kirpma = false,
  kilitli = false,
}: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const areaRef = useRef<HTMLDivElement>(null);
  const drag = useRef<{
    mode: DragMode; id: string; sx: number; sy: number; tip: string;
    start: {
      x: number; y: number; w: number; h: number; rot: number; size?: number;
      crop?: { x: number; y: number; w: number; h: number };
    };
  } | null>(null);
  const [, forceRender] = useState(0);
  // Baskı alanının ekrandaki ölçüsü — oransal metin boyutunu piksele çevirmek
  // için gerekli (saf CSS ile yapılamıyor).
  const [areaPx, setAreaPx] = useState({ w: 0, h: 0 });
  const alaniOlc = useCallback(() => {
    const el = areaRef.current;
    if (!el) return;
    const w = el.clientWidth, h = el.clientHeight;
    setAreaPx((eski) => (eski.w === w && eski.h === h ? eski : { w, h }));
  }, []);
  useEffect(() => {
    const el = areaRef.current;
    if (!el) return;
    alaniOlc();
    // Kılıf görseli yüklenince alan büyür. Tek başına ResizeObserver yetmiyor:
    // görsel önbellekten gelirse onLoad hiç tetiklenmiyor, RO da her ortamda
    // çalışmıyor. Kısa bir pencerede yeniden ölçülür (punto buna oranlı).
    const ro = new ResizeObserver(alaniOlc);
    ro.observe(el);
    window.addEventListener("resize", alaniOlc);
    const zamanlar = [120, 350, 800, 1600].map((ms) => window.setTimeout(alaniOlc, ms));
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", alaniOlc);
      zamanlar.forEach(window.clearTimeout);
    };
  }, [alaniOlc]);

  // Her render'dan sonra da ölç: yukarıdaki tetikler (RO / onLoad / resize /
  // zamanlayıcı) hiçbiri çalışmasa bile katman, şablon ya da metin değişimiyle
  // gelen render ölçüyü tazeler. Değer değişmediğinde setAreaPx yeni render
  // üretmediği için döngü olmaz.
  useLayoutEffect(alaniOlc);

  // Baskı alanının ekrandaki piksel ölçüsü — oranları piksele çevirmek için
  const areaBox = () => areaRef.current?.getBoundingClientRect();

  const onPointerDown = (e: React.PointerEvent, id: string, mode: DragMode) => {
    // Kısıtlı şablonda yerleşim sabittir — dokunuş hiçbir şeyi oynatmaz
    if (kilitli) return;
    e.preventDefault();
    e.stopPropagation();
    const l = layers.find((x) => x.id === id);
    if (!l) return;
    onSelect(id);
    const anyL = l as ImageLayer;   // ortak alanlar (x/y/w/rot) her iki katmanda da var
    drag.current = {
      mode, id, sx: e.clientX, sy: e.clientY, tip: l.type,
      start: {
        x: anyL.x, y: anyL.y, w: anyL.w,
        h: anyL.h ?? (areaPx.h ? ((l as unknown as TextLayer).size || 0.1) : 0.06),
        rot: anyL.rot || 0,
        size: (l as unknown as TextLayer).size,
        crop: anyL.crop ? { ...anyL.crop } : { x: 0, y: 0, w: 1, h: 1 },
      },
    };
    // Yakalama başarısız olabilir (iptal edilmiş pointer) — sürükleme yine
    // window dinleyicileriyle çalışır, bu yüzden hata yutulur.
    try { (e.target as Element).setPointerCapture?.(e.pointerId); } catch { /* önemsiz */ }
  };

  const onPointerMove = useCallback((e: PointerEvent) => {
    const d = drag.current;
    const box = areaBox();
    if (!d || !box) return;
    const dx = (e.clientX - d.sx) / box.width;
    const dy = (e.clientY - d.sy) / box.height;

    if (d.mode === "move") {
      onChange(d.id, { x: d.start.x + dx, y: d.start.y + dy });
    } else if (kirpma && d.tip === "image" && d.mode !== "rotate") {
      // ── KIRPMA ──
      // Çerçeve kenardan içeri gelir, görselin GÖRÜNEN kısmı aynı ölçekte kalır:
      // yani görsel ezilmez, sadece dışarıda kalan bölüm kırpılır. Kırpma
      // penceresi orijinal dosyaya oransaldır (0-1), baskıda da bu bölge basılır.
      const yon = d.mode as Yon;
      const c0 = d.start.crop || { x: 0, y: 0, w: 1, h: 1 };
      let { x, y, w, h } = d.start;
      let { x: cx, y: cy, w: cw, h: ch } = c0;

      if (yon.includes("e")) {
        w = Math.max(0.05, d.start.w + dx);
        cw = (c0.w * w) / d.start.w;
        if (cx + cw > 1) { cw = 1 - cx; w = (d.start.w * cw) / c0.w; }   // orijinalin sonu
      }
      if (yon.includes("w")) {
        w = Math.max(0.05, d.start.w - dx);
        cw = (c0.w * w) / d.start.w;
        cx = c0.x + c0.w - cw;
        if (cx < 0) { cx = 0; cw = c0.x + c0.w; w = (d.start.w * cw) / c0.w; }
        x = d.start.x + d.start.w - w;
      }
      if (yon.includes("s")) {
        h = Math.max(0.03, d.start.h + dy);
        ch = (c0.h * h) / d.start.h;
        if (cy + ch > 1) { ch = 1 - cy; h = (d.start.h * ch) / c0.h; }
      }
      if (yon.includes("n")) {
        h = Math.max(0.03, d.start.h - dy);
        ch = (c0.h * h) / d.start.h;
        cy = c0.y + c0.h - ch;
        if (cy < 0) { cy = 0; ch = c0.y + c0.h; h = (d.start.h * ch) / c0.h; }
        y = d.start.y + d.start.h - h;
      }
      onChange(d.id, { x, y, w, h, crop: { x: cx, y: cy, w: cw, h: ch } });
    } else if (d.mode !== "rotate") {
      // 8 yönlü boyutlandırma. Metinde yükseklik yazının kendisinden gelir:
      // yatay tutamak genişliği, dikey tutamak PUNTOYU değiştirir.
      const yon = d.mode as Yon;
      const metin = d.tip === "text";
      let { x, y, w, h } = d.start;
      const oran = d.start.h > 0 ? d.start.h / d.start.w : 0;
      const kose = yon.length === 2;

      if (yon.includes("e")) w = d.start.w + dx;
      if (yon.includes("w")) { w = d.start.w - dx; x = d.start.x + dx; }
      if (!metin) {
        if (yon.includes("s")) h = d.start.h + dy;
        if (yon.includes("n")) { h = d.start.h - dy; y = d.start.y + dy; }
        // Köşeden çekince en/boy oranı korunur (görsel bozulmasın)
        if (kose && oran > 0) {
          h = w * oran;
          if (yon.includes("n")) y = d.start.y + (d.start.h - h);
        }
      }
      w = Math.max(0.05, w);
      h = Math.max(0.03, h);
      if (metin) {
        // Dikey tutamak → punto; yatay tutamak → sarma genişliği
        const puntoDeg = yon.includes("n") ? -dy : yon.includes("s") ? dy : 0;
        const yeniPunto = puntoDeg
          ? Math.max(0.02, Math.min(0.4, (d.start.size || 0.1) + puntoDeg))
          : undefined;
        onChange(d.id, {
          x, w,
          ...(yeniPunto !== undefined ? { size: yeniPunto } : {}),
          ...(yon.includes("n") && !yeniPunto ? { y } : {}),
        });
      } else {
        onChange(d.id, { x, y, w, h });
      }
    } else if (d.mode === "rotate") {
      const cx = box.left + (d.start.x + d.start.w / 2) * box.width;
      const cy = box.top + (d.start.y + (d.start.h || 0.1) / 2) * box.height;
      const aci = (Math.atan2(e.clientY - cy, e.clientX - cx) * 180) / Math.PI + 90;
      onChange(d.id, { rot: Math.round(aci) });
    }
    forceRender((n) => n + 1);
    // kirpma bağımlılıkta OLMALI: yoksa closure eski değeri yakalar ve
    // kırpma modu açıkken tutamaklar hâlâ ölçekleme yapar.
  }, [onChange, kirpma]);

  const onPointerUp = useCallback(() => { drag.current = null; }, []);

  useEffect(() => {
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    return () => {
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
    };
  }, [onPointerMove, onPointerUp]);

  const a = template.area;

  return (
    <div ref={wrapRef} className="relative inline-block select-none touch-none"
      onPointerDown={() => onSelect(null)}>
      {/* Kılıf görseli — tasarım BUNUN ALTINDA kalır (şeffaf kılıfta doğru görünüm) */}
      {/* Mobilde ekran genişliğine, masaüstünde yüksekliğe göre sığar */}
      {/* Kılıf görseli yüklenince baskı alanı büyür — punto ona oranlı
          olduğundan yeniden ölçülmeli (ResizeObserver'a tek başına güvenilmez) */}
      <img src={template.image_url} alt={template.label} draggable={false}
        onLoad={alaniOlc}
        style={{
          maxHeight, maxWidth: "100%", width: "auto", height: "auto", display: "block",
        }} />

      {/* Baskı alanı: katmanlar buraya çizilir ve dışına taşanlar kırpılır */}
      <div ref={areaRef} data-baski-alani=""
        className="absolute overflow-hidden"
        style={{
          left: `${a.x * 100}%`, top: `${a.y * 100}%`,
          width: `${a.w * 100}%`, height: `${a.h * 100}%`,
          borderRadius: `${(a.radius || 0) * Math.min(areaPx.w, areaPx.h)}px`,
        }}>
        {layers.map((l) => {
          const secili = l.id === selected;
          if (l.type === "overlay") {
            // Hazır şablon. Kutusu yoksa baskı alanını tam kaplar; kutusu varsa
            // kısıtlı şablonun açılabilir öğesidir (bayrak, logo) ve kendi
            // konumuna çizilir. İkisi de tıklanamaz — yanlışlıkla taşınmasın.
            const ov = l as OverlayLayer;
            const k = ov.kutu;
            return (
              <img key={l.id} data-katman={l.id} src={ov.url} alt={ov.label || ""}
                draggable={false}
                className="absolute pointer-events-none"
                style={k ? {
                  left: `${k.x * 100}%`, top: `${k.y * 100}%`,
                  width: `${k.w * 100}%`, height: `${k.h * 100}%`,
                  objectFit: "contain",
                } : { inset: 0, width: "100%", height: "100%", objectFit: "fill" }} />
            );
          }
          if (l.type === "sekil") {
            // Kısıtlı şablonun ilerleme çubuğu (Spotify): dolu kısım + nokta,
            // konumu müşterinin yazdığı sürelerden gelir
            const sk = l as ShapeLayer;
            const kal = `${sk.kalinlik * 100}%`;
            return (
              <div key={l.id} data-katman={l.id} className="absolute pointer-events-none"
                style={{ left: `${sk.x * 100}%`, top: `${sk.y * 100}%`,
                  width: `${sk.w * 100}%`, height: kal, transform: "translateY(-50%)" }}>
                <div className="absolute inset-0 rounded-full"
                  style={{ background: sk.renk_pasif }} />
                <div className="absolute left-0 top-0 bottom-0 rounded-full"
                  style={{ width: `${sk.oran * 100}%`, background: sk.renk }} />
                <div className="absolute rounded-full"
                  style={{
                    left: `${sk.oran * 100}%`,
                    top: "50%",
                    width: `${(sk.boyut * 2 * 100) / (sk.w * 100) * 100}%`,
                    aspectRatio: "1",
                    transform: "translate(-50%,-50%)",
                    background: sk.renk,
                  }} />
              </div>
            );
          }
          if (l.type === "image") {
            const im = l as ImageLayer;
            const c = im.crop;
            return (
              <div key={l.id} data-katman={l.id}
                onPointerDown={(e) => onPointerDown(e, l.id, "move")}
                className={`absolute ${secili && !kilitli ? "outline outline-2 outline-white/90" : ""}`}
                style={{
                  left: `${im.x * 100}%`, top: `${im.y * 100}%`,
                  width: `${im.w * 100}%`, height: `${im.h * 100}%`,
                  transform: `rotate(${im.rot || 0}deg)`,
                  cursor: kilitli ? "default" : "move", overflow: "hidden",
                  pointerEvents: kilitli ? "none" : undefined,
                }}>
                <img src={im.url} alt="" draggable={false}
                  style={c ? {
                    position: "absolute",
                    width: `${100 / c.w}%`, height: `${100 / c.h}%`,
                    left: `${(-c.x / c.w) * 100}%`, top: `${(-c.y / c.h) * 100}%`,
                    maxWidth: "none", objectFit: "fill",
                  } : { width: "100%", height: "100%", objectFit: "fill" }} />
              </div>
            );
          }
          const tx = l as TextLayer;
          const f = fontByKey(tx.font);
          const puntoPx = Math.max(8, tx.size * areaPx.h);
          // Çerçeve yüksekliği: verilmemişse tek satırlık (eski alanlar).
          // "Doldur" açıkken punto bunu aşamaz — tek harf taşırmasın.
          // Çerçeve yüksekliği; verilmemişse serbest (metin büyümez)
          const cerceveYuk = (tx.h ?? 0) * areaPx.h;
          return (
            <div key={l.id} data-katman={l.id}
              onPointerDown={(e) => onPointerDown(e, l.id, "move")}
              className={`absolute ${secili && !kilitli ? "outline outline-2 outline-white/90" : ""}`}
              style={{
                left: `${tx.x * 100}%`, top: `${tx.y * 100}%`, width: `${tx.w * 100}%`,
                // Metin çerçeveye dikey ortalanır; küçülen metin tepeye yapışmaz
                height: cerceveYuk ? `${cerceveYuk}px` : undefined,
                display: "flex", alignItems: "center",
                justifyContent: tx.align === "center" ? "center"
                  : tx.align === "right" ? "flex-end" : "flex-start",
                transform: `rotate(${tx.rot || 0}deg)`,
                fontFamily: `'${f.css}', sans-serif`,
                color: tx.color,
                textAlign: tx.align,
                lineHeight: 1.15,
                cursor: kilitli ? "default" : "move",
                pointerEvents: kilitli ? "none" : undefined,
                wordBreak: "break-word",
              }}>
              {/* Sığdırma yalnız kısıtlı şablon alanlarında (sigdir === true);
                  serbest editörde punto müşterinin kendi ayarıdır */}
              <SigdirilanYazi metin={tx.text} punto={puntoPx}
                sigdir={tx.sigdir === true} cerceveYuk={cerceveYuk}
                tavan={TAVAN_PUNTO * areaPx.h}
                stil={{ fontFamily: `'${f.css}', sans-serif` }} />
            </div>
          );
        })}

        {/* Basılamayan bölgeler (kamera, MagSafe): tasarım buraya BASILMAZ.
            Bulanık örtü yerine KILIF GÖRSELİNİN o bölgesi gösterilir — yani
            gerçek kamera adası görünür, delik gibi durur. Arka plan konumu
            görselin tamamını cutout kutusuna hizalayacak şekilde hesaplanır. */}
        {template.cutouts?.map((c, i) => (
          <div key={i} className="absolute pointer-events-none"
            style={{
              // Kesikler ŞABLONA oransal; baskı alanına çeviriyoruz
              left: `${((c.x - a.x) / a.w) * 100}%`,
              top: `${((c.y - a.y) / a.h) * 100}%`,
              width: `${(c.w / a.w) * 100}%`,
              height: `${(c.h / a.h) * 100}%`,
              borderRadius: `${(c.radius || 0) * Math.min((c.w / a.w) * areaPx.w, (c.h / a.h) * areaPx.h)}px`,
              backgroundImage: `url(${template.image_url})`,
              backgroundSize: `${100 / c.w}% ${100 / c.h}%`,
              backgroundPosition:
                `${c.w < 1 ? (c.x / (1 - c.w)) * 100 : 0}% ${c.h < 1 ? (c.y / (1 - c.h)) * 100 : 0}%`,
            }} />
        ))}
      </div>

      {/* Seçili katmanın tutamakları — 8 yön + döndürme. Baskı alanının
          DIŞINDA çizilir ki kenara yapışık katmanlarda kırpılmasın. */}
      {selected && !kilitli && (() => {
        const secim = layers.find((x) => x.id === selected);
        // Hazır şablon taşınmaz/ölçeklenmez (kılıfa bire bir oturur) → tutamak yok
        if (!secim || secim.type === "overlay") return null;
        const l = secim as ImageLayer | TextLayer;
        const metin = l.type === "text";
        const yuk = metin
          ? Math.max(0.05, ((l as TextLayer).size || 0.1) * 1.3)
          : (l as ImageLayer).h;
        const px = (v: number, eksen: "x" | "y") =>
          eksen === "x" ? (a.x + v * a.w) * 100 : (a.y + v * a.h) * 100;
        return (
          <>
            {YONLER.map(([yon, lx, ly, cur]) => (
              <div key={yon}
                onPointerDown={(e) => onPointerDown(e, l.id, yon)}
                className="absolute w-6 h-6 -m-3 flex items-center justify-center touch-none"
                style={{
                  left: `${px(l.x + (lx / 100) * l.w, "x")}%`,
                  top: `${px(l.y + (ly / 100) * yuk, "y")}%`,
                  cursor: cur, zIndex: 3,
                }}>
                <span className="block w-3 h-3 rounded-full bg-white border-2 border-zinc-800 shadow" />
              </div>
            ))}
            <div onPointerDown={(e) => onPointerDown(e, l.id, "rotate")}
              className="absolute w-7 h-7 -m-3.5 flex items-center justify-center touch-none"
              style={{
                left: `${px(l.x + l.w / 2, "x")}%`,
                top: `${px(l.y - 0.05, "y")}%`,
                cursor: "grab", zIndex: 3,
              }}>
              <span className="block w-5 h-5 rounded-full bg-white border-2 border-zinc-800 shadow text-[11px] leading-4 text-center">↻</span>
            </div>
          </>
        );
      })()}
    </div>
  );
}
