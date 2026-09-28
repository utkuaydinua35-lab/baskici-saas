import Reveal from "@/components/Reveal";
import YorumSeridi from "@/components/sections/YorumSeridi";
import SectionHeading from "@/components/SectionHeading";

type Yorum = { author: string; text: string; rating: number; image?: string };

// Müşteri yorumları vitrini (ShinePro results) — anasayfa sosyal kanıt.
//  stil kart:       yıldızlı kutular
//  stil fotografli: koyu bant, fotoğraf + alıntı yan yana yatay kartlar;
//                   oklu, kendiliğinden ilerleyen şerit (Füzyon)
export default function Testimonials({
  eyebrow,
  title,
  subtitle,
  items = [],
  stil = "kart",
  altNot,
  instagram,
}: {
  eyebrow?: string;
  title?: string;
  subtitle?: string;
  items?: Yorum[];
  stil?: string;
  altNot?: string;
  instagram?: string;
}) {
  const valid = items.filter((i) => i.text);
  if (valid.length === 0) return null;

  if (stil === "fotografli") {
    return (
      <section className="bg-[#050505] text-zinc-100 py-10 sm:py-16 my-8 sm:my-12 koyu-bant">
        <div className="mx-auto max-w-6xl px-4">
          <YorumSeridi items={valid} ariaLabel={title || "Müşteri yorumları"}
            baslik={<SectionHeading eyebrow={eyebrow} title={title || "Müşterilerimiz Ne Diyor?"} subtitle={subtitle} />} />
          {(altNot || instagram) && (
            <div className="mt-6 flex flex-col sm:flex-row gap-2 sm:justify-between text-[11px] text-zinc-500">
              {altNot && <span>{altNot}</span>}
              {instagram && (
                <a href={`https://instagram.com/${instagram}`} target="_blank" rel="noopener noreferrer"
                  className="text-zinc-300 hover:text-white">@{instagram} →</a>
              )}
            </div>
          )}
        </div>
      </section>
    );
  }

  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <SectionHeading eyebrow={eyebrow} title={title || "Müşterilerimiz Ne Diyor?"}
        subtitle={subtitle} center />
      <div className={`grid gap-4 sm:grid-cols-2 ${valid.length >= 3 ? "lg:grid-cols-3" : ""}`}>
        {valid.map((t, i) => (
          <Reveal key={i} delay={(i % 3) * 80}>
            <figure className="h-full bg-white border border-zinc-200 rounded-2xl p-5 flex flex-col">
              <div className="text-amber-400 text-sm">
                {"★".repeat(Math.min(5, Math.max(1, t.rating)))}
                {"☆".repeat(5 - Math.min(5, Math.max(1, t.rating)))}
              </div>
              <blockquote className="mt-2 text-sm text-zinc-600 leading-relaxed flex-1">
                “{t.text}”
              </blockquote>
              <figcaption className="mt-3 text-xs font-semibold text-zinc-700">
                — {t.author || "Müşteri"}
              </figcaption>
            </figure>
          </Reveal>
        ))}
      </div>
    </section>
  );
}
