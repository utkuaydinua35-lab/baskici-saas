"use client";

// Akış çizgisi (Füzyon) — anasayfada kaydırdıkça çizilen renkli, halkalı
// kurdele. Rota CANLI yerleşime bağlıdır: sayfadaki geçiş boşluklarını
// ([data-akis-gecis]) ve footer'ı ölçer; ilk boşlukta soldan girer, sağ
// kenardan iner, her boşlukta karşı kenara geçer, footer'da biter. Kaydırma
// yalnız ÇİZİLEN UZUNLUĞU değiştirir (stroke-dasharray).
//
// Akıcılık:
//  • Katman kendi GPU katmanında (will-change) — çizgi değişince sayfa
//    içeriği yeniden boyanmaz; pointer-events yok, tıklamayı engellemez.
//  • Kaydırmada yalnız hedef hesaplanır; çizim karede bir kez, hedefe
//    varınca rAF DURUR (boşta döngü yok). Sekme gizliyken döngü kesilir.
//  • Ölçüm yalnız boyut değişince (ResizeObserver, yazı tipi, yükleme).
//  • Hareket azaltma tercihinde çizgi tam çizili durur, animasyon yok.
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

type N = [number, number];

export default function AkisCizgisi() {
  const katman = useRef<HTMLDivElement>(null);
  const svg = useRef<SVGSVGElement>(null);
  // Katman body'ye taşınır: sayfa geçişindeki transform'lu sarmalayıcı
  // konum kökü olsaydı çizgi header yüksekliği kadar kayardı.
  const [hazir, setHazir] = useState(false);
  useEffect(() => setHazir(true), []);

  useEffect(() => {
    if (!hazir) return;
    const layer = katman.current, svgEl = svg.current;
    if (!layer || !svgEl) return;
    const paths = [...svgEl.querySelectorAll<SVGPathElement>("path")];
    const govde = paths[2];
    const hareket = matchMedia("(prefers-reduced-motion: reduce)");
    let length = 0, drawn = 0, target = 0, raf = 0, olcKare = 0, entryY = 0, endY = 0, lastTime = 0;
    let samples: { y: number; l: number }[] = [];

    const footer = () => document.querySelector<HTMLElement>(".vitrin-footer");
    const gecisler = () => [...document.querySelectorAll<HTMLElement>("[data-akis-gecis]")];
    const orta = (el: HTMLElement) => { const r = el.getBoundingClientRect(); return r.top + scrollY + r.height / 2; };
    const uygula = (n: number) => {
      const d = `${n.toFixed(2)} ${(length + 2).toFixed(2)}`;
      for (const p of paths) p.style.strokeDasharray = d;
    };
    const hedefUzunluk = () => {
      if (!samples.length) return 0;
      const dipte = scrollY + innerHeight >= document.documentElement.scrollHeight - 8;
      const y = dipte ? endY : scrollY + innerHeight * 0.76;
      if (y < entryY - 30) return 0;
      if (y >= endY) return length;
      let lo = 0, hi = samples.length - 1;
      while (lo < hi) { const m = (lo + hi) >> 1; if (samples[m].y < y) lo = m + 1; else hi = m; }
      return samples[lo].l;
    };
    const tik = (t: number) => {
      raf = 0;
      const dt = lastTime ? Math.min(t - lastTime, 48) : 16;
      lastTime = t;
      if (hareket.matches) { drawn = length; uygula(drawn); return; }
      drawn += (target - drawn) * (1 - Math.exp(-dt / 85));
      if (Math.abs(target - drawn) < 0.4) drawn = target;
      uygula(drawn);
      if (drawn !== target) raf = requestAnimationFrame(tik);
    };
    const guncelle = () => {
      target = hedefUzunluk();
      if (hareket.matches) { drawn = length; uygula(length); return; }
      if (!raf && !document.hidden) { lastTime = 0; raf = requestAnimationFrame(tik); }
    };

    const olc = () => {
      olcKare = 0;
      const f = footer();
      const gs = gecisler();
      if (!f || gs.length === 0) { layer.style.height = "0px"; return; }
      const w = document.documentElement.clientWidth;
      const h = Math.ceil(f.getBoundingClientRect().bottom + scrollY);
      const kucuk = w <= 760;
      const left = kucuk ? Math.max(7, w * 0.02) : Math.max(22, w * 0.019), right = w - left;
      const ys = gs.map(orta);
      entryY = ys[0];
      endY = f.getBoundingClientRect().bottom + scrollY - 16;
      const R = kucuk ? 34 : 64, lb = kucuk ? 19 : 36, cb = kucuk ? 21 : 40;
      const db = kucuk ? 0 : Math.min(38, Math.max(18, left * 0.95));
      const amp = kucuk ? 5 : 19, lam = kucuk ? 210 : 300;
      const E = entryY;
      const P: N[] = [[-40, E]];
      let cur: N = P[0];
      const add = (x: number, y: number) => { cur = [x, y]; P.push(cur); };
      // Kübik Bezier köşe (20 örnek)
      const corner = (p1: N, p2: N, to: N) => {
        const p0 = cur;
        for (let k = 1; k <= 20; k++) {
          const t = k / 20, u = 1 - t;
          add(u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * to[0],
            u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * to[1]);
        }
      };
      // Düz koşu: hafif dalga + istenen yerlerde tam halka (b = halka yarıçapı)
      const run = (to: N, pull: N, b: number, loops: number[], wave: number) => {
        const [x0, y0] = cur, dx = to[0] - x0, dy = to[1] - y0, D = Math.hypot(dx, dy);
        if (D < 1) return;
        const ux = dx / D, uy = dy / D, la = b * 0.3, Lp = 2 * Math.PI * la;
        const at = (q: number, o: number) => add(x0 + ux * q + pull[0] * o, y0 + uy * q + pull[1] * o);
        const straight = (sa: number, sb: number) => {
          const len = sb - sa, ok = wave && len > lam * 0.6;
          for (let q = sa + 6; q < sb; q += 6) {
            let o = 0;
            if (ok) { const e = Math.sin(Math.PI * (q - sa) / len); o = wave * Math.sin(2 * Math.PI * (q - sa) / lam) * e * e; }
            at(q, o);
          }
          at(sb, 0);
        };
        let q = 0;
        const starts = b ? loops.map((t) => t * D - Lp / 2).filter((v) => v > R && v + Lp < D - R) : [];
        for (const s0 of starts) {
          straight(q, s0);
          for (let k = 1; k <= 64; k++) {
            const t = Math.PI + (k / 64) * 2 * Math.PI;
            at(s0 + la * (t - Math.PI) - b * Math.sin(t), b * (1 + Math.cos(t)));
          }
          q = s0 + Lp;
        }
        straight(q, D);
      };
      // Uzun dikey inişte her ~750 px'de bir halka
      const dl = (a: number, b: number) => {
        const n = Math.floor((b - a) / 750);
        return Array.from({ length: n }, (_, k) => (k + 0.5) / n);
      };

      // Giriş: soldan sağ kenara, köşeden aşağı
      run([right - R, E], [0, -1], lb, [0.38], amp * 0.7);
      corner([right - R * 0.45, E], [right, E + R * 0.55], [right, E + R]);
      let sagda = true, yBas = E + R;
      for (const y of ys.slice(1)) {
        if (y - R <= yBas + 10) continue;   // üst üste binen boşluk: atla
        const xs = sagda ? right : left, xo = sagda ? left : right, yon = sagda ? -1 : 1;
        run([xs, y - R], [yon, 0], db, dl(yBas, y - R), amp);
        corner([xs, y - R * 0.45], [xs + yon * R * 0.55, y], [xs + yon * R, y]);
        run([xo - yon * R, y], [0, -1], cb, [0.5], amp * 0.7);
        corner([xo - yon * R * 0.45, y], [xo, y + R * 0.55], [xo, y + R]);
        sagda = !sagda; yBas = y + R;
      }
      run([sagda ? right : left, endY], [sagda ? -1 : 1, 0], 0, [], amp);
      const d = "M " + P.map((p) => `${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(" L ");

      layer.style.height = `${h}px`;
      svgEl.setAttribute("viewBox", `0 0 ${w} ${h}`);
      for (const p of paths) p.setAttribute("d", d);
      for (const id of ["akisPigment", "akisGolge"]) {
        const g = svgEl.querySelector(`#${id}`);
        g?.setAttribute("y1", String(entryY));
        g?.setAttribute("y2", String(endY));
      }
      length = govde.getTotalLength();
      samples = [];
      let maxY = -Infinity;
      for (let i = 0; i <= 650; i++) {
        const l = (length * i) / 650, pt = govde.getPointAtLength(l);
        maxY = Math.max(maxY, pt.y);
        samples.push({ y: maxY, l });
      }
      layer.classList.add("hazir");
      drawn = Math.min(Math.max(drawn, 0), length);
      guncelle();
    };
    const olcSirala = () => { if (!olcKare) olcKare = requestAnimationFrame(olc); };
    const gorunurluk = () => {
      if (document.hidden && raf) { cancelAnimationFrame(raf); raf = 0; } else guncelle();
    };

    addEventListener("scroll", guncelle, { passive: true });
    addEventListener("resize", olcSirala, { passive: true });
    addEventListener("load", olcSirala, { once: true });
    document.addEventListener("visibilitychange", gorunurluk);
    hareket.addEventListener("change", guncelle);
    document.fonts?.ready.then(olcSirala).catch(() => {});
    const ro = new ResizeObserver(olcSirala);
    const main = document.querySelector("main");
    if (main) ro.observe(main);
    const f = footer();
    if (f) ro.observe(f);
    olcSirala();
    return () => {
      removeEventListener("scroll", guncelle);
      removeEventListener("resize", olcSirala);
      removeEventListener("load", olcSirala);
      document.removeEventListener("visibilitychange", gorunurluk);
      hareket.removeEventListener("change", guncelle);
      ro.disconnect();
      if (raf) cancelAnimationFrame(raf);
      if (olcKare) cancelAnimationFrame(olcKare);
    };
  }, [hazir]);

  if (!hazir) return null;
  return createPortal(
    <div ref={katman} className="akis-katman" aria-hidden="true">
      <svg ref={svg} xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none" focusable="false">
        <defs>
          <linearGradient id="akisPigment" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2="4000">
            <stop offset="0" stopColor="#edf83d" /><stop offset=".2" stopColor="#ffdc6a" />
            <stop offset=".42" stopColor="#efa5c8" /><stop offset=".68" stopColor="#b3a1ef" />
            <stop offset="1" stopColor="#5368f0" />
          </linearGradient>
          <linearGradient id="akisGolge" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2="4000">
            <stop offset="0" stopColor="#bac42c" /><stop offset=".24" stopColor="#d8a654" />
            <stop offset=".45" stopColor="#bb7599" /><stop offset=".7" stopColor="#8774c6" />
            <stop offset="1" stopColor="#3448af" />
          </linearGradient>
        </defs>
        <g fill="none" strokeLinecap="round" strokeLinejoin="round">
          <path className="akis-yol akis-golge" />
          <path className="akis-yol akis-kenar" stroke="url(#akisGolge)" />
          <path className="akis-yol akis-govde" stroke="url(#akisPigment)" />
          <path className="akis-yol akis-isilti" />
        </g>
      </svg>
    </div>,
    document.body,
  );
}
