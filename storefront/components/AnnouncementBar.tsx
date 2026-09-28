"use client";

// Duyuru şeridi — tema ayarından (announcement). Birden fazla duyuru olabilir
// ("3 AL 2 ÖDE!", "950 TL ÜZERİ ÜCRETSİZ KARGO!").
//  kayan: duyurular araya ✦ konarak SÜREKLİ akar (üstüne gelince durur).
//         Her yarı en az ekran genişliğinde → geniş ekranda boşluk kalmaz.
//  kayan değil: duyurular 4 sn'de bir sırayla değişir (tek duyuru sabit durur).
import { useEffect, useState } from "react";

interface Duyuru { text: string; url?: string }

export default function AnnouncementBar({
  items,
  kayan = true,
  bg,
}: {
  items: Duyuru[];
  kayan?: boolean;
  // #rrggbb (backend doğrular); boşsa temanın ana rengi
  bg?: string;
}) {
  const liste = items.filter((d) => d.text);
  const [sira, setSira] = useState(0);

  useEffect(() => {
    if (kayan || liste.length < 2) return;
    const t = setInterval(() => setSira((i) => (i + 1) % liste.length), 4000);
    return () => clearInterval(t);
  }, [kayan, liste.length]);

  if (liste.length === 0) return null;

  const yazi = (d: Duyuru, anahtar: string, gizli = false) => {
    const ic = <span className="text-xs font-medium tracking-wide whitespace-nowrap">{d.text}</span>;
    return d.url && !gizli
      ? <a key={anahtar} href={d.url} className="hover:underline">{ic}</a>
      : <span key={anahtar}>{ic}</span>;
  };

  const zemin = { background: bg || "var(--c-primary)" };

  if (kayan) {
    // Kısa listede yarıyı dolduracak kadar tekrarla
    const tekrar = Math.max(1, Math.ceil(6 / liste.length));
    const yarim = Array.from({ length: tekrar }, () => liste).flat();
    const harf = yarim.reduce((t, d) => t + d.text.length, 0);
    const sure = `${Math.max(18, Math.round(harf * 0.28))}s`;
    const parca = (gizli: boolean) => (
      <div className="flex shrink-0 min-w-full items-center justify-around gap-10 px-5"
        aria-hidden={gizli || undefined}>
        {yarim.map((d, i) => (
          <span key={i} className="flex items-center gap-10">
            {yazi(d, `${gizli ? "g" : "a"}${i}`, gizli)}
            <span className="text-[10px] opacity-60" aria-hidden>✦</span>
          </span>
        ))}
      </div>
    );
    return (
      <div className="akan-kap overflow-hidden py-2 text-white" style={zemin}
        role="region" aria-label="Duyurular">
        <div className="akan-serit flex w-max" style={{ "--akan-sure": sure } as React.CSSProperties}>
          {parca(false)}
          {parca(true)}
        </div>
      </div>
    );
  }

  const d = liste[sira % liste.length];
  return (
    <div className="text-center py-2 px-4 text-white" style={zemin} role="region" aria-label="Duyuru">
      <div key={sira} className="duyuru-gecis">{yazi(d, "d")}</div>
    </div>
  );
}
