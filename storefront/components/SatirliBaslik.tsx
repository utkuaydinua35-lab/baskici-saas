"use client";

// Satır satır açılan başlık (Füzyon tasarımındaki "split-line"). Metin "\n"
// ile satırlara bölünür; her satır kendi taşma kutusunda aşağıdan yükselir,
// satırlar arası .12 sn. Ekrana %30 girince bir kez oynar (IntersectionObserver).
// italikAlt: ilk satırdan sonrakiler <em> (italik, gri) — serif başlık kalıbı.
// Görünüm CSS'te yalnız editoryal başlık stilinde etkin; diğer temalarda
// satırlar düz metin gibi akar.
import { hareketSorgusu } from "@/lib/hareket";
import { createElement, useEffect, useRef, useState } from "react";

export default function SatirliBaslik({
  metin,
  as = "h2",
  className = "",
  italikAlt = false,
  italikSinif = "text-zinc-500",
}: {
  metin: string;
  as?: "h1" | "h2" | "h3";
  className?: string;
  italikAlt?: boolean;
  // İtalik satırın rengi (koyu panolarda açık gri)
  italikSinif?: string;
}) {
  const ref = useRef<HTMLHeadingElement>(null);
  const [acik, setAcik] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (!("IntersectionObserver" in window) || hareketSorgusu().matches) {
      setAcik(true);
      return;
    }
    const io = new IntersectionObserver((es) => {
      if (es[0]?.isIntersecting) { setAcik(true); io.disconnect(); }
    }, { threshold: 0.3 });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  const satirlar = metin.split("\n").filter((s, i) => s || i === 0);
  const cocuklar = satirlar.map((s, i) => {
    const ic = <span style={i ? { transitionDelay: `${i * 0.12}s` } : undefined}>{s}</span>;
    return i > 0 && italikAlt
      ? <em key={i} className={`satir italik-satir italic ${italikSinif}`}>{ic}</em>
      : <span key={i} className="satir">{i > 0 ? " " : ""}{ic}</span>;
  });
  return createElement(as, { ref, className: `satirli ${acik ? "satir-in" : ""} ${className}` }, cocuklar);
}
