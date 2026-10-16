"use client";

// Kişiye özel ürün görseli kırpıcı — müşteri ürün önizlemesi GÖRMEZ, yalnız
// görselini panelde istenen orana (1:1, 9:16…) ya da piksel ölçüsüne kırpar.
// Kırpma TARAYICIDA, orijinal çözünürlükten yapılır (sunucuya yalnız kırpılmış
// dosya gider). Piksel ölçüsü verilmişse çıktı tam o ölçüdedir; görsel o
// ölçüden küçükse müşteri uyarılır (baskıda bulanık çıkabilir).
import { useCallback, useEffect, useRef, useState } from "react";

export interface KirpAyari { oran: string; px_w?: number; px_h?: number }

export function kirpOrani(k?: KirpAyari | null): number | null {
  if (!k) return null;
  if (k.oran === "px" && k.px_w && k.px_h) return k.px_w / k.px_h;
  const m = /^(\d+):(\d+)$/.exec(k.oran || "");
  return m ? Number(m[1]) / Number(m[2]) : null;
}

export function kirpAciklama(k?: KirpAyari | null): string {
  if (!k) return "";
  return k.oran === "px" ? `${k.px_w}×${k.px_h} px` : `${k.oran} oranında`;
}

export default function GorselKirpici({ dosya, ayar, onBitti, onVazgec }: {
  dosya: File; ayar: KirpAyari;
  onBitti: (kirpilmis: File) => void; onVazgec: () => void;
}) {
  const oran = kirpOrani(ayar) || 1;
  const [img, setImg] = useState<HTMLImageElement | null>(null);
  const [hata, setHata] = useState("");
  const [zoom, setZoom] = useState(1);
  const [merkez, setMerkez] = useState({ x: 0.5, y: 0.5 });     // kaynakta, 0-1
  const [cerceve, setCerceve] = useState(0);                     // çerçeve genişliği px
  const kutu = useRef<HTMLDivElement>(null);
  const surukle = useRef<{ px: number; py: number; x: number; y: number } | null>(null);

  useEffect(() => {
    // İptal bayrağı: bileşen kapanınca (ya da geliştirme modunda effect iki kez
    // çalışınca) eski yüklemenin geç gelen hatası ekrana yazılmasın
    let iptal = false;
    const url = URL.createObjectURL(dosya);
    const i = new Image();
    i.onload = () => { if (!iptal) setImg(i); };
    i.onerror = () => { if (!iptal) setHata("Bu görsel açılamadı. JPG ya da PNG deneyin (iPhone'da 'En Uyumlu' biçim)."); };
    i.src = url;
    return () => { iptal = true; URL.revokeObjectURL(url); };
  }, [dosya]);

  useEffect(() => {
    const olc = () => setCerceve(kutu.current?.clientWidth || 0);
    olc();
    window.addEventListener("resize", olc);
    return () => window.removeEventListener("resize", olc);
  }, [img]);

  // Kaynaktaki kırpma kutusu (px): yakınlaştırma 1'de çerçeveyi dolduran en büyük kutu
  const kirpKutusu = useCallback(() => {
    if (!img) return null;
    const sw = img.naturalWidth, sh = img.naturalHeight;
    let cw = sw, ch = sw / oran;
    if (ch > sh) { ch = sh; cw = sh * oran; }
    cw /= zoom; ch /= zoom;
    const x = Math.min(Math.max(merkez.x * sw - cw / 2, 0), sw - cw);
    const y = Math.min(Math.max(merkez.y * sh - ch / 2, 0), sh - ch);
    return { x, y, w: cw, h: ch, sw, sh };
  }, [img, oran, zoom, merkez]);

  const k = kirpKutusu();
  const olcek = k && cerceve ? cerceve / k.w : 1;

  const basla = (e: React.PointerEvent) => {
    e.preventDefault();
    (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
    if (k) surukle.current = { px: e.clientX, py: e.clientY, x: k.x + k.w / 2, y: k.y + k.h / 2 };
  };
  const tasi = (e: React.PointerEvent) => {
    const s = surukle.current;
    if (!s || !k) return;
    const nx = (s.x - (e.clientX - s.px) / olcek) / k.sw;
    const ny = (s.y - (e.clientY - s.py) / olcek) / k.sh;
    setMerkez({ x: Math.min(1, Math.max(0, nx)), y: Math.min(1, Math.max(0, ny)) });
  };

  // Çıktı ölçüsü: piksel istenmişse tam o; yoksa kırpılan bölgenin kendi
  // çözünürlüğü (en uzun kenar 6000 px ile sınırlı)
  const cikti = k ? (ayar.oran === "px" && ayar.px_w && ayar.px_h
    ? { w: ayar.px_w, h: ayar.px_h }
    : (() => { const o = Math.min(1, 6000 / Math.max(k.w, k.h)); return { w: Math.round(k.w * o), h: Math.round(k.h * o) }; })())
    : null;
  const dusuk = !!(k && cikti && ayar.oran === "px" && k.w < cikti.w * 0.8);

  const bitir = () => {
    if (!img || !k || !cikti) return;
    const c = document.createElement("canvas");
    c.width = cikti.w; c.height = cikti.h;
    const ctx = c.getContext("2d");
    if (!ctx) return;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(img, k.x, k.y, k.w, k.h, 0, 0, cikti.w, cikti.h);
    const png = /png$/i.test(dosya.type);
    c.toBlob((b) => {
      if (!b) { setHata("Kırpılamadı, tekrar deneyin."); return; }
      const ad = dosya.name.replace(/\.[^.]+$/, "") + (png ? "-kirpik.png" : "-kirpik.jpg");
      onBitti(new File([b], ad, { type: png ? "image/png" : "image/jpeg" }));
    }, png ? "image/png" : "image/jpeg", 0.95);
  };

  return (
    <div className="fixed inset-0 z-[95] bg-black/70 flex items-center justify-center p-4" onClick={onVazgec}>
      <div className="w-full max-w-md rounded-2xl bg-white p-4 space-y-3" onClick={(e) => e.stopPropagation()}>
        <div className="text-sm font-semibold">Görselini kırp</div>
        <p className="text-xs text-zinc-500">
          Bu ürün için görsel {kirpAciklama(ayar)} hazırlanır. Sürükleyerek konumlandır, çubukla yakınlaştır.
        </p>
        {hata && <p className="text-xs text-red-600">{hata}</p>}
        <div ref={kutu} onPointerDown={basla} onPointerMove={tasi}
          onPointerUp={() => { surukle.current = null; }} onPointerCancel={() => { surukle.current = null; }}
          className="relative mx-auto w-full max-h-[60vh] overflow-hidden rounded-xl bg-zinc-100 cursor-grab active:cursor-grabbing touch-none select-none"
          style={{ aspectRatio: String(oran), maxWidth: `calc(60vh * ${oran})` }}>
          {img && k && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={img.src} alt="" draggable={false} className="absolute max-w-none pointer-events-none"
              style={{ width: k.sw * olcek, height: k.sh * olcek, left: -k.x * olcek, top: -k.y * olcek }} />
          )}
          {!img && !hata && <div className="absolute inset-0 grid place-items-center text-xs text-zinc-400">Yükleniyor…</div>}
        </div>
        {img && (
          <input type="range" min={1} max={4} step={0.01} value={zoom} aria-label="Yakınlaştır"
            onChange={(e) => setZoom(Number(e.target.value))} className="w-full" />
        )}
        {dusuk && k && (
          <p className="text-xs text-amber-700 bg-amber-50 rounded-lg px-2 py-1.5">
            Görselin bu kısmı {Math.round(k.w)}×{Math.round(k.h)} px — istenen {cikti?.w}×{cikti?.h} px&apos;ten küçük;
            baskıda bulanık çıkabilir. Daha az yakınlaştır ya da daha büyük bir görsel seç.
          </p>
        )}
        <div className="flex gap-2">
          <button type="button" onClick={onVazgec} className="rounded-xl border border-zinc-300 px-4 py-2 text-sm">Vazgeç</button>
          <button type="button" onClick={bitir} disabled={!img}
            className="flex-1 rounded-xl px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
            style={{ background: "var(--c-primary)" }}>
            Kırp ve yükle
          </button>
        </div>
      </div>
    </div>
  );
}
