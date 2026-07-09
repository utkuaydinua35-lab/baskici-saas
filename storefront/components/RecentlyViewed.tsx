"use client";

// Son gezilenler — localStorage tabanlı (sunucuya veri gitmez, KVKK-nötr).
// Ürün sayfasında mevcut ürünü kaydeder ve diğerlerini şerit olarak gösterir.
import { useEffect, useState } from "react";
import Link from "next/link";
import { formatPrice } from "@/lib/format";

const KEY = "vitrin_son_gezilenler";
const MAX = 8;

interface Seen {
  slug: string;
  title: string;
  price: string;
  currency: string;
  image: string | null;
}

function readSeen(): Seen[] {
  try {
    const raw = localStorage.getItem(KEY);
    const list = raw ? JSON.parse(raw) : [];
    return Array.isArray(list) ? list : [];
  } catch {
    return [];
  }
}

export default function RecentlyViewed({ current }: { current: Seen }) {
  const [others, setOthers] = useState<Seen[]>([]);

  useEffect(() => {
    const list = readSeen().filter((s) => s.slug !== current.slug);
    setOthers(list.slice(0, MAX));
    try {
      localStorage.setItem(KEY, JSON.stringify([current, ...list].slice(0, MAX + 1)));
    } catch {
      /* private mode vb. — sessiz geç */
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current.slug]);

  if (others.length === 0) return null;

  return (
    <section className="mt-12 border-t border-zinc-200 pt-8">
      <h2 className="text-base font-semibold mb-4">Son Gezdikleriniz</h2>
      <div className="flex gap-3 overflow-x-auto pb-2 -mx-1 px-1">
        {others.map((s) => (
          <Link key={s.slug} href={`/urun/${s.slug}`}
            className="shrink-0 w-36 rounded-2xl border border-zinc-200 bg-white overflow-hidden hover:shadow-md transition-shadow">
            <div className="aspect-square bg-zinc-100">
              {s.image ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={s.image} alt={s.title} className="w-full h-full object-cover" loading="lazy" />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-2xl text-zinc-300">📱</div>
              )}
            </div>
            <div className="p-2">
              <div className="text-xs font-medium line-clamp-2">{s.title}</div>
              <div className="text-xs font-semibold mt-1">{formatPrice(s.price, s.currency)}</div>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
