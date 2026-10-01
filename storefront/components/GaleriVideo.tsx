"use client";

// Galeri videosu — sessiz, döngülü; YALNIZ ekrandayken oynar. Akan şeritte
// 12 videonun aynı anda çalışması telefonda pili ve veriyi eritirdi.
// Hareket azaltma tercihinde hiç otomatik oynamaz (ilk kare görünür).
import { hareketSorgusu } from "@/lib/hareket";
import { useEffect, useRef } from "react";

export default function GaleriVideo({ src, etiket }: { src: string; etiket?: string }) {
  const ref = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const v = ref.current;
    if (!v) return;
    if (hareketSorgusu().matches) return;
    const io = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) v.play().catch(() => { /* tarayıcı reddederse ilk kare kalır */ });
      else v.pause();
    }, { threshold: 0.35 });
    io.observe(v);
    return () => io.disconnect();
  }, []);

  return (
    <video ref={ref} src={src} muted loop playsInline preload="metadata"
      aria-label={etiket || "Müşteri videosu"}
      className="w-full h-full object-cover" />
  );
}
