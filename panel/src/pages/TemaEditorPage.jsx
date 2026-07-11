import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'
import { useStore } from '../lib/store'
import { useToast } from '../components/Toast'
import {
  FONTS, SECTION_TYPES, SECTION_DEFAULTS,
  SectionSettings, Section, ColorField, Toggle, AssetField,
} from '../components/ThemeEditorParts'

// Tam ekran tema editörü (Shopify tarzı) — sol ayar paneli + sağ canlı önizleme.
// ?taslak=<key> ile taslak tema, parametresiz yayındaki tema düzenlenir.
// Önizlemede bir bölüme tıklanınca sol panel o bölümün ayarlarına geçer.
export default function TemaEditorPage() {
  const { storeId, store } = useStore()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const draftKey = searchParams.get('taslak')
  const toast = useToast()

  const [theme, setTheme] = useState(null)
  const [draftName, setDraftName] = useState('')
  const [collections, setCollections] = useState([])
  const [products, setProducts] = useState([])
  const [busy, setBusy] = useState(false)
  const [saveCount, setSaveCount] = useState(0)   // iframe reload anahtarı
  const [device, setDevice] = useState('desktop')
  const [openSection, setOpenSection] = useState(null) // dolu ise tek-bölüm modu
  const [customCode, setCustomCode] = useState(null)
  const [presets, setPresets] = useState([])
  const [dragIdx, setDragIdx] = useState(null)   // sürüklenen bölüm indeksi
  const [overIdx, setOverIdx] = useState(null)   // üzerine gelinen indeks
  const initialRef = useRef('')

  const storefrontUrl = store?.config?.storefront_url
    || (store?.config?.shop_domain ? `https://${store.config.shop_domain}` : 'http://localhost:3001')
  const iframeRef = useRef(null)
  const previewTimer = useRef(null)
  const skipFirst = useRef(true)

  // CANLI ÖNİZLEME: değişiklikten 800ms sonra taslağı gönder, iframe'i tazele
  useEffect(() => {
    if (!theme || !storeId) return
    if (skipFirst.current) { skipFirst.current = false; return }
    clearTimeout(previewTimer.current)
    previewTimer.current = setTimeout(async () => {
      try {
        await api.put(`/api/store-settings/${storeId}/theme/preview`, theme)
        iframeRef.current?.contentWindow?.location.reload()
      } catch { /* önizleme başarısız — kaydetmeyi engellemez */ }
    }, 800)
    return () => clearTimeout(previewTimer.current)
  }, [theme, storeId])

  // Önizlemede bölüme tıklanınca sol panel o bölümün ayarına geçer
  useEffect(() => {
    const onMsg = (e) => {
      if (e.data?.type === 'vitrin-sec-click' && e.data.id) setOpenSection(e.data.id)
    }
    window.addEventListener('message', onMsg)
    return () => window.removeEventListener('message', onMsg)
  }, [])

  const load = useCallback(async () => {
    if (!storeId) return
    try {
      const [c, cc, pr] = await Promise.all([
        api.get(`/api/catalog/collections?store_id=${storeId}`),
        api.get(`/api/store-settings/${storeId}/custom-code`),
        api.get(`/api/catalog/products?store_id=${storeId}&status=active`),
      ])
      setCollections(c.filter(x => x.is_active))
      setProducts(pr)
      setCustomCode(cc)
      api.get(`/api/store-settings/${storeId}/theme/presets`)
        .then(setPresets).catch(() => {})

      let t
      if (draftKey) {
        const { drafts } = await api.get(`/api/store-settings/${storeId}/theme/drafts`)
        const d = drafts.find(x => x.key === draftKey)
        if (!d) { toast.error('Taslak bulunamadı'); navigate('/tema'); return }
        t = d.theme
        setDraftName(d.name)
        // Önizleme taslağı göstersin (yayındaki temayı değil)
        skipFirst.current = true
        api.put(`/api/store-settings/${storeId}/theme/preview`, t)
          .then(() => setSaveCount(n => n + 1)).catch(() => {})
      } else {
        t = await api.get(`/api/store-settings/${storeId}/theme`)
      }
      setTheme(t)
      initialRef.current = JSON.stringify([t, cc])
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Tema yüklenemedi')
    }
  }, [storeId, draftKey])
  useEffect(() => { load() }, [load])

  const save = async () => {
    setBusy(true)
    try {
      if (draftKey) {
        await Promise.all([
          api.put(`/api/store-settings/${storeId}/theme/drafts/${draftKey}`, { theme }),
          customCode ? api.put(`/api/store-settings/${storeId}/custom-code`, customCode) : Promise.resolve(),
        ])
        initialRef.current = JSON.stringify([theme, customCode])
        toast.success('Taslak kaydedildi (yayında değişiklik yok)')
      } else {
        const [t] = await Promise.all([
          api.put(`/api/store-settings/${storeId}/theme`, theme),
          customCode ? api.put(`/api/store-settings/${storeId}/custom-code`, customCode) : Promise.resolve(),
        ])
        setTheme(t)
        initialRef.current = JSON.stringify([t, customCode])
        api.del(`/api/store-settings/${storeId}/theme/preview`).catch(() => {})
        setSaveCount(n => n + 1)
        toast.success('Tema kaydedildi ve yayında ✓')
      }
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Kaydedilemedi')
    } finally { setBusy(false) }
  }

  const publish = async () => {
    if (!window.confirm(`"${draftName}" yayına alınacak — vitrindeki tema değişir. `
        + `Şu anki yayın, taslak olarak saklanır. Devam?`)) return
    setBusy(true)
    try {
      if (dirty) await api.put(`/api/store-settings/${storeId}/theme/drafts/${draftKey}`, { theme })
      await api.post(`/api/store-settings/${storeId}/theme/drafts/${draftKey}/publish`)
      toast.success('Tema yayında ✓')
      navigate('/tema')
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Yayınlanamadı')
    } finally { setBusy(false) }
  }

  const discard = () => {
    try {
      const [t, cc] = JSON.parse(initialRef.current)
      setTheme(t); setCustomCode(cc)
      const after = draftKey
        ? api.put(`/api/store-settings/${storeId}/theme/preview`, t)
        : api.del(`/api/store-settings/${storeId}/theme/preview`)
      after.then(() => iframeRef.current?.contentWindow?.location.reload()).catch(() => {})
    } catch { /* ilk yükleme yoksa */ }
  }
  const dirty = !!theme && initialRef.current !== '' &&
    JSON.stringify([theme, customCode]) !== initialRef.current

  const goBack = () => {
    if (dirty && !window.confirm('Kaydedilmemiş değişiklikler var — çıkılsın mı?')) return
    if (draftKey) api.del(`/api/store-settings/${storeId}/theme/preview`).catch(() => {})
    navigate('/tema')
  }

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
  const dropSec = (from, to) => {
    setDragIdx(null); setOverIdx(null)
    if (from === null || to === null || from === to) return
    setTheme(t => {
      const arr = [...t.sections]
      const [moved] = arr.splice(from, 1)
      arr.splice(to, 0, moved)
      return { ...t, sections: arr }
    })
  }
  const removeSec = (id) => {
    if (!window.confirm('Bu bölüm anasayfadan kaldırılacak. Emin misiniz?')) return
    setTheme(t => ({ ...t, sections: t.sections.filter(s => s.id !== id) }))
    setOpenSection(o => (o === id ? null : o))
  }
  const addSec = (type) => {
    const id = `${type}-${Date.now().toString(36)}`
    setTheme(t => ({
      ...t,
      sections: [...t.sections, { id, type, settings: structuredClone(SECTION_DEFAULTS[type]) }],
    }))
    setOpenSection(id)
  }

  if (!theme) {
    return (
      <div className="h-screen flex items-center justify-center text-sm text-panel-muted">
        Tema yükleniyor…
      </div>
    )
  }

  const activeSec = openSection ? theme.sections.find(s => s.id === openSection) : null
  const activeIdx = activeSec ? theme.sections.findIndex(s => s.id === openSection) : -1

  return (
    <div className="h-screen flex flex-col bg-panel-input/40">
      {/* Üst çubuk */}
      <header className="h-14 shrink-0 bg-white border-b border-panel-border flex items-center gap-3 px-4">
        <button onClick={goBack} className="btn-ghost !py-1.5 text-xs">← Temalar</button>
        <div className="min-w-0">
          <div className="text-sm font-semibold truncate">
            {draftKey ? draftName || 'Taslak' : 'Yayındaki Tema'}
          </div>
          <div className="text-[10px] leading-none">
            {draftKey ? (
              <span className="text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded-full">Taslak — yayını etkilemez</span>
            ) : (
              <span className="text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded-full">● Yayında</span>
            )}
          </div>
        </div>
        <div className="flex gap-1 bg-panel-input rounded-lg p-0.5 ml-auto">
          {[['desktop', '🖥 Masaüstü'], ['mobile', '📱 Mobil']].map(([k, l]) => (
            <button key={k} onClick={() => setDevice(k)}
              className={`px-2.5 py-1 rounded-md text-xs transition ${device === k
                ? 'bg-white shadow-sm font-medium' : 'text-panel-muted hover:text-panel-ink'}`}>
              {l}
            </button>
          ))}
        </div>
        <button onClick={() => setSaveCount(n => n + 1)} className="btn-ghost !py-1.5 text-xs">↻</button>
        {dirty && (
          <button onClick={discard} disabled={busy} className="btn-ghost !py-1.5 text-xs">
            Vazgeç
          </button>
        )}
        <button onClick={save} disabled={busy || !dirty}
          className="px-4 py-1.5 rounded-xl text-xs font-medium bg-panel-accent text-white disabled:opacity-40">
          {busy ? '…' : draftKey ? 'Taslağı Kaydet' : 'Kaydet ve Yayınla'}
        </button>
        {draftKey && (
          <button onClick={publish} disabled={busy}
            className="px-4 py-1.5 rounded-xl text-xs font-medium bg-emerald-600 text-white disabled:opacity-40">
            🚀 Yayınla
          </button>
        )}
      </header>

      <div className="flex-1 flex min-h-0">
        {/* Sol panel */}
        <div className="w-[400px] shrink-0 bg-white border-r border-panel-border overflow-y-auto p-4 space-y-4">
          {activeSec ? (
            /* ── Tek bölüm modu — önizlemede tıklanan/lısteden seçilen bölüm ── */
            <>
              <div className="flex items-center gap-2 sticky -top-4 -mx-4 px-4 py-2.5 bg-white border-b border-panel-border z-10">
                <button onClick={() => setOpenSection(null)} className="btn-ghost !py-1 text-xs">← Geri</button>
                <span className="text-sm font-semibold truncate">
                  {(SECTION_TYPES[activeSec.type] || { icon: '▫️', label: activeSec.type }).icon}{' '}
                  {(SECTION_TYPES[activeSec.type] || { label: activeSec.type }).label}
                </span>
                {activeSec.hidden && (
                  <span className="text-[10px] bg-slate-200 text-slate-600 px-1.5 py-0.5 rounded-full">gizli</span>
                )}
              </div>
              <div className="flex items-center gap-1.5 text-xs">
                <button onClick={() => patchSectionMeta(activeSec.id, { hidden: !activeSec.hidden })}
                  className="btn-ghost !py-1 text-xs">
                  {activeSec.hidden ? '🙈 Gizli — göster' : '👁 Görünür — gizle'}
                </button>
                <button onClick={() => moveSec(activeIdx, -1)} disabled={activeIdx === 0}
                  className="w-7 h-7 rounded-lg border border-panel-border disabled:opacity-30">↑</button>
                <button onClick={() => moveSec(activeIdx, 1)} disabled={activeIdx === theme.sections.length - 1}
                  className="w-7 h-7 rounded-lg border border-panel-border disabled:opacity-30">↓</button>
                <button onClick={() => removeSec(activeSec.id)}
                  className="ml-auto text-red-400 hover:text-red-600">Bölümü Sil</button>
              </div>
              <div className="flex items-center gap-2 text-xs text-panel-muted">
                Zemin:
                {[['none', 'Sayfa rengi'], ['band', 'Beyaz bant']].map(([v, l]) => (
                  <button key={v} onClick={() => patchSectionMeta(activeSec.id, { scheme: v })}
                    className={`px-2 py-0.5 rounded-full border ${(activeSec.scheme || 'none') === v
                      ? 'border-panel-accent bg-emerald-50 text-emerald-700'
                      : 'border-panel-border'}`}>{l}</button>
                ))}
              </div>
              <div className="space-y-2">
                <SectionSettings sec={activeSec} collections={collections} products={products}
                  patch={p => patchSection(activeSec.id, p)} uploadAsset={uploadAsset} />
              </div>
            </>
          ) : (
            /* ── Liste modu — genel ayarlar + bölüm listesi ── */
            <>
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
                {theme.logo_url && (
                  <label className="block text-sm">
                    <span className="text-panel-muted text-xs">
                      Logo genişliği: <b>{theme.logo_width || 120}px</b>
                    </span>
                    <input type="range" min="60" max="320" step="10"
                      value={theme.logo_width || 120}
                      onChange={e => set('logo_width', Number(e.target.value))}
                      className="w-full mt-1 accent-emerald-600" />
                  </label>
                )}
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

              <Section title="Sepet Kampanya Mesajları" icon="🛒">
                <p className="text-[11px] text-panel-muted -mt-1">
                  X Al Y Öde kampanyası aktifken sepette görünen yazılar.
                  Yer tutucular: <code>{'{x}'}</code> <code>{'{y}'}</code> <code>{'{kalan}'}</code>
                </p>
                <label className="block text-sm">
                  <span className="text-panel-muted text-xs">Hedefe yaklaşırken</span>
                  <input className="input mt-1" maxLength={200}
                    value={theme.cart_messages?.bxgy_progress || ''}
                    onChange={e => set('cart_messages.bxgy_progress', e.target.value)} />
                </label>
                <label className="block text-sm">
                  <span className="text-panel-muted text-xs">Hedefe ulaşınca</span>
                  <input className="input mt-1" maxLength={200}
                    value={theme.cart_messages?.bxgy_reached || ''}
                    onChange={e => set('cart_messages.bxgy_reached', e.target.value)} />
                </label>
              </Section>

              <Section title="Güven Şeridi" icon="🛡️">
                <Toggle checked={theme.trust_badges?.enabled !== false}
                  onChange={v => set('trust_badges.enabled', v)}
                  label="Ürün ve ödeme sayfasında güven rozetleri (SSL, iade, kargo) göster" />
              </Section>

              {/* ── Bölüm listesi — tıklanan bölüm tek-bölüm modunda açılır ── */}
              <Section title={`Anasayfa Bölümleri (${theme.sections.length})`} icon="🧱">
                <div className="space-y-1.5">
                  {theme.sections.map((sec, i) => {
                    const meta = SECTION_TYPES[sec.type] || { label: sec.type, icon: '▫️' }
                    return (
                      <div key={sec.id} draggable
                        onDragStart={e => { setDragIdx(i); e.dataTransfer.effectAllowed = 'move' }}
                        onDragOver={e => { e.preventDefault(); if (overIdx !== i) setOverIdx(i) }}
                        onDrop={() => dropSec(dragIdx, i)}
                        onDragEnd={() => { setDragIdx(null); setOverIdx(null) }}
                        className={`flex items-center gap-2 px-3 py-2 rounded-xl border transition
                          bg-panel-input/60 hover:border-panel-accent ${sec.hidden ? 'opacity-55' : ''} ${
                          dragIdx === i ? 'opacity-40 border-dashed border-panel-accent'
                            : overIdx === i && dragIdx !== null ? 'border-panel-accent ring-1 ring-emerald-200'
                              : 'border-panel-border'}`}>
                        <span className="cursor-grab active:cursor-grabbing text-panel-muted select-none"
                          title="Sürükleyerek sırala">⠿</span>
                        <button onClick={() => setOpenSection(sec.id)}
                          className="flex items-center gap-2 text-sm font-medium flex-1 text-left min-w-0">
                          <span>{meta.icon}</span>
                          <span className="truncate">{meta.label}</span>
                          {sec.hidden && (
                            <span className="text-[10px] bg-slate-200 text-slate-600 px-1.5 py-0.5 rounded-full shrink-0">gizli</span>
                          )}
                          <span className="text-panel-muted text-xs ml-auto shrink-0">Düzenle ›</span>
                        </button>
                        <button onClick={() => moveSec(i, -1)} disabled={i === 0}
                          className="w-6 h-6 rounded-lg border border-panel-border text-xs disabled:opacity-30">↑</button>
                        <button onClick={() => moveSec(i, 1)} disabled={i === theme.sections.length - 1}
                          className="w-6 h-6 rounded-lg border border-panel-border text-xs disabled:opacity-30">↓</button>
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

              <Section title="Alt Bilgi (Footer)" icon="⬇️">
                <label className="block text-sm">
                  <span className="text-panel-muted text-xs">Hakkında metni (footer'da görünür)</span>
                  <textarea className="input mt-1" rows={3} maxLength={500}
                    value={theme.footer?.about || ''}
                    onChange={e => set('footer.about', e.target.value)} />
                </label>
                <label className="block text-sm">
                  <span className="text-panel-muted text-xs">Instagram kullanıcı adı</span>
                  <input className="input mt-1" value={theme.footer?.instagram || ''} maxLength={60}
                    onChange={e => set('footer.instagram', e.target.value)} placeholder="@magazam" />
                </label>
              </Section>

              <Section title="Özel Kod (Gelişmiş)" icon="⚡">
                <p className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-2.5 py-1.5">
                  ⚠️ Buraya eklenen kod vitrininizde aynen çalışır — yalnızca güvendiğiniz
                  kodu ekleyin. Özel kod temadan bağımsızdır (taslakta da kaydedilse yayına yansır).
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
            </>
          )}
        </div>

        {/* Sağ: canlı önizleme */}
        <div className="flex-1 min-w-0 flex flex-col p-3">
          <div className={`flex-1 min-h-0 ${device === 'mobile'
            ? 'flex justify-center bg-panel-input/50 rounded-2xl py-4' : ''}`}>
            <iframe key={`${saveCount}-${device}`} ref={iframeRef}
              src={`${storefrontUrl}/?onizleme=1`} title="Vitrin önizleme"
              className={device === 'mobile'
                ? 'w-[390px] h-full rounded-[2rem] border-8 border-zinc-800 bg-white shadow-xl'
                : 'w-full h-full rounded-2xl border border-panel-border bg-white'} />
          </div>
          <p className="text-[11px] text-panel-muted mt-1.5 px-1">
            ⚡ Canlı önizleme: değişiklikler ~1 sn içinde yansır (kaydetmeden yayınlanmaz).
            Önizlemede bir bölüme tıklayın — ayarları solda açılır.
          </p>
        </div>
      </div>
    </div>
  )
}
