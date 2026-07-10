import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { useStore } from '../lib/store'
import { useToast } from '../components/Toast'
import SaveBar from '../components/SaveBar'

// Tema Ayarları — sol form (bölüm editörü dahil), sağ canlı önizleme.
// Tema v2: anasayfa "sections" listesidir; bölüm ekle/sil/sırala + tipe özel ayar.
const FONTS = [
  { key: 'inter', label: 'Inter (modern, varsayılan)' },
  { key: 'poppins', label: 'Poppins (yuvarlak, samimi)' },
  { key: 'playfair', label: 'Playfair Display (şık, serif)' },
  { key: 'dm-sans', label: 'DM Sans (sade, geometrik)' },
]

const SECTION_TYPES = {
  hero_slider: { label: 'Hero / Slayt Gösterisi', icon: '🌅' },
  featured_collections: { label: 'Koleksiyon Kartları', icon: '🗂️' },
  products_grid: { label: 'Ürün Izgarası', icon: '🛍️' },
  featured_products: { label: 'Öne Çıkan Ürünler (elle seç)', icon: '🌟' },
  rich_text: { label: 'Metin Bölümü', icon: '📝' },
  banner: { label: 'Banner Görseli', icon: '🖼️' },
  image_with_text: { label: 'Görsel + Metin', icon: '🏞️' },
  faq: { label: 'SSS (Akordeon)', icon: '❓' },
  newsletter: { label: 'Bülten Kaydı', icon: '📮' },
  icon_bar: { label: 'İkon Şeridi (Avantajlar)', icon: '✨' },
  comparison: { label: 'Karşılaştırma (Biz vs Diğerleri)', icon: '⚖️' },
  testimonials: { label: 'Müşteri Yorumları Vitrini', icon: '💬' },
  gallery: { label: 'Görsel Galerisi', icon: '🖼️' },
  contact: { label: 'İletişim Formu', icon: '✉️' },
  countdown: { label: 'Kampanya Geri Sayımı', icon: '⏳' },
}

const SECTION_DEFAULTS = {
  hero_slider: { slides: [], autoplay_sec: 5 },
  featured_collections: { title: 'Koleksiyonlar', slugs: [] },
  products_grid: { title: 'Öne Çıkanlar', collection: null, limit: 8 },
  featured_products: { title: 'Öne Çıkan Ürünler', slugs: [] },
  rich_text: { title: '', body: '' },
  banner: { image: null, url: '' },
  image_with_text: { image: null, title: '', body: '', cta_text: '', cta_url: '', image_side: 'left' },
  faq: { title: 'Sıkça Sorulan Sorular', items: [] },
  newsletter: { title: 'Kampanyalardan haberdar olun', subtitle: 'İndirim ve yeni tasarımlar e-postanıza gelsin.' },
  icon_bar: { items: [{ icon: '🚚', title: 'Hızlı Kargo', text: '1-3 iş gününde kargoda' }] },
  comparison: { title: 'Neden Biz?', us_label: 'Biz', them_label: 'Diğerleri',
    rows: [{ feature: 'Kişiye özel baskı kalitesi', us: true, them: false }] },
  testimonials: { title: 'Müşterilerimiz Ne Diyor?', items: [] },
  gallery: { title: 'Sizden Gelenler', images: [] },
  contact: { title: 'İletişim', subtitle: 'Soru ve önerileriniz için bize yazın.' },
  countdown: { title: 'Kampanya bitiyor!', subtitle: '', ends_at: '',
    cta_text: 'Alışverişe Başla', cta_url: '/urunler' },
}

export default function TemaPage() {
  const { storeId, store } = useStore()
  const [theme, setTheme] = useState(null)
  const [collections, setCollections] = useState([])
  const [products, setProducts] = useState([])
  const [busy, setBusy] = useState(false)
  const [saveCount, setSaveCount] = useState(0)  // iframe reload anahtarı
  const [device, setDevice] = useState('desktop') // desktop | mobile önizleme
  const toast = useToast()
  const initialRef = useRef('')
  const [openSection, setOpenSection] = useState(null)  // açık bölüm id'si
  const [customCode, setCustomCode] = useState(null)     // {head_html, css, body_html}
  const [presets, setPresets] = useState([])             // hazır şablonlar

  const storefrontUrl = store?.config?.storefront_url
    || (store?.config?.shop_domain ? `https://${store.config.shop_domain}` : 'http://localhost:3001')

  const load = useCallback(async () => {
    if (!storeId) return
    try {
      const [t, c, cc, pr] = await Promise.all([
        api.get(`/api/store-settings/${storeId}/theme`),
        api.get(`/api/catalog/collections?store_id=${storeId}`),
        api.get(`/api/store-settings/${storeId}/custom-code`),
        api.get(`/api/catalog/products?store_id=${storeId}&status=active`),
      ])
      setTheme(t)
      setCollections(c.filter(x => x.is_active))
      setProducts(pr)
      api.get(`/api/store-settings/${storeId}/theme/presets`)
        .then(setPresets).catch(() => {})
      setCustomCode(cc)
      initialRef.current = JSON.stringify([t, cc])
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Tema yüklenemedi')
    }
  }, [storeId])
  useEffect(() => { load() }, [load])

  const save = async () => {
    setBusy(true)
    try {
      const [t] = await Promise.all([
        api.put(`/api/store-settings/${storeId}/theme`, theme),
        customCode ? api.put(`/api/store-settings/${storeId}/custom-code`, customCode) : Promise.resolve(),
      ])
      setTheme(t)
      initialRef.current = JSON.stringify([t, customCode])
      setSaveCount(n => n + 1)
      toast.success('Tema kaydedildi — vitrin ~1 dk içinde güncellenir')
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Kaydedilemedi')
    } finally { setBusy(false) }
  }

  const discard = () => {
    try {
      const [t, cc] = JSON.parse(initialRef.current)
      setTheme(t); setCustomCode(cc)
    } catch { /* ilk yükleme yoksa */ }
  }
  const dirty = !!theme && initialRef.current !== '' &&
    JSON.stringify([theme, customCode]) !== initialRef.current

  const applyPreset = (preset) => {
    if (!window.confirm(`"${preset.label}" şablonu uygulanacak — renk, yazı tipi, duyuru ve `
        + `anasayfa bölümleri değişir; logo, WhatsApp ve özel kodunuz korunur. Devam?`)) return
    setTheme(t => ({
      ...t,
      colors: { ...preset.theme.colors },
      font: preset.theme.font,
      announcement: { ...preset.theme.announcement },
      animations: { ...t.animations, ...preset.theme.animations },
      sections: structuredClone(preset.theme.sections),
    }))
    setOpenSection(null)
    toast.success(`${preset.label} yüklendi — beğendiyseniz Kaydet'e basın`)
  }

  const uploadAsset = async (kind, file, target) => {
    if (!file) return
    setBusy(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('kind', kind)
      const r = await api.postForm(`/api/store-settings/${storeId}/assets`, fd)
      target(r.url)
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Yükleme başarısız')
    } finally { setBusy(false) }
  }

  const set = (path, value) => {
    setTheme(t => {
      const next = structuredClone(t)
      const keys = path.split('.')
      let obj = next
      for (const k of keys.slice(0, -1)) obj = obj[k]
      obj[keys[keys.length - 1]] = value
      return next
    })
  }

  // ── Bölüm işlemleri ──
  const patchSectionMeta = (id, meta) => {
    setTheme(t => ({
      ...t,
      sections: t.sections.map(s => s.id === id ? { ...s, ...meta } : s),
    }))
  }
  const patchSection = (id, patch) => {
    setTheme(t => ({
      ...t,
      sections: t.sections.map(s => s.id === id
        ? { ...s, settings: { ...s.settings, ...patch } } : s),
    }))
  }
  const moveSec = (idx, dir) => {
    setTheme(t => {
      const arr = [...t.sections]
      const j = idx + dir
      if (j < 0 || j >= arr.length) return t
      ;[arr[idx], arr[j]] = [arr[j], arr[idx]]
      return { ...t, sections: arr }
    })
  }
  const removeSec = (id) => {
    if (!window.confirm('Bu bölüm anasayfadan kaldırılacak. Emin misiniz?')) return
    setTheme(t => ({ ...t, sections: t.sections.filter(s => s.id !== id) }))
  }
  const addSec = (type) => {
    const id = `${type}-${Date.now().toString(36)}`
    setTheme(t => ({
      ...t,
      sections: [...t.sections, { id, type, settings: structuredClone(SECTION_DEFAULTS[type]) }],
    }))
    setOpenSection(id)
  }

  if (!theme) return <p className="text-sm text-panel-muted">Yükleniyor…</p>

  return (
    <div className="flex gap-5 h-full">
      <SaveBar dirty={dirty} busy={busy} onSave={save} onDiscard={discard} />
      {/* Sol: form */}
      <div className="w-[400px] shrink-0 space-y-4 overflow-y-auto pb-10">
        <h1 className="text-xl font-semibold py-2">Tema</h1>

        {presets.length > 0 && (
          <Section title="Hazır Şablonlar" icon="🎁">
            <div className="space-y-2">
              {presets.map(pr => (
                <div key={pr.key} className="border border-panel-border rounded-xl p-3">
                  <div className="flex items-center gap-2">
                    <span className="flex gap-1">
                      {[pr.colors.primary, pr.colors.accent, pr.colors.bg].map((c2, i) => (
                        <span key={i} className="w-4 h-4 rounded-full border border-panel-border"
                          style={{ background: c2 }} />
                      ))}
                    </span>
                    <span className="text-sm font-medium">{pr.label}</span>
                    <button onClick={() => applyPreset(pr)}
                      className="btn-ghost !py-1 text-xs ml-auto">Uygula</button>
                  </div>
                  <p className="text-[11px] text-panel-muted mt-1.5">{pr.description}</p>
                </div>
              ))}
            </div>
            <p className="text-[11px] text-panel-muted">
              Şablon; renk, yazı tipi ve anasayfa düzenini değiştirir. Logo, görseller ve
              özel kodunuz korunur — Kaydet'e basmadan vitrine yansımaz.
            </p>
          </Section>
        )}

        <Section title="Renkler" icon="🎨">
          <div className="grid grid-cols-3 gap-3">
            <ColorField label="Ana renk" value={theme.colors.primary} onChange={v => set('colors.primary', v)} />
            <ColorField label="Vurgu" value={theme.colors.accent} onChange={v => set('colors.accent', v)} />
            <ColorField label="Zemin" value={theme.colors.bg} onChange={v => set('colors.bg', v)} />
          </div>
        </Section>

        <Section title="Yazı Tipi" icon="🔤">
          <select className="input" value={theme.font} onChange={e => set('font', e.target.value)}>
            {FONTS.map(f => <option key={f.key} value={f.key}>{f.label}</option>)}
          </select>
        </Section>

        <Section title="Logo ve Favicon" icon="🖼️">
          <AssetField label="Logo" current={theme.logo_url}
            onUpload={f => uploadAsset('logo', f, url => set('logo_url', url))}
            onClear={() => set('logo_url', null)} />
          <AssetField label="Favicon" current={theme.favicon_url}
            onUpload={f => uploadAsset('favicon', f, url => set('favicon_url', url))}
            onClear={() => set('favicon_url', null)} />
        </Section>

        <Section title="Üst Menü" icon="🧭">
          <p className="text-[11px] text-panel-muted -mt-1">
            Boş bırakılırsa varsayılan menü (Ürünler + Koleksiyonlar) kullanılır.
          </p>
          {(theme.nav_links || []).map((l, i) => (
            <div key={i} className="flex gap-1.5">
              <input className="input !py-1.5 text-xs !w-32" value={l.label} maxLength={40}
                placeholder="Etiket"
                onChange={e => set('nav_links', theme.nav_links.map((x, j) =>
                  j === i ? { ...x, label: e.target.value } : x))} />
              <input className="input !py-1.5 text-xs font-mono" value={l.url} maxLength={300}
                placeholder="/urunler veya https://…"
                onChange={e => set('nav_links', theme.nav_links.map((x, j) =>
                  j === i ? { ...x, url: e.target.value } : x))} />
              <button onClick={() => set('nav_links', theme.nav_links.filter((_, j) => j !== i))}
                className="text-red-400 hover:text-red-600 px-1">×</button>
            </div>
          ))}
          {(theme.nav_links || []).length < 8 && (
            <button onClick={() => set('nav_links', [...(theme.nav_links || []), { label: '', url: '' }])}
              className="btn-ghost !py-1 text-xs">+ Link Ekle</button>
          )}
        </Section>

        <Section title="Duyuru Şeridi" icon="📢">
          <Toggle checked={theme.announcement.enabled}
            onChange={v => set('announcement.enabled', v)} label="Duyuru şeridini göster" />
          {theme.announcement.enabled && (
            <>
              <input className="input" value={theme.announcement.text} maxLength={140}
                onChange={e => set('announcement.text', e.target.value)}
                placeholder="🚚 500 TL üzeri kargo bedava!" />
              <input className="input" value={theme.announcement.url}
                onChange={e => set('announcement.url', e.target.value)}
                placeholder="Tıklanınca gidilecek adres (ops.)" />
            </>
          )}
        </Section>

        <Section title="WhatsApp Butonu" icon="💬">
          <Toggle checked={!!theme.whatsapp?.enabled}
            onChange={v => set('whatsapp.enabled', v)} label="Vitrinde yüzen WhatsApp butonu göster" />
          {theme.whatsapp?.enabled && (
            <>
              <input className="input" value={theme.whatsapp.number || ''} maxLength={15}
                onChange={e => set('whatsapp.number', e.target.value.replace(/[^0-9]/g, ''))}
                placeholder="905xxxxxxxxx (ülke koduyla, + olmadan)" />
              <input className="input" value={theme.whatsapp.message || ''} maxLength={200}
                onChange={e => set('whatsapp.message', e.target.value)}
                placeholder="Hazır mesaj (müşteri tıklayınca dolu gelir)" />
            </>
          )}
        </Section>

        <Section title="Güven Şeridi" icon="🛡️">
          <Toggle checked={theme.trust_badges?.enabled !== false}
            onChange={v => set('trust_badges.enabled', v)}
            label="Ürün ve ödeme sayfasında güven rozetleri (SSL, iade, kargo) göster" />
        </Section>

        {/* ── Bölüm Editörü ── */}
        <Section title={`Anasayfa Bölümleri (${theme.sections.length})`} icon="🧱">
          <div className="space-y-2">
            {theme.sections.map((sec, i) => {
              const meta = SECTION_TYPES[sec.type] || { label: sec.type, icon: '▫️' }
              const open = openSection === sec.id
              return (
                <div key={sec.id} className={`border border-panel-border rounded-xl overflow-hidden ${
                  sec.hidden ? 'opacity-55' : ''}`}>
                  <div className="flex items-center gap-2 px-3 py-2 bg-panel-input">
                    <button onClick={() => setOpenSection(open ? null : sec.id)}
                      className="flex items-center gap-2 text-sm font-medium flex-1 text-left min-w-0">
                      <span>{meta.icon}</span>
                      <span className="truncate">{meta.label}</span>
                      {sec.hidden && (
                        <span className="text-[10px] bg-slate-200 text-slate-600 px-1.5 py-0.5 rounded-full shrink-0">gizli</span>
                      )}
                      <span className="text-panel-muted text-xs">{open ? '▾' : '▸'}</span>
                    </button>
                    <button onClick={() => patchSectionMeta(sec.id, { hidden: !sec.hidden })}
                      title={sec.hidden ? 'Vitrinde göster' : 'Vitrinde gizle (silmez)'}
                      className="w-6 h-6 rounded-lg border border-panel-border text-xs">
                      {sec.hidden ? '🙈' : '👁'}
                    </button>
                    <button onClick={() => moveSec(i, -1)} disabled={i === 0}
                      className="w-6 h-6 rounded-lg border border-panel-border text-xs disabled:opacity-30">↑</button>
                    <button onClick={() => moveSec(i, 1)} disabled={i === theme.sections.length - 1}
                      className="w-6 h-6 rounded-lg border border-panel-border text-xs disabled:opacity-30">↓</button>
                    <button onClick={() => removeSec(sec.id)}
                      className="w-6 h-6 rounded-lg text-xs text-red-400 hover:text-red-600">×</button>
                  </div>
                  {open && (
                    <div className="p-3 space-y-2 bg-white">
                      <div className="flex items-center gap-2 text-xs text-panel-muted">
                        Zemin:
                        {[['none', 'Sayfa rengi'], ['band', 'Beyaz bant']].map(([v, l]) => (
                          <button key={v} onClick={() => patchSectionMeta(sec.id, { scheme: v })}
                            className={`px-2 py-0.5 rounded-full border ${(sec.scheme || 'none') === v
                              ? 'border-panel-accent bg-emerald-50 text-emerald-700'
                              : 'border-panel-border'}`}>{l}</button>
                        ))}
                      </div>
                      <SectionSettings sec={sec} collections={collections} products={products}
                        patch={p => patchSection(sec.id, p)}
                        uploadAsset={uploadAsset} />
                    </div>
                  )}
                </div>
              )
            })}
          </div>
          {theme.sections.length < 12 && (
            <div className="flex gap-1.5 flex-wrap pt-1">
              {Object.entries(SECTION_TYPES).map(([type, meta]) => (
                <button key={type} onClick={() => addSec(type)}
                  className="px-2.5 py-1 rounded-lg text-xs border border-dashed border-panel-border text-panel-muted hover:text-panel-ink hover:border-slate-400">
                  + {meta.icon} {meta.label}
                </button>
              ))}
            </div>
          )}
        </Section>

        <Section title="Animasyonlar" icon="✨">
          <Toggle checked={theme.animations.reveal}
            onChange={v => set('animations.reveal', v)} label="Kaydırmada belirme + sayfa geçişleri" />
          <Toggle checked={theme.animations.hover_zoom}
            onChange={v => set('animations.hover_zoom', v)} label="Ürün görseline yakınlaşma (hover)" />
          <Toggle checked={theme.animations.cart_drawer}
            onChange={v => set('animations.cart_drawer', v)} label="Sepet çekmecesi (yandan kayan)" />
        </Section>

        <Section title="Özel Kod (Gelişmiş)" icon="⚡">
          <p className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-2.5 py-1.5">
            ⚠️ Buraya eklenen kod vitrininizde aynen çalışır — yalnızca güvendiğiniz
            kodu ekleyin. Panel ve yönetim sistemleri etkilenmez.
          </p>
          {customCode && (
            <>
              <label className="block text-sm">
                <span className="text-panel-muted text-xs">Özel CSS</span>
                <textarea className="input mt-1 font-mono text-xs" rows={4} maxLength={20000}
                  value={customCode.css}
                  onChange={e => setCustomCode(c => ({ ...c, css: e.target.value }))}
                  placeholder=".urun-karti { border-radius: 0; }" />
              </label>
              <label className="block text-sm">
                <span className="text-panel-muted text-xs">Üst kod (sayfa başı — script/HTML)</span>
                <textarea className="input mt-1 font-mono text-xs" rows={3} maxLength={20000}
                  value={customCode.head_html}
                  onChange={e => setCustomCode(c => ({ ...c, head_html: e.target.value }))} />
              </label>
              <label className="block text-sm">
                <span className="text-panel-muted text-xs">Alt kod (sayfa sonu — script/HTML)</span>
                <textarea className="input mt-1 font-mono text-xs" rows={3} maxLength={20000}
                  value={customCode.body_html}
                  onChange={e => setCustomCode(c => ({ ...c, body_html: e.target.value }))} />
              </label>
            </>
          )}
        </Section>

        <Section title="Footer" icon="🦶">
          <textarea className="input" rows={2} maxLength={300} value={theme.footer.about}
            onChange={e => set('footer.about', e.target.value)}
            placeholder="Kısa marka tanıtımı (ops.)" />
          <input className="input" value={theme.footer.instagram} maxLength={60}
            onChange={e => set('footer.instagram', e.target.value)} placeholder="Instagram kullanıcı adı" />
        </Section>
      </div>

      {/* Sağ: önizleme */}
      <div className="flex-1 min-w-0 flex flex-col">
        <div className="flex items-center gap-2 py-2">
          <span className="text-xs text-panel-muted truncate">Önizleme — {storefrontUrl}</span>
          <div className="flex gap-1 bg-panel-input rounded-lg p-0.5 ml-auto">
            {[['desktop', '🖥 Masaüstü'], ['mobile', '📱 Mobil']].map(([k, l]) => (
              <button key={k} onClick={() => setDevice(k)}
                className={`px-2.5 py-1 rounded-md text-xs transition ${device === k
                  ? 'bg-white shadow-sm font-medium' : 'text-panel-muted hover:text-panel-ink'}`}>
                {l}
              </button>
            ))}
          </div>
          <button onClick={() => setSaveCount(n => n + 1)} className="btn-ghost !py-1 text-xs">↻ Yenile</button>
        </div>
        <div className={`flex-1 min-h-[70vh] ${device === 'mobile'
          ? 'flex justify-center bg-panel-input/50 rounded-2xl py-4' : ''}`}>
          <iframe key={`${saveCount}-${device}`} src={storefrontUrl} title="Vitrin önizleme"
            className={device === 'mobile'
              ? 'w-[390px] h-full rounded-[2rem] border-8 border-zinc-800 bg-white shadow-xl'
              : 'w-full h-full rounded-2xl border border-panel-border bg-white'} />
        </div>
        <p className="text-[11px] text-panel-muted mt-1">
          Vitrin temayı ~1 dakika önbellekler; değişiklik hemen görünmezse Yenile'ye basın.
        </p>
      </div>
    </div>
  )
}

// Bölüm tipine özel ayar formu.
function SectionSettings({ sec, collections, products = [], patch, uploadAsset }) {
  const s = sec.settings

  if (sec.type === 'hero_slider') {
    const slides = s.slides || []
    const patchSlide = (i, p) => patch({ slides: slides.map((sl, j) => j === i ? { ...sl, ...p } : sl) })
    return (
      <>
        {slides.map((slide, i) => (
          <div key={i} className="border border-panel-border rounded-xl p-2.5 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium">Slayt {i + 1}</span>
              <button onClick={() => patch({ slides: slides.filter((_, j) => j !== i) })}
                className="text-xs text-red-400 hover:text-red-600">Sil</button>
            </div>
            <AssetField label="Görsel" current={slide.image}
              onUpload={f => uploadAsset('hero', f, url => patchSlide(i, { image: url }))}
              onClear={() => patchSlide(i, { image: null })} />
            <input className="input" value={slide.title || ''} maxLength={100}
              onChange={e => patchSlide(i, { title: e.target.value })} placeholder="Başlık" />
            <input className="input" value={slide.subtitle || ''} maxLength={200}
              onChange={e => patchSlide(i, { subtitle: e.target.value })} placeholder="Alt başlık" />
            <div className="grid grid-cols-2 gap-2">
              <input className="input" value={slide.cta_text || ''} maxLength={40}
                onChange={e => patchSlide(i, { cta_text: e.target.value })} placeholder="Buton yazısı" />
              <input className="input" value={slide.cta_url || ''}
                onChange={e => patchSlide(i, { cta_url: e.target.value })} placeholder="/urunler" />
              <input className="input" value={slide.cta2_text || ''} maxLength={40}
                onChange={e => patchSlide(i, { cta2_text: e.target.value })}
                placeholder="2. buton yazısı (ops. — çerçeveli görünür)" />
              <input className="input" value={slide.cta2_url || ''}
                onChange={e => patchSlide(i, { cta2_url: e.target.value })} placeholder="2. buton adresi" />
            </div>
          </div>
        ))}
        {slides.length < 6 && (
          <button onClick={() => patch({ slides: [...slides, { image: null, title: '', subtitle: '', cta_text: '', cta_url: '/urunler' }] })}
            className="btn-ghost !py-1.5 text-xs w-full">+ Slayt Ekle</button>
        )}
        {slides.length > 1 && (
          <label className="block text-sm">
            <span className="text-panel-muted text-xs">Otomatik geçiş (saniye; 0 = kapalı)</span>
            <input className="input mt-1 !w-24" type="number" min="0" max="30"
              value={s.autoplay_sec ?? 5}
              onChange={e => patch({ autoplay_sec: Number(e.target.value) })} />
          </label>
        )}
        {slides.length === 0 && (
          <p className="text-[11px] text-panel-muted">
            Slayt eklemezseniz sade bir karşılama metni gösterilir.
          </p>
        )}
      </>
    )
  }

  if (sec.type === 'featured_collections') {
    const slugs = s.slugs || []
    return (
      <>
        <input className="input" value={s.title || ''} maxLength={80}
          onChange={e => patch({ title: e.target.value })} placeholder="Bölüm başlığı" />
        {collections.length === 0 ? (
          <p className="text-xs text-panel-muted">Önce Koleksiyonlar sayfasından koleksiyon oluşturun.</p>
        ) : (
          <div className="flex gap-2 flex-wrap">
            {collections.map(c => {
              const active = slugs.includes(c.slug)
              return (
                <button key={c.slug}
                  onClick={() => patch({ slugs: active ? slugs.filter(x => x !== c.slug) : [...slugs, c.slug] })}
                  className={`px-3 py-1 rounded-full text-xs border transition ${active
                    ? 'border-panel-accent bg-emerald-50 text-emerald-700'
                    : 'border-panel-border text-panel-muted hover:text-panel-ink'}`}>
                  {c.title}
                </button>
              )
            })}
          </div>
        )}
        <p className="text-[11px] text-panel-muted">Hiçbiri seçilmezse ilk 4 koleksiyon gösterilir.</p>
      </>
    )
  }

  if (sec.type === 'featured_products') {
    const slugs = s.slugs || []
    const available = products.filter(pr => !slugs.includes(pr.slug))
    const bySlug = Object.fromEntries(products.map(pr => [pr.slug, pr]))
    const move = (i, dir) => {
      const j = i + dir
      if (j < 0 || j >= slugs.length) return
      const next = [...slugs]
      ;[next[i], next[j]] = [next[j], next[i]]
      patch({ slugs: next })
    }
    return (
      <>
        <input className="input" value={s.title || ''} maxLength={80}
          onChange={e => patch({ title: e.target.value })} placeholder="Bölüm başlığı" />
        {slugs.length > 0 && (
          <div className="space-y-1">
            {slugs.map((slug, i) => (
              <div key={slug} className="flex items-center gap-1.5 text-xs bg-panel-input rounded-lg px-2 py-1.5">
                <span className="flex-1 min-w-0 truncate">
                  {bySlug[slug]?.title || <span className="text-red-400">{slug} (silinmiş ürün)</span>}
                </span>
                <button onClick={() => move(i, -1)} disabled={i === 0}
                  className="text-panel-muted hover:text-panel-ink disabled:opacity-30 px-0.5">↑</button>
                <button onClick={() => move(i, 1)} disabled={i === slugs.length - 1}
                  className="text-panel-muted hover:text-panel-ink disabled:opacity-30 px-0.5">↓</button>
                <button onClick={() => patch({ slugs: slugs.filter(x => x !== slug) })}
                  className="text-red-400 hover:text-red-600 px-0.5">×</button>
              </div>
            ))}
          </div>
        )}
        {slugs.length < 12 && available.length > 0 && (
          <select className="input" value=""
            onChange={e => e.target.value && patch({ slugs: [...slugs, e.target.value] })}>
            <option value="">+ Ürün ekle…</option>
            {available.map(pr => <option key={pr.slug} value={pr.slug}>{pr.title}</option>)}
          </select>
        )}
        {products.length === 0 && (
          <p className="text-xs text-panel-muted">Önce Ürünler sayfasından aktif ürün ekleyin.</p>
        )}
        <p className="text-[11px] text-panel-muted">
          Seçtiğiniz sırayla gösterilir (en fazla 12). Boşsa bölüm vitrinde görünmez.
        </p>
      </>
    )
  }

  if (sec.type === 'products_grid') {
    return (
      <>
        <input className="input" value={s.title || ''} maxLength={80}
          onChange={e => patch({ title: e.target.value })} placeholder="Bölüm başlığı" />
        <div className="grid grid-cols-2 gap-2">
          <label className="block text-sm">
            <span className="text-panel-muted text-xs">Koleksiyon (ops.)</span>
            <select className="input mt-1" value={s.collection || ''}
              onChange={e => patch({ collection: e.target.value || null })}>
              <option value="">Tüm ürünler</option>
              {collections.map(c => <option key={c.slug} value={c.slug}>{c.title}</option>)}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-panel-muted text-xs">Ürün sayısı</span>
            <input className="input mt-1" type="number" min="1" max="24" value={s.limit ?? 8}
              onChange={e => patch({ limit: Number(e.target.value) })} />
          </label>
        </div>
      </>
    )
  }

  if (sec.type === 'rich_text') {
    return (
      <>
        <input className="input" value={s.title || ''} maxLength={100}
          onChange={e => patch({ title: e.target.value })} placeholder="Başlık" />
        <textarea className="input" rows={4} maxLength={2000} value={s.body || ''}
          onChange={e => patch({ body: e.target.value })} placeholder="Metin (satır sonları korunur)" />
      </>
    )
  }

  if (sec.type === 'image_with_text') {
    return (
      <>
        <AssetField label="Görsel" current={s.image}
          onUpload={f => uploadAsset('hero', f, url => patch({ image: url }))}
          onClear={() => patch({ image: null })} />
        <input className="input" value={s.title || ''} maxLength={100}
          onChange={e => patch({ title: e.target.value })} placeholder="Başlık" />
        <textarea className="input" rows={3} maxLength={2000} value={s.body || ''}
          onChange={e => patch({ body: e.target.value })} placeholder="Metin" />
        <div className="grid grid-cols-2 gap-2">
          <input className="input" value={s.cta_text || ''} maxLength={40}
            onChange={e => patch({ cta_text: e.target.value })} placeholder="Buton yazısı (ops.)" />
          <input className="input" value={s.cta_url || ''}
            onChange={e => patch({ cta_url: e.target.value })} placeholder="Buton adresi" />
        </div>
        <div className="flex gap-2 text-xs items-center">
          <span className="text-panel-muted">Görsel tarafı:</span>
          {[['left', 'Sol'], ['right', 'Sağ']].map(([v, l]) => (
            <button key={v} onClick={() => patch({ image_side: v })}
              className={`px-2.5 py-1 rounded-full border ${(s.image_side || 'left') === v
                ? 'border-panel-accent bg-emerald-50 text-emerald-700'
                : 'border-panel-border text-panel-muted'}`}>{l}</button>
          ))}
        </div>
      </>
    )
  }

  if (sec.type === 'faq') {
    const items = s.items || []
    const patchItem = (i, p2) =>
      patch({ items: items.map((it, j) => j === i ? { ...it, ...p2 } : it) })
    return (
      <>
        <input className="input" value={s.title || ''} maxLength={100}
          onChange={e => patch({ title: e.target.value })} placeholder="Bölüm başlığı" />
        <div className="space-y-2">
          {items.map((it, i) => (
            <div key={i} className="border border-panel-border rounded-xl p-2 space-y-1.5">
              <div className="flex gap-1.5">
                <input className="input !py-1.5 text-xs" value={it.q || ''} maxLength={300}
                  onChange={e => patchItem(i, { q: e.target.value })} placeholder="Soru" />
                <button onClick={() => patch({ items: items.filter((_, j) => j !== i) })}
                  className="text-red-400 hover:text-red-600 px-1">×</button>
              </div>
              <textarea className="input !py-1.5 text-xs" rows={2} maxLength={2000} value={it.a || ''}
                onChange={e => patchItem(i, { a: e.target.value })} placeholder="Cevap" />
            </div>
          ))}
        </div>
        {items.length < 12 && (
          <button onClick={() => patch({ items: [...items, { q: '', a: '' }] })}
            className="btn-ghost !py-1 text-xs">+ Soru Ekle</button>
        )}
        <p className="text-[11px] text-panel-muted">
          SSS, Google'da zengin sonuç (FAQ şeması) olarak da işaretlenir.
        </p>
      </>
    )
  }

  if (sec.type === 'newsletter') {
    return (
      <>
        <input className="input" value={s.title || ''} maxLength={100}
          onChange={e => patch({ title: e.target.value })} placeholder="Başlık" />
        <input className="input" value={s.subtitle || ''} maxLength={200}
          onChange={e => patch({ subtitle: e.target.value })} placeholder="Alt başlık (ops.)" />
      </>
    )
  }

  if (sec.type === 'icon_bar') {
    const items = s.items || []
    const patchItem = (i, p2) => patch({ items: items.map((it, j) => j === i ? { ...it, ...p2 } : it) })
    return (
      <>
        {items.map((it, i) => (
          <div key={i} className="flex gap-1.5 items-start">
            <input className="input !py-1.5 text-base !w-14 text-center" value={it.icon || ''} maxLength={8}
              onChange={e => patchItem(i, { icon: e.target.value })} placeholder="🚚" />
            <div className="flex-1 space-y-1">
              <input className="input !py-1.5 text-xs" value={it.title || ''} maxLength={80}
                onChange={e => patchItem(i, { title: e.target.value })} placeholder="Başlık" />
              <input className="input !py-1.5 text-xs" value={it.text || ''} maxLength={200}
                onChange={e => patchItem(i, { text: e.target.value })} placeholder="Kısa açıklama (ops.)" />
            </div>
            <button onClick={() => patch({ items: items.filter((_, j) => j !== i) })}
              className="text-red-400 hover:text-red-600 px-1">×</button>
          </div>
        ))}
        {items.length < 6 && (
          <button onClick={() => patch({ items: [...items, { icon: '✨', title: '', text: '' }] })}
            className="btn-ghost !py-1 text-xs">+ Avantaj Ekle</button>
        )}
      </>
    )
  }

  if (sec.type === 'comparison') {
    const rows = s.rows || []
    const patchRow = (i, p2) => patch({ rows: rows.map((r, j) => j === i ? { ...r, ...p2 } : r) })
    return (
      <>
        <input className="input" value={s.title || ''} maxLength={100}
          onChange={e => patch({ title: e.target.value })} placeholder="Bölüm başlığı" />
        <div className="grid grid-cols-2 gap-2">
          <input className="input !py-1.5 text-xs" value={s.us_label || ''} maxLength={30}
            onChange={e => patch({ us_label: e.target.value })} placeholder="Sol kolon (Biz)" />
          <input className="input !py-1.5 text-xs" value={s.them_label || ''} maxLength={30}
            onChange={e => patch({ them_label: e.target.value })} placeholder="Sağ kolon (Diğerleri)" />
        </div>
        {rows.map((r, i) => (
          <div key={i} className="flex gap-1.5 items-center">
            <input className="input !py-1.5 text-xs flex-1" value={r.feature || ''} maxLength={120}
              onChange={e => patchRow(i, { feature: e.target.value })} placeholder="Özellik" />
            <label className="text-[11px] flex items-center gap-1" title={s.us_label || 'Biz'}>
              <input type="checkbox" checked={!!r.us} onChange={e => patchRow(i, { us: e.target.checked })} />✓
            </label>
            <label className="text-[11px] flex items-center gap-1 text-panel-muted" title={s.them_label || 'Diğerleri'}>
              <input type="checkbox" checked={!!r.them} onChange={e => patchRow(i, { them: e.target.checked })} />✓
            </label>
            <button onClick={() => patch({ rows: rows.filter((_, j) => j !== i) })}
              className="text-red-400 hover:text-red-600 px-1">×</button>
          </div>
        ))}
        {rows.length < 8 && (
          <button onClick={() => patch({ rows: [...rows, { feature: '', us: true, them: false }] })}
            className="btn-ghost !py-1 text-xs">+ Satır Ekle</button>
        )}
      </>
    )
  }

  if (sec.type === 'testimonials') {
    const items = s.items || []
    const patchItem = (i, p2) => patch({ items: items.map((it, j) => j === i ? { ...it, ...p2 } : it) })
    return (
      <>
        <input className="input" value={s.title || ''} maxLength={100}
          onChange={e => patch({ title: e.target.value })} placeholder="Bölüm başlığı" />
        {items.map((it, i) => (
          <div key={i} className="border border-panel-border rounded-xl p-2 space-y-1.5">
            <div className="flex gap-1.5">
              <input className="input !py-1.5 text-xs" value={it.author || ''} maxLength={80}
                onChange={e => patchItem(i, { author: e.target.value })} placeholder="Müşteri adı" />
              <select className="input !py-1.5 text-xs !w-24" value={it.rating ?? 5}
                onChange={e => patchItem(i, { rating: Number(e.target.value) })}>
                {[5, 4, 3, 2, 1].map(n => <option key={n} value={n}>{'★'.repeat(n)}</option>)}
              </select>
              <button onClick={() => patch({ items: items.filter((_, j) => j !== i) })}
                className="text-red-400 hover:text-red-600 px-1">×</button>
            </div>
            <textarea className="input !py-1.5 text-xs" rows={2} maxLength={600} value={it.text || ''}
              onChange={e => patchItem(i, { text: e.target.value })} placeholder="Yorum metni" />
          </div>
        ))}
        {items.length < 6 && (
          <button onClick={() => patch({ items: [...items, { author: '', text: '', rating: 5 }] })}
            className="btn-ghost !py-1 text-xs">+ Yorum Ekle</button>
        )}
        <p className="text-[11px] text-panel-muted">
          Ürün sayfalarındaki gerçek yorumlardan bağımsız, anasayfa vitrini içindir.
        </p>
      </>
    )
  }

  if (sec.type === 'gallery') {
    const images = s.images || []
    return (
      <>
        <input className="input" value={s.title || ''} maxLength={100}
          onChange={e => patch({ title: e.target.value })} placeholder="Bölüm başlığı" />
        <div className="grid grid-cols-4 gap-1.5">
          {images.map((u, i) => (
            <div key={i} className="relative group">
              <img src={u} alt="" className="w-full aspect-square object-cover rounded-lg border border-panel-border" />
              <button onClick={() => patch({ images: images.filter((_, j) => j !== i) })}
                className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-red-500 text-white text-xs
                  opacity-0 group-hover:opacity-100 transition">×</button>
            </div>
          ))}
          {images.length < 8 && (
            <label className="aspect-square rounded-lg border border-dashed border-panel-border
              flex items-center justify-center text-panel-muted cursor-pointer text-lg">
              +
              <input type="file" accept="image/*" className="hidden"
                onChange={e => e.target.files?.[0] && uploadAsset('hero', e.target.files[0],
                  url => patch({ images: [...images, url] }))} />
            </label>
          )}
        </div>
        <p className="text-[11px] text-panel-muted">
          Müşteri fotoğrafları, kullanım kareleri… (en fazla 8 görsel)
        </p>
      </>
    )
  }

  if (sec.type === 'contact') {
    return (
      <>
        <input className="input" value={s.title || ''} maxLength={100}
          onChange={e => patch({ title: e.target.value })} placeholder="Başlık" />
        <input className="input" value={s.subtitle || ''} maxLength={200}
          onChange={e => patch({ subtitle: e.target.value })} placeholder="Alt başlık (ops.)" />
        <p className="text-[11px] text-panel-muted">
          Mesajlar, Ayarlar'daki <b>iletişim e-postanıza</b> gönderilir — orayı doldurmayı unutmayın.
        </p>
      </>
    )
  }

  if (sec.type === 'countdown') {
    return (
      <>
        <input className="input" value={s.title || ''} maxLength={100}
          onChange={e => patch({ title: e.target.value })} placeholder="Başlık" />
        <input className="input" value={s.subtitle || ''} maxLength={200}
          onChange={e => patch({ subtitle: e.target.value })} placeholder="Alt başlık (ops.)" />
        <label className="block text-sm">
          <span className="text-panel-muted text-xs">Bitiş zamanı</span>
          <input className="input mt-1" type="datetime-local"
            value={s.ends_at ? s.ends_at.slice(0, 16) : ''}
            onChange={e => patch({ ends_at: e.target.value ? new Date(e.target.value).toISOString() : '' })} />
        </label>
        <div className="grid grid-cols-2 gap-2">
          <input className="input" value={s.cta_text || ''} maxLength={40}
            onChange={e => patch({ cta_text: e.target.value })} placeholder="Buton yazısı" />
          <input className="input" value={s.cta_url || ''}
            onChange={e => patch({ cta_url: e.target.value })} placeholder="/urunler" />
        </div>
        <p className="text-[11px] text-panel-muted">
          Süre dolunca bölüm vitrinde kendiliğinden kaybolur.
        </p>
      </>
    )
  }

  if (sec.type === 'banner') {
    return (
      <>
        <AssetField label="Banner görseli" current={s.image}
          onUpload={f => uploadAsset('hero', f, url => patch({ image: url }))}
          onClear={() => patch({ image: null })} />
        <input className="input" value={s.url || ''}
          onChange={e => patch({ url: e.target.value })} placeholder="Tıklanınca gidilecek adres (ops.)" />
      </>
    )
  }
  return null
}

function Section({ title, icon, children }) {
  return (
    <section className="card space-y-2.5">
      <h2 className="text-sm font-semibold flex items-center gap-2"><span>{icon}</span> {title}</h2>
      {children}
    </section>
  )
}

function ColorField({ label, value, onChange }) {
  return (
    <label className="block text-sm">
      <span className="text-panel-muted text-xs">{label}</span>
      <div className="mt-1 flex items-center gap-1.5">
        <input type="color" value={value} onChange={e => onChange(e.target.value)}
          className="w-9 h-9 rounded-lg border border-panel-border cursor-pointer p-0.5 bg-white" />
        <input className="input !px-2 font-mono text-xs" value={value}
          onChange={e => onChange(e.target.value)} maxLength={7} />
      </div>
    </label>
  )
}

function Toggle({ checked, onChange, label }) {
  return (
    <label className="flex items-center gap-2 text-sm cursor-pointer">
      <input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} />
      {label}
    </label>
  )
}

function AssetField({ label, current, onUpload, onClear }) {
  return (
    <div className="text-sm">
      <span className="text-panel-muted text-xs">{label}</span>
      <div className="mt-1 flex items-center gap-2">
        {current ? (
          <>
            <img src={current} alt={label} className="h-10 max-w-[120px] object-contain rounded-lg border border-panel-border bg-white p-1" />
            <button onClick={onClear} className="text-xs text-red-400 hover:text-red-600">Kaldır</button>
          </>
        ) : (
          <label className="btn-ghost !py-1.5 text-xs cursor-pointer">
            Dosya seç
            <input type="file" accept="image/png,image/jpeg,image/webp,image/x-icon" className="hidden"
              onChange={e => onUpload(e.target.files?.[0])} />
          </label>
        )}
      </div>
    </div>
  )
}
