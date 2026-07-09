"use client";

import { useEffect, useState } from "react";

interface Image {
  url: string;
  alt: string | null;
  variant_id?: string | null;
}

// Varyant seçici galeriye "variant-selected" olayı yollar (bileşenler kardeş
// olduğundan ortak state yerine hafif DOM olayı) — o varyanta bağlı görsel öne gelir.
export default function ProductGallery({ images, title }: { images: Image[]; title: string }) {
  const [active, setActive] = useState(0);
  const current = images[active];

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
      <div className="aspect-square rounded-2xl border border-zinc-200 bg-white overflow-hidden">
        {current ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={current.url} alt={current.alt || title} className="w-full h-full object-contain" />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-6xl text-zinc-200">📱</div>
        )}
      </div>
      {images.length > 1 && (
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
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={im.url} alt={im.alt || ""} className="w-full h-full object-cover" />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
