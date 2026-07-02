"use client";

import Link from "next/link";
import { useCart } from "@/lib/cart";

export default function Header({ siteName }: { siteName: string }) {
  const { count } = useCart();
  return (
    <header className="sticky top-0 z-40 bg-white/90 backdrop-blur border-b border-zinc-200">
      <div className="mx-auto max-w-6xl px-4 h-14 flex items-center gap-6">
        <Link href="/" className="font-bold text-lg tracking-tight">
          {siteName}
        </Link>
        <nav className="flex items-center gap-4 text-sm text-zinc-600">
          <Link href="/urunler" className="hover:text-zinc-900">
            Ürünler
          </Link>
        </nav>
        <Link
          href="/sepet"
          className="ml-auto relative inline-flex items-center gap-1.5 text-sm font-medium hover:text-zinc-900"
          aria-label="Sepet"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <path d="M6 7h12l-1.2 11.1a2 2 0 0 1-2 1.9H9.2a2 2 0 0 1-2-1.9L6 7Z" />
            <path d="M9 7V6a3 3 0 0 1 6 0v1" />
          </svg>
          Sepet
          {count > 0 && (
            <span className="absolute -top-2 -right-3 bg-zinc-900 text-white text-[10px] rounded-full min-w-4 h-4 px-1 flex items-center justify-center">
              {count}
            </span>
          )}
        </Link>
      </div>
    </header>
  );
}
