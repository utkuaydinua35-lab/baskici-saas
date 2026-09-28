// Çapraz kurdeleler (Füzyon) — üç eğik şerit, zıt yönlerde sürekli akar.
// Tamamen CSS: her şerit kendi katmanında transform ile kayar (GPU), JS yok.
// İçerik iki kez basılır, yarısı kadar kayar → dikişsiz döngü. Ekran
// dışındayken tarayıcı katmanı boyamaz; hareket azaltma tercihinde durur.
//  palet neon: sarı ön şerit + pembe-lila şerit + açık gri arka şerit
//  palet tema: temanın ana rengi + vurgu rengi
export default function Kurdele({
  items = [],
  sembol = "✦",
  palet = "neon",
}: {
  items?: { text?: string; buyuk?: boolean }[];
  sembol?: string;
  palet?: "neon" | "tema";
}) {
  const liste = items.filter((i) => i.text);
  if (liste.length === 0) return null;
  // Kısa listede yarım şerit ekranı doldursun
  const tekrar = Math.max(1, Math.ceil(6 / liste.length));
  const yarim = Array.from({ length: tekrar }, () => liste).flat();

  const grup = (gizli: boolean) => (
    <div className="kurdele-grup" aria-hidden={gizli || undefined}>
      {yarim.map((i, k) => (
        <span key={k} className="contents">
          <span className={`kurdele-yazi${i.buyuk ? " buyuk" : ""}`}>{i.text}</span>
          <span className="kurdele-sembol" aria-hidden>{sembol}</span>
        </span>
      ))}
    </div>
  );
  const serit = (sinif: string) => (
    <div className={`kurdele ${sinif}`} aria-hidden="true">
      <div className="kurdele-iz">{grup(false)}{grup(true)}</div>
    </div>
  );

  return (
    <section className={`kurdele-sahne palet-${palet}`}
      aria-label={liste.map((i) => i.text).join(", ")}>
      {serit("kurdele-arka")}
      {serit("kurdele-on")}
      {serit("kurdele-alt")}
    </section>
  );
}
