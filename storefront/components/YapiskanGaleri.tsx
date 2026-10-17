"use client";

// Ürün sayfası: masaüstünde sağ sütun kaydırılırken galeri sabit kalır.
// Üst menü de sabitse (mağaza ayarı + ekran genişliğine göre değişir) galeri
// onun altında durur — menü yüksekliği ölçülür, sabit bir değer varsayılmaz.
import { useEffect, useState, type ReactNode } from "react";

export default function YapiskanGaleri({ children }: { children: ReactNode }) {
  const [ust, setUst] = useState(16);

  useEffect(() => {
    const header = document.querySelector("header");
    if (!header) return;
    const olc = () => {
      const p = getComputedStyle(header).position;
      setUst((p === "sticky" || p === "fixed" ? header.getBoundingClientRect().height : 0) + 16);
    };
    olc();
    const ro = new ResizeObserver(olc);
    ro.observe(header);
    window.addEventListener("resize", olc);
    return () => { ro.disconnect(); window.removeEventListener("resize", olc); };
  }, []);

  return (
    <div className="md:sticky md:self-start" style={{ top: ust }}>
      {children}
    </div>
  );
}
