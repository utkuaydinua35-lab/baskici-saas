import Reveal from "@/components/Reveal";
import Carousel from "@/components/Carousel";
import SectionHeading from "@/components/SectionHeading";
import { urunGorsel } from "@/lib/gorsel";

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
          <SectionHeading eyebrow={eyebrow} title={title || "Müşterilerimiz Ne Diyor?"} subtitle={subtitle} />
          <Carousel autoplaySec={5} ariaLabel={title || "Müşteri yorumları"}>
            {valid.map((t, i) => {
              const g = t.image ? urunGorsel(t.image) : null;
              return (
                <figure key={i}
                  className={`shrink-0 snap-start grid overflow-hidden rounded-[9px] sm:rounded-[5px] border border-[#303030] bg-[#131313]
                    w-[83vw] max-w-[380px] sm:max-w-none ${g ? "sm:w-[710px] sm:h-[355px] sm:grid-cols-2 grid-rows-[250px_1fr] sm:grid-rows-1" : "sm:w-[420px]"}`}>
                  {g && (
                    <div className="relative bg-zinc-800 overflow-hidden">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={g.src} srcSet={g.srcSet || undefined} sizes="(min-width: 640px) 355px, 83vw"
                        alt={`${t.author || "Müşteri"} paylaşımı`} loading="lazy" decoding="async"
                        className="absolute inset-0 w-full h-full object-cover" />
                    </div>
                  )}
                  <figcaption className="flex flex-col justify-center gap-5 p-5 sm:p-7 min-w-0">
                    <div className="flex items-center gap-3">
                      <span aria-hidden className="f-baslik w-9 h-9 shrink-0 rounded-full bg-zinc-800 text-zinc-300 grid place-items-center text-lg">
                        {(t.author || "M").trim().charAt(0).toLocaleUpperCase("tr")}
                      </span>
                      <div className="min-w-0">
                        <div className="text-[13px] sm:text-sm truncate">{t.author || "Müşteri"}</div>
                        <div className="text-[10px] sm:text-[11px] text-zinc-500">
                          {"★".repeat(Math.min(5, Math.max(1, t.rating || 5)))}
                        </div>
                      </div>
                    </div>
                    <blockquote className="text-[13px] sm:text-[15px] leading-[1.8] text-zinc-300">“{t.text}”</blockquote>
                  </figcaption>
                </figure>
              );
            })}
          </Carousel>
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
