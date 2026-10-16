// Slayt gösterisinin üstünde/altında sürekli kayan şerit — telefon markaları,
// "iPhone 17 geldi" gibi duyurular. Tema › Slayt gösterisi › Üst/Alt şerit.
// Duyuru şeridiyle aynı teknik (globals.css .akan-serit): içerik iki kez
// basılır, yarısı kadar kayar → dikişsiz döngü; JS yok, katmanında kayar.
import Link from "next/link";
import type { KayanSeritAyari } from "@/lib/theme";

export default function KayanSerit({ ayar }: { ayar?: KayanSeritAyari }) {
  const ogeler = (ayar?.ogeler || []).filter((o) => o.text);
  if (!ayar?.aktif || ogeler.length === 0) return null;
  // Kısa listede de şerit dolu kalsın: yarım şerit en geniş ekranı doldursun
  const tahmini = ogeler.reduce((t, o) => t + o.text.length * 9 + 64, 0);
  const tekrar = Math.max(1, Math.ceil(2800 / Math.max(1, tahmini)));
  const yarim = Array.from({ length: tekrar }, () => ogeler).flat();
  const parca = (gizli: boolean) => (
    <div className="flex shrink-0 items-center" aria-hidden={gizli || undefined}>
      {yarim.map((o, i) => (
        <span key={i} className="flex items-center">
          {o.link && !gizli ? (
            <Link href={o.link} className="whitespace-nowrap hover:underline underline-offset-4">{o.text}</Link>
          ) : (
            <span className="whitespace-nowrap">{o.text}</span>
          )}
          {ayar.sembol && <span className="mx-6 sm:mx-8 opacity-60 text-[0.7em]" aria-hidden>{ayar.sembol}</span>}
          {!ayar.sembol && <span className="mx-5" aria-hidden />}
        </span>
      ))}
    </div>
  );
  return (
    <div className="akan-kap overflow-hidden py-2.5 text-[13px] sm:text-sm font-semibold uppercase tracking-[0.12em]"
      style={{ background: ayar.zemin, color: ayar.yazi }}
      role="region" aria-label={ogeler.map((o) => o.text).join(", ")}>
      <div className="akan-serit flex w-max"
        style={{ "--akan-sure": `${ayar.hiz}s`,
          animationDirection: ayar.yon === "saga" ? "reverse" : "normal" } as React.CSSProperties}>
        {parca(false)}
        {parca(true)}
      </div>
    </div>
  );
}
