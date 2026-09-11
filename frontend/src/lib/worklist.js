import { api } from './api'

// Zil (Layout) ve Dashboard aynı açılışta worklist'i AYRI AYRI istiyordu —
// ağır bir sorgu, iki kez. Kısa ömürlü ortak söz: 60 sn içindeki ikinci
// istek aynı cevabı kullanır. Hata olursa söz atılır, sonraki istek yeniden sorar.
const OMUR_MS = 60_000
let _soz = null
let _zaman = 0

export function worklistGetir() {
  const simdi = Date.now()
  if (_soz && simdi - _zaman < OMUR_MS) return _soz
  _zaman = simdi
  _soz = api.get('/api/dashboard/worklist').catch((e) => { _soz = null; throw e })
  return _soz
}
