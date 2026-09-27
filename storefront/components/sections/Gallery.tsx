import Reveal from "@/components/Reveal";
import Carousel from "@/components/Carousel";
import SectionHeading from "@/components/SectionHeading";

// Görsel galerisi ("Sizden Gelenler", hikâye paylaşımları…).
//  aspect: square (kare) | story (9:16 Instagram hikâyesi)
//  mode:   scroll   — elle kaydırılan şerit
//          carousel — oklu, kendiliğinden ilerleyen şerit
//          marquee  — hiç durmadan akan şerit (üstüne gelince durur)
export default function Gallery({
  eyebrow,
  title,
  subtitle,
  images = [],
  aspect = "square",
  mode = "scroll",
}: {
  eyebrow?: string;
  title?: string;
  subtitle?: string;
  images?: string[];
  aspect?: "square" | "story";
  mode?: "scroll" | "carousel" | "marquee";
}) {
  const valid = images.filter(Boolean);
  if (valid.length === 0) return null;

  const story = aspect === "story";
  const oran = story ? "aspect-[9/16]" : "aspect-square";
  const en = story ? "w-[62vw] max-w-[280px] sm:w-[260px]" : "w-52 sm:w-60";
  const kart = (u: string, i: number, tekrar = false) => (
    <div key={`${tekrar ? "t" : "a"}-${i}`}
      className={`shrink-0 ${en} ${oran} rounded-2xl overflow-hidden bg-zinc-100 snap-start`}
      aria-hidden={tekrar || undefined}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={u} alt={tekrar ? "" : `${title || "Galeri"} ${i + 1}`} loading="lazy" decoding="async"
        className="w-full h-full object-cover hover:scale-105 transition-transform duration-500" />
    </div>
  );

  const baslik = <SectionHeading eyebrow={eyebrow} title={title || "Sizden Gelenler"} subtitle={subtitle} center />;

  if (mode === "marquee") {
    // Kart başına ~5 sn: az görselde de hız makul kalır
    const sure = `${Math.max(20, valid.length * 5)}s`;
    return (
      <section className="py-10">
        <div className="mx-auto max-w-6xl px-4">{baslik}</div>
        <div className="akan-kap overflow-hidden">
          <div className="akan-serit flex w-max gap-4 px-2"
            style={{ "--akan-sure": sure } as React.CSSProperties}>
            {valid.map((u, i) => kart(u, i))}
            {valid.map((u, i) => kart(u, i, true))}
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="mx-auto max-w-6xl px-4 py-10">
      {baslik}
      <Reveal>
        {mode === "carousel" ? (
          <Carousel autoplaySec={4} ariaLabel={title || "Galeri"}>
            {valid.map((u, i) => kart(u, i))}
          </Carousel>
        ) : (
          <div className="serit-gizli flex gap-3 overflow-x-auto pb-2 snap-x snap-mandatory">
            {valid.map((u, i) => kart(u, i))}
          </div>
        )}
      </Reveal>
    </section>
  );
}
