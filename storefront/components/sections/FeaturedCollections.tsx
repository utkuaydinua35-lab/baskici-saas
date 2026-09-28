import { urunGorsel } from "@/lib/gorsel";
import Link from "next/link";
import { getCollections } from "@/lib/api";
import Reveal from "@/components/Reveal";
import SectionHeading from "@/components/SectionHeading";

// Öne çıkan koleksiyonlar — tema ayarındaki slug listesi (boşsa ilk `limit`).
//  layout: grid     — 4'lü küçük kartlar
//          showcase — 2'li büyük kartlar; numara, açıklama ve "Keşfet"
//          kartlar  — 4'lü yuvarlak görsel kart, altta beyaz etiket kutusu (Füzyon)
export default async function FeaturedCollections({
  eyebrow,
  title,
  subtitle,
  slugs,
  layout = "grid",
  limit = 4,
}: {
  eyebrow?: string;
  title?: string;
  subtitle?: string;
  slugs: string[];
  layout?: "grid" | "showcase" | "kartlar";
  limit?: number;
}) {
  const all = await getCollections();
  const picked = (
    slugs.length > 0
      ? slugs.map((s) => all.find((c) => c.slug === s))
      : all.slice(0, limit)
  ).filter((c): c is NonNullable<typeof c> => !!c);
  if (picked.length === 0) return null;

  if (layout === "kartlar") {
    return (
      <section className="mx-auto max-w-6xl px-4 pt-10 sm:pt-12 pb-4">
        <SectionHeading eyebrow={eyebrow} title={title || "Kategoriler"} subtitle={subtitle}
          href="/urunler" linkText="Tümünü gör →" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-5">
          {picked.map((c, i) => (
            <Reveal key={c.slug} delay={(i % 4) * 70}>
              <Link href={`/koleksiyon/${c.slug}`}
                className="group relative block aspect-[1/1.2] sm:aspect-[1/1.1] rounded-[14px] sm:rounded-[18px] overflow-hidden bg-zinc-100"
                style={c.image_url ? undefined
                  : { background: "linear-gradient(140deg, color-mix(in srgb, var(--c-accent) 18%, #f4f4f4), #ececec)" }}>
                {c.image_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={urunGorsel(c.image_url).src} srcSet={urunGorsel(c.image_url).srcSet || undefined}
                    sizes="(min-width: 1024px) 280px, 50vw" alt={c.title} loading="lazy" decoding="async"
                    className="absolute inset-0 w-full h-full object-cover transition-transform duration-1000 ease-[cubic-bezier(.22,1,.36,1)] group-hover:scale-[1.06]" />
                ) : null}
                {/* Etiket kutusu opak (bulanıklık yok: görsel büyürken her
                    karede yeniden bulanıklaştırma mobilde takılırdı) */}
                <div className="absolute inset-x-2 bottom-2 sm:inset-x-3.5 sm:bottom-3.5 flex items-center justify-between gap-2
                  rounded-[9px] sm:rounded-xl border border-white/60 bg-white/[.93] px-2.5 py-2.5 sm:px-4 sm:py-4">
                  <div className="min-w-0">
                    <h3 className="text-[12px] sm:text-[15px] font-medium leading-tight tracking-[-.01em] truncate">{c.title}</h3>
                    {c.description ? (
                      <p className="hidden sm:block mt-1 text-[10px] text-zinc-500 truncate">{c.description}</p>
                    ) : null}
                  </div>
                  <span aria-hidden className="text-lg sm:text-2xl text-zinc-700 transition-transform duration-300 group-hover:translate-x-[3px] group-hover:-translate-y-[3px]">→</span>
                </div>
              </Link>
            </Reveal>
          ))}
        </div>
      </section>
    );
  }

  if (layout === "showcase") {
    return (
      <section className="mx-auto max-w-6xl px-4 py-12">
        <SectionHeading eyebrow={eyebrow} title={title || "Koleksiyonlar"} subtitle={subtitle} />
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          {picked.map((c, i) => (
            <Reveal key={c.slug} delay={(i % 2) * 90}>
              <Link href={`/koleksiyon/${c.slug}`}
                className="group relative block aspect-[4/5] sm:aspect-[15/16] rounded-2xl overflow-hidden"
                style={c.image_url ? undefined
                  : { background: "linear-gradient(140deg, var(--c-primary), var(--c-accent))" }}>
                {c.image_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={urunGorsel(c.image_url).src} srcSet={urunGorsel(c.image_url).srcSet || undefined}
                    sizes="(min-width: 640px) 50vw, 100vw" alt={c.title} loading="lazy" decoding="async"
                    className="absolute inset-0 w-full h-full object-cover group-hover:scale-105 transition-transform duration-700" />
                ) : null}
                <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/15 to-transparent" />
                <div className="absolute inset-x-0 bottom-0 p-6 sm:p-7 text-white">
                  <div className="text-sm font-medium opacity-90">{String(i + 1).padStart(2, "0")}</div>
                  <div className="mt-0.5 text-2xl font-bold tracking-tight">{c.title}</div>
                  {c.description ? (
                    <p className="mt-2 text-sm text-white/85 line-clamp-2 max-w-sm">{c.description}</p>
                  ) : null}
                  <div className="mt-4 inline-flex items-center gap-2 text-sm font-semibold">
                    Keşfet
                    <span className="group-hover:translate-x-1 transition-transform">→</span>
                  </div>
                </div>
              </Link>
            </Reveal>
          ))}
        </div>
      </section>
    );
  }

  return (
    <section className="mx-auto max-w-6xl px-4 py-10">
      <SectionHeading eyebrow={eyebrow} title={title || "Koleksiyonlar"} subtitle={subtitle} />
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {picked.map((c) => (
          <Link
            key={c.slug}
            href={`/koleksiyon/${c.slug}`}
            className="group relative rounded-2xl overflow-hidden border border-zinc-200 bg-white hover:shadow-md transition"
          >
            {c.image_url ? (
              <div className="relative aspect-[4/3] overflow-hidden">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={urunGorsel(c.image_url).src} srcSet={urunGorsel(c.image_url).srcSet || undefined}
                  sizes="(min-width: 640px) 25vw, 50vw" alt={c.title} loading="lazy" decoding="async"
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" />
                <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
                <div className="absolute bottom-0 inset-x-0 p-3">
                  <div className="font-semibold text-sm text-white">{c.title}</div>
                  <div className="text-[11px] text-white/80">Keşfet →</div>
                </div>
              </div>
            ) : (
              <div className="p-5">
                <div
                  className="absolute inset-x-0 bottom-0 h-1 opacity-70 group-hover:opacity-100 transition"
                  style={{ background: "var(--c-accent)" }}
                />
                <div className="font-medium text-sm">{c.title}</div>
                {c.description && (
                  <div className="mt-1 text-xs text-zinc-500 line-clamp-2">{c.description}</div>
                )}
                <div className="mt-3 text-xs text-zinc-400 group-hover:translate-x-1 transition-transform">
                  Keşfet →
                </div>
              </div>
            )}
          </Link>
        ))}
      </div>
    </section>
  );
}
