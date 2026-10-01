"use client";

// Ürün kartı medyası — kapak görsel; imleç gelince 2. görsel, o yoksa video oynar.
import { useRef, useState } from "react";
import { urunGorsel } from "@/lib/gorsel";

export default function CardMedia({
  cover,
  hoverImage,
  videoUrl,
  title,
  oncelikli = false,
}: {
  oncelikli?: boolean;
  cover: string | null;
  hoverImage?: string | null;
  videoUrl?: string | null;
  title: string;
}) {
  const [hover, setHover] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const kare = useRef<number | null>(null);
  // Farede 3B eğilme + ışık: yalnız CSS değişkeni yazılır (yeniden çizim yok),
  // karede bir kez. Görünümü tema seçer (globals.css — "yumuşak" kart).
  const egil = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.pointerType !== "mouse" || kare.current != null) return;
    const el = e.currentTarget, x0 = e.clientX, y0 = e.clientY;
    kare.current = requestAnimationFrame(() => {
      kare.current = null;
      const r = el.getBoundingClientRect(), x = (x0 - r.left) / r.width, y = (y0 - r.top) / r.height;
      el.style.setProperty("--tilt-x", `${((0.5 - y) * 4).toFixed(2)}deg`);
      el.style.setProperty("--tilt-y", `${((x - 0.5) * 5).toFixed(2)}deg`);
      el.style.setProperty("--light-x", `${(x * 100).toFixed(1)}%`);
      el.style.setProperty("--light-y", `${(y * 100).toFixed(1)}%`);
    });
  };
  const useVideo = !hoverImage && !!videoUrl;

  const enter = () => {
    setHover(true);
    if (useVideo) videoRef.current?.play().catch(() => {});
  };
  const leave = () => {
    setHover(false);
    if (useVideo && videoRef.current) {
      videoRef.current.pause();
      videoRef.current.currentTime = 0;
    }
  };

  return (
    // Yalnız gerçek fare: iOS dokunuşta sahte mouseenter üretip mouseleave
    // göndermiyor → 2. görsel/video takılı kalıyor, üstelik içerik değiştiği
    // için Safari ilk dokunuşu yutup ürüne ancak ikinci dokunuşta gidiyordu.
    <div
      className="kart-medya aspect-square bg-zinc-100 overflow-hidden hover-zoom relative"
      onPointerEnter={(e) => { if (e.pointerType === "mouse") enter(); }}
      onPointerMove={egil}
      onPointerLeave={(e) => {
        if (e.pointerType !== "mouse") return;
        leave();
        e.currentTarget.style.setProperty("--tilt-x", "0deg");
        e.currentTarget.style.setProperty("--tilt-y", "0deg");
      }}
    >
      {cover ? (
        // Liste: onlarca kart. Varyantlar statik; srcset ile telefon 400,
        // tablet 800, masaüstü 1280'i seçer. Tembel yüklenir; açılışta ekranda
        // olan ilk satır (oncelikli) hemen ve yüksek öncelikle istenir.
        <img src={urunGorsel(cover).src} srcSet={urunGorsel(cover).srcSet}
          sizes="(min-width: 1024px) 25vw, (min-width: 640px) 33vw, 50vw"
          alt={title} loading={oncelikli ? "eager" : "lazy"} decoding="async"
          fetchPriority={oncelikli ? "high" : undefined}
          className={`absolute inset-0 w-full h-full object-cover transition-opacity duration-300 ${
            hover && (hoverImage || useVideo) ? "opacity-0" : "opacity-100"}`} />
      ) : (
        <div className="w-full h-full flex items-center justify-center text-4xl text-zinc-300">
          📱
        </div>
      )}
      {hoverImage && (
        <img src={urunGorsel(hoverImage).src} srcSet={urunGorsel(hoverImage).srcSet}
          sizes="(min-width: 1024px) 25vw, (min-width: 640px) 33vw, 50vw"
          alt="" aria-hidden loading="lazy" decoding="async"
          className={`ikinci absolute inset-0 w-full h-full object-cover transition-opacity duration-300 ${
            hover ? "opacity-100" : "opacity-0"}`} />
      )}
      {useVideo && (
        <video ref={videoRef} src={videoUrl!} muted loop playsInline preload="none"
          className={`absolute inset-0 w-full h-full object-cover transition-opacity duration-300 ${
            hover ? "opacity-100" : "opacity-0"}`} />
      )}
      {/* Köşedeki "+" — yalnız yumuşak kart stilinde görünür (globals.css) */}
      <span aria-hidden className="kart-arti">+</span>
    </div>
  );
}
