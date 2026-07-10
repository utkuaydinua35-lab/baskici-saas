import Reveal from "@/components/Reveal";

// Karşılaştırma tablosu (ShinePro comparison-table) — Biz vs Diğerleri.
export default function Comparison({
  title,
  usLabel,
  themLabel,
  rows = [],
}: {
  title?: string;
  usLabel?: string;
  themLabel?: string;
  rows?: { feature: string; us: boolean; them: boolean }[];
}) {
  const valid = rows.filter((r) => r.feature);
  if (valid.length === 0) return null;
  return (
    <section className="mx-auto max-w-3xl px-4 py-8">
      <Reveal>
        <h2 className="text-lg font-semibold text-center mb-5">{title || "Neden Biz?"}</h2>
        <div className="bg-white border border-zinc-200 rounded-2xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-200">
                <th className="text-left px-4 py-3 font-medium text-zinc-500 text-xs"></th>
                <th className="px-4 py-3 text-center">
                  <span className="inline-block text-white text-xs font-bold rounded-full px-3 py-1"
                    style={{ background: "var(--c-primary)" }}>
                    {usLabel || "Biz"}
                  </span>
                </th>
                <th className="px-4 py-3 text-center text-xs font-medium text-zinc-400">
                  {themLabel || "Diğerleri"}
                </th>
              </tr>
            </thead>
            <tbody>
              {valid.map((r, i) => (
                <tr key={i} className={i > 0 ? "border-t border-zinc-100" : ""}>
                  <td className="px-4 py-3 text-zinc-700">{r.feature}</td>
                  <td className="px-4 py-3 text-center text-lg">
                    {r.us ? <span className="text-emerald-500">✓</span> : <span className="text-zinc-300">✕</span>}
                  </td>
                  <td className="px-4 py-3 text-center text-lg">
                    {r.them ? <span className="text-emerald-500">✓</span> : <span className="text-red-300">✕</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Reveal>
    </section>
  );
}
