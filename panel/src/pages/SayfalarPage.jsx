import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { useStore } from '../lib/store'
import { useToast } from '../components/Toast'
import SaveBar from '../components/SaveBar'

// Sayfalar — yasal metinler (vitrindeki hazır şablonları özelleştirir) +
// özel sayfalar (/sayfa/adres olarak yayınlanır, footer'a link düşer).
const LEGAL = [
  { key: 'kvkk_text', title: 'Gizlilik ve KVKK', path: '/gizlilik' },
  { key: 'mesafeli_satis_text', title: 'Mesafeli Satış Sözleşmesi', path: '/mesafeli-satis' },
  { key: 'iade_text', title: 'İade ve Değişim', path: '/iade' },
]

export default function SayfalarPage() {
  const { storeId } = useStore()
  const [legal, setLegal] = useState({})
  const [pages, setPages] = useState([])
  const [openIdx, setOpenIdx] = useState(null)   // açık özel sayfa
  const [openLegal, setOpenLegal] = useState(null)
  const [busy, setBusy] = useState(false)
  const toast = useToast()
  const initialRef = useRef('')

  const load = useCallback(async () => {
    if (!storeId) return
    try {
      const [settings, pg] = await Promise.all([
        api.get(`/api/store-settings/${storeId}`),
        api.get(`/api/store-settings/${storeId}/pages`),
      ])
      setLegal({
        kvkk_text: settings.config.kvkk_text || '',
        mesafeli_satis_text: settings.config.mesafeli_satis_text || '',
        iade_text: settings.config.iade_text || '',
      })
      setPages(pg.pages || [])
      initialRef.current = JSON.stringify([{
        kvkk_text: settings.config.kvkk_text || '',
        mesafeli_satis_text: settings.config.mesafeli_satis_text || '',
        iade_text: settings.config.iade_text || '',
      }, pg.pages || []])
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Yüklenemedi')
    }
  }, [storeId])
  useEffect(() => { load() }, [load])

  const save = async () => {
    setBusy(true)
    try {
      await Promise.all([
        api.patch(`/api/store-settings/${storeId}`, { config: legal }),
        api.put(`/api/store-settings/${storeId}/pages`, { pages }),
      ])
      await load()
      toast.success('Sayfalar kaydedildi')
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Kaydedilemedi')
    } finally { setBusy(false) }
  }

  const discard = () => {
    try {
      const [l, p2] = JSON.parse(initialRef.current)
      setLegal(l); setPages(p2)
    } catch { /* yok */ }
  }
  const dirty = initialRef.current !== '' &&
    JSON.stringify([legal, pages]) !== initialRef.current

  const addPage = () => {
    setPages(p => [...p, { slug: '', title: 'Yeni Sayfa', content: '' }])
    setOpenIdx(pages.length)
  }
  const patchPage = (i, patch) =>
    setPages(p => p.map((pg, j) => j === i ? { ...pg, ...patch } : pg))
  const removePage = (i) => {
    if (!window.confirm('Sayfa silinecek. Emin misiniz?')) return
    setPages(p => p.filter((_, j) => j !== i))
    setOpenIdx(null)
  }

  return (
    <div className="max-w-2xl space-y-4 pb-10">
      <SaveBar dirty={dirty} busy={busy} onSave={save} onDiscard={discard} />
      <h1 className="text-xl font-semibold">Sayfalar</h1>

      {/* Sistem sayfaları — içerikleri Tema editöründen/ayarlardan yönetilir */}
      <section className="card space-y-1.5">
        <h2 className="text-sm font-semibold">🏗 Sistem Sayfaları</h2>
        <p className="text-[11px] text-panel-muted -mt-1">
          Bu sayfalar mağazanın yapı taşlarıdır — silinip eklenmez, içerikleri
          ilgili düzenleyicilerden yönetilir.
        </p>
        {[
          ['🏠 Ana Sayfa', 'Bölümler, slaytlar ve tüm görünüm', '/tema/duzenle', 'Tema editöründe aç'],
          ['🛒 Sepet', 'Kampanya mesajları (X Al Y Öde) tema editöründe; kargo eşiği Ayarlar → Kargo\'da', '/tema/duzenle', 'Tema editöründe aç'],
          ['🧾 Sipariş Takip / Teşekkür', 'Ödeme sonrası müşteri takip sayfası — e-posta metinleri Ayarlar → E-posta sekmesinde', '/ayarlar', 'Ayarları aç'],
        ].map(([title, desc, to, cta]) => (
          <div key={title} className="flex items-center gap-3 border border-panel-border rounded-xl px-3 py-2.5">
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium">{title}</div>
              <div className="text-[11px] text-panel-muted">{desc}</div>
            </div>
            <a href={to} className="btn-ghost !py-1 text-xs whitespace-nowrap">{cta} →</a>
          </div>
        ))}
      </section>

      <section className="card space-y-2">
        <h2 className="text-sm font-semibold">📄 Yasal Sayfalar</h2>
        <p className="text-[11px] text-panel-muted -mt-1">
          Boş bırakılan alanlarda vitrindeki hazır şablon metinler gösterilir.
        </p>
        {LEGAL.map(l => (
          <div key={l.key} className="border border-panel-border rounded-xl overflow-hidden">
            <button onClick={() => setOpenLegal(openLegal === l.key ? null : l.key)}
              className="w-full flex items-center gap-2 px-3 py-2 bg-panel-input text-sm font-medium text-left">
              {l.title}
              <span className="text-panel-muted text-xs">{l.path}</span>
              <span className="ml-auto text-[10px] text-panel-muted">
                {legal[l.key] ? 'özel metin' : 'şablon'} {openLegal === l.key ? '▾' : '▸'}
              </span>
            </button>
            {openLegal === l.key && (
              <div className="p-3 bg-white">
                <textarea className="input" rows={8} maxLength={20000} value={legal[l.key]}
                  onChange={e => setLegal(v => ({ ...v, [l.key]: e.target.value }))}
                  placeholder="Boş = vitrindeki hazır şablon kullanılır" />
              </div>
            )}
          </div>
        ))}
      </section>

      <section className="card space-y-2">
        <div className="flex items-center">
          <h2 className="text-sm font-semibold">📃 Özel Sayfalar</h2>
          <button onClick={addPage} className="btn-ghost !py-1 text-xs ml-auto">+ Sayfa Ekle</button>
        </div>
        {pages.length === 0 && (
          <p className="text-xs text-panel-muted">
            Hakkımızda, SSS, iletişim gibi sayfalar ekleyin — footer'a otomatik link düşer.
          </p>
        )}
        {pages.map((pg, i) => (
          <div key={i} className="border border-panel-border rounded-xl overflow-hidden">
            <div className="flex items-center gap-2 px-3 py-2 bg-panel-input">
              <button onClick={() => setOpenIdx(openIdx === i ? null : i)}
                className="flex-1 text-left text-sm font-medium">
                {pg.title || 'Adsız sayfa'}
                <span className="text-panel-muted text-xs ml-2">/sayfa/{pg.slug || '…'}</span>
              </button>
              <button onClick={() => removePage(i)}
                className="text-xs text-red-400 hover:text-red-600 px-1">Sil</button>
            </div>
            {openIdx === i && (
              <div className="p-3 bg-white space-y-2">
                <div className="grid grid-cols-2 gap-2">
                  <label className="block text-sm">
                    <span className="text-panel-muted text-xs">Başlık</span>
                    <input className="input mt-1" value={pg.title} maxLength={200}
                      onChange={e => patchPage(i, { title: e.target.value })} />
                  </label>
                  <label className="block text-sm">
                    <span className="text-panel-muted text-xs">Adres (boş = başlıktan üretilir)</span>
                    <input className="input mt-1 font-mono text-xs" value={pg.slug}
                      onChange={e => patchPage(i, { slug: e.target.value })}
                      placeholder="hakkimizda" />
                  </label>
                </div>
                <textarea className="input" rows={8} maxLength={20000} value={pg.content}
                  onChange={e => patchPage(i, { content: e.target.value })}
                  placeholder="Sayfa içeriği (satır sonları korunur)" />
              </div>
            )}
          </div>
        ))}
      </section>
    </div>
  )
}
