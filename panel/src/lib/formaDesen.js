// Forma deseni — panel önizlemesi için. BU DOSYA BİR KOPYADIR:
//   backend/app/services/forma.py            → desen_sekilleri   (baskı, asıl)
//   storefront/components/studio/forma.ts    → desenSekilleri    (tuval + önizleme)
//   panel/src/lib/formaDesen.js              → desenSekilleri    (bu dosya)
// Birini değiştirirsen üçünü de değiştir.

const yuvarla = (n) => Math.round(n * 1e6) / 1e6;

/** Desen → çokgenler, birim karede (0-1). Zemin HER ZAMAN renk 0'dır;
 *  buradakiler onun üstüne çizilir. */
export function desenSekilleri(desen, yogunluk = "orta") {
  const y = yogunluk === "ince" ? 0 : yogunluk === "kalin" ? 2 : 1;
  const s = [];
  const kutu = (renk, x0, y0, x1, y1) =>
    s.push({ renk, nokta: [[x0, y0], [x1, y0], [x1, y1], [x0, y1]] });

  if (desen === "dikey") {
    const n = [11, 7, 5][y];
    for (let i = 1; i < n; i += 2) kutu(1, i / n, 0, (i + 1) / n, 1);
  } else if (desen === "yatay") {
    const n = [17, 11, 7][y];
    for (let i = 1; i < n; i += 2) kutu(1, 0, i / n, 1, (i + 1) / n);
  } else if (desen === "capraz") {
    const n = [9, 6, 4][y];
    const g = 1 / n;
    for (let i = -n; i <= n; i++) {
      const x0 = i * g;
      s.push({ renk: 1, nokta: [[x0, 0], [x0 + g / 2, 0], [x0 + g / 2 + 1, 1], [x0 + 1, 1]] });
    }
  } else if (desen === "yari") {
    kutu(1, 0.5, 0, 1, 1);
  } else if (desen === "kareli") {
    const sutun = [6, 4, 2][y];
    const satir = sutun * 2;
    for (let r = 0; r < satir; r++) {
      for (let c = 0; c < sutun; c++) {
        if ((r + c) % 2 === 1) kutu(1, c / sutun, r / satir, (c + 1) / sutun, (r + 1) / satir);
      }
    }
  } else if (desen === "bant") {
    const h = [0.10, 0.16, 0.24][y];
    const ust = 0.50 - h / 2;
    kutu(1, 0, ust, 1, ust + h);
    kutu(2, 0, ust - 0.012, 1, ust);
    kutu(2, 0, ust + h, 1, ust + h + 0.012);
  } else if (desen === "orta_serit") {
    const w = [0.18, 0.30, 0.44][y];
    const sol = 0.5 - w / 2;
    kutu(1, sol, 0, sol + w, 1);
    kutu(2, sol - 0.024, 0, sol, 1);
    kutu(2, sol + w, 0, sol + w + 0.024, 1);
  } else if (desen === "capraz_bant") {
    const w = [0.16, 0.26, 0.38][y];
    s.push({ renk: 2, nokta: [[-w / 2 - 0.03, 0], [w / 2 + 0.03, 0], [1 + w / 2 + 0.03, 1], [1 - w / 2 - 0.03, 1]] });
    s.push({ renk: 1, nokta: [[-w / 2, 0], [w / 2, 0], [1 + w / 2, 1], [1 - w / 2, 1]] });
  }
  return s.map((c) => ({
    renk: c.renk, nokta: c.nokta.map(([px, py]) => [yuvarla(px), yuvarla(py)]),
  }));
}

export const UC_RENKLI = new Set(["bant", "orta_serit", "capraz_bant"]);
export const YOGUNLUKSUZ = new Set(["duz", "yari"]);
