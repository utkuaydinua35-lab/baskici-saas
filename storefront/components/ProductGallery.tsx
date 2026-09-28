"use client";

import { useEffect, useState } from "react";
import { urunGorsel } from "@/lib/gorsel";

interface Image {
  url: string;
  alt: string | null;
  variant_id?: string | null;
}

// Varyant seçici galeriye "variant-selected" olayı yollar (bileşenler kardeş
// olduğundan ortak state yerine hafif DOM olayı) — o varyanta bağlı görsel öne gelir.
function youtubeId(url: string): string | null {
  const m = url.match(/(?:youtube\.com\/(?:watch\?v=|shorts\/|embed\/)|youtu\.be\/)([\w-]{6,})/);
  return m ? m[1] : null;
}

export default function ProductGallery({
  images,
  title,
  videoUrl,
}: {
  images: Image[];
  title: string;
  videoUrl?: string | null;
}) {
  const [active, setActive] = useState(0);
  const [lightbox, setLightbox] = useState(false);
  const hasVideo = !!videoUrl;
  const videoIndex = images.length;          // video, galerinin son karesi
  const showingVideo = hasVideo && active === videoIndex;
  const current = images[active];
  const ytId = videoUrl ? youtubeId(videoUrl) : null;

  useEffect(() => {
    const onVariant = (e: Event) => {
      const variantId = (e as CustomEvent<{ variantId: string }>).detail?.variantId;
      if (!variantId) return;
      const idx = images.findIndex((im) => im.variant_id === variantId);
      if (idx >= 0) setActive(idx);
    };
    window.addEventListener("variant-selected", onVariant);
    return () => window.removeEventListener("variant-selected", onVariant);
  }, [images]);

  return (
    <div>
      {/* relative: mutlak konumlu görsel/video için konumlanmış kap */}
      <div className="relative aspect-square rounded-2xl border border-zinc-200 bg-white overflow-hidden">
        {showingVideo ? (
          ytId ? (
            <iframe
              src={`https://www.youtube-nocookie.com/embed/${ytId}`}
              title={`${title} video`} allowFullScreen
              className="w-full h-full"
              allow="accelerometer; autoplay; encrypted-media; picture-in-picture" />
          ) : (
            <video src={videoUrl!} controls playsInline className="w-full h-full object-contain" />
          )
        ) : current ? (
          // Sayfanın LCP öğesi. Varyantlar yükleme anında üretildiği için
          // statik gelir — ilk ziyaretçi optimize beklemez.
          <img src={urunGorsel(current.url).src} srcSet={urunGorsel(current.url).srcSet}
            sizes="(min-width: 768px) 50vw, 100vw" alt={current.alt || title}
            fetchPriority="high" decoding="async"
            onClick={() => setLightbox(true)}
            data-urun-ana-gorsel=""
            className="absolute inset-0 w-full h-full object-contain cursor-zoom-in" />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-6xl text-zinc-200">📱</div>
        )}
      </div>
      {/* Lightbox — görsele tıklayınca tam ekran büyür */}
      {lightbox && current && (
        <div onClick={() => setLightbox(false)}
          className="fixed inset-0 z-[90] bg-black/85 flex items-center justify-center p-6 cursor-zoom-out">
          <img src={current.url} alt={current.alt || title} decoding="async"
            className="max-w-full max-h-full object-contain rounded-xl w-auto h-auto" />
          <button aria-label="Kapat"
            className="absolute top-4 right-4 w-9 h-9 rounded-full bg-white/15 text-white text-lg">
            ×
          </button>
        </div>
      )}
      {(images.length + (hasVideo ? 1 : 0)) > 1 && (
        <div className="mt-3 flex gap-2 overflow-x-auto">
          {images.map((im, i) => (
            <button
              key={im.url}
              onClick={() => setActive(i)}
              className={`w-16 h-16 rounded-lg border overflow-hidden shrink-0 ${
                i === active ? "border-zinc-900" : "border-zinc-200"
              }`}
              aria-label={`Görsel ${i + 1}`}
            >
              {/* 64px kutu: en küçük varyant (400w) yeterli, tembel yüklenir */}
              <img src={urunGorsel(im.url).srcSet ? urunGorsel(im.url).src.replace(/(\.[a-z]+)$/, "-400$1") : im.url}
                alt={im.alt || ""} loading="lazy" decoding="async"
                className="w-full h-full object-cover" />
            </button>
          ))}
          {hasVideo && (
            <button
              onClick={() => setActive(videoIndex)}
              className={`w-16 h-16 rounded-lg border overflow-hidden shrink-0 bg-zinc-900 text-white
                flex items-center justify-center ${showingVideo ? "border-zinc-900" : "border-zinc-200"}`}
              aria-label="Ürün videosu"
            >
              ▶
            </button>
          )}
        </div>
      )}
    </div>
  );
}
