import Link from "next/link";

// Numaralı sayfalama: ‹ 1 … 4 5 6 … 61 › — ilk/son sayfa ve etkin sayfanın
// komşuları görünür. Filtre parametreleri korunur; 1. sayfada "sayfa"
// parametresi yazılmaz (aynı içerik tek adreste kalsın — SEO).
export default function Sayfalama({
  page,
  lastPage,
  basePath,
  params,
}: {
  page: number;
  lastPage: number;
  basePath: string;
  params: Record<string, string | undefined>;
}) {
  if (lastPage <= 1) return null;

  const href = (n: number) => {
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v) q.set(k, v);
    if (n > 1) q.set("sayfa", String(n));
    const s = q.toString();
    return `${basePath}${s ? `?${s}` : ""}`;
  };

  // Görünecek sayfa numaraları; aradaki boşluklar null (…)
  const set = new Set([1, lastPage, page - 1, page, page + 1].filter((n) => n >= 1 && n <= lastPage));
  const sirali = [...set].sort((a, b) => a - b);
  const ogeler: (number | null)[] = [];
  sirali.forEach((n, i) => {
    if (i > 0 && n - sirali[i - 1] > 1) ogeler.push(null);
    ogeler.push(n);
  });

  const kutu = "min-w-9 h-9 px-2 grid place-items-center rounded-lg border text-sm transition";
  return (
    <nav className="mt-8 flex justify-center items-center gap-1.5 flex-wrap" aria-label="Sayfalar">
      {page > 1 && (
        <Link href={href(page - 1)} rel="prev" aria-label="Önceki sayfa"
          className={`${kutu} border-zinc-300 hover:border-zinc-500`}>‹</Link>
      )}
      {ogeler.map((n, i) =>
        n === null ? (
          <span key={`b${i}`} className="px-1 text-zinc-400">…</span>
        ) : n === page ? (
          <span key={n} aria-current="page"
            className={`${kutu} border-transparent text-white`} style={{ background: "var(--c-primary)" }}>
            {n}
          </span>
        ) : (
          <Link key={n} href={href(n)} className={`${kutu} border-zinc-300 hover:border-zinc-500`}>{n}</Link>
        ),
      )}
      {page < lastPage && (
        <Link href={href(page + 1)} rel="next" aria-label="Sonraki sayfa"
          className={`${kutu} border-zinc-300 hover:border-zinc-500`}>›</Link>
      )}
    </nav>
  );
}
