import { jsonLdScript } from "@/lib/jsonld";
// SSS akordeonu (Shopify "Collapsible content") — native <details>, JS gerekmez.
export default function Faq({
  title,
  items = [],
}: {
  title?: string;
  items?: { q: string; a: string }[];
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
