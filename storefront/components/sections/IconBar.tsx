import Link from "next/link";
import Reveal from "@/components/Reveal";
import CizgiIkon from "@/lib/cizgiIkon";

type Oge = { icon: string; title: string; text?: string; url?: string };

// İkon şeridi (ShinePro icon-bar) — avantaj vurguları.
//  stil kart:  ortalı ayrı kutular (emoji ikon)
//  stil serit: tek çerçevede yan yana, solda çizgi ikon; bağlantısı olan
//              öğe tıklanır (Füzyon "hizmet şeridi")
export default function IconBar({
  items = [],
  stil = "kart",
}: {
  items?: Oge[];
  stil?: string;
}) {
  const valid = items.filter((i) => i.title);
  if (valid.length === 0) return null;

  if (stil === "serit") {
    const ic = (i: Oge) => (
      <>
        <span className="w-7 shrink-0 grid place-items-center text-zinc-600">
          <CizgiIkon ad={i.icon} className="w-6 h-6 sm:w-6 sm:h-6" />
        </span>
        <span className="min-w-0">
          <span className="block text-[12px] sm:text-[13px] font-medium leading-snug">{i.title}</span>
          {i.text && <span className="block text-[10px] sm:text-[11px] text-zinc-500 leading-snug mt-0.5">{i.text}</span>}
        </span>
      </>
    );
    const hucre = "flex items-center gap-3 px-3 sm:px-5 py-4 sm:py-6 border-zinc-200";
    return (
      <section className="mx-auto max-w-6xl px-4 pt-5">
        <div className={`grid grid-cols-2 ${valid.length >= 4 ? "lg:grid-cols-4" : "lg:grid-cols-3"}
          rounded-2xl border border-zinc-200 bg-zinc-50 overflow-hidden
          [&>*]:border-b lg:[&>*]:border-b-0 [&>*:nth-child(odd)]:border-r lg:[&>*]:border-r lg:[&>*:last-child]:border-r-0
          [&>*:nth-last-child(-n+2)]:border-b-0`}>
          {valid.map((i, idx) => i.url ? (
            i.url.startsWith("/") ? (
              <Link key={idx} href={i.url} className={`${hucre} hover:bg-zinc-100 transition-colors`}>{ic(i)}</Link>
            ) : (
              <a key={idx} href={i.url} className={`${hucre} hover:bg-zinc-100 transition-colors`}
                {...(i.url.startsWith("http") ? { target: "_blank", rel: "noopener noreferrer" } : {})}>{ic(i)}</a>
            )
          ) : (
            <div key={idx} className={hucre}>{ic(i)}</div>
          ))}
        </div>
      </section>
    );
  }

  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <Reveal>
        <div className={`grid gap-3 grid-cols-2 ${valid.length >= 4 ? "lg:grid-cols-4" : "lg:grid-cols-3"}`}>
          {valid.map((i, idx) => (
            <div key={idx}
              className="bg-white border border-zinc-200 rounded-2xl p-4 text-center">
              <div className="text-3xl flex justify-center"><CizgiIkon ad={i.icon || "✨"} className="w-8 h-8" /></div>
              <div className="mt-2 text-sm font-semibold">{i.title}</div>
              {i.text && <div className="mt-1 text-xs text-zinc-500">{i.text}</div>}
            </div>
          ))}
        </div>
      </Reveal>
    </section>
  );
}
