import { urunGorsel } from "@/lib/gorsel";
import Reveal from "@/components/Reveal";

// Banner bölümü — tıklanabilir geniş görsel. Köşe ovalliği panelden ayarlanır:
// radius_scope (both|mobile|desktop|none) + radius_pct (0-100 → 0-48px).
export default function Banner({
  image,
  url,
  radius_scope = "both",
  radius_pct = 50,
}: {
  image?: string | null;
  url?: string;
  radius_scope?: "both" | "mobile" | "desktop" | "none";
  radius_pct?: number;
}) {
  if (!image) return null;
  const px = Math.round(Math.max(0, Math.min(100, radius_pct)) * 0.48);
  const roundCls =
    radius_scope === "none" || px === 0 ? "rounded-none"
    : radius_scope === "mobile" ? "rounded-[var(--banner-r)] sm:rounded-none"
    : radius_scope === "desktop" ? "rounded-none sm:rounded-[var(--banner-r)]"
    : "rounded-[var(--banner-r)]";
  const img = (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={urunGorsel(image).src} srcSet={urunGorsel(image).srcSet || undefined}
      sizes="(min-width: 1152px) 1152px, 100vw" loading="lazy" decoding="async"
      alt="" style={{ "--banner-r": `${px}px` } as React.CSSProperties}
      className={`w-full object-cover max-h-80 ${roundCls}`} />
  );
  return (
    <section className="mx-auto max-w-6xl px-4 py-6">
      <Reveal>{url ? <a href={url}>{img}</a> : img}</Reveal>
    </section>
  );
}
