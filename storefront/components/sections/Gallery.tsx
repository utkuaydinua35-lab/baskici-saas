import Link from "next/link";
import Reveal from "@/components/Reveal";
import Carousel from "@/components/Carousel";
import GaleriVideo from "@/components/GaleriVideo";
import SectionHeading from "@/components/SectionHeading";
import { urunGorsel } from "@/lib/gorsel";

export interface GaleriOgesi {
  url: string;
  tip?: "gorsel" | "video";
  link?: string;
  etiket?: string;
}

// Görsel galerisi ("Sizden Gelenler", hikâye paylaşımları…).
//  Öğe: görsel ya da video; isteğe bağlı bağlantı ve etiket ("@kullanıcı").
//  aspect: square (kare) | story (9:16 Instagram hikâyesi)
//  mode:   scroll   — elle kaydırılan şerit
//          carousel — oklu, kendiliğinden ilerleyen şerit
//          marquee  — hiç durmadan akan şerit (üstüne gelince durur)
export default function Gallery({
  eyebrow,
  title,
  subtitle,
  items = [],
  aspect = "square",
  mode = "scroll",
}: {
  eyebrow?: string;
  title?: string;
  subtitle?: string;
  items?: GaleriOgesi[];
  aspect?: "square" | "story";
  mode?: "scroll" | "carousel" | "marquee";
}) {
  const valid = items.filter((o) => o?.url);
  if (valid.length === 0) return null;

  const story = aspect === "story";
  const oran = story ? "aspect-[9/16]" : "aspect-square";
  const en = story ? "w-[62vw] max-w-[280px] sm:w-[260px]" : "w-52 sm:w-60";
  // Kart ekranda en fazla ~280px — 400w varyant yeter, retina 800w'yi seçer
  const sizes = story ? "(min-width: 640px) 260px, 62vw" : "(min-width: 640px) 240px, 208px";

  const kart = (o: GaleriOgesi, i: number, tekrar = false) => {
    const alt = tekrar ? "" : o.etiket || `${title || "Galeri"} ${i + 1}`;
    const g = urunGorsel(o.url);
    const icerik = (
      <>
        {o.tip === "video" ? (
          <GaleriVideo src={o.url} etiket={o.etiket} />
        ) : (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={g.src} srcSet={g.srcSet || undefined} sizes={g.srcSet ? sizes : undefined}
            alt={alt} loading="lazy" decoding="async"
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
        )}
        {o.etiket ? (
          <span className="pointer-events-none absolute left-2.5 top-2.5 max-w-[85%] truncate rounded-full
            bg-black/55 px-2.5 py-1 text-[11px] font-medium text-white">
            {o.etiket}
          </span>
        ) : null}
      </>
    );
    const kap = `group relative block shrink-0 ${en} ${oran} rounded-2xl overflow-hidden bg-zinc-100 snap-start`;
    const anahtar = `${tekrar ? "t" : "a"}-${i}`;
    // Tekrar kopyası (akan şeridin dikişsiz döngüsü) odaklanamaz, okunmaz
    if (o.link && !tekrar) {
      return o.link.startsWith("/") ? (
        <Link key={anahtar} href={o.link} className={kap}>{icerik}</Link>
      ) : (
        <a key={anahtar} href={o.link} target="_blank" rel="noopener noreferrer" className={kap}>{icerik}</a>
      );
    }
    return (
      <div key={anahtar} className={kap} aria-hidden={tekrar || undefined}>{icerik}</div>
    );
  };

  const baslik = <SectionHeading eyebrow={eyebrow} title={title || "Sizden Gelenler"} subtitle={subtitle} center />;

  if (mode === "marquee") {
    // Kart başına ~5 sn: az öğede de hız makul kalır
    const sure = `${Math.max(20, valid.length * 5)}s`;
    return (
      <section className="py-10">
        <div className="mx-auto max-w-6xl px-4">{baslik}</div>
        <div className="akan-kap overflow-hidden">
          <div className="akan-serit flex w-max gap-4 px-2"
            style={{ "--akan-sure": sure } as React.CSSProperties}>
            {valid.map((o, i) => kart(o, i))}
            {valid.map((o, i) => kart(o, i, true))}
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
            {valid.map((o, i) => kart(o, i))}
          </Carousel>
        ) : (
          <div className="serit-gizli flex gap-3 overflow-x-auto pb-2 snap-x snap-mandatory">
            {valid.map((o, i) => kart(o, i))}
          </div>
        )}
      </Reveal>
    </section>
  );
}
