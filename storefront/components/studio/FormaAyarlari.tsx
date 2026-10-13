"use client";

// Forma tasarlayıcı kontrolleri — kısıtlı şablon formunun içinde görünür.
// Müşteri desen, renk, yazı tipi ve amblem seçer; yerleşim şablonda kilitlidir.
// Seçimler alanDegerleri'nde `_…` anahtarlarıyla tutulur (bkz. forma.ts);
// sunucu kaydederken hepsini şablonun izin verdikleriyle yeniden doğrular.
import { fontByKey } from "./fonts";
import { UC_RENKLI, YOGUNLUKSUZ, desenSekilleri, formaSecimi } from "./forma";
import { basilabilirRenk } from "./renk";
import type { StudioOverlay } from "./types";

const YOGUNLUK_AD: Record<string, string> = { ince: "İnce", orta: "Orta", kalin: "Kalın" };
const RENK_AD = ["Zemin", "Desen", "Çizgi"];

function DesenOnizleme({ desen, yogunluk, renkler }: { desen: string; yogunluk: string; renkler: string[] }) {
  return (
    <svg viewBox="0 0 1 1" preserveAspectRatio="none" className="w-full h-full block" aria-hidden>
      <rect x="0" y="0" width="1" height="1" fill={renkler[0]} />
      {desenSekilleri(desen, yogunluk).map((c, i) => (
        <polygon key={i} fill={renkler[Math.min(c.renk, 2)]}
          points={c.nokta.map(([x, y]) => `${x},${y}`).join(" ")} />
      ))}
    </svg>
  );
}

function RenkKutusu({ etiket, deger, onDegis }: { etiket: string; deger: string; onDegis: (v: string) => void }) {
  return (
    <label className="flex items-center gap-1.5 text-[11px] text-zinc-600 cursor-pointer">
      <input type="color" value={deger} aria-label={etiket}
        onChange={(e) => onDegis(basilabilirRenk(e.target.value).renk)}
        className="w-7 h-7 rounded-md border border-zinc-300 p-0 bg-transparent cursor-pointer" />
      {etiket}
    </label>
  );
}

export default function FormaAyarlari({ overlay, degerler, onYaz }: {
  overlay: StudioOverlay;
  degerler: Record<string, unknown>;
  /** Bir ya da birden çok `_…` anahtarını birlikte yazar (renk takımı = 3 renk) */
  onYaz: (yama: Record<string, string>) => void;
}) {
  const f = overlay.forma;
  const s = formaSecimi(overlay, degerler);
  if (!f || !s) return null;

  const baslik = "text-xs font-medium text-zinc-700 mb-1.5";
  const secili = (aktif: boolean) =>
    aktif ? "border-zinc-900 ring-1 ring-zinc-900" : "border-zinc-200 hover:border-zinc-400";
  const takimSecili = (r: string[]) => r.every((x, i) => x.toLowerCase() === s.renkler[i].toLowerCase());

  return (
    <div className="space-y-3.5 border-t border-zinc-200 pt-3">
      {f.paletler.length > 0 && (
        <div>
          <div className={baslik}>Renk takımı</div>
          <div className="flex flex-wrap gap-1.5">
            {f.paletler.map((p) => (
              <button key={p.ad} type="button" title={p.ad} aria-pressed={takimSecili(p.renkler)}
                onClick={() => onYaz({ _renk1: p.renkler[0], _renk2: p.renkler[1], _renk3: p.renkler[2] })}
                className={`flex items-center gap-1.5 rounded-full border pl-1 pr-2.5 py-1 text-[11px] ${secili(takimSecili(p.renkler))}`}>
                <span className="flex h-5 w-8 overflow-hidden rounded-full border border-black/10">
                  <span className="flex-1" style={{ background: p.renkler[0] }} />
                  <span className="flex-1" style={{ background: p.renkler[1] }} />
                </span>
                {p.ad}
              </button>
            ))}
          </div>
        </div>
      )}

      {f.serbest_renk && (
        <div>
          <div className={baslik}>Renkler</div>
          <div className="flex flex-wrap gap-x-4 gap-y-1.5">
            {/* Yalnız seçili desenin KULLANDIĞI renkler: tek renkte desen
                rengi, çizgisiz desenlerde üçüncü renk gösterilmez */}
            {[0, 1, 2].filter((i) => i === 0 || (i === 1 && s.desen !== "duz")
              || (i === 2 && UC_RENKLI.has(s.desen))).map((i) => (
              <RenkKutusu key={i} etiket={RENK_AD[i]} deger={s.renkler[i]}
                onDegis={(v) => onYaz({ [`_renk${i + 1}`]: v })} />
            ))}
          </div>
        </div>
      )}

      {f.desenler.length > 1 && (
        <div>
          <div className={baslik}>Desen</div>
          <div className="grid grid-cols-5 gap-1.5">
            {f.desenler.map((d) => (
              <button key={d.key} type="button" title={d.ad} aria-label={d.ad}
                aria-pressed={s.desen === d.key} onClick={() => onYaz({ _desen: d.key })}
                className={`aspect-[1/1.6] overflow-hidden rounded-lg border ${secili(s.desen === d.key)}`}>
                <DesenOnizleme desen={d.key} yogunluk={s.yogunluk} renkler={s.renkler} />
              </button>
            ))}
          </div>
          {!YOGUNLUKSUZ.has(s.desen) && (
            <div className="mt-2 flex items-center gap-1.5">
              <span className="text-[11px] text-zinc-500 mr-1">Kalınlık</span>
              {(["ince", "orta", "kalin"] as const).map((y) => (
                <button key={y} type="button" aria-pressed={s.yogunluk === y}
                  onClick={() => onYaz({ _yogunluk: y })}
                  className={`rounded-full border px-2.5 py-1 text-[11px] ${secili(s.yogunluk === y)}`}>
                  {YOGUNLUK_AD[y]}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {f.fontlar.length > 1 && (
        <div>
          <div className={baslik}>Yazı tipi</div>
          <div className="grid grid-cols-4 gap-1.5">
            {f.fontlar.map((k) => {
              const font = fontByKey(k);
              return (
                <button key={k} type="button" title={font.label} aria-label={font.label}
                  aria-pressed={s.font === k} onClick={() => onYaz({ _font: k })}
                  className={`rounded-lg border py-1.5 text-lg leading-none ${secili(s.font === k)}`}
                  style={{ fontFamily: `'${font.css}', sans-serif` }}>
                  10
                </button>
              );
            })}
          </div>
        </div>
      )}

      <div>
        <div className={baslik}>Yazı rengi</div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
          <RenkKutusu etiket="Yazı" deger={s.yazi_renk} onDegis={(v) => onYaz({ _yazi_renk: v })} />
          <label className="flex items-center gap-1.5 text-[11px] text-zinc-600 cursor-pointer">
            <input type="checkbox" checked={!!s.kontur}
              onChange={(e) => onYaz({ _kontur: e.target.checked ? (f.varsayilan.kontur || "#111111") : "" })} />
            Kontur
          </label>
          {s.kontur && (
            <RenkKutusu etiket="Kontur rengi" deger={s.kontur} onDegis={(v) => onYaz({ _kontur: v })} />
          )}
        </div>
      </div>

      {f.amblemler.length > 0 && (
        <div>
          <div className={baslik}>Amblem</div>
          <div className="grid grid-cols-6 gap-1.5">
            <button type="button" aria-pressed={!s.amblem} onClick={() => onYaz({ _amblem: "" })}
              className={`aspect-square rounded-lg border text-[10px] text-zinc-500 ${secili(!s.amblem)}`}>
              Yok
            </button>
            {f.amblemler.map((a) => {
              const maske = `url("${a.url}") center / 70% no-repeat`;
              return (
                <button key={a.key} type="button" title={a.ad} aria-label={a.ad}
                  aria-pressed={s.amblem === a.key} onClick={() => onYaz({ _amblem: a.key })}
                  className={`aspect-square rounded-lg border bg-zinc-100 ${secili(s.amblem === a.key)}`}>
                  <span className="block w-full h-full"
                    style={{ background: "#18181b", WebkitMask: maske, mask: maske }} />
                </button>
              );
            })}
          </div>
          {s.amblem && (
            <div className="mt-2">
              <RenkKutusu etiket="Amblem rengi" deger={s.amblem_renk} onDegis={(v) => onYaz({ _amblem_renk: v })} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
