"use client";

// "Yukarı çık" düğmesi — sayfa bir ekran aşağı kayınca sol altta belirir.
// Sağ alt köşe WhatsApp ve destek balonunun; çakışmasın diye soldadır.
import { useEffect, useState } from "react";

export default function ScrollTopButton() {
  const [gorunur, setGorunur] = useState(false);

  useEffect(() => {
    const olc = () => setGorunur(window.scrollY > window.innerHeight);
    olc();
    window.addEventListener("scroll", olc, { passive: true });
    return () => window.removeEventListener("scroll", olc);
  }, []);

  return (
    <button
      onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
      aria-label="Sayfanın başına dön"
      tabIndex={gorunur ? 0 : -1}
      className={`fixed left-4 bottom-4 z-[60] grid h-11 w-11 place-items-center rounded-full
        bg-white text-zinc-800 shadow-lg border border-zinc-200 transition-all duration-300
        hover:-translate-y-0.5 ${gorunur ? "opacity-100" : "opacity-0 pointer-events-none translate-y-2"}`}
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <polyline points="18 15 12 9 6 15" />
      </svg>
    </button>
  );
}
