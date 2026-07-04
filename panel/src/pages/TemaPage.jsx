import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useStore } from '../lib/store'

// Tema Ayarları — sol form, sağ canlı önizleme (kaydette iframe reload).
const FONTS = [
  { key: 'inter', label: 'Inter (modern, varsayılan)' },
  { key: 'poppins', label: 'Poppins (yuvarlak, samimi)' },
  { key: 'playfair', label: 'Playfair Display (şık, serif)' },
  { key: 'dm-sans', label: 'DM Sans (sade, geometrik)' },
]
const SECTION_LABELS = { hero: 'Hero (karşılama)', featured: 'Koleksiyonlar', products: 'Öne çıkan ürünler' }

export default function TemaPage() {
  const { storeId, store } = useStore()
  const [theme, setTheme] = useState(null)
  const [collections, setCollections] = useState([])
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)
  const [saveCount, setSaveCount] = useState(0)  // iframe reload anahtarı

  const storefrontUrl = store?.config?.storefront_url
    || (store?.config?.shop_domain ? `https://${store.config.shop_domain}` : 'http://localhost:3001')

  const load = useCallback(async () => {
    if (!storeId) return
    try {
      const [t, c] = await Promise.all([
        api.get(`/api/store-settings/${storeId}/theme`),
        api.get(`/api/catalog/collections?store_id=${storeId}`),
      ])
      setTheme(t)
      setCollections(c.filter(x => x.is_active))
    } catch (e) {
      setMsg({ ok: false, text: typeof e?.detail === 'string' ? e.detail : 'Tema yüklenemedi' })
    }
  }, [storeId])
  useEffect(() => { load() }, [load])

  const save = async () => {
    setBusy(true); setMsg(null)
    try {
      setTheme(await api.put(`/api/store-settings/${storeId}/theme`, theme))
      setSaveCount(n => n + 1)
      setMsg({ ok: true, text: 'Tema kaydedildi ✓ (vitrin ~1 dk içinde güncellenir)' })
    } catch (e) {
      setMsg({ ok: false, text: typeof e?.detail === 'string' ? e.detail : 'Kaydedilemedi' })
    } finally { setBusy(false) }
  }

  const uploadAsset = async (kind, file, target) => {
    if (!file) return
    setBusy(true); setMsg(null)
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('kind', kind)
      const r = await api.postForm(`/api/store-settings/${storeId}/assets`, fd)
      target(r.url)
    } catch (e) {
      setMsg({ ok: false, text: typeof e?.detail === 'string' ? e.detail : 'Yükleme başarısız' })
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

  const moveSection = (idx, dir) => {
    setTheme(t => {
      const order = [...t.sections_order]
      const j = idx + dir
      if (j < 0 || j >= order.length) return t
      ;[order[idx], order[j]] = [order[j], order[idx]]
      return { ...t, sections_order: order }
    })
  }

  if (!theme) return <p className="text-sm text-panel-muted">Yükleniyor…</p>

  return (
    <div className="flex gap-5 h-full">
      {/* Sol: form */}
      <div className="w-[380px] shrink-0 space-y-4 overflow-y-auto pb-10">
        <div className="flex items-center gap-2 sticky top-0 bg-panel-bg py-2 z-10">
          <h1 className="text-xl font-semibold">Tema</h1>
          <button onClick={save} disabled={busy} className="btn-primary ml-auto">
            {busy ? 'Kaydediliyor…' : 'Kaydet'}
          </button>
        </div>
        {msg && <p className={`text-xs ${msg.ok ? 'text-emerald-700' : 'text-red-600'}`}>{msg.text}</p>}

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

        <Section title="Hero (Karşılama)" icon="🌅">
          <Toggle checked={theme.hero.enabled}
            onChange={v => set('hero.enabled', v)} label="Hero bölümünü göster" />
          {theme.hero.enabled && (
            <>
              <AssetField label="Arka plan görseli" current={theme.hero.image}
                onUpload={f => uploadAsset('hero', f, url => set('hero.image', url))}
                onClear={() => set('hero.image', null)} />
              <input className="input" value={theme.hero.title} maxLength={100}
                onChange={e => set('hero.title', e.target.value)} placeholder="Başlık" />
              <input className="input" value={theme.hero.subtitle} maxLength={200}
                onChange={e => set('hero.subtitle', e.target.value)} placeholder="Alt başlık" />
              <div className="grid grid-cols-2 gap-2">
                <input className="input" value={theme.hero.cta_text} maxLength={40}
                  onChange={e => set('hero.cta_text', e.target.value)} placeholder="Buton yazısı" />
                <input className="input" value={theme.hero.cta_url}
                  onChange={e => set('hero.cta_url', e.target.value)} placeholder="/urunler" />
              </div>
            </>
          )}
        </Section>

        <Section title="Öne Çıkan Koleksiyonlar" icon="🗂️">
          {collections.length === 0 ? (
            <p className="text-xs text-panel-muted">Önce Koleksiyonlar sayfasından koleksiyon oluşturun.</p>
          ) : (
            <div className="flex gap-2 flex-wrap">
              {collections.map(c => {
                const active = theme.featured_collections.includes(c.slug)
                return (
                  <button key={c.slug}
                    onClick={() => set('featured_collections', active
                      ? theme.featured_collections.filter(s => s !== c.slug)
                      : [...theme.featured_collections, c.slug])}
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
        </Section>

        <Section title="Bölüm Sırası" icon="↕️">
          {theme.sections_order.map((s, i) => (
            <div key={s} className="flex items-center gap-2 bg-panel-input rounded-xl px-3 py-2 text-sm">
              <span>{SECTION_LABELS[s] || s}</span>
              <div className="ml-auto flex gap-1">
                <button onClick={() => moveSection(i, -1)} disabled={i === 0}
                  className="w-6 h-6 rounded-lg border border-panel-border text-xs disabled:opacity-30">↑</button>
                <button onClick={() => moveSection(i, 1)} disabled={i === theme.sections_order.length - 1}
                  className="w-6 h-6 rounded-lg border border-panel-border text-xs disabled:opacity-30">↓</button>
              </div>
            </div>
          ))}
        </Section>

        <Section title="Animasyonlar" icon="✨">
          <Toggle checked={theme.animations.reveal}
            onChange={v => set('animations.reveal', v)} label="Kaydırmada yumuşak belirme" />
          <Toggle checked={theme.animations.hover_zoom}
            onChange={v => set('animations.hover_zoom', v)} label="Ürün görseline yakınlaşma (hover)" />
          <Toggle checked={theme.animations.cart_drawer}
            onChange={v => set('animations.cart_drawer', v)} label="Sepet çekmecesi (yandan kayan)" />
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
          <span className="text-xs text-panel-muted">Önizleme — {storefrontUrl}</span>
          <button onClick={() => setSaveCount(n => n + 1)} className="btn-ghost !py-1 text-xs ml-auto">↻ Yenile</button>
        </div>
        <iframe key={saveCount} src={storefrontUrl} title="Vitrin önizleme"
          className="flex-1 w-full rounded-2xl border border-panel-border bg-white min-h-[70vh]" />
        <p className="text-[11px] text-panel-muted mt-1">
          Vitrin temayı ~1 dakika önbellekler; değişiklik hemen görünmezse Yenile'ye basın.
        </p>
      </div>
    </div>
  )
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
