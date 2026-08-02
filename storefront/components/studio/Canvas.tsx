"use client";

// Tasarım tuvali — kılıf görseli + baskı alanı içindeki katmanlar.
//
// Katmanlar DOM elemanıdır (canvas değil): metin gerçek font'la render olur,
// dokunmatik tutamaklar kolay, kırpma CSS ile yapılır. Önizleme PNG'si ayrıca
// canvas'a çizilir (Preview.ts), baskı dosyası ise sunucuda üretilir.
import { useCallback, useEffect, useRef, useState } from "react";
import { fontByKey } from "./fonts";
import type { CaseTemplate, ImageLayer, Layer, LayerPatch, TextLayer } from "./types";

interface Props {
  template: CaseTemplate;
  layers: Layer[];
  selected: string | null;
  onSelect: (id: string | null) => void;
  onChange: (id: string, patch: LayerPatch) => void;
  maxHeight?: number;
}

type DragMode = "move" | "resize" | "rotate";

export default function Canvas({
  template, layers, selected, onSelect, onChange, maxHeight = 560,
}: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const areaRef = useRef<HTMLDivElement>(null);
  const drag = useRef<{
    mode: DragMode; id: string; sx: number; sy: number;
    start: { x: number; y: number; w: number; h: number; rot: number };
  } | null>(null);
  const [, forceRender] = useState(0);
  // Baskı alanının ekrandaki ölçüsü — oransal metin boyutunu piksele çevirmek
  // için gerekli (saf CSS ile yapılamıyor).
  const [areaPx, setAreaPx] = useState({ w: 0, h: 0 });
  useEffect(() => {
    const el = areaRef.current;
    if (!el) return;
    const olc = () => setAreaPx({ w: el.clientWidth, h: el.clientHeight });
    olc();
    const ro = new ResizeObserver(olc);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Baskı alanının ekrandaki piksel ölçüsü — oranları piksele çevirmek için
  const areaBox = () => areaRef.current?.getBoundingClientRect();

  const onPointerDown = (e: React.PointerEvent, id: string, mode: DragMode) => {
    e.preventDefault();
    e.stopPropagation();
    const l = layers.find((x) => x.id === id);
    if (!l) return;
    onSelect(id);
    const anyL = l as ImageLayer;   // ortak alanlar (x/y/w/rot) her iki katmanda da var
    drag.current = {
      mode, id, sx: e.clientX, sy: e.clientY,
      start: { x: anyL.x, y: anyL.y, w: anyL.w, h: anyL.h ?? 0, rot: anyL.rot || 0 },
    };
    (e.target as Element).setPointerCapture?.(e.pointerId);
  };

  const onPointerMove = useCallback((e: PointerEvent) => {
    const d = drag.current;
    const box = areaBox();
    if (!d || !box) return;
    const dx = (e.clientX - d.sx) / box.width;
    const dy = (e.clientY - d.sy) / box.height;

    if (d.mode === "move") {
      onChange(d.id, { x: d.start.x + dx, y: d.start.y + dy });
    } else if (d.mode === "resize") {
      // Köşeden ölçekleme — en/boy oranı korunur
      const oran = d.start.h > 0 ? d.start.h / d.start.w : 0;
      const w = Math.max(0.05, d.start.w + dx);
      onChange(d.id, oran > 0 ? { w, h: w * oran } : { w });
    } else if (d.mode === "rotate") {
      const cx = box.left + (d.start.x + d.start.w / 2) * box.width;
      const cy = box.top + (d.start.y + (d.start.h || 0.1) / 2) * box.height;
      const aci = (Math.atan2(e.clientY - cy, e.clientX - cx) * 180) / Math.PI + 90;
      onChange(d.id, { rot: Math.round(aci) });
    }
    forceRender((n) => n + 1);
  }, [onChange]);

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
      <img src={template.image_url} alt={template.label} draggable={false}
        style={{ maxHeight, width: "auto", display: "block" }} />

      {/* Baskı alanı: katmanlar buraya çizilir ve dışına taşanlar kırpılır */}
      <div ref={areaRef}
        className="absolute overflow-hidden"
        style={{
          left: `${a.x * 100}%`, top: `${a.y * 100}%`,
          width: `${a.w * 100}%`, height: `${a.h * 100}%`,
          borderRadius: `${(a.radius || 0) * 100}%`,
        }}>
        {layers.map((l) => {
          const secili = l.id === selected;
          if (l.type === "image") {
            const im = l as ImageLayer;
            const c = im.crop;
            return (
              <div key={l.id}
                onPointerDown={(e) => onPointerDown(e, l.id, "move")}
                className={`absolute ${secili ? "outline outline-2 outline-white/90" : ""}`}
                style={{
                  left: `${im.x * 100}%`, top: `${im.y * 100}%`,
                  width: `${im.w * 100}%`, height: `${im.h * 100}%`,
                  transform: `rotate(${im.rot || 0}deg)`,
                  cursor: "move", overflow: "hidden",
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
          return (
            <div key={l.id}
              onPointerDown={(e) => onPointerDown(e, l.id, "move")}
              className={`absolute ${secili ? "outline outline-2 outline-white/90" : ""}`}
              style={{
                left: `${tx.x * 100}%`, top: `${tx.y * 100}%`, width: `${tx.w * 100}%`,
                transform: `rotate(${tx.rot || 0}deg)`,
                fontFamily: `'${f.css}', sans-serif`,
                fontSize: `${Math.max(8, tx.size * areaPx.h)}px`,
                color: tx.color,
                textAlign: tx.align,
                lineHeight: 1.15,
                cursor: "move",
                wordBreak: "break-word",
              }}>
              {tx.text}
            </div>
          );
        })}

        {/* Basılamayan bölgeler — müşteri buraya tasarım koyamayacağını görsün */}
        {template.cutouts?.map((c, i) => (
          <div key={i} className="absolute pointer-events-none border border-dashed border-white/70"
            style={{
              // Kesikler ŞABLONA oransal; baskı alanına çeviriyoruz
              left: `${((c.x - a.x) / a.w) * 100}%`,
              top: `${((c.y - a.y) / a.h) * 100}%`,
              width: `${(c.w / a.w) * 100}%`,
              height: `${(c.h / a.h) * 100}%`,
              borderRadius: `${(c.radius || 0) * 100}%`,
              background: "rgba(0,0,0,.55)",
              backdropFilter: "blur(2px)",
            }} />
        ))}
      </div>

      {/* Seçili katmanın tutamakları — baskı alanının DIŞINDA, kırpılmasın */}
      {selected && (() => {
        const l = layers.find((x) => x.id === selected);
        if (!l) return null;
        const h = l.type === "image" ? (l as ImageLayer).h : 0.06;
        const px = (v: number, eksen: "x" | "y") =>
          eksen === "x" ? (a.x + v * a.w) * 100 : (a.y + v * a.h) * 100;
        return (
          <>
            <div onPointerDown={(e) => onPointerDown(e, l.id, "resize")}
              className="absolute w-5 h-5 rounded-full bg-white border-2 border-zinc-800 shadow cursor-nwse-resize"
              style={{
                left: `${px(l.x + l.w, "x")}%`, top: `${px(l.y + h, "y")}%`,
                transform: "translate(-50%,-50%)",
              }} />
            <div onPointerDown={(e) => onPointerDown(e, l.id, "rotate")}
              className="absolute w-5 h-5 rounded-full bg-white border-2 border-zinc-800 shadow cursor-grab flex items-center justify-center text-[10px]"
              style={{
                left: `${px(l.x + l.w / 2, "x")}%`, top: `${px(l.y - 0.04, "y")}%`,
                transform: "translate(-50%,-50%)",
              }}>↻</div>
          </>
        );
      })()}
    </div>
  );
}
