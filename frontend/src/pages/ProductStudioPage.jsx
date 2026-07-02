import { useEffect, useState } from 'react'
import { api, getToken } from '../lib/api'
import { useToast } from '../components/Toast'

// XHR tabanlı yükleme — fetch'te olmayan upload ilerlemesi (%) için.
function uploadXHR(url, formData, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', url)
    const tok = getToken()
    if (tok) xhr.setRequestHeader('Authorization', `Bearer ${tok}`)
    xhr.upload.onprogress = (e) => { if (e.lengthComputable && onProgress) onProgress(Math.round((e.loaded / e.total) * 100)) }
    xhr.onload = () => {
      let data = null
      try { data = JSON.parse(xhr.responseText) } catch {}
      if (xhr.status >= 200 && xhr.status < 300) resolve(data)
      else reject({ detail: (data && data.detail) || `HTTP ${xhr.status}` })
    }
    xhr.onerror = () => reject({ detail: 'Bağlantı hatası' })
    xhr.send(formData)
  })
}

export default function ProductStudioPage() {
  const toast = useToast()
  const [stores, setStores] = useState([])
  const [storeId, setStoreId] = useState(localStorage.getItem('studio_store') || '')
  const [cfg, setCfg] = useState(null)
  const [files, setFiles] = useState([])
  const [analyzing, setAnalyzing] = useState(false)
  const [items, setItems] = useState([])       // önizleme sonuçları
  const [skipped, setSkipped] = useState([])    // kenara alınan (aspect/hata)
  const [publishing, setPublishing] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [mockupPct, setMockupPct] = useState(null)   // mockup yükleme %
  const [analyzePct, setAnalyzePct] = useState(null) // analiz yükleme %

  useEffect(() => {
    api.get('/api/stores?include_bayii=false').then(s => {
      const list = (Array.isArray(s) ? s : []).filter(x => x.platform !== 'bayii')
      setStores(list)
      if (!storeId && list[0]) { setStoreId(list[0].id); localStorage.setItem('studio_store', list[0].id) }
    }).catch(() => {})
  }, [])

  const loadCfg = async (sid = storeId) => {
    if (!sid) return
    try { setCfg(await api.get(`/api/studio/config?store_id=${sid}`)) } catch { setCfg(null) }
  }
  useEffect(() => { setItems([]); setFiles([]); loadCfg() }, [storeId])

  const uploadMockup = async (f) => {
    if (!f) return
    const fd = new FormData(); fd.append('store_id', storeId); fd.append('file', f)
    setMockupPct(0)
    try {
      const r = await uploadXHR('/api/studio/mockup', fd, setMockupPct)
      setCfg(r); toast.success('Mockup yüklendi')
    } catch (e) { toast.error(e.detail || 'Yüklenemedi') }
    finally { setMockupPct(null) }
  }

  const analyze = async () => {
    if (!files.length) { toast.error('Tasarım görseli seç'); return }
    if (!cfg?.mockup_ready) { toast.error('Önce mockup PSD yükle'); return }
    setAnalyzing(true); setItems([]); setSkipped([]); setAnalyzePct(0)
    try {
      const fd = new FormData(); fd.append('store_id', storeId)
      files.forEach(f => fd.append('files', f))
      const r = await uploadXHR('/api/studio/analyze', fd, setAnalyzePct)
      const ok = (r.items || []).filter(x => x.ok)
      const bad = (r.items || []).filter(x => !x.ok)
      setItems(ok); setSkipped(bad)
      if (ok.length) toast.success(`${ok.length} ürün hazırlandı — kontrol et`)
      if (bad.length) toast.error(`${bad.length} görsel kenara alındı`)
      setFiles([])
    } catch (e) { toast.error(e.detail || 'Analiz başarısız') }
    finally { setAnalyzing(false); setAnalyzePct(null) }
  }

  const setItem = (i, patch) => setItems(arr => arr.map((it, j) => j === i ? { ...it, ...patch } : it))
  const removeItem = (i) => setItems(arr => arr.filter((_, j) => j !== i))

  const publish = async () => {
    if (!items.length) return
    setPublishing(true)
    try {
      const r = await api.post('/api/studio/publish', {
        store_id: storeId,
        items: items.map(it => ({ code: it.code, title: it.title, body_html: it.body_html, tags: it.tags || [] })),
      })
      const res = r.results || []
      const ok = res.filter(x => x.ok).length
      const fail = res.filter(x => !x.ok)
      // sonuçları item'lara işle
      setItems(arr => arr.map(it => {
        const m = res.find(x => x.code === it.code)
        return m ? { ...it, published: m.ok, admin_url: m.admin_url, pub_error: m.error } : it
      }))
      if (ok) toast.success(`${ok} ürün Shopify'a yüklendi`)
      if (fail.length) toast.error(`${fail.length} ürün yüklenemedi`)
    } catch (e) { toast.error(e.detail || 'Yayınlanamadı') }
    finally { setPublishing(false) }
  }

  return (
    <div className="mx-auto w-full max-w-[760px] page-enter pb-16">
      <h1 className="text-2xl font-semibold text-gray-100">🎨 Ürün Stüdyosu</h1>
      <p className="text-sm text-gray-500 mt-1 mb-4">Tasarım yükle → AI analiz + mockup → tek tıkla Shopify ürünü.</p>

      {/* Mağaza + config */}
      <div className="card mb-4">
        <div className="flex items-center gap-2 flex-wrap">
          <select value={storeId} onChange={e => { setStoreId(e.target.value); localStorage.setItem('studio_store', e.target.value) }}
            className="input !text-sm flex-1 min-w-[160px]">
            {stores.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          <button onClick={() => setShowSettings(v => !v)} className="btn-secondary !text-sm">⚙️ Ayarlar</button>
        </div>
        {cfg && (
          <div className="flex items-center gap-2 flex-wrap mt-2 text-[11px]">
            <span className={`px-2 py-0.5 rounded-full ${cfg.mockup_ready ? 'bg-emerald-500/15 text-emerald-300' : 'bg-amber-500/15 text-amber-300'}`}>
              {cfg.mockup_ready ? '✓ Mockup hazır' : '⚠ Mockup yüklenmedi'}
            </span>
            <span className="text-gray-500">Marka: <b className="text-gray-300">{cfg.brand}</b></span>
            <span className="text-gray-500">Kod öneki: <b className="text-gray-300">{cfg.prefix}</b></span>
            <span className="text-gray-500">Fiyat: <b className="text-gray-300">{cfg.price || '—'}</b></span>
          </div>
        )}
        {showSettings && cfg && <StudioSettings cfg={cfg} storeId={storeId} onSaved={loadCfg} onMockup={uploadMockup} mockupPct={mockupPct} />}
      </div>

      {/* Tasarım yükleme */}
      {cfg?.mockup_ready && (
        <div className="card mb-4">
          <label className="block border border-dashed border-brand-border rounded-lg p-6 text-center text-sm text-gray-400 cursor-pointer hover:border-accent">
            {files.length ? `${files.length} görsel seçildi — değiştir` : '🖼 Tasarım görsellerini seç (çoklu)'}
            <input type="file" accept="image/png,image/jpeg,image/webp" multiple className="hidden"
              onChange={e => setFiles(Array.from(e.target.files || []))} />
          </label>
          {files.length > 0 && (
            <div className="flex gap-1.5 mt-2 overflow-x-auto no-scrollbar">
              {files.map((f, i) => <img key={i} src={URL.createObjectURL(f)} alt="" className="w-12 h-12 rounded object-cover shrink-0" />)}
            </div>
          )}
          <button onClick={analyze} disabled={analyzing || !files.length} className="btn-primary w-full !text-sm mt-3 disabled:opacity-50">
            {analyzing ? 'İşleniyor…' : '✨ Analiz Et'}
          </button>
          {analyzing && (
            <div className="mt-2">
              {analyzePct !== null && analyzePct < 100
                ? <Bar pct={analyzePct} label={`Görseller yükleniyor · %${analyzePct}`} />
                : <Bar indeterminate label="🤖 AI analiz + mockup üretiliyor… (görsel başına birkaç saniye)" />}
            </div>
          )}
        </div>
      )}

      {/* Kenara alınanlar */}
      {skipped.length > 0 && (
        <div className="card mb-4 border-amber-500/30">
          <div className="text-xs font-medium text-amber-300 mb-1.5">⚠ {skipped.length} görsel kenara alındı</div>
          <ul className="space-y-1 text-[11px] text-gray-400">
            {skipped.map((s, i) => <li key={i}>• <b className="text-gray-300">{s.filename || 'görsel'}</b>: {s.error}</li>)}
          </ul>
        </div>
      )}

      {/* Önizlemeler */}
      {items.length > 0 && (
        <>
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-sm font-medium text-gray-200">{items.length} ürün hazır</h2>
            <button onClick={publish} disabled={publishing} className="btn-primary !text-sm disabled:opacity-50">
              {publishing ? 'Yükleniyor…' : `🚀 Shopify'a Yükle (${items.filter(i => !i.published).length})`}
            </button>
          </div>
          <div className="space-y-3">
            {items.map((it, i) => (
              <PreviewCard key={it.code} it={it} onChange={(p) => setItem(i, p)} onRemove={() => removeItem(i)} />
            ))}
          </div>
        </>
      )}
    </div>
  )
}

function Bar({ pct, indeterminate, label }) {
  return (
    <div>
      <div className="h-2 rounded-full bg-brand-input overflow-hidden">
        <div className={`h-full bg-accent ${indeterminate ? 'animate-pulse w-full' : ''}`}
          style={indeterminate ? undefined : { width: `${pct || 0}%`, transition: 'width .2s' }} />
      </div>
      {label && <div className="text-[11px] text-gray-500 mt-1">{label}</div>}
    </div>
  )
}

function StudioSettings({ cfg, storeId, onSaved, onMockup, mockupPct }) {
  const toast = useToast()
  const [price, setPrice] = useState(cfg.price || '')
  const [prefix, setPrefix] = useState(cfg.prefix || '')
  const [marka, setMarka] = useState(cfg.brand || '')
  const [aiExpand, setAiExpand] = useState(!!cfg.ai_expand)
  const [aiProvider, setAiProvider] = useState(cfg.ai_provider || 'auto')
  const anyProvider = cfg.fal_ready || cfg.gemini_ready
  const save = async () => {
    try {
      await api.patch('/api/studio/config', { store_id: storeId, price, prefix, marka_adi: marka, ai_expand: aiExpand, ai_provider: aiProvider })
      toast.success('Kaydedildi'); onSaved()
    } catch (e) { toast.error(e.detail || 'Kaydedilemedi') }
  }
  return (
    <div className="mt-3 pt-3 border-t border-brand-border/60 grid sm:grid-cols-3 gap-2">
      <Field label="Marka adı (başlıkta)"><input className="input w-full !text-sm" value={marka} onChange={e => setMarka(e.target.value)} /></Field>
      <Field label="Kod öneki"><input className="input w-full !text-sm" value={prefix} onChange={e => setPrefix(e.target.value)} placeholder="B" /></Field>
      <Field label="Varsayılan fiyat"><input className="input w-full !text-sm" value={price} onChange={e => setPrice(e.target.value)} placeholder="örn. 299.90" /></Field>

      {/* AI ile görsel genişletme (outpaint) */}
      <div className="sm:col-span-3 rounded-lg bg-brand-input/30 border border-brand-border/60 p-2.5">
        <label className="flex items-center gap-2 cursor-pointer text-sm text-gray-200">
          <input type="checkbox" checked={aiExpand} onChange={e => setAiExpand(e.target.checked)} className="accent-accent" disabled={!anyProvider} />
          🪄 Oran uymayan görselleri AI ile genişlet (alta yasla, üstü doldur → 1:2)
        </label>
        <div className="flex items-center gap-2 mt-2 flex-wrap text-xs">
          <span className="text-gray-500">Sağlayıcı:</span>
          <select className="input !text-xs !py-1" value={aiProvider} onChange={e => setAiProvider(e.target.value)} disabled={!aiExpand}>
            <option value="auto">Otomatik (varsa fal.ai, yoksa Gemini)</option>
            <option value="fal">fal.ai (FLUX Fill)</option>
            <option value="gemini">Gemini</option>
          </select>
          <span className={`px-1.5 py-0.5 rounded-full text-[10px] ${cfg.fal_ready ? 'bg-emerald-500/15 text-emerald-300' : 'bg-brand-input text-gray-500'}`}>fal.ai {cfg.fal_ready ? '✓' : 'anahtar yok'}</span>
          <span className={`px-1.5 py-0.5 rounded-full text-[10px] ${cfg.gemini_ready ? 'bg-emerald-500/15 text-emerald-300' : 'bg-brand-input text-gray-500'}`}>Gemini {cfg.gemini_ready ? '✓' : 'anahtar yok'}</span>
        </div>
        {!anyProvider && <p className="text-[10px] text-amber-300 mt-1.5">Aktifleştirmek için .env'e FAL_KEY ve/veya GEMINI_API_KEY ekleyip backend'i yeniden başlat.</p>}
      </div>

      <div className="sm:col-span-3 flex items-center justify-between gap-2 flex-wrap">
        <label className={`text-xs cursor-pointer hover:underline ${mockupPct != null ? 'text-gray-500 pointer-events-none' : 'text-accent'}`}>
          📎 Mockup PSD yükle {cfg.mockup_ready && '(değiştir)'}
          <input type="file" accept=".psd,.psb" className="hidden" disabled={mockupPct != null} onChange={e => onMockup(e.target.files?.[0])} />
        </label>
        <button onClick={save} className="btn-primary !text-xs">Ayarları Kaydet</button>
      </div>
      {mockupPct != null && (
        <div className="sm:col-span-3">
          <Bar pct={mockupPct} indeterminate={mockupPct >= 100} label={mockupPct < 100 ? `Mockup yükleniyor · %${mockupPct}` : 'İşleniyor…'} />
        </div>
      )}
    </div>
  )
}

function PreviewCard({ it, onChange, onRemove }) {
  const [open, setOpen] = useState(false)
  return (
    <div className={`card ${it.published ? 'border-emerald-500/40' : ''}`}>
      <div className="flex gap-3">
        <img src={it.mockup_url} alt="" className="w-24 h-24 rounded-lg object-cover bg-brand-input shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent/15 text-accent font-mono">{it.code}</span>
            {it.ai_expanded && <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/15 text-purple-300" title="Oran uymadığı için üstü AI ile genişletildi">🪄 AI genişletildi</span>}
            {it.published ? <span className="text-[10px] text-emerald-300">✓ Yüklendi</span>
              : it.pub_error ? <span className="text-[10px] text-red-300" title={it.pub_error}>⚠ {it.pub_error}</span> : null}
            <button onClick={onRemove} className="ml-auto text-gray-500 hover:text-red-300 text-sm">×</button>
          </div>
          <input className="input w-full !text-sm mb-1" value={it.title} onChange={e => onChange({ title: e.target.value })} />
          <div className="flex flex-wrap gap-1">
            {(it.tags || []).slice(0, 6).map((t, i) => <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-brand-input text-gray-400">{t}</span>)}
          </div>
        </div>
      </div>
      <div className="flex items-center gap-3 mt-2 text-[11px]">
        <button onClick={() => setOpen(o => !o)} className="text-gray-400 hover:text-gray-200">{open ? '▲ Açıklamayı gizle' : '▼ Açıklama'}</button>
        <a href={it.mockup_url} download={`${it.code}_mockup.jpg`} className="text-accent hover:underline">⬇ mockup.jpg</a>
        <a href={it.baski_url} download={`${it.code}_baski.jpg`} className="text-accent hover:underline">⬇ baskı.jpg</a>
        {it.admin_url && <a href={it.admin_url} target="_blank" rel="noreferrer" className="text-emerald-300 hover:underline ml-auto">Shopify'da aç →</a>}
      </div>
      {open && (
        <textarea className="input w-full !text-xs mt-2 font-mono" rows={5} value={it.body_html} onChange={e => onChange({ body_html: e.target.value })} />
      )}
    </div>
  )
}

function Field({ label, children }) {
  return <div><label className="block text-[10px] uppercase text-gray-500 mb-1">{label}</label>{children}</div>
}
