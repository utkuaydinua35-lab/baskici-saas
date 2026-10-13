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
  // Açık zeminde (ör. #f1f1f1) beyaz yazı okunmaz → koyu yazı
  const yaziRengi = acikMi(bg) ? "text-zinc-900" : "text-white";

  if (kayan) {
    // Şerit HER ZAMAN dolu: duyurular eşit aralıkla art arda dizilir ve
    // bir "yarı", en geniş ekranı da dolduracak kadar tekrarlanır.
    // Eskiden yarı "ekran genişliği kadar" yapılıp öğeler aralara YAYILIYORDU
    // (justify-around): kısa listede duyurular arasında uzun boşluk kalıyordu.
    const tahminiPx = liste.reduce((t, d) => t + d.text.length * 7.5 + 64, 0);
    const tekrar = Math.max(1, Math.ceil(2800 / Math.max(1, tahminiPx)));
    const yarim = Array.from({ length: tekrar }, () => liste).flat();
    // Hız sabit (~45 px/sn): liste uzadıkça süre uzar, akış hızlanmaz
    const sure = `${Math.max(20, Math.round((tahminiPx * tekrar) / 45))}s`;
    const parca = (gizli: boolean) => (
      <div className="flex shrink-0 items-center" aria-hidden={gizli || undefined}>
        {yarim.map((d, i) => (
          <span key={i} className="flex items-center">
            {yazi(d, `${gizli ? "g" : "a"}${i}`, gizli)}
            <span className="mx-5 sm:mx-7 text-[10px] opacity-60" aria-hidden>✦</span>
          </span>
        ))}
      </div>
    );
    return (
      <div className={`akan-kap overflow-hidden py-2 ${yaziRengi}`} style={zemin}
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
    <div className={`text-center py-2 px-4 ${yaziRengi}`} style={zemin} role="region" aria-label="Duyuru">
      <div key={sira} className="duyuru-gecis">{yazi(d, "d")}</div>
    </div>
  );
}

// #rrggbb algısal parlaklığı yüksekse açık zemin say
function acikMi(renk?: string): boolean {
  const m = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(renk || "");
  if (!m) return false;
  const [r, g, b] = m.slice(1).map((h) => parseInt(h, 16));
  return 0.299 * r + 0.587 * g + 0.114 * b > 170;
}
