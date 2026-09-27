import Link from "next/link";
import { getCollections } from "@/lib/api";
import Reveal from "@/components/Reveal";
import SectionHeading from "@/components/SectionHeading";

// Öne çıkan koleksiyonlar — tema ayarındaki slug listesi (boşsa ilk `limit`).
//  layout: grid     — 4'lü küçük kartlar
//          showcase — 2'li büyük kartlar; numara, açıklama ve "Keşfet"
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
  layout?: "grid" | "showcase";
  limit?: number;
}) {
  const all = await getCollections();
  const picked = (
    slugs.length > 0
      ? slugs.map((s) => all.find((c) => c.slug === s))
      : all.slice(0, limit)
  ).filter((c): c is NonNullable<typeof c> => !!c);
  if (picked.length === 0) return null;

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
                  <img src={c.image_url} alt={c.title} loading="lazy" decoding="async"
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
                <img src={c.image_url} alt={c.title} loading="lazy" decoding="async"
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
