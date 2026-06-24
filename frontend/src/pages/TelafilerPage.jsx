import { useEffect, useState, useCallback } from 'react'
import { api } from '../lib/api'

const SEBEP_ONERILER = ['Hatalı model', 'Yanlış hazırlandı', 'Hasarlı geldi', 'Kargo kaybı', 'Yanlış tasarım']

export default function TelafilerPage() {
  const [items, setItems] = useState([])
  const [stages, setStages] = useState([])
  const [loading, setLoading] = useState(true)
  const [modal, setModal] = useState(null) // 'clone' | 'manual' | null

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [t, s] = await Promise.all([
        api.get('/api/telafiler'),
        api.get('/api/telafiler/_meta/stages'),
      ])
      setItems(t.items || [])
      setStages(s.stages || [])
    } catch (e) { console.error(e) }
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <div className="p-4 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-semibold text-gray-100 flex items-center gap-2">♻️ Telafiler</h1>
          <p className="text-[12px] text-gray-500 mt-0.5">
            Hatalı model / yanlış hazırlama nedeniyle yeniden gönderilecek siparişler. Kalıp oluşturucuya dahildir.
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setModal('clone')}
            className="text-xs px-3 py-1.5 rounded bg-accent/15 text-accent hover:bg-accent/25">Siparişten Klonla</button>
          <button onClick={() => setModal('manual')}
            className="text-xs px-3 py-1.5 rounded bg-brand-input text-gray-200 hover:text-white">Elle Ekle</button>
        </div>
      </div>

      {loading ? (
        <div className="text-sm text-gray-500 py-12 text-center">Yükleniyor...</div>
      ) : items.length === 0 ? (
        <div className="text-sm text-gray-500 py-12 text-center border border-dashed border-brand-border rounded-xl">
          Henüz telafi siparişi yok. "Siparişten Klonla" veya "Elle Ekle" ile başla.
        </div>
      ) : (
        <div className="space-y-2">
          {items.map(t => (
            <TelafiCard key={t.id} t={t} stages={stages} onChanged={load} />
          ))}
        </div>
      )}

      {modal === 'clone' && <CloneModal stages={stages} onClose={() => setModal(null)} onDone={() => { setModal(null); load() }} />}
      {modal === 'manual' && <ManualModal onClose={() => setModal(null)} onDone={() => { setModal(null); load() }} />}
    </div>
  )
}

function StageBadge({ info }) {
  return <span className="text-[11px] px-1.5 py-0.5 rounded bg-brand-input text-gray-300">{info?.label || '—'}</span>
}

function TelafiCard({ t, stages, onChanged }) {
  const [busy, setBusy] = useState(false)
  const [matchOpen, setMatchOpen] = useState(false)

  const setStage = async (stage) => {
    setBusy(true)
    try { await api.patch(`/api/telafiler/${t.id}/stage`, { current_stage: Number(stage) }); onChanged() }
    catch (e) { alert(e.message) } finally { setBusy(false) }
  }
  const del = async () => {
    if (!confirm('Bu telafi siparişi silinsin mi?')) return
    setBusy(true)
    try { await api.del(`/api/telafiler/${t.id}`); onChanged() }
    catch (e) { alert(e.message) } finally { setBusy(false) }
  }
  const unmatch = async () => {
    setBusy(true)
    try { await api.patch(`/api/telafiler/${t.id}/match`, { order_id: null }); onChanged() }
    catch (e) { alert(e.message) } finally { setBusy(false) }
  }

  return (
    <div className="rounded-xl border border-brand-border bg-brand-card p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 font-medium">TELAFİ</span>
            <span className="text-sm font-medium text-gray-100">{t.order_number}</span>
            <span className="text-sm text-gray-300">{t.customer_name || '—'}</span>
            <span className="text-[11px] text-gray-500">{t.item_count} ürün</span>
          </div>
          {t.telafi_sebep && <div className="text-[12px] text-amber-400/90 mt-1">Sebep: {t.telafi_sebep}</div>}
          <div className="text-[12px] text-gray-500 mt-1">
            {t.kaynak
              ? <>Kaynak sipariş: <span className="text-gray-300">{t.kaynak.order_number}</span> ({t.kaynak.customer_name})
                  <button onClick={unmatch} disabled={busy} className="ml-2 text-[11px] text-gray-500 hover:text-red-400">eşi kaldır</button></>
              : <button onClick={() => setMatchOpen(true)} className="text-[11px] text-accent hover:underline">+ siparişle eşleştir</button>}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <select value={t.current_stage} disabled={busy} onChange={e => setStage(e.target.value)}
            className="input !text-xs !py-1">
            {stages.map(s => <option key={s.no} value={s.no}>{s.no}. {s.label}</option>)}
          </select>
          <button onClick={del} disabled={busy} className="text-[11px] text-gray-500 hover:text-red-400 px-1">Sil</button>
        </div>
      </div>
      {/* ilerleme */}
      <div className="mt-2 h-1 rounded bg-brand-input overflow-hidden">
        <div className="h-full bg-accent/70" style={{ width: `${t.progress_percent || 0}%` }} />
      </div>

      {matchOpen && <MatchPicker telafiId={t.id} onClose={() => setMatchOpen(false)} onDone={() => { setMatchOpen(false); onChanged() }} />}
    </div>
  )
}

function MatchPicker({ telafiId, onClose, onDone }) {
  const [q, setQ] = useState('')
  const [rows, setRows] = useState([])
  useEffect(() => {
    const h = setTimeout(async () => {
      try { const r = await api.get(`/api/telafiler/searchable-orders?q=${encodeURIComponent(q)}`); setRows(r.items || []) } catch {}
    }, 250)
    return () => clearTimeout(h)
  }, [q])
  const pick = async (oid) => {
    try { await api.patch(`/api/telafiler/${telafiId}/match`, { order_id: oid }); onDone() }
    catch (e) { alert(e.message) }
  }
  return (
    <Overlay onClose={onClose} title="Siparişle Eşleştir">
      <input autoFocus value={q} onChange={e => setQ(e.target.value)} placeholder="Sipariş no / müşteri ara..."
        className="input w-full !text-sm mb-2" />
      <div className="max-h-72 overflow-y-auto space-y-1">
        {rows.map(o => (
          <button key={o.id} onClick={() => pick(o.id)}
            className="w-full text-left px-2 py-1.5 rounded hover:bg-brand-input text-sm flex justify-between">
            <span className="text-gray-200">{o.order_number}</span>
            <span className="text-gray-500">{o.customer_name}</span>
          </button>
        ))}
        {rows.length === 0 && <div className="text-xs text-gray-500 py-4 text-center">Sonuç yok</div>}
      </div>
    </Overlay>
  )
}

function CloneModal({ onClose, onDone }) {
  const [q, setQ] = useState('')
  const [rows, setRows] = useState([])
  const [selOrder, setSelOrder] = useState(null)
  const [selLis, setSelLis] = useState({}) // id -> bool
  const [sebep, setSebep] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (selOrder) return
    const h = setTimeout(async () => {
      try { const r = await api.get(`/api/telafiler/searchable-orders?q=${encodeURIComponent(q)}`); setRows(r.items || []) } catch {}
    }, 250)
    return () => clearTimeout(h)
  }, [q, selOrder])

  const toggle = (id) => setSelLis(s => ({ ...s, [id]: !s[id] }))
  const create = async () => {
    const ids = Object.keys(selLis).filter(k => selLis[k])
    if (!ids.length) { alert('En az bir ürün seç'); return }
    setBusy(true)
    try {
      await api.post(`/api/telafiler/from-order/${selOrder.id}`, { line_item_ids: ids, telafi_sebep: sebep })
      onDone()
    } catch (e) { alert(e.message) } finally { setBusy(false) }
  }

  return (
    <Overlay onClose={onClose} title="Siparişten Telafi Oluştur">
      {!selOrder ? (
        <>
          <input autoFocus value={q} onChange={e => setQ(e.target.value)} placeholder="Sipariş no / müşteri ara..."
            className="input w-full !text-sm mb-2" />
          <div className="max-h-80 overflow-y-auto space-y-1">
            {rows.map(o => (
              <button key={o.id} onClick={() => { setSelOrder(o); setSelLis({}) }}
                className="w-full text-left px-2 py-1.5 rounded hover:bg-brand-input text-sm flex justify-between">
                <span className="text-gray-200">{o.order_number} <span className="text-gray-500">({o.line_items.length} ürün)</span></span>
                <span className="text-gray-500">{o.customer_name}</span>
              </button>
            ))}
            {rows.length === 0 && <div className="text-xs text-gray-500 py-4 text-center">Sonuç yok</div>}
          </div>
        </>
      ) : (
        <>
          <div className="flex items-center justify-between mb-2">
            <div className="text-sm text-gray-200">{selOrder.order_number} — {selOrder.customer_name}</div>
            <button onClick={() => setSelOrder(null)} className="text-[11px] text-gray-500 hover:text-gray-200">← başka sipariş</button>
          </div>
          <div className="text-[12px] text-gray-500 mb-1">Telafi gönderilecek ürünleri seç (hepsi olmak zorunda değil):</div>
          <div className="max-h-60 overflow-y-auto space-y-1 mb-3">
            {selOrder.line_items.map(li => (
              <label key={li.id} className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-brand-input cursor-pointer">
                <input type="checkbox" checked={!!selLis[li.id]} onChange={() => toggle(li.id)} />
                <span className="text-sm text-gray-200 flex-1 min-w-0 truncate">{li.title}</span>
                <span className="text-[11px] text-gray-500">{li.device_model || '?'}{li.design_code ? ` · ${li.design_code}` : ''} ×{li.quantity}</span>
              </label>
            ))}
          </div>
          <SebepInput value={sebep} onChange={setSebep} />
          <div className="flex justify-end gap-2 mt-3">
            <button onClick={onClose} className="text-xs px-3 py-1.5 rounded bg-brand-input text-gray-300">Vazgeç</button>
            <button onClick={create} disabled={busy} className="text-xs px-3 py-1.5 rounded bg-accent/20 text-accent hover:bg-accent/30 disabled:opacity-50">
              {busy ? '...' : 'Telafi Oluştur'}</button>
          </div>
        </>
      )}
    </Overlay>
  )
}

function ManualModal({ onClose, onDone }) {
  const [stores, setStores] = useState([])
  const [storeId, setStoreId] = useState('')
  const [customer, setCustomer] = useState('')
  const [sebep, setSebep] = useState('')
  const [lis, setLis] = useState([{ title: '', device_model: '', quantity: 1 }])
  const [busy, setBusy] = useState(false)

  useEffect(() => { api.get('/api/stores').then(s => {
    const arr = Array.isArray(s) ? s.filter(x => x.platform !== 'bayii') : []
    setStores(arr); if (arr[0]) setStoreId(arr[0].id)
  }).catch(() => {}) }, [])

  const setLi = (i, k, v) => setLis(p => p.map((x, j) => j === i ? { ...x, [k]: v } : x))
  const addLi = () => setLis(p => [...p, { title: '', device_model: '', quantity: 1 }])
  const rmLi = (i) => setLis(p => p.filter((_, j) => j !== i))

  const create = async () => {
    if (!storeId) { alert('Mağaza seç'); return }
    if (!customer.trim()) { alert('Müşteri adı gir'); return }
    const valid = lis.filter(l => l.title.trim())
    if (!valid.length) { alert('En az bir ürün gir'); return }
    setBusy(true)
    try {
      await api.post('/api/telafiler/manual', {
        store_id: storeId, customer_name: customer, telafi_sebep: sebep,
        line_items: valid.map(l => ({ title: l.title, device_model: l.device_model || null, quantity: Number(l.quantity) || 1 })),
      })
      onDone()
    } catch (e) { alert(e.message) } finally { setBusy(false) }
  }

  return (
    <Overlay onClose={onClose} title="Elle Telafi Ekle">
      <div className="space-y-2">
        <div className="grid grid-cols-2 gap-2">
          <select value={storeId} onChange={e => setStoreId(e.target.value)} className="input !text-sm">
            {stores.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          <input value={customer} onChange={e => setCustomer(e.target.value)} placeholder="Müşteri adı" className="input !text-sm" />
        </div>
        <SebepInput value={sebep} onChange={setSebep} />
        <div className="text-[12px] text-gray-500 pt-1">Ürünler:</div>
        {lis.map((l, i) => (
          <div key={i} className="flex gap-1.5">
            <input value={l.title} onChange={e => setLi(i, 'title', e.target.value)} placeholder="Ürün başlığı" className="input !text-sm flex-1" />
            <input value={l.device_model} onChange={e => setLi(i, 'device_model', e.target.value)} placeholder="Model (örn iPhone 14)" className="input !text-sm w-40" />
            <input type="number" min="1" value={l.quantity} onChange={e => setLi(i, 'quantity', e.target.value)} className="input !text-sm w-16" />
            {lis.length > 1 && <button onClick={() => rmLi(i)} className="text-gray-500 hover:text-red-400 px-1">×</button>}
          </div>
        ))}
        <button onClick={addLi} className="text-[12px] text-accent hover:underline">+ ürün ekle</button>
      </div>
      <div className="flex justify-end gap-2 mt-3">
        <button onClick={onClose} className="text-xs px-3 py-1.5 rounded bg-brand-input text-gray-300">Vazgeç</button>
        <button onClick={create} disabled={busy} className="text-xs px-3 py-1.5 rounded bg-accent/20 text-accent hover:bg-accent/30 disabled:opacity-50">
          {busy ? '...' : 'Telafi Oluştur'}</button>
      </div>
    </Overlay>
  )
}

function SebepInput({ value, onChange }) {
  return (
    <div>
      <input value={value} onChange={e => onChange(e.target.value)} placeholder="Telafi sebebi" className="input !text-sm w-full" />
      <div className="flex gap-1 flex-wrap mt-1">
        {SEBEP_ONERILER.map(s => (
          <button key={s} onClick={() => onChange(s)}
            className="text-[10px] px-1.5 py-0.5 rounded bg-brand-input text-gray-400 hover:text-gray-100">{s}</button>
        ))}
      </div>
    </div>
  )
}

function Overlay({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="w-full max-w-lg rounded-xl border border-brand-border bg-brand-card p-4 shadow-xl" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-100">{title}</h3>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-200">×</button>
        </div>
        {children}
      </div>
    </div>
  )
}
