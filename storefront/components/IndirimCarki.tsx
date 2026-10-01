"use client";

// İndirim çarkı — Tema → Kampanya araçları (eskiden "Özel Kod → Hazır ekle"
// ile ham kod olarak eklenen parçacığın yerine).
//  • gecikmeSn sonra belirir; ekranda başka pencere (açılış pop-up'ı vb.)
//    açıksa o kapanana kadar bekler — üst üste binmez.
//  • Kazanan dilim eşit olasılıkla seçilir; kuponlu dilimde kod + "Sepette
//    kullan" (/sepet?kupon=…), kuponsuz dilimde "Bu sefer olmadı".
//  • "Gördüm" kaydı eski parçacıkla AYNI anahtarda (bz_wheel_seen): koddan
//    ayara geçen mağazada çarkı görmüş ziyaretçiye tekrar çıkmaz.
//  • Tema editörü önizlemesinde kendiliğinden açılmaz; editör "Önizlemede
//    göster" deyince açılır, iz bırakmaz.
import KuponKodu from "@/components/KuponKodu";
import { useEffect, useRef, useState } from "react";

interface Dilim { yazi: string; kod: string }
const ANAHTAR = "bz_wheel_seen";
const GUN = 864e5;
const RENKLER = ["var(--c-primary)", "var(--c-accent)", "#0f766e", "#b45309", "#4338ca", "#be185d", "#334155", "#15803d"];

function baskaPencereAcik() {
  return !!document.querySelector('[role="dialog"][aria-modal="true"]:not([data-cark])');
}

export default function IndirimCarki({
  onizleme, baslik, metin, buton, gecikmeSn, tekrarGun, dilimler,
}: {
  onizleme?: boolean; baslik: string; metin?: string; buton: string;
  gecikmeSn: number; tekrarGun: number; dilimler: Dilim[];
}) {
  const [acik, setAcik] = useState(false);
  const [aci, setAci] = useState(0);
  const [sonuc, setSonuc] = useState<Dilim | null>(null);
  const [donuyor, setDonuyor] = useState(false);
  const zamanlayici = useRef<ReturnType<typeof setTimeout> | null>(null);
  const kuponVar = dilimler.some((d) => d.kod);

  const kaydet = (ms: number) => {
    if (onizleme) return;
    try { localStorage.setItem(ANAHTAR, String(ms)); } catch { /* yok */ }
  };

  useEffect(() => {
    if (!onizleme) return;
    const dinle = (e: MessageEvent) => {
      if (e.source === window.parent && e.data?.type === "vitrin-cark-onizle") {
        setSonuc(null); setAci(0); setDonuyor(false); setAcik(true);
      }
    };
    window.addEventListener("message", dinle);
    return () => window.removeEventListener("message", dinle);
  }, [onizleme]);

  useEffect(() => {
    if (onizleme || !kuponVar) return;
    try {
      const son = Number(localStorage.getItem(ANAHTAR) || 0);
      if (son && Date.now() - son < tekrarGun * GUN) return;
    } catch { /* yok */ }
    const dene = () => {
      if (baskaPencereAcik()) { zamanlayici.current = setTimeout(dene, 2000); return; }
      setAcik(true);
    };
    zamanlayici.current = setTimeout(dene, gecikmeSn * 1000);
    return () => { if (zamanlayici.current) clearTimeout(zamanlayici.current); };
  }, [onizleme, kuponVar, gecikmeSn, tekrarGun]);

  if (!acik) return null;

  const n = dilimler.length;
  const dilimAci = 360 / n;
  const kapat = () => { setAcik(false); kaydet(Date.now()); };

  const cevir = () => {
    if (donuyor || sonuc) return;
    setDonuyor(true);
    const i = Math.floor(Math.random() * n);
    // i. dilimin ortası üstteki işaretin altına gelsin (+6 tam tur)
    setAci(360 * 6 + (360 - (i * dilimAci + dilimAci / 2)));
    setTimeout(() => {
      const d = dilimler[i];
      setSonuc(d);
      setDonuyor(false);
      // Kazanan tekrar tekrarGun görmez; kazanamayan yarın tekrar denesin
      kaydet(d.kod ? Date.now() : Date.now() - (tekrarGun - 1) * GUN);
    }, 4600);
  };

  const R = 130;
  const nokta = (derece: number, r = R) => {
    const rad = ((derece - 90) * Math.PI) / 180;
    return [R + r * Math.cos(rad), R + r * Math.sin(rad)];
  };

  return (
    <div role="dialog" aria-modal="true" aria-label={baslik} data-cark
      onMouseDown={(e) => e.target === e.currentTarget && kapat()}
      className="fixed inset-0 z-[125] flex items-center justify-center bg-black/55 p-4 popup-perde">
      <div className="popup-kart relative w-full max-w-[340px] rounded-3xl bg-white p-6 text-center shadow-2xl">
        <button onClick={kapat} aria-label="Kapat"
          className="absolute right-3 top-3 grid h-8 w-8 place-items-center rounded-full bg-zinc-100 text-zinc-600 hover:bg-zinc-200">✕</button>
        <h2 className="text-xl font-bold">{baslik}</h2>
        {metin ? <p className="mt-1 text-sm text-zinc-500">{metin}</p> : null}

        <div className="relative mx-auto mt-4 w-[260px] max-w-full">
          <div aria-hidden className="absolute left-1/2 -top-1.5 z-10 -translate-x-1/2 h-0 w-0
            border-x-[9px] border-t-[17px] border-x-transparent border-t-zinc-900" />
          <svg viewBox="0 0 260 260" className="w-full"
            style={{ transform: `rotate(${aci}deg)`, transition: "transform 4.5s cubic-bezier(.17,.67,.12,1)" }}>
            {dilimler.map((d, i) => {
              const [x1, y1] = nokta(i * dilimAci);
              const [x2, y2] = nokta((i + 1) * dilimAci);
              const orta = i * dilimAci + dilimAci / 2;
              return (
                <g key={i}>
                  <path d={`M${R},${R} L${x1},${y1} A${R},${R} 0 ${dilimAci > 180 ? 1 : 0},1 ${x2},${y2} Z`}
                    style={{ fill: RENKLER[i % RENKLER.length] }} />
                  {/* Yazı yarıçap boyunca, kenara yaslı. Sol yarıda 180° çevrilir:
                      yoksa soldaki dilimlerin yazısı tersten okunur. */}
                  <text x={orta > 180 ? 14 : 2 * R - 14} y={R + 4} fill="#fff" fontSize="11" fontWeight="700"
                    textAnchor={orta > 180 ? "start" : "end"}
                    transform={`rotate(${orta - 90 + (orta > 180 ? 180 : 0)} ${R} ${R})`}>{d.yazi}</text>
                </g>
              );
            })}
          </svg>
        </div>

        {sonuc ? (
          <div className="mt-4" aria-live="polite">
            {sonuc.kod ? (
              <>
                <p className="font-semibold">{sonuc.yazi} kazandın! 🎉</p>
                <KuponKodu kod={sonuc.kod} />
                <a href={`/sepet?kupon=${encodeURIComponent(sonuc.kod)}`}
                  className="btn-r mt-3 block w-full py-3 text-sm font-semibold text-white"
                  style={{ background: "var(--c-primary)" }}>Sepette kullan</a>
              </>
            ) : (
              <p className="font-medium text-zinc-600">Bu sefer olmadı 😊 Yarın tekrar dene!</p>
            )}
          </div>
        ) : (
          <button onClick={cevir} disabled={donuyor}
            className="btn-r mt-4 w-full py-3 font-semibold text-white disabled:opacity-60"
            style={{ background: "var(--c-primary)" }}>
            {donuyor ? "Dönüyor…" : buton}
          </button>
        )}
      </div>
    </div>
  );
}
