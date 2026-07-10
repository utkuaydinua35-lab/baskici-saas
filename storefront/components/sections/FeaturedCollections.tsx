import Link from "next/link";
import { getCollections } from "@/lib/api";

// Öne çıkan koleksiyonlar — tema ayarındaki slug listesi (boşsa hepsi, max 4).
export default async function FeaturedCollections({
  title,
  slugs,
}: {
  title?: string;
  slugs: string[];
}) {
  const all = await getCollections();
  const picked =
    slugs.length > 0
      ? slugs.map((s) => all.find((c) => c.slug === s)).filter(Boolean)
      : all.slice(0, 4);
  if (picked.length === 0) return null;

  return (
    <section className="mx-auto max-w-6xl px-4 py-10">
      <h2 className="text-lg font-semibold mb-4">{title || "Koleksiyonlar"}</h2>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {picked.map((c) => (
          <Link
            key={c!.slug}
            href={`/koleksiyon/${c!.slug}`}
            className="group relative rounded-2xl overflow-hidden border border-zinc-200 bg-white hover:shadow-md transition"
          >
            {c!.image_url ? (
              <div className="relative aspect-[4/3] overflow-hidden">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={c!.image_url} alt={c!.title}
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" />
                <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
                <div className="absolute bottom-0 inset-x-0 p-3">
                  <div className="font-semibold text-sm text-white">{c!.title}</div>
                  <div className="text-[11px] text-white/80">Keşfet →</div>
                </div>
              </div>
            ) : (
              <div className="p-5">
                <div
                  className="absolute inset-x-0 bottom-0 h-1 opacity-70 group-hover:opacity-100 transition"
                  style={{ background: "var(--c-accent)" }}
                />
                <div className="font-medium text-sm">{c!.title}</div>
                {c!.description && (
                  <div className="mt-1 text-xs text-zinc-500 line-clamp-2">{c!.description}</div>
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
