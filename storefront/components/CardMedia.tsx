"use client";

// Ürün kartı medyası — kapak görsel; imleç gelince 2. görsel, o yoksa video oynar.
import { useRef, useState } from "react";

export default function CardMedia({
  cover,
  hoverImage,
  videoUrl,
  title,
}: {
  cover: string | null;
  hoverImage?: string | null;
  videoUrl?: string | null;
  title: string;
}) {
  const [hover, setHover] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
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
    <div
      className="aspect-square bg-zinc-100 overflow-hidden hover-zoom relative"
      onMouseEnter={enter}
      onMouseLeave={leave}
    >
      {cover ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={cover} alt={title} loading="lazy"
          className={`w-full h-full object-cover transition-opacity duration-300 ${
            hover && (hoverImage || useVideo) ? "opacity-0" : "opacity-100"}`} />
      ) : (
        <div className="w-full h-full flex items-center justify-center text-4xl text-zinc-300">
          📱
        </div>
      )}
      {hoverImage && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={hoverImage} alt="" loading="lazy" aria-hidden
          className={`absolute inset-0 w-full h-full object-cover transition-opacity duration-300 ${
            hover ? "opacity-100" : "opacity-0"}`} />
      )}
      {useVideo && (
        <video ref={videoRef} src={videoUrl!} muted loop playsInline preload="none"
          className={`absolute inset-0 w-full h-full object-cover transition-opacity duration-300 ${
            hover ? "opacity-100" : "opacity-0"}`} />
      )}
    </div>
  );
}
