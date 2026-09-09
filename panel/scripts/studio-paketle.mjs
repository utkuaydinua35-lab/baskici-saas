/**
 * Studio'yu (frontend/) uygulama paketinin içine koyar.
 *
 * NEDEN: uygulamada iki panel tek kabukta yaşıyor. Mağaza paneli `/`, Studio
 * ise `/studio/` altında duruyor; ikisi de `capacitor://localhost` origin'inde
 * olduğu için localStorage ve platform seçimi ortak.
 *
 * Studio'nun web derlemesi ETKİLENMEZ: burada verilen VITE_ALT_YOL ve
 * VITE_API_TABAN yalnız bu derlemeye özgüdür, `frontend`'in kendi
 * `npm run build`'i bugünkü gibi kökten çalışır.
 */
import { execFileSync } from 'node:child_process'
import { cpSync, existsSync, rmSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const kok = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..')
const studio = resolve(kok, 'frontend')
const hedef = resolve(kok, 'panel', 'dist', 'studio')

const taban = process.env.VITE_API_TABAN
if (!taban) {
  console.error('[studio] VITE_API_TABAN yok — bu betik yalnız uygulama derlemesinde çalışır.')
  process.exit(1)
}

if (!existsSync(resolve(studio, 'node_modules'))) {
  console.error('[studio] frontend/node_modules yok — önce `npm install --prefix frontend`.')
  process.exit(1)
}

console.log('[studio] derleniyor (base=/studio/, api=' + taban + ')')
execFileSync('npx', ['vite', 'build'], {
  cwd: studio,
  stdio: 'inherit',
  env: { ...process.env, VITE_ALT_YOL: '/studio/', VITE_API_TABAN: taban },
})

rmSync(hedef, { recursive: true, force: true })
cpSync(resolve(studio, 'dist'), hedef, { recursive: true })
console.log('[studio] kopyalandi -> panel/dist/studio')
