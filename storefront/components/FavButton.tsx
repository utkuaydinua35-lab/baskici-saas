"use client";

// Favori kalbi — localStorage tabanlı istek listesi (sunucuya veri gitmez).
// Header rozeti "fav-changed" olayıyla senkron kalır.
import { useEffect, useState } from "react";

const KEY = "vitrin_favoriler";

export interface FavItem {
  slug: string;
  title: string;
  price: string;
  currency: string;
  image: string | null;
}

export function readFavs(): FavItem[] {
  try {
    const raw = localStorage.getItem(KEY);
    const list = raw ? JSON.parse(raw) : [];
    return Array.isArray(list) ? list : [];
  } catch {
    return [];
  }
}

export function writeFavs(list: FavItem[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(list.slice(0, 100)));
    window.dispatchEvent(new CustomEvent("fav-changed", { detail: { count: list.length } }));
  } catch {
    /* private mode */
  }
}

export default function FavButton({ item, floating = true }: { item: FavItem; floating?: boolean }) {
  const [fav, setFav] = useState(false);

  useEffect(() => {
    setFav(readFavs().some((f) => f.slug === item.slug));
  }, [item.slug]);

  const toggle = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const list = readFavs();
    if (list.some((f) => f.slug === item.slug)) {
      writeFavs(list.filter((f) => f.slug !== item.slug));
      setFav(false);
    } else {
      writeFavs([item, ...list]);
      setFav(true);
    }
  };

  return (
    <button
      onClick={toggle}
      aria-label={fav ? "Favorilerden çıkar" : "Favorilere ekle"}
      className={
        floating
          ? "absolute top-2 right-2 z-10 w-8 h-8 rounded-full bg-white/90 shadow flex items-center justify-center hover:scale-110 transition-transform"
          : "inline-flex items-center gap-1.5 text-sm text-zinc-600 hover:text-zinc-900"
      }
    >
      <svg width="18" height="18" viewBox="0 0 24 24"
        fill={fav ? "#ef4444" : "none"} stroke={fav ? "#ef4444" : "currentColor"} strokeWidth="1.8">
        <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.6l-1-1a5.5 5.5 0 0 0-7.8 7.8l1 1L12 21.2l7.8-7.8 1-1a5.5 5.5 0 0 0 0-7.8Z" />
      </svg>
      {!floating && (fav ? "Favorilerde" : "Favorilere Ekle")}
    </button>
  );
}
