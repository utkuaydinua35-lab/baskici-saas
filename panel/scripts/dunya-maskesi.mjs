// Küre için kara noktalarını ÜRETİR — çalışma zamanında değil, BURADA.
//
// Neden: dünya geometrisini (topojson) panele koymak ~100KB ve her açılışta
// binlerce nokta-içinde-mi testi demek. Bunun yerine noktalar bir kez burada
// hesaplanıp sıkıştırılmış olarak gömülüyor; tarayıcıda yalnız izdüşüm
// matematiği kalıyor ve hiçbir çalışma zamanı bağımlılığı olmuyor.
//
// Üretilen dosya (src/data/karaNoktalari.js) sürüm kontrolündedir; bu script
// yalnız kara verisi değişirse yeniden çalıştırılır. Bağımlılıkları KALICI
// olarak package.json'a koymuyoruz — VPS'teki `npm ci` her derlemede ~50MB
// harita veri paketini indirmesin diye.
//
// Çalıştırma:
//   npm i --no-save world-atlas@2 topojson-client d3-geo
//   node scripts/dunya-maskesi.mjs
import { writeFileSync } from 'node:fs'
import { feature } from 'topojson-client'
import { geoContains } from 'd3-geo'
import topo from 'world-atlas/land-110m.json' with { type: 'json' }

const kara = feature(topo, topo.objects.land)

// Fibonacci küresi: noktalar yüzeye EŞİT aralıkla dağılır. Enlem/boylam
// ızgarası kullanılsaydı kutuplarda yığılma olurdu.
const N = 20000
const ALTIN = Math.PI * (3 - Math.sqrt(5))
const noktalar = []
for (let i = 0; i < N; i++) {
  const y = 1 - (i / (N - 1)) * 2
  const yaricap = Math.sqrt(1 - y * y)
  const aci = ALTIN * i
  const x = Math.cos(aci) * yaricap
  const z = Math.sin(aci) * yaricap
  const lat = Math.asin(y) * 180 / Math.PI
  const lon = Math.atan2(z, x) * 180 / Math.PI
  if (geoContains(kara, [lon, lat])) noktalar.push([lat, lon])
}

// 0.1 derece hassasiyet int16'ya sığar (lat ±900, lon ±1800)
const buf = new Int16Array(noktalar.length * 2)
noktalar.forEach(([lat, lon], i) => {
  buf[i * 2] = Math.round(lat * 10)
  buf[i * 2 + 1] = Math.round(lon * 10)
})
const b64 = Buffer.from(buf.buffer).toString('base64')

writeFileSync(new URL('../src/data/karaNoktalari.js', import.meta.url),
`// ÜRETİLMİŞ DOSYA — elle düzenlemeyin. Kaynak: scripts/dunya-maskesi.mjs
//
// Dünya karalarına eşit aralıkla serpilmiş ${noktalar.length} nokta
// (Fibonacci küresi, ${N} adaydan kara üstüne düşenler). Küre bunları
// ortografik izdüşümle çizer. 0.1 derece hassasiyet — küre ölçeğinde
// bir pikselin çok altında.
export const KARA_B64 = "${b64}"

let _onbellek = null
/** [lat, lon] çiftleri — ilk çağrıda çözülür, sonra önbellekten. */
export function karaNoktalari() {
  if (_onbellek) return _onbellek
  const ikili = atob(KARA_B64)
  const bayt = new Uint8Array(ikili.length)
  for (let i = 0; i < ikili.length; i++) bayt[i] = ikili.charCodeAt(i)
  const i16 = new Int16Array(bayt.buffer)
  _onbellek = new Float32Array(i16.length)
  for (let i = 0; i < i16.length; i++) _onbellek[i] = i16[i] / 10
  return _onbellek
}
`)
console.log(`${noktalar.length} kara noktasi · ${(b64.length / 1024).toFixed(1)} KB base64`)
