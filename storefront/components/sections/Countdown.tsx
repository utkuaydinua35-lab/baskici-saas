"use client";

// Kampanya geri sayımı — süre dolunca bölüm kendini gizler.
import { useEffect, useState } from "react";
import Link from "next/link";

function remaining(endsAt: string) {
  const diff = new Date(endsAt).getTime() - Date.now();
  if (Number.isNaN(diff) || diff <= 0) return null;
  const s = Math.floor(diff / 1000);
  return {
    gun: Math.floor(s / 86400),
    saat: Math.floor((s % 86400) / 3600),
    dakika: Math.floor((s % 3600) / 60),
    saniye: s % 60,
  };
}

export default function Countdown({
  title,
  subtitle,
  endsAt,
  ctaText,
  ctaUrl,
}: {
  title?: string;
  subtitle?: string;
  endsAt?: string;
  ctaText?: string;
  ctaUrl?: string;
}) {
  const [left, setLeft] = useState<ReturnType<typeof remaining>>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!endsAt) return;
    const tick = () => setLeft(remaining(endsAt));
    tick();
    setReady(true);
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, [endsAt]);

  if (!endsAt || !ready || !left) return null; // süresi dolan kampanya görünmez

  const cells: [string, number][] = [
    ["Gün", left.gun], ["Saat", left.saat], ["Dakika", left.dakika], ["Saniye", left.saniye],
  ];

  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <div className="rounded-3xl px-6 py-10 text-center text-white"
        style={{ background: "linear-gradient(120deg, var(--c-primary), var(--c-accent))" }}>
        <h2 className="text-2xl font-bold">{title || "Kampanya bitiyor!"}</h2>
        {subtitle && <p className="mt-1.5 text-sm text-white/85">{subtitle}</p>}
        <div className="mt-6 flex justify-center gap-3">
          {cells.map(([label, val]) => (
            <div key={label}
              className="w-16 sm:w-20 rounded-2xl bg-white/15 backdrop-blur py-3">
              <div className="text-2xl sm:text-3xl font-bold tabular-nums">
                {String(val).padStart(2, "0")}
              </div>
              <div className="text-[10px] uppercase tracking-wide text-white/75">{label}</div>
            </div>
          ))}
        </div>
        {ctaText && (
          <Link href={ctaUrl || "/urunler"}
            className="mt-7 inline-block rounded-xl bg-white text-zinc-900 px-6 py-3 font-medium hover:scale-[1.03] transition">
            {ctaText}
          </Link>
        )}
      </div>
    </section>
  );
}
