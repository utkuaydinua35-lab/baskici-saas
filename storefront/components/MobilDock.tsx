"use client";

// Telefon alt çubuğu (Füzyon) — Keşfet / Tasarla / Favoriler / Sepet.
// Yalnız dar ekranda (lg altı). Kendi alt çubuğu olan sayfalarda (tasarım
// stüdyosu, ödeme) gizlenir. Görünürken body'ye "dock-var" eklenir: yüzen
// WhatsApp/destek balonları çubuğun üstüne çıkar, sayfa sonu çubuğun
// altında kalmaz (globals.css).
// Zemin OPAK: kayan içeriğin üstünde kalıcı bulanıklık (backdrop-filter)
// her karede yeniden hesaplanır ve telefonda kaydırmayı takıltır.
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCart } from "@/lib/cart";

const GIZLI = ["/tasarla", "/odeme", "/sepet"];

export default function MobilDock({
  cartDrawer,
  tasarla,
}: {
  cartDrawer: boolean;
  // Kişiye özel ürün satan mağazada orta düğme "Tasarla" (/tasarla);
  // değilse "Koleksiyonlar" (/urunler)
  tasarla: boolean;
}) {
  const pathname = usePathname() || "/";
  const { count, setDrawerOpen } = useCart();
  const [fav, setFav] = useState(0);
  const gizli = GIZLI.some((y) => pathname === y || pathname.startsWith(`${y}/`));

  useEffect(() => {
    if (gizli) return;
    document.body.classList.add("dock-var");
    return () => document.body.classList.remove("dock-var");
  }, [gizli]);

  useEffect(() => {
    const oku = () => {
      try { const l = JSON.parse(localStorage.getItem("vitrin_favoriler") || "[]"); setFav(Array.isArray(l) ? l.length : 0); }
      catch { setFav(0); }
    };
    oku();
    const degisti = (e: Event) => setFav((e as CustomEvent<{ count: number }>).detail?.count ?? 0);
    window.addEventListener("fav-changed", degisti);
    return () => window.removeEventListener("fav-changed", degisti);
  }, []);

  if (gizli) return null;

  const oge = "relative flex flex-col items-center justify-center gap-1 py-0.5 text-[9px] text-zinc-300 active:text-white";
  const rozet = (n: number) => n > 0 && (
    <span className="absolute -top-1 left-1/2 ml-2 min-w-4 h-4 px-1 rounded-full bg-white text-zinc-900 text-[9px] font-semibold grid place-items-center">{n}</span>
  );
  return (
    <nav aria-label="Hızlı erişim"
      className="mobil-dock lg:hidden fixed inset-x-3.5 z-40 grid grid-cols-4 rounded-[19px] border border-white/15 bg-[#171717] px-2 py-2.5 shadow-[0_9px_30px_#0003]"
      style={{ bottom: "calc(12px + env(safe-area-inset-bottom))" }}>
      <Link href="/urunler" className={oge}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" className="w-[22px] h-[22px]" aria-hidden>
          <circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" />
        </svg>
        Keşfet
      </Link>
      <Link href={tasarla ? "/tasarla" : "/urunler"}
        className={`${oge} !text-white rounded-[14px] -my-0.5 mx-0.5`} style={{ background: "var(--c-accent)" }}>
        <span aria-hidden className="text-[22px] leading-none">{tasarla ? "+" : "☰"}</span>
        {tasarla ? "Tasarla" : "Koleksiyonlar"}
      </Link>
      <Link href="/favoriler" className={oge}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" className="w-[22px] h-[22px]" aria-hidden>
          <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.6l-1-1a5.5 5.5 0 0 0-7.8 7.8l1 1L12 21.2l7.8-7.8 1-1a5.5 5.5 0 0 0 0-7.8Z" />
        </svg>
        Favoriler{rozet(fav)}
      </Link>
      {cartDrawer ? (
        <button type="button" onClick={() => setDrawerOpen(true)} className={oge}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" className="w-[22px] h-[22px]" aria-hidden>
            <path d="M5 7h14l1 14H4L5 7Z" /><path d="M8 8V5a4 4 0 0 1 8 0v3" />
          </svg>
          Sepetim{rozet(count)}
        </button>
      ) : (
        <Link href="/sepet" className={oge}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" className="w-[22px] h-[22px]" aria-hidden>
            <path d="M5 7h14l1 14H4L5 7Z" /><path d="M8 8V5a4 4 0 0 1 8 0v3" />
          </svg>
          Sepetim{rozet(count)}
        </Link>
      )}
    </nav>
  );
}
