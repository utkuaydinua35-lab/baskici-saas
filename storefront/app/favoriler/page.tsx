"use client";

// Favoriler (istek listesi) — localStorage; girişli müşteride hesapla senkron.
import { useEffect, useState } from "react";
import Link from "next/link";
import { formatPrice } from "@/lib/format";
import { readFavs, writeFavs, type FavItem } from "@/components/FavButton";

export default function FavoritesPage() {
  const [favs, setFavs] = useState<FavItem[] | null>(null);

  useEffect(() => {
    const local = readFavs();
    setFavs(local);
    // Girişli müşteride hesaptaki favorilerle birleştir (misafirde 401 → dokunma)
    (async () => {
      try {
        const res = await fetch("/api/account?action=favorites");
        if (!res.ok) return;
        const data = await res.json();
        const serverSlugs: string[] = Array.isArray(data.favorites) ? data.favorites : [];
        const missing = serverSlugs.filter((s) => !local.some((f) => f.slug === s));
        let merged = local;
        if (missing.length > 0) {
          // Eksik ürünlerin kart verisini çek (silinen/yayından kalkan ürünler elenir)
          const pr = await fetch(`/api/search?slugs=${encodeURIComponent(missing.join(","))}`);
          const pd = pr.ok ? await pr.json() : { items: [] };
          const fetched: FavItem[] = (pd.items || []).map(
            (p: { slug: string; title: string; price: string; currency: string; cover_image: string | null }) => ({
              slug: p.slug, title: p.title, price: p.price,
              currency: p.currency, image: p.cover_image,
            }),
          );
          merged = [...local, ...fetched];
        }
        // Cihazda olup hesapta olmayanlar da hesaba yazılsın
        if (missing.length > 0 || merged.some((f) => !serverSlugs.includes(f.slug))) {
          writeFavs(merged);
        }
        setFavs(merged);
      } catch {
        /* backend erişilemedi — yerel liste yeter */
      }
    })();
  }, []);

  const remove = (slug: string) => {
    const next = (favs ?? []).filter((f) => f.slug !== slug);
    writeFavs(next);
    setFavs(next);
  };

  if (favs === null) {
    return <div className="mx-auto max-w-xl px-4 py-20 text-center text-sm text-zinc-400">Yükleniyor…</div>;
  }

  if (favs.length === 0) {
    return (
      <div className="mx-auto max-w-xl px-4 py-20 text-center">
        <div className="text-5xl mb-3">🤍</div>
        <h1 className="text-xl font-semibold">Favori listeniz boş</h1>
        <p className="mt-2 text-sm text-zinc-500">Beğendiğiniz ürünlerin kalbine dokunun, burada birikssin.</p>
        <Link href="/urunler"
          className="mt-6 inline-block rounded-xl text-white px-5 py-2.5 text-sm font-medium hover:opacity-90 transition"
          style={{ background: "var(--c-primary)" }}>
          Ürünlere Göz At
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="text-xl font-semibold mb-5">Favorilerim ({favs.length})</h1>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
        {favs.map((f) => (
          <div key={f.slug}
            className="relative rounded-2xl border border-zinc-200 overflow-hidden bg-white hover:shadow-md transition-shadow">
            <button onClick={() => remove(f.slug)} aria-label="Favorilerden çıkar"
              className="absolute top-2 right-2 z-10 w-8 h-8 rounded-full bg-white/90 shadow flex items-center justify-center text-red-500 hover:scale-110 transition-transform">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="#ef4444" stroke="#ef4444" strokeWidth="1.8">
                <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.6l-1-1a5.5 5.5 0 0 0-7.8 7.8l1 1L12 21.2l7.8-7.8 1-1a5.5 5.5 0 0 0 0-7.8Z" />
              </svg>
            </button>
            <Link href={`/urun/${f.slug}`} className="block">
              <div className="aspect-square bg-zinc-100">
                {f.image ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={f.image} alt={f.title} className="w-full h-full object-cover" loading="lazy" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-4xl text-zinc-300">📱</div>
                )}
              </div>
              <div className="p-3">
                <h3 className="text-sm font-medium line-clamp-2">{f.title}</h3>
                <div className="mt-1 font-semibold text-sm">{formatPrice(f.price, f.currency)}</div>
              </div>
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
}
