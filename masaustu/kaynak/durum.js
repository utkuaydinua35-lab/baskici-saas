/**
 * Kabuğun küçük hafızası — kullanıcı klasöründe tek JSON dosyası.
 *
 * Neden dosya: hangi olayı gösterdiğimizi uygulama kapanınca da bilmeliyiz,
 * yoksa her açılışta aynı bildirimler tekrar düşer.
 */
const { app } = require('electron')
const fs = require('fs')
const path = require('path')

const DOSYA = () => path.join(app.getPath('userData'), 'durum.json')
const GECMIS_SINIRI = 300          // en son 300 olay kimliği yeter

let bellek = null

function oku() {
  if (bellek) return bellek
  try {
    bellek = JSON.parse(fs.readFileSync(DOSYA(), 'utf8'))
  } catch {
    bellek = { sonGorulen: null, gosterilen: [], izinSoruldu: false, bildirimAcik: true }
  }
  return bellek
}

function yaz() {
  try {
    fs.mkdirSync(path.dirname(DOSYA()), { recursive: true })
    fs.writeFileSync(DOSYA(), JSON.stringify(bellek))
  } catch { /* disk yazılamıyorsa bellekte devam */ }
}

module.exports = {
  sonGorulen: () => oku().sonGorulen,
  sonGorulenYaz: (iso) => { oku().sonGorulen = iso; yaz() },
  gorulduMu: (id) => oku().gosterilen.includes(id),
  gorulduYaz: (id) => {
    const d = oku()
    d.gosterilen.push(id)
    if (d.gosterilen.length > GECMIS_SINIRI) d.gosterilen = d.gosterilen.slice(-GECMIS_SINIRI)
    yaz()
  },
  izinSoruldu: () => oku().izinSoruldu,
  izinSorulduYaz: () => { oku().izinSoruldu = true; yaz() },
  bildirimAcik: () => oku().bildirimAcik !== false,
  bildirimAcikYaz: (v) => { oku().bildirimAcik = !!v; yaz() },
}
