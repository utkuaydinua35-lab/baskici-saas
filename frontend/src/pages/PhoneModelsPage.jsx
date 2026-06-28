import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { useToast } from '../components/Toast'

const EMPTY = {
  display_name: '', brand: '', width_cm: '', height_cm: '', radius_cm: '', notes: '',
}

export default function PhoneModelsPage() {
  const toast = useToast()
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [baselineCount, setBaselineCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  const [form, setForm] = useState(EMPTY)
  const [editId, setEditId] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState(null)

  const [mockupModel, setMockupModel] = useState(null)
  const [testInput, setTestInput] = useState('')
  const [testRes, setTestRes] = useState(null)
  const [testing, setTesting] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (search) params.set('search', search)
      const r = await api.get(`/api/phone-models?${params}`)
      setItems(r.items || [])
      setTotal(r.db_total || 0)
      setBaselineCount(r.baseline_count || 0)
    } catch {
      setItems([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])
  useEffect(() => {
    const t = setTimeout(load, 400)
    return () => clearTimeout(t)
    // eslint-disable-next-line
  }, [search])

  const openCreate = () => {
    setForm(EMPTY); setEditId(null); setShowForm(true); setMsg(null)
  }
  const openEdit = (m) => {
    setForm({
      display_name: m.display_name || '',
      brand: m.brand || '',
      width_cm: m.width_cm ?? '',
      height_cm: m.height_cm ?? '',
      radius_cm: m.radius_cm ?? '',
      notes: m.notes || '',
    })
    setEditId(m.id); setShowForm(true); setMsg(null)
  }

  const save = async () => {
    setSaving(true); setMsg(null)
    const payload = {
      display_name: form.display_name.trim(),
      brand: form.brand.trim() || null,
      width_cm: parseFloat(form.width_cm),
      height_cm: parseFloat(form.height_cm),
      radius_cm: form.radius_cm === '' ? 0 : parseFloat(form.radius_cm),
      notes: form.notes.trim() || null,
    }
    if (!payload.display_name || isNaN(payload.width_cm) || isNaN(payload.height_cm)) {
      setMsg({ ok: false, text: 'Model adı, genişlik ve yükseklik zorunlu.' })
      setSaving(false); return
    }
    try {
      if (editId) {
        await api.patch(`/api/phone-models/${editId}`, payload)
        setMsg({ ok: true, text: 'Model güncellendi.' })
      } else {
        const r = await api.post('/api/phone-models', payload)
        setMsg({
          ok: true,
          text: r.overrides_baseline
            ? 'Model eklendi — baseline ölçüsünü EZİYOR (override).'
            : 'Yeni model eklendi.',
        })
      }
      setShowForm(false); setForm(EMPTY); setEditId(null)
      load()
    } catch (e) {
      setMsg({ ok: false, text: typeof e?.detail === 'string' ? e.detail : 'Kaydedilemedi' })
    } finally {
      setSaving(false)
    }
  }

  const remove = async (m) => {
    if (!confirm(`"${m.display_name}" silinecek. Bu modelde baseline ölçüsü varsa tekrar ona düşülür. Emin misin?`)) return
    try {
      await api.del(`/api/phone-models/${m.id}`)
      load()
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Silinemedi')
    }
  }

  const runTest = async () => {
    if (!testInput.trim()) return
    setTesting(true); setTestRes(null)
    try {
      const r = await api.post('/api/phone-models/check', { model: testInput.trim() })
      setTestRes(r)
    } catch (e) {
      setTestRes({ error: typeof e?.detail === 'string' ? e.detail : 'Hata' })
    } finally {
      setTesting(false)
    }
  }

  return (
    <div className="max-w-[1400px]">
      <div className="flex items-start justify-between mb-5 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-gray-100">📱 Telefon Modelleri</h1>
          <p className="text-sm text-gray-500 mt-1">
            Yeni telefon çıkınca veya bir ölçü yanlışsa buradan ekle/düzelt. Eklenen model
            baseline kataloğunu ezer — deploy gerekmez.
          </p>
        </div>
        <button onClick={openCreate} className="btn-primary !text-sm">+ Yeni Model</button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <Kpi label="EKLENEN MODEL" value={total} color="accent" />
        <Kpi label="BASELINE KATALOG" value={baselineCount} color="gray" />
      </div>

      {/* Tanıma testi */}
      <div className="card mb-4 !p-3">
        <div className="text-xs text-gray-400 mb-2">
          Model tanınıyor mu? Sipariş eşleşmesi için modelin sistemde olup olmadığını test et.
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          <input
            type="text"
            placeholder="ör: iPhone 16 Pro Max"
            value={testInput}
            onChange={e => setTestInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && runTest()}
            className="input !text-xs !py-1.5 flex-1 min-w-[220px]"
          />
          <button onClick={runTest} disabled={testing} className="btn-secondary !text-sm disabled:opacity-50">
            {testing ? 'Kontrol...' : 'Test Et'}
          </button>
        </div>
        {testRes && (
          <div className="mt-2 text-xs">
            {testRes.error ? (
              <span className="text-red-400">✗ {testRes.error}</span>
            ) : testRes.recognized ? (
              <div className="text-emerald-300">
                ✓ Tanındı —{' '}
                <span className="text-gray-400">
                  anahtar: <span className="font-mono">{testRes.normalized_key}</span> · kaynak:{' '}
                  {testRes.source === 'db'
                    ? <span className="text-accent">eklenen model</span>
                    : <span className="text-gray-300">baseline katalog</span>}
                </span>
                {testRes.source === 'db' && testRes.width_cm != null && (
                  <span className="text-gray-400">
                    {' '}· {testRes.width_cm} × {testRes.height_cm} cm · r={testRes.radius_cm}
                  </span>
                )}
              </div>
            ) : (
              <span className="text-amber-400">
                ⚠ Tanınmadı (anahtar: <span className="font-mono">{testRes.normalized_key}</span>).
                Yukarıdan "+ Yeni Model" ile ekleyebilirsin.
              </span>
            )}
          </div>
        )}
      </div>

      {msg && (
        <div className={`text-sm rounded-lg px-3 py-2 mb-3 border ${
          msg.ok
            ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300'
            : 'bg-red-500/10 border-red-500/20 text-red-300'
        }`}>{msg.ok ? '✓ ' : '✗ '}{msg.text}</div>
      )}

      {/* Ekle / Düzenle formu */}
      {showForm && (
        <div className="card mb-4 !p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-200">
              {editId ? 'Modeli Düzenle' : 'Yeni Model Ekle'}
            </h2>
            <button onClick={() => { setShowForm(false); setEditId(null) }}
                    className="text-gray-500 hover:text-gray-200 text-xl leading-none">×</button>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <Field label="Model adı *">
              <input className="input w-full !text-xs !py-1.5" value={form.display_name}
                     placeholder="iPhone 16 Pro Max"
                     onChange={e => setForm(f => ({ ...f, display_name: e.target.value }))} />
            </Field>
            <Field label="Marka">
              <input className="input w-full !text-xs !py-1.5" value={form.brand}
                     placeholder="Apple / Samsung..."
                     onChange={e => setForm(f => ({ ...f, brand: e.target.value }))} />
            </Field>
            <Field label="Genişlik (cm) *">
              <input type="number" step="0.01" className="input w-full !text-xs !py-1.5" value={form.width_cm}
                     onChange={e => setForm(f => ({ ...f, width_cm: e.target.value }))} />
            </Field>
            <Field label="Yükseklik (cm) *">
              <input type="number" step="0.01" className="input w-full !text-xs !py-1.5" value={form.height_cm}
                     onChange={e => setForm(f => ({ ...f, height_cm: e.target.value }))} />
            </Field>
            <Field label="Köşe yarıçapı (cm)">
              <input type="number" step="0.01" className="input w-full !text-xs !py-1.5" value={form.radius_cm}
                     placeholder="0"
                     onChange={e => setForm(f => ({ ...f, radius_cm: e.target.value }))} />
            </Field>
            <Field label="Not">
              <input className="input w-full !text-xs !py-1.5" value={form.notes}
                     onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} />
            </Field>
          </div>
          <div className="flex justify-end gap-2 mt-3">
            <button onClick={() => { setShowForm(false); setEditId(null) }}
                    className="btn-secondary !text-sm">İptal</button>
            <button onClick={save} disabled={saving} className="btn-primary !text-sm disabled:opacity-50">
              {saving ? 'Kaydediliyor...' : editId ? 'Güncelle' : 'Ekle'}
            </button>
          </div>
        </div>
      )}

      <div className="card mb-4 flex flex-wrap gap-2 !p-3">
        <input
          type="text"
          placeholder="Ara: model adı, marka, anahtar, not..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="input !text-xs !py-1.5 flex-1 min-w-[200px]"
        />
      </div>

      {loading && <div className="text-gray-500 text-sm text-center py-8">Yükleniyor...</div>}

      {!loading && items.length === 0 && (
        <div className="card text-center py-12 text-gray-500">
          <div className="text-3xl mb-2">📱</div>
          Henüz eklenmiş model yok. <br/>
          <span className="text-xs">
            Baseline kataloğunda {baselineCount} model zaten tanınıyor. Buraya sadece
            yeni çıkanları veya ölçüsünü düzeltmek istediklerini eklersin.
          </span>
        </div>
      )}

      {!loading && items.length > 0 && (
        <div className="card !p-0 overflow-hidden">
          <div className="overflow-x-auto"><table className="w-full text-sm min-w-[640px]">
            <thead className="bg-brand-input border-b border-brand-border">
              <tr className="text-left text-xs text-gray-500">
                <th className="px-3 py-2 font-medium">Model</th>
                <th className="px-3 py-2 font-medium">Marka</th>
                <th className="px-3 py-2 font-medium">Anahtar</th>
                <th className="px-3 py-2 font-medium text-right">G × Y (cm)</th>
                <th className="px-3 py-2 font-medium text-right">Yarıçap</th>
                <th className="px-3 py-2 font-medium text-center">Aktif</th>
                <th className="px-3 py-2 font-medium">Not</th>
                <th className="w-20 px-2"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-brand-border/50">
              {items.map(m => (
                <tr key={m.id} className={`hover:bg-brand-input/30 ${!m.is_active ? 'opacity-50' : ''}`}>
                  <td className="px-3 py-2 text-gray-200">{m.display_name}</td>
                  <td className="px-3 py-2 text-gray-400 text-xs">{m.brand || '—'}</td>
                  <td className="px-3 py-2 font-mono text-[11px] text-accent">{m.spec_key}</td>
                  <td className="px-3 py-2 text-right text-gray-200 whitespace-nowrap">
                    {m.width_cm} × {m.height_cm}
                  </td>
                  <td className="px-3 py-2 text-right text-gray-400">{m.radius_cm}</td>
                  <td className="px-3 py-2 text-center">
                    {m.is_active
                      ? <span className="text-emerald-400">●</span>
                      : <span className="text-gray-600">○</span>}
                  </td>
                  <td className="px-3 py-2 text-xs text-gray-400 max-w-[180px] truncate" title={m.notes || ''}>
                    {m.notes || '—'}
                  </td>
                  <td className="px-2 py-2">
                    <div className="flex items-center gap-1 justify-end">
                      <button onClick={() => setMockupModel(m)}
                        className={`w-7 h-7 flex items-center justify-center rounded transition-colors hover:bg-accent/10 ${m.mockup_template_url ? 'text-emerald-400' : 'text-gray-500 hover:text-accent'}`}
                        title="Mockup şablonu">🖼</button>
                      <button onClick={() => openEdit(m)}
                        className="w-7 h-7 flex items-center justify-center text-gray-500 hover:text-accent hover:bg-accent/10 rounded transition-colors"
                        title="Düzenle">✎</button>
                      <button onClick={() => remove(m)}
                        className="w-7 h-7 flex items-center justify-center text-red-400/70 hover:text-red-300 hover:bg-red-500/10 rounded transition-colors"
                        title="Sil">🗑</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table></div>
        </div>
      )}
      {mockupModel && (
        <MockupEditor model={mockupModel} onClose={() => setMockupModel(null)} onSaved={load} />
      )}
    </div>
  )
}

// Mockup şablonu: gerçek ürün fotoğrafı yükle + tasarım alanını fareyle sürükleyerek çiz
function MockupEditor({ model, onClose, onSaved }) {
  const [tplUrl, setTplUrl] = useState(model.mockup_template_url || '')
  const [rect, setRect] = useState(model.mockup_rect || null)
  const [mode, setMode] = useState('design')  // 'design' | 'camera'
  const [uploading, setUploading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')
  const boxRef = useRef(null)
  const drag = useRef(null)

  const upload = async (e) => {
    const file = e.target.files?.[0]; if (!file) return
    setUploading(true); setErr('')
    try {
      const fd = new FormData(); fd.append('file', file)
      const r = await api.postForm(`/api/phone-models/${model.id}/mockup-template`, fd)
      setTplUrl(r.mockup_template_url || ''); setRect(r.mockup_rect || null)
    } catch (e2) { setErr(e2.detail || 'Yüklenemedi') }
    finally { setUploading(false); e.target.value = '' }
  }
  const removeTpl = async () => {
    if (!confirm('Şablon kaldırılsın mı?')) return
    try { await api.del(`/api/phone-models/${model.id}/mockup-template`); setTplUrl(''); setRect(null); onSaved?.() }
    catch (e2) { setErr(e2.detail || 'Olmadı') }
  }

  const frac = (e) => {
    const b = boxRef.current.getBoundingClientRect()
    return {
      x: Math.min(1, Math.max(0, (e.clientX - b.left) / b.width)),
      y: Math.min(1, Math.max(0, (e.clientY - b.top) / b.height)),
    }
  }
  const onDown = (e) => {
    e.preventDefault(); drag.current = frac(e)
    const start = { x: drag.current.x, y: drag.current.y, w: 0, h: 0 }
    setRect(prev => mode === 'camera'
      ? { ...(prev || { x: 0, y: 0, w: 0, h: 0 }), camera: start }
      : { ...start, camera: prev?.camera })
  }
  const onMove = (e) => {
    if (!drag.current) return
    const p = frac(e), s = drag.current
    const box = { x: Math.min(s.x, p.x), y: Math.min(s.y, p.y), w: Math.abs(p.x - s.x), h: Math.abs(p.y - s.y) }
    setRect(prev => mode === 'camera'
      ? { ...(prev || { x: 0, y: 0, w: 0, h: 0 }), camera: box }
      : { ...box, camera: prev?.camera })
  }
  const onUp = () => { drag.current = null }

  const saveRect = async () => {
    if (!rect || rect.w < 0.02 || rect.h < 0.02) { setErr('Önce fotoğraf üzerinde tasarım alanını çiz'); return }
    setSaving(true); setErr('')
    try { await api.patch(`/api/phone-models/${model.id}`, { mockup_rect: rect }); onSaved?.(); onClose() }
    catch (e2) { setErr(e2.detail || 'Kaydedilemedi') }
    finally { setSaving(false) }
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-lg p-5 max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-3">
          <h2 className="text-lg font-semibold text-gray-100">Mockup şablonu — {model.display_name}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-200 text-2xl leading-none">×</button>
        </div>
        {err && <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded px-3 py-2 mb-3">{err}</div>}

        {!tplUrl ? (
          <label className="block border border-dashed border-brand-border rounded-lg p-8 text-center text-sm text-gray-400 cursor-pointer hover:border-accent">
            {uploading ? 'Yükleniyor…' : '🖼 Ürün fotoğrafı yükle (png / jpg / webp)'}
            <input type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={upload} disabled={uploading} />
          </label>
        ) : (
          <>
            <div className="flex items-center gap-2 mb-2">
              <button onClick={() => setMode('design')}
                className={`text-xs px-2.5 py-1 rounded ${mode === 'design' ? 'bg-accent text-white' : 'bg-brand-input text-gray-400 hover:text-gray-200'}`}>1) Tasarım alanı</button>
              <button onClick={() => setMode('camera')}
                className={`text-xs px-2.5 py-1 rounded ${mode === 'camera' ? 'bg-amber-500 text-white' : 'bg-brand-input text-gray-400 hover:text-gray-200'}`}>2) Kamera alanı</button>
            </div>
            <p className="text-xs text-gray-400 mb-2">
              {mode === 'design'
                ? <>Tasarımın oturacağı <b className="text-accent">alanı</b> fareyle sürükleyerek çiz.</>
                : <>Kameranın olduğu <b className="text-amber-400">bölgeyi</b> çiz — bu alan tasarımdan hariç tutulur, fotoğraftaki kamera görünür kalır. (Opsiyonel)</>}
            </p>
            <div ref={boxRef} onMouseDown={onDown} onMouseMove={onMove} onMouseUp={onUp} onMouseLeave={onUp}
              className="relative select-none rounded-lg overflow-hidden border border-brand-border" style={{ cursor: 'crosshair' }}>
              <img src={tplUrl} alt="" className="w-full block pointer-events-none" draggable={false} />
              {rect && rect.w > 0 && (
                <div className="absolute border-2 border-accent bg-accent/20 pointer-events-none"
                  style={{ left: `${rect.x * 100}%`, top: `${rect.y * 100}%`, width: `${rect.w * 100}%`, height: `${rect.h * 100}%` }} />
              )}
              {rect?.camera && rect.camera.w > 0 && (
                <div className="absolute border-2 border-amber-400 bg-amber-400/25 pointer-events-none"
                  style={{ left: `${rect.camera.x * 100}%`, top: `${rect.camera.y * 100}%`, width: `${rect.camera.w * 100}%`, height: `${rect.camera.h * 100}%` }} />
              )}
            </div>
            <div className="flex justify-between items-center mt-3">
              <button onClick={removeTpl} className="text-xs text-red-400 hover:text-red-300">Şablonu kaldır</button>
              <div className="flex gap-2">
                <button onClick={onClose} className="btn-secondary !text-sm">İptal</button>
                <button onClick={saveRect} disabled={saving} className="btn-primary !text-sm disabled:opacity-50">{saving ? '...' : 'Alanı Kaydet'}</button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function Field({ label, children }) {
  return (
    <div>
      <label className="block text-[10px] uppercase text-gray-500 mb-1">{label}</label>
      {children}
    </div>
  )
}

function Kpi({ label, value, color = 'gray' }) {
  const colors = { gray: 'text-gray-100', accent: 'text-accent' }
  return (
    <div className="bg-brand-card border border-brand-border rounded-lg p-3">
      <div className="text-[10px] uppercase text-gray-500">{label}</div>
      <div className={`text-2xl font-semibold ${colors[color]}`}>{value}</div>
    </div>
  )
}
