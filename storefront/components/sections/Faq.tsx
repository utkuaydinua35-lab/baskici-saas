import SatirliBaslik from "@/components/SatirliBaslik";
import { jsonLdScript } from "@/lib/jsonld";
// SSS akordeonu (Shopify "Collapsible content") — native <details>, JS gerekmez.
//  stil tek:       ortada kutulu liste
//  stil iki_sutun: solda başlık + açıklama + iletişim, sağda çizgili liste;
//                  biri açılınca diğeri kapanır (details name — JS gerekmez)
export default function Faq({
  title,
  items = [],
  stil = "tek",
  eyebrow,
  subtitle,
  eposta,
}: {
  title?: string;
  items?: { q: string; a: string }[];
  stil?: string;
  eyebrow?: string;
  subtitle?: string;
  eposta?: string | null;
}) {
  const valid = items.filter((i) => i.q && i.a);
  if (valid.length === 0) return null;

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: valid.map((i) => ({
      "@type": "Question",
      name: i.q,
      acceptedAnswer: { "@type": "Answer", text: i.a },
    })),
  };

  if (stil === "iki_sutun") {
    return (
      <section className="mx-auto max-w-6xl px-4 py-10 sm:py-16 grid lg:grid-cols-[1fr_1.4fr] gap-6 lg:gap-20">
        <script type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: jsonLdScript(jsonLd) }} />
        <div>
          {eyebrow && <p className="text-[10px] font-semibold tracking-[.16em] uppercase text-zinc-500">{eyebrow}</p>}
          <SatirliBaslik metin={title || "Sıkça Sorulan Sorular"} italikAlt
            className="f-baslik mt-4 text-[42px] sm:text-[52px] leading-[1.1] tracking-[-.015em]" />
          {subtitle && <p className="mt-4 text-[13px] sm:text-sm leading-[1.8] text-zinc-500 max-w-xs">{subtitle}</p>}
          {eposta && (
            <a href={`mailto:${eposta}`} className="mt-4 inline-block border-b border-zinc-300 py-2 text-xs hover:border-zinc-900">{eposta}</a>
          )}
        </div>
        <div className="border-t border-zinc-200">
          {valid.map((item, i) => (
            <details key={i} name="sss" className="group border-b border-zinc-200 py-5 sm:py-6">
              <summary className="flex justify-between gap-5 cursor-pointer list-none [&::-webkit-details-marker]:hidden text-sm sm:text-[15px] leading-normal">
                {item.q}
                <span aria-hidden className="text-xl font-light text-zinc-500 leading-none group-open:hidden">+</span>
                <span aria-hidden className="text-xl font-light text-zinc-500 leading-none hidden group-open:inline">−</span>
              </summary>
              <p className="mt-4 mb-1 text-[13px] sm:text-sm leading-[1.9] text-zinc-500 whitespace-pre-line">{item.a}</p>
            </details>
          ))}
        </div>
      </section>
    );
  }

  return (
    <section className="mx-auto max-w-3xl px-4 py-8">
      <script type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: jsonLdScript(jsonLd) }} />
      <h2 className="text-lg font-semibold mb-4">{title || "Sıkça Sorulan Sorular"}</h2>
      <div className="space-y-2">
        {valid.map((item, i) => (
          <details key={i}
            className="group bg-white border border-zinc-200 rounded-xl px-4 py-3 open:shadow-sm">
            <summary className="flex items-center justify-between cursor-pointer text-sm font-medium list-none [&::-webkit-details-marker]:hidden">
              {item.q}
              <span className="text-zinc-400 group-open:rotate-180 transition-transform">▾</span>
            </summary>
            <p className="mt-2 text-sm text-zinc-600 leading-relaxed whitespace-pre-line">{item.a}</p>
          </details>
        ))}
      </div>
    </section>
  );
}
