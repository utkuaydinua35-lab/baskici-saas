import SatirliBaslik from "@/components/SatirliBaslik";
import Link from "next/link";
import Reveal from "@/components/Reveal";

type Adim = { title?: string; text?: string; url?: string };

// Numaralı adımlar (Füzyon) — solda serif başlık (2. satır italik), sağda
// 01 / 02 / 03 satırları. Bağlantısı olan satır tıklanır ve oku kayar.
export default function Adimlar({
  eyebrow,
  title,
  subtitle,
  items = [],
}: {
  eyebrow?: string;
  title?: string;
  subtitle?: string;
  items?: Adim[];
}) {
  const liste = items.filter((i) => i.title);
  if (liste.length === 0) return null;

  const satir = (a: Adim, i: number) => {
    const ic = (
      <>
        <span className="text-[13px] font-semibold tracking-wider text-zinc-400 tabular-nums">
          {String(i + 1).padStart(2, "0")}
        </span>
        <span className="min-w-0">
          <span className="block text-[15px] sm:text-base">{a.title}</span>
          {a.text && <span className="block mt-2 text-xs sm:text-[13px] leading-[1.7] text-zinc-500">{a.text}</span>}
        </span>
        <span aria-hidden className="text-xl text-zinc-400 transition-transform duration-300 group-hover:translate-x-1">
          {a.url ? "→" : ""}
        </span>
      </>
    );
    const cls = "group grid grid-cols-[35px_1fr_24px] gap-3 sm:gap-5 items-center py-6 border-b border-zinc-200";
    if (!a.url) return <div key={i} className={cls}>{ic}</div>;
    return a.url.startsWith("/")
      ? <Link key={i} href={a.url} className={cls}>{ic}</Link>
      : <a key={i} href={a.url} target="_blank" rel="noopener noreferrer" className={cls}>{ic}</a>;
  };

  return (
    <section className="mx-auto max-w-6xl px-4 py-10 sm:py-16 grid lg:grid-cols-[1fr_1.4fr] gap-6 lg:gap-20">
      <Reveal>
        {eyebrow && <p className="text-[10px] font-semibold tracking-[.16em] uppercase text-zinc-500">{eyebrow}</p>}
        {title && (
          <SatirliBaslik metin={title} italikAlt className="f-baslik mt-4 text-[42px] sm:text-[54px] leading-[1.12] tracking-[-.015em]" />
        )}
        {subtitle && <p className="mt-4 text-sm text-zinc-500 max-w-xs leading-relaxed">{subtitle}</p>}
      </Reveal>
      <Reveal delay={80}>
        <div className="border-t border-zinc-200">{liste.map(satir)}</div>
      </Reveal>
    </section>
  );
}
