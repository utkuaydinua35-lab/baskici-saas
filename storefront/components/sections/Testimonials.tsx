import Reveal from "@/components/Reveal";
import SectionHeading from "@/components/SectionHeading";

// Müşteri yorumları vitrini (ShinePro results) — anasayfa sosyal kanıt.
export default function Testimonials({
  eyebrow,
  title,
  subtitle,
  items = [],
}: {
  eyebrow?: string;
  title?: string;
  subtitle?: string;
  items?: { author: string; text: string; rating: number }[];
}) {
  const valid = items.filter((i) => i.text);
  if (valid.length === 0) return null;
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
