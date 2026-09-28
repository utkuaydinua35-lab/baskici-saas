"use client";

// "Animasyonları durdur / oynat" — ziyaretçinin tercihi (tarayıcıda saklanır).
// <html class="hareketsiz"> tüm CSS animasyonlarını dondurur; akış çizgisi
// tam çizili durur, yorum şeridi akmaz (globals.css, AkisCizgisi, YorumSeridi).
import { useEffect, useState } from "react";

const ANAHTAR = "vitrin_hareketsiz";

export default function HareketDugmesi() {
  const [durgun, setDurgun] = useState(false);
  useEffect(() => {
    let v = false;
    try { v = localStorage.getItem(ANAHTAR) === "1"; } catch { /* gizli sekme */ }
    setDurgun(v);
    document.documentElement.classList.toggle("hareketsiz", v);
  }, []);
  const degistir = () => {
    const v = !durgun;
    setDurgun(v);
    document.documentElement.classList.toggle("hareketsiz", v);
    try { localStorage.setItem(ANAHTAR, v ? "1" : "0"); } catch { /* gizli sekme */ }
  };
  return (
    <button type="button" onClick={degistir} aria-pressed={durgun}
      className="underline underline-offset-4 hover:text-zinc-900">
      {durgun ? "Animasyonları oynat" : "Animasyonları durdur"}
    </button>
  );
}
