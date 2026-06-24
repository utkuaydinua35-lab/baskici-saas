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

function fmtDate(iso) {
  if (!iso) return ''
  try { return new Date(iso).toLocaleDateString('tr-TR', { day: '2-digit', month: '2-digit', year: '2-digit' }) } catch { return '' }
}

function CloneModal({ onClose, onDone }) {
  const [q, setQ] = useState('')
  const [storeId, setStoreId] = useState('')
  const [durum, setDurum] = useState('all')
  const [stores, setStores] = useState([])
  const [rows, setRows] = useState([])
  const [searching, setSearching] = useState(false)
  const [selOrder, setSelOrder] = useState(null)
  const [selLis, setSelLis] = useState({}) // id -> bool
  const [sebep, setSebep] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => { api.get('/api/telafiler/_meta/stores').then(r => setStores(r.items || [])).catch(() => {}) }, [])

  useEffect(() => {
    if (selOrder) return
    setSearching(true)
    const h = setTimeout(async () => {
      try {
        const params = new URLSearchParams()
        if (q.trim()) params.set('q', q.trim())
        if (storeId) params.set('store_id', storeId)
        if (durum !== 'all') params.set('durum', durum)
        const r = await api.get(`/api/telafiler/searchable-orders?${params.toString()}`)
        setRows(r.items || [])
      } catch {} finally { setSearching(false) }
    }, 250)
    return () => clearTimeout(h)
  }, [q, storeId, durum, selOrder])

  const toggle = (id) => setSelLis(s => ({ ...s, [id]: !s[id] }))
  const allChecked = selOrder && selOrder.line_items.length > 0 && selOrder.line_items.every(li => selLis[li.id])
  const toggleAll = () => {
    if (!selOrder) return
    if (allChecked) setSelLis({})
    else setSelLis(Object.fromEntries(selOrder.line_items.map(li => [li.id, true])))
  }
  const selCount = Object.values(selLis).filter(Boolean).length

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
    <Overlay onClose={onClose} title="Siparişten Telafi Oluştur" wide>
      {!selOrder ? (
        <>
          <div className="flex gap-2 mb-2">
            <input autoFocus value={q} onChange={e => setQ(e.target.value)} placeholder="Sipariş no / müşteri ara..."
              className="input flex-1 !text-sm" />
            <select value={storeId} onChange={e => setStoreId(e.target.value)} className="input !text-sm w-40">
              <option value="">Tüm mağazalar</option>
              {stores.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
            <select value={durum} onChange={e => setDurum(e.target.value)} className="input !text-sm w-36">
              <option value="all">Tüm durumlar</option>
              <option value="acik">Açık</option>
              <option value="gonderilmis">Gönderilmiş</option>
            </select>
          </div>
          <div className="text-[11px] text-gray-500 mb-1">{searching ? 'Aranıyor...' : `${rows.length} sipariş`}</div>
          <div className="max-h-96 overflow-y-auto divide-y divide-brand-border/50 border border-brand-border rounded-lg">
            {rows.map(o => (
              <button key={o.id} onClick={() => { setSelOrder(o); setSelLis({}) }}
                className="w-full text-left px-3 py-2 hover:bg-brand-input flex items-center gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-100">{o.order_number}</span>
                    {o.fulfillment_status === 'fulfilled'
                      ? <span className="text-[10px] px-1.5 rounded bg-emerald-500/15 text-emerald-300">gönderilmiş</span>
                      : <span className="text-[10px] px-1.5 rounded bg-blue-500/15 text-blue-300">açık</span>}
                  </div>
                  <div className="text-xs text-gray-400 truncate">{o.customer_name || '—'}</div>
                </div>
                <div className="text-right shrink-0">
                  <div className="text-[11px] text-gray-400">{o.store_name || ''}</div>
                  <div className="text-[11px] text-gray-500">{fmtDate(o.created_at_platform)} · {o.item_count} ürün</div>
                </div>
              </button>
            ))}
            {!searching && rows.length === 0 && <div className="text-xs text-gray-500 py-6 text-center">Sonuç yok</div>}
          </div>
        </>
      ) : (
        <>
          <div className="flex items-center justify-between mb-2">
            <div>
              <div className="text-sm font-medium text-gray-100">{selOrder.order_number} — {selOrder.customer_name}</div>
              <div className="text-[11px] text-gray-500">{selOrder.store_name || ''} · {fmtDate(selOrder.created_at_platform)}</div>
            </div>
            <button onClick={() => setSelOrder(null)} className="text-[11px] text-gray-500 hover:text-gray-200">← başka sipariş</button>
          </div>
          <div className="flex items-center justify-between mb-1">
            <div className="text-[12px] text-gray-500">Telafi gönderilecek ürünleri seç ({selCount} seçili):</div>
            <button onClick={toggleAll} className="text-[11px] text-accent hover:underline">{allChecked ? 'hiçbirini' : 'tümünü'} seç</button>
          </div>
          <div className="max-h-72 overflow-y-auto space-y-1 mb-3 border border-brand-border rounded-lg p-1">
            {selOrder.line_items.map(li => (
              <label key={li.id} className={`flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer ${selLis[li.id] ? 'bg-accent/10' : 'hover:bg-brand-input'}`}>
                <input type="checkbox" checked={!!selLis[li.id]} onChange={() => toggle(li.id)} />
                <div className="w-11 h-11 shrink-0 rounded overflow-hidden bg-brand-input border border-brand-border flex items-center justify-center">
                  {li.thumbnail_url
                    ? <img src={li.thumbnail_url} alt="" className="w-full h-full object-cover" onError={e => { e.target.style.display = 'none' }} />
                    : <span className="text-[8px] text-gray-600">görsel yok</span>}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-gray-200 truncate">{li.title}</div>
                  <div className="text-[11px] text-gray-500 truncate">
                    {li.device_model || '?'}{li.design_name ? ` · ${li.design_name}` : ''}{li.design_code ? ` (${li.design_code})` : ''}
                  </div>
                </div>
                <span className="text-[11px] text-gray-400 shrink-0">×{li.quantity}</span>
              </label>
            ))}
          </div>
          <SebepInput value={sebep} onChange={setSebep} />
          <div className="flex justify-end gap-2 mt-3">
            <button onClick={onClose} className="text-xs px-3 py-1.5 rounded bg-brand-input text-gray-300">Vazgeç</button>
            <button onClick={create} disabled={busy || selCount === 0} className="text-xs px-3 py-1.5 rounded bg-accent/20 text-accent hover:bg-accent/30 disabled:opacity-50">
              {busy ? '...' : `Telafi Oluştur (${selCount})`}</button>
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

function Overlay({ title, onClose, children, wide }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className={`w-full ${wide ? 'max-w-2xl' : 'max-w-lg'} rounded-xl border border-brand-border bg-brand-card p-4 shadow-xl`} onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-100">{title}</h3>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-200">×</button>
        </div>
        {children}
      </div>
    </div>
  )
}
