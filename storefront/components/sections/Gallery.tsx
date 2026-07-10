import Reveal from "@/components/Reveal";

// Görsel galerisi (ShinePro "Sizden Gelenler") — müşteri fotoğrafları şeridi.
export default function Gallery({
  title,
  images = [],
}: {
  title?: string;
  images?: string[];
}) {
  const valid = images.filter(Boolean);
  if (valid.length === 0) return null;
  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <h2 className="text-lg font-semibold text-center mb-5">{title || "Sizden Gelenler"}</h2>
      <Reveal>
        <div className="flex gap-3 overflow-x-auto pb-2 snap-x snap-mandatory">
          {valid.map((u, i) => (
            <div key={i}
              className="shrink-0 w-52 sm:w-60 aspect-square rounded-2xl overflow-hidden border border-zinc-200 bg-zinc-100 snap-start">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={u} alt={`${title || "Galeri"} ${i + 1}`} loading="lazy"
                className="w-full h-full object-cover hover:scale-105 transition-transform duration-300" />
            </div>
          ))}
        </div>
      </Reveal>
    </section>
  );
}
