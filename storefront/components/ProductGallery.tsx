"use client";

import { useEffect, useState } from "react";
import { urunGorsel } from "@/lib/gorsel";

interface Image {
  url: string;
  alt: string | null;
  variant_id?: string | null;
  /** Bu görsele eşlenmiş varyantların model_key'leri (ürünün varyant görseli açıksa) */
  varyantlar?: string[];
  /** Arkası saydam görselde ürünün dolu kutusu (0-1) + görselin piksel ölçüsü */
  dolu?: { x0: number; y0: number; x1: number; y1: number; w: number; h: number } | null;
}

// Saydam PNG'de ürün görselin küçük bir kısmını kaplıyor: dolu kutu kare
// çerçevenin ~%92'sini dolduracak şekilde ORTALANIP büyütülür (dosya aynı).
// Kare kutuda "object-contain" ile görselin kapladığı alan hesaplanır, dolu
// kutunun merkezi etrafında ölçeklenip merkeze taşınır.
function doluStil(d?: Image["dolu"]): React.CSSProperties | undefined {
  if (!d || !d.w || !d.h) return undefined;
  const oran = d.w / d.h;
  const rw = oran >= 1 ? 1 : oran, rh = oran >= 1 ? 1 / oran : 1;   // kutudaki görsel ölçüsü
  const bw = (d.x1 - d.x0) * rw, bh = (d.y1 - d.y0) * rh;
  const olcek = Math.min(0.92 / bw, 0.92 / bh, 2.6);
  if (olcek <= 1.03) return undefined;
  const cx = 0.5 + ((d.x0 + d.x1) / 2 - 0.5) * rw;
  const cy = 0.5 + ((d.y0 + d.y1) / 2 - 0.5) * rh;
  return {
    transformOrigin: `${cx * 100}% ${cy * 100}%`,
    transform: `translate(${(0.5 - cx) * 100}%, ${(0.5 - cy) * 100}%) scale(${olcek})`,
  };
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
  // Seçenek görseli ürün görsellerinde yoksa galerinin SONUNA eklenir
  const [ekGorsel, setEkGorsel] = useState<Image | null>(null);
  const gorseller = ekGorsel ? [...images, ekGorsel] : images;
  const hasVideo = !!videoUrl;
  const videoIndex = gorseller.length;       // video, galerinin son karesi
  const showingVideo = hasVideo && active === videoIndex;
  const current = gorseller[active];
  const ytId = videoUrl ? youtubeId(videoUrl) : null;

  useEffect(() => {
    const onVariant = (e: Event) => {
      const d = (e as CustomEvent<{ variantId: string; modelKey?: string }>).detail;
      if (!d?.variantId) return;
      const idx = images.findIndex((im) =>
        im.variant_id === d.variantId || (!!d.modelKey && (im.varyantlar || []).includes(d.modelKey)));
      if (idx >= 0) { setActive(idx); return; }
      // Eşlenmemiş varyant seçildi: ekranda BAŞKA bir varyantın görseli
      // kaldıysa yanlış ürünü gösteriyor olur → ilk genel görsele dön
      setActive((a) => {
        const su = images[a];
        if (!su || !(su.varyantlar?.length || su.variant_id)) return a;
        const genel = images.findIndex((im) => !(im.varyantlar?.length || im.variant_id));
        return genel >= 0 ? genel : a;
      });
    };
    // Kişiye özel seçenek (mat/parlak…) seçildi: görseli öne gelsin
    const onSecenek = (e: Event) => {
      const d = (e as CustomEvent<{ url: string; ad?: string }>).detail;
      if (!d?.url) return;
      const idx = images.findIndex((im) => im.url === d.url);
      if (idx >= 0) { setEkGorsel(null); setActive(idx); return; }
      setEkGorsel({ url: d.url, alt: d.ad || null });
      setActive(images.length);
    };
    window.addEventListener("variant-selected", onVariant);
    window.addEventListener("secenek-gorseli", onSecenek);
    return () => {
      window.removeEventListener("variant-selected", onVariant);
      window.removeEventListener("secenek-gorseli", onSecenek);
    };
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
            style={doluStil(current.dolu)}
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
      {(gorseller.length + (hasVideo ? 1 : 0)) > 1 && (
        <div className="mt-3 flex gap-2 overflow-x-auto">
          {gorseller.map((im, i) => (
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
                // Küçük sürümü olmayan görsel (ör. seçenek görseli) → asıl dosya
                onError={(e) => { if (e.currentTarget.src !== new URL(im.url, location.href).href) e.currentTarget.src = im.url; }}
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
