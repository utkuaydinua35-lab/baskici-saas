/**
 * BERNZ Bayi — masaüstü kabuğu (Windows + macOS).
 *
 * NE YAPAR: bayi panelini kendi penceresinde açar ve arka planda sunucuya
 * "benim için yeni olay var mı?" diye sorar; kargo ve sohbet olaylarını
 * işletim sisteminin bildirimi olarak gösterir.
 *
 * NEDEN ÇEKME (polling), Web Push DEĞİL: Electron'da tarayıcı push servisi
 * yok — VAPID/servis çalışanı zinciri burada çalışmıyor. Çekme usulü hem
 * basit hem de güvenli: sunucuda yeni altyapı gerekmiyor, olaylar var olan
 * kayıtlardan türetiliyor (GET /api/bayii/bildirimler?since=...).
 *
 * OTURUM: panel kendi JWT'sini localStorage'da tutuyor. Kabuk onu pencereden
 * OKUR (yazmaz); oturum yoksa yoklama yapılmaz.
 */
const { app, BrowserWindow, Notification, shell, Menu, dialog } = require('electron')
const path = require('path')
const AYAR = require('./ayarlar')
const durum = require('./durum')

let pencere = null
let yoklamaZaman = null

// Windows'ta bildirimlerin uygulama adıyla görünmesi için şart
if (process.platform === 'win32') app.setAppUserModelId('com.bernzcompany.bayi')

function pencereOlustur() {
  pencere = new BrowserWindow({
    width: 1280, height: 860, minWidth: 960, minHeight: 600,
    title: 'BERNZ Bayi',
    backgroundColor: '#0b0d12',          // panel koyu tema — beyaz parlama olmasın
    autoHideMenuBar: true,
    icon: path.join(__dirname, 'varliklar', process.platform === 'win32' ? 'icon.ico' : 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,            // panel sayfası Node'a ERİŞEMEZ
      spellcheck: true,
    },
  })

  pencere.webContents.setUserAgent(
    `${pencere.webContents.getUserAgent()} ${AYAR.KULLANICI_ARACI_EKI}`)

  pencere.loadURL(AYAR.PANEL_URL)

  // Panel dışındaki bağlantılar VARSAYILAN TARAYICIDA açılsın (WhatsApp,
  // kargo takip, e-posta…). Kabuğun içinde açılırsa kullanıcı geri dönemiyor.
  pencere.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })
  pencere.webContents.on('will-navigate', (olay, url) => {
    if (!ayniSite(url)) {
      olay.preventDefault()
      shell.openExternal(url)
    }
  })

  pencere.on('closed', () => { pencere = null })

  // Sunucuya ulaşılamazsa boş beyaz pencere kalmasın
  pencere.webContents.on('did-fail-load', (_o, kod, aciklama, url) => {
    if (kod === -3) return                 // kullanıcı iptal etti
    pencere.webContents.executeJavaScript(`
      document.body.innerHTML = ${JSON.stringify(hataSayfasi(aciklama))}
    `).catch(() => {})
  })
}

function ayniSite(url) {
  try {
    return new URL(url).origin === new URL(AYAR.PANEL_URL).origin
  } catch { return false }
}

function hataSayfasi(aciklama) {
  return `<div style="font:15px -apple-system,Segoe UI,sans-serif;color:#e5e7eb;
    background:#0b0d12;height:100vh;display:flex;align-items:center;justify-content:center;
    text-align:center;padding:40px"><div>
    <div style="font-size:40px;margin-bottom:12px">📡</div>
    <div style="font-size:18px;margin-bottom:6px">Panele ulaşılamadı</div>
    <div style="color:#9ca3af;font-size:13px">İnternet bağlantını kontrol et, pencereyi kapatıp yeniden aç.<br>
    <span style="color:#6b7280">(${String(aciklama || '').slice(0, 120)})</span></div>
  </div></div>`
}

/** Panelin localStorage'ındaki oturum jetonu (okuma). */
async function jetonAl() {
  if (!pencere) return null
  try {
    return await pencere.webContents.executeJavaScript(
      "localStorage.getItem('baskici_token')", true)
  } catch { return null }
}

async function yokla() {
  const jeton = await jetonAl()
  if (!jeton) return AYAR.TOKEN_BEKLEME_MS      // oturum yok — sık sık bak, hafif
  const taban = new URL(AYAR.PANEL_URL).origin
  const since = durum.sonGorulen()
  const adres = `${taban}/api/bayii/bildirimler${since ? `?since=${encodeURIComponent(since)}` : ''}`
  try {
    const yanit = await fetch(adres, { headers: { Authorization: `Bearer ${jeton}` } })
    if (yanit.status === 401) return AYAR.TOKEN_BEKLEME_MS   // oturum düştü
    if (!yanit.ok) return AYAR.YOKLAMA_MS
    const veri = await yanit.json()
    for (const olay of (veri.olaylar || [])) {
      if (durum.gorulduMu(olay.id)) continue
      bildirimGoster(olay)
      durum.gorulduYaz(olay.id)
    }
    durum.sonGorulenYaz(veri.sunucu_saati)
  } catch {
    // Ağ yoksa sessiz geç — bir sonraki turda yeniden denenir
  }
  return AYAR.YOKLAMA_MS
}

function bildirimGoster(olay) {
  if (!Notification.isSupported()) return
  const b = new Notification({
    title: olay.baslik || 'BERNZ Bayi',
    body: olay.govde || '',
    silent: false,
  })
  // Bildirime tıklayınca ilgili sayfa açılsın
  b.on('click', () => {
    if (!pencere) pencereOlustur()
    else { if (pencere.isMinimized()) pencere.restore(); pencere.focus() }
    if (olay.link) {
      const hedef = new URL(AYAR.PANEL_URL).origin + olay.link
      pencere.loadURL(hedef)
    }
  })
  b.show()
}

/** Bildirim izni: macOS'ta ilk bildirimde sistem sorar; kullanıcıya önce
 *  ne olacağını anlatıyoruz ki sistem kutusu beklenmedik gelmesin. */
async function bildirimIzniIste() {
  if (durum.izinSoruldu()) return
  durum.izinSorulduYaz()
  const r = await dialog.showMessageBox(pencere, {
    type: 'info',
    title: 'Bildirimler',
    message: 'Bildirimleri açalım mı?',
    detail: 'Siparişin kargoya verildiğinde ve atölye sana mesaj yazdığında '
      + 'bilgisayarında bildirim görürsün. İstersen sonra kapatabilirsin.',
    buttons: ['Bildirimleri aç', 'Şimdi değil'],
    defaultId: 0, cancelId: 1,
  })
  if (r.response === 0) {
    durum.bildirimAcikYaz(true)
    new Notification({
      title: 'Bildirimler açık',
      body: 'Kargo ve mesaj bildirimleri buraya düşecek.',
    }).show()                              // macOS izin kutusunu bu tetikler
  } else {
    durum.bildirimAcikYaz(false)
  }
}

function dongu() {
  const calistir = async () => {
    let sonraki = AYAR.YOKLAMA_MS
    if (durum.bildirimAcik()) sonraki = await yokla()
    yoklamaZaman = setTimeout(calistir, sonraki)
  }
  calistir()
}

app.whenReady().then(async () => {
  Menu.setApplicationMenu(menuOlustur())
  pencereOlustur()
  // Duman testi: BERNZ_SMOKE=1 ile açılır, yüklenir ve kendiliğinden kapanır.
  // Paketleme öncesi "kabuk hiç açılıyor mu?" sorusunu insan gözü olmadan yanıtlar.
  if (process.env.BERNZ_SMOKE) {
    pencere.webContents.once('did-finish-load', () => {
      console.log('SMOKE: pencere açıldı ve sayfa yüklendi')
      setTimeout(() => app.exit(0), 800)
    })
    setTimeout(() => { console.log('SMOKE: zaman aşımı'); app.exit(1) }, 20000)
    return
  }
  pencere.webContents.once('did-finish-load', () => {
    setTimeout(bildirimIzniIste, 1500)     // sayfa otursun, sonra sor
  })
  dongu()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
app.on('activate', () => { if (!pencere) pencereOlustur() })
app.on('before-quit', () => { if (yoklamaZaman) clearTimeout(yoklamaZaman) })

function menuOlustur() {
  const mac = process.platform === 'darwin'
  return Menu.buildFromTemplate([
    ...(mac ? [{ role: 'appMenu' }] : []),
    {
      label: 'Dosya',
      submenu: [
        { label: 'Yenile', accelerator: 'CmdOrCtrl+R', click: () => pencere?.reload() },
        { label: 'Panele dön', click: () => pencere?.loadURL(AYAR.PANEL_URL) },
        { type: 'separator' },
        {
          label: 'Bildirimler açık',
          type: 'checkbox',
          checked: durum.bildirimAcik(),
          click: (m) => {
            durum.bildirimAcikYaz(m.checked)
            if (m.checked) new Notification({ title: 'Bildirimler açık', body: 'Kargo ve mesaj bildirimleri gelecek.' }).show()
          },
        },
        { type: 'separator' },
        mac ? { role: 'close', label: 'Kapat' } : { role: 'quit', label: 'Çıkış' },
      ],
    },
    { label: 'Düzen', role: 'editMenu' },
    {
      label: 'Görünüm',
      submenu: [
        { role: 'resetZoom', label: 'Yakınlaştırmayı sıfırla' },
        { role: 'zoomIn', label: 'Yakınlaştır' },
        { role: 'zoomOut', label: 'Uzaklaştır' },
        { type: 'separator' },
        { role: 'togglefullscreen', label: 'Tam ekran' },
      ],
    },
  ])
}
