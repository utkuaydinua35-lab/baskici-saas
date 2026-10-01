// Sepete uçan görsel (Füzyon, tema animations.sepete_ucus) — sepete ekleyince
// ürün görselinin küçük kopyası kavis çizerek sepet simgesine uçar; iş bitince
// `bitince` çağrılır (ör. sepet çekmecesi o zaman açılır). Yalnız Web
// Animations API + transform/opacity (GPU). Kapalıysa, hareket azaltma
// tercihinde ya da hedef bulunamazsa hiç beklemeden bitince() çalışır.
import { hareketSorgusu } from "@/lib/hareket";

export function sepeteUcur(kaynak: HTMLImageElement | null, bitince: () => void) {
  const html = document.documentElement;
  if (!kaynak || html.dataset.ucus !== "1" || html.classList.contains("hareketsiz")
    || hareketSorgusu().matches) { bitince(); return; }
  const r = kaynak.getBoundingClientRect();
  // Görünür sepet simgesi: telefonda alt çubuk, değilse üst menü
  const hedef = [...document.querySelectorAll<HTMLElement>("[data-sepet-hedef]")]
    .map((el) => ({ tur: el.dataset.sepetHedef, b: el.getBoundingClientRect() }))
    .filter(({ b }) => b.width && b.bottom > 0 && b.top < innerHeight)
    .sort((a) => (a.tur === "dock" ? -1 : 1))[0]?.b;
  if (!r.width || !hedef) { bitince(); return; }
  const boy = Math.min(140, r.width, r.height);
  const x0 = r.left + r.width / 2 - boy / 2, y0 = r.top + r.height / 2 - boy / 2;
  const kopya = document.createElement("img");
  kopya.src = kaynak.currentSrc || kaynak.src;
  kopya.alt = "";
  kopya.className = "ucan-gorsel";
  Object.assign(kopya.style, { left: `${x0}px`, top: `${y0}px`, width: `${boy}px`, height: `${boy}px` });
  document.body.append(kopya);
  const dx = hedef.left + hedef.width / 2 - (x0 + boy / 2), dy = hedef.top + hedef.height / 2 - (y0 + boy / 2);
  const anim = kopya.animate([
    { transform: "translate(0,0) scale(1)", opacity: 1 },
    { transform: `translate(${dx * 0.5}px,${dy * 0.5 - 90}px) scale(.6) rotate(-8deg)`, opacity: 1, offset: 0.5 },
    { transform: `translate(${dx}px,${dy}px) scale(.12)`, opacity: 0.25 },
  ], { duration: 900, easing: "cubic-bezier(.5,0,.25,1)" });
  const son = () => { kopya.remove(); bitince(); };
  anim.onfinish = son;
  anim.oncancel = son;
}
