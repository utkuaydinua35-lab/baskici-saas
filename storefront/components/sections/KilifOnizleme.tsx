"use client";

// Canlı kılıf önizleme (Füzyon) — ziyaretçi fotoğrafını seçer, kılıfın
// üstünde sürükler ve yakınlaştırır; model (iPhone/Samsung) ve yüzey
// (parlak/mat) değiştirir. Fotoğraf CİHAZDAN ÇIKMAZ: yalnız tarayıcıda
// nesne URL'si olarak gösterilir, hiçbir yere yüklenmez.
// Akıcılık: sürükleme/yakınlaştırma yalnız transform yazar (yeniden
// yerleşim yok), karede en fazla bir güncelleme (rAF). Farenin eğdirmesi
// yalnız gerçek farede; dokunmatikte parmak sürüklemeyle karışmasın.
import SatirliBaslik from "@/components/SatirliBaslik";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";

export default function KilifOnizleme({
  eyebrow,
  title,
  subtitle,
  buton = "FOTOĞRAF SEÇ",
  ctaText,
  ctaUrl = "/tasarla",
  logoYazi,
  not: altNot,
}: {
  eyebrow?: string;
  title?: string;
  subtitle?: string;
  buton?: string;
  ctaText?: string;
  ctaUrl?: string;
  logoYazi?: string;
  not?: string;
}) {
  const kasa = useRef<HTMLDivElement>(null);
  const baski = useRef<HTMLDivElement>(null);
  const [foto, setFoto] = useState<string | null>(null);
  const [sekil, setSekil] = useState<"iphone" | "samsung">("iphone");
  const [yuzey, setYuzey] = useState<"parlak" | "mat">("parlak");
  const [zoom, setZoom] = useState(120);
  const [taze, setTaze] = useState(0);        // yeni fotoğraf: bulanıktan netleşir
  const egimKare = useRef<number | null>(null);
  const konum = useRef({ x: 0, y: 0 });
  const surukle = useRef<{ x: number; y: number; tx: number; ty: number } | null>(null);
  const kare = useRef<number | null>(null);

  // Sınırlar içinde transform yaz (karede bir kez)
  const boya = () => {
    if (kare.current != null) return;
    kare.current = requestAnimationFrame(() => {
      kare.current = null;
      const k = kasa.current, b = baski.current;
      if (!k || !b) return;
      const z = zoom / 100;
      const mx = (k.clientWidth * (z - 1)) / 2, my = (k.clientHeight * (z - 1)) / 2;
      konum.current.x = Math.max(-mx, Math.min(mx, konum.current.x));
      konum.current.y = Math.max(-my, Math.min(my, konum.current.y));
      b.style.transform = `translate3d(${konum.current.x}px,${konum.current.y}px,0) scale(${z})`;
    });
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { boya(); }, [zoom, sekil, taze]);   // taze: baskı katmanı yeniden kuruldu
  // Sayfadan çıkınca nesne URL'sini bırak (bellek)
  useEffect(() => () => { if (foto) URL.revokeObjectURL(foto); }, [foto]);

  const dosyaSec = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f || !f.type.startsWith("image/")) return;
    setFoto(URL.createObjectURL(f));
    konum.current = { x: 0, y: 0 };
    setZoom(120);
    setTaze((n) => n + 1);
  };

  // Farede kılıf imleci izleyerek hafifçe eğilir (sürüklerken değil)
  const egil = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.pointerType !== "mouse" || surukle.current || egimKare.current != null) return;
    const sahne = e.currentTarget, x0 = e.clientX, y0 = e.clientY;
    egimKare.current = requestAnimationFrame(() => {
      egimKare.current = null;
      const k = kasa.current;
      if (!k) return;
      const r = sahne.getBoundingClientRect();
      k.style.setProperty("--ry", `${(((x0 - r.left) / r.width - 0.5) * 22).toFixed(2)}deg`);
      k.style.setProperty("--rx", `${((0.5 - (y0 - r.top) / r.height) * 14).toFixed(2)}deg`);
    });
  };
  const egimSifirla = () => {
    kasa.current?.style.removeProperty("--rx");
    kasa.current?.style.removeProperty("--ry");
  };


  const chip = (aktif: boolean) =>
    `rounded-full border px-3.5 py-2 text-xs transition-colors ${aktif
      ? "bg-[#f3f3f0] text-zinc-900 border-[#f3f3f0]" : "border-white/20 text-zinc-300 hover:border-white/50"}`;

  return (
    <section className="mx-auto max-w-6xl px-4 py-8 sm:py-12">
      <div className="grid lg:grid-cols-[1fr_1.1fr] rounded-[18px] sm:rounded-3xl overflow-hidden bg-[#171717] text-[#f3f3f0] lg:min-h-[660px]">
        <div className="order-2 lg:order-1 flex flex-col justify-center px-6 py-9 sm:px-[11%] sm:py-16">
          {eyebrow && <p className="text-[10px] font-semibold tracking-[.16em] uppercase text-zinc-400">{eyebrow}</p>}
          {title && (
            <SatirliBaslik metin={title} italikAlt italikSinif="text-zinc-400"
              className="f-baslik mt-5 text-[44px] sm:text-[62px] leading-[1.02] tracking-[-.015em]" />
          )}
          {subtitle && <p className="mt-4 text-sm leading-[1.8] text-zinc-400 max-w-sm">{subtitle}</p>}
          <label className="onizleme-yukle parilti-gec mt-6 self-start inline-flex items-center gap-6 rounded-full px-6 py-4 text-[11px] font-medium tracking-wide cursor-pointer">
            {buton} <span aria-hidden className="text-lg leading-none">+</span>
            <input type="file" accept="image/*" className="sr-only" onChange={dosyaSec} />
          </label>
          <div className="mt-7 grid gap-3.5 max-w-sm text-xs text-zinc-400">
            <div className="flex items-center justify-between gap-4">
              <span>Model</span>
              <div className="flex gap-1.5" role="group" aria-label="Telefon modeli">
                <button type="button" aria-pressed={sekil === "iphone"} onClick={() => setSekil("iphone")} className={chip(sekil === "iphone")}>iPhone</button>
                <button type="button" aria-pressed={sekil === "samsung"} onClick={() => setSekil("samsung")} className={chip(sekil === "samsung")}>Samsung</button>
              </div>
            </div>
            <div className="flex items-center justify-between gap-4">
              <span>Yüzey</span>
              <div className="flex gap-1.5" role="group" aria-label="Kılıf yüzeyi">
                <button type="button" aria-pressed={yuzey === "parlak"} onClick={() => setYuzey("parlak")} className={chip(yuzey === "parlak")}>Parlak</button>
                <button type="button" aria-pressed={yuzey === "mat"} onClick={() => setYuzey("mat")} className={chip(yuzey === "mat")}>Mat</button>
              </div>
            </div>
            <label className="flex items-center justify-between gap-4">
              <span>Yakınlaştır</span>
              <input type="range" min={100} max={250} value={zoom} disabled={!foto}
                onChange={(e) => setZoom(Number(e.target.value))}
                className="onizleme-aralik w-36 sm:w-44 disabled:opacity-40" />
            </label>
          </div>
          <p className="mt-2 mb-5 text-[11px] text-zinc-500">
            {foto ? "Görseli kılıfın üstünde sürükleyerek konumlandırabilirsin." : "Önce bir fotoğraf seç."}
          </p>
          {ctaText && (
            <Link href={ctaUrl || "/tasarla"}
              className="self-start inline-flex items-center gap-5 border-b border-zinc-600 py-2.5 text-xs hover:border-white transition-colors">
              {ctaText} <span aria-hidden>→</span>
            </Link>
          )}
        </div>
        <div className="order-1 lg:order-2 relative grid place-items-center overflow-hidden px-5 pt-10 pb-14 sm:py-16 min-h-[470px]"
          onPointerMove={egil} onPointerLeave={(e) => { if (e.pointerType === "mouse") egimSifirla(); }}
          style={{ background: "radial-gradient(circle at 50% 38%, #2e2e2b, #121212 70%)" }}>
          <div className="onizleme-suzul">
            <div ref={kasa} role="img" aria-label="Kılıf önizlemesi"
              data-sekil={sekil} data-yuzey={yuzey}
              className={`onizleme-kasa relative w-[min(230px,58vw)] sm:w-[min(285px,62vw)] aspect-[1/2.04] overflow-hidden bg-zinc-800 select-none ${
                foto ? "cursor-grab active:cursor-grabbing touch-none" : ""}`}
              onPointerDown={(e) => {
                if (!foto) return;
                surukle.current = { x: e.clientX, y: e.clientY, tx: konum.current.x, ty: konum.current.y };
                e.currentTarget.setPointerCapture(e.pointerId);
                e.currentTarget.classList.add("suruklen");
              }}
              onPointerMove={(e) => {
                const d = surukle.current;
                if (!d) return;
                konum.current = { x: d.tx + e.clientX - d.x, y: d.ty + e.clientY - d.y };
                boya();
              }}
              onPointerUp={(e) => { surukle.current = null; e.currentTarget.classList.remove("suruklen"); }}
              onPointerCancel={(e) => { surukle.current = null; e.currentTarget.classList.remove("suruklen"); }}>
              <div ref={baski} key={taze} className={`onizleme-baski absolute inset-0 ${foto ? "dolu" : ""} ${taze ? "taze" : ""}`}
                style={foto ? { backgroundImage: `url("${foto}")` } : undefined}>
                {!foto && <span className="absolute inset-x-0 top-[56%] text-center text-[11px] font-semibold tracking-[5px] text-black/25">FOTOĞRAFIN</span>}
              </div>
              <div className="onizleme-kamera" aria-hidden><i /><i /><i /><b /></div>
              <div className="onizleme-parilti" aria-hidden />
              {logoYazi && (
                <span aria-hidden className="absolute bottom-[7%] inset-x-0 text-center text-[10px] font-semibold tracking-[6px] text-white mix-blend-difference opacity-75 pointer-events-none uppercase">
                  {logoYazi}
                </span>
              )}
            </div>
          </div>
          {altNot && <span className="absolute bottom-4 inset-x-5 text-center text-[10px] text-zinc-500">{altNot}</span>}
        </div>
      </div>
    </section>
  );
}
