import { useState, useEffect, useMemo } from 'react'
import { api } from '../lib/api'

/**
 * Slot Ataması — bir kalıbın boş slotuna sipariş kaleminden veya manuel atama.
 *
 * Props:
 *   open: boolean
 *   mold: { id, kod, variation, kalip_kodlari, ... }
 *   kalipKodu: string  (boş slotun ait olduğu kalıp kodu, örn "A1")
 *   onClose: () => void
 *   onAssigned: () => void  (atama başarılı; parent refresh yapar)
 */
export default function SlotAssignDialog({ open, mold, kalipKodu, onClose, onAssigned }) {
  const [tab, setTab] = useState('order')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  useEffect(() => {
    if (open) {
      setTab('order')
      setErr('')
      setBusy(false)
    }
  }, [open, mold?.id, kalipKodu])

  if (!open || !mold) return null
  const _bosKalip = !kalipKodu  // bos kalip: ilk ekleme

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4"
      onMouseDown={(e) => e.target === e.currentTarget && !busy && onClose()}
    >
      <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-5 py-3 border-b border-brand-border flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-gray-100">Slot Ataması</h2>
            <p className="text-xs text-gray-500 mt-0.5">
              Kalıp: <span className="font-mono text-gray-300">{mold.kod}</span>
              {_bosKalip ? (
                <span className="text-amber-300">{' · '}İlk kılıf — varyasyon ilk eklemeyle belirlenecek</span>
              ) : (
                <>
                  {' · '}Kod: <span className="font-mono text-accent">{kalipKodu}</span>
                  {' · '}Varyasyon: <span className="text-gray-300">{mold.variation}</span>
                </>
              )}
            </p>
          </div>
          <button
            onClick={onClose}
            disabled={busy}
            className="text-gray-400 hover:text-gray-200 text-2xl leading-none px-2 disabled:opacity-50"
          >×</button>
        </div>

        {/* Tabs */}
        <div className="px-5 flex gap-0 border-b border-brand-border bg-brand-card">
          <TabBtn active={tab === 'order'} onClick={() => setTab('order')}>📦 Siparişler</TabBtn>
          <TabBtn active={tab === 'manual'} onClick={() => setTab('manual')}>✋ Manuel Atama</TabBtn>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5">
          {err && (
            <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded px-3 py-2 mb-3">
              {err}
            </div>
          )}

          {tab === 'order' && (
            <OrderTab
              mold={mold}
              kalipKodu={kalipKodu}
              busy={busy} setBusy={setBusy} setErr={setErr}
              onClose={onClose} onAssigned={onAssigned}
            />
          )}

          {tab === 'manual' && (
            <ManualTab
              mold={mold}
              kalipKodu={kalipKodu}
              busy={busy} setBusy={setBusy} setErr={setErr}
              onClose={onClose} onAssigned={onAssigned}
            />
          )}
        </div>
      </div>
    </div>
  )
}

function OrderTab({ mold, kalipKodu, busy, setBusy, setErr, onClose, onAssigned }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)
  const [filterOrder, setFilterOrder] = useState('')
  const [filterText, setFilterText] = useState('')

  useEffect(() => {
    setLoading(true)
    api.get(`/api/molds/${mold.id}/assignable/line-items`)
      .then(r => setItems(r.items || []))
      .catch(e => setErr(typeof e?.detail === 'string' ? e.detail : 'Liste yüklenemedi'))
      .finally(() => setLoading(false))
  }, [mold.id])

  const orderOptions = useMemo(() => {
    const map = new Map()
    for (const it of items) {
      if (!map.has(it.order_id)) {
        map.set(it.order_id, { id: it.order_id, number: it.order_number, customer: it.customer_name })
      }
    }
    return Array.from(map.values())
  }, [items])

  const filtered = useMemo(() => {
    let arr = items
    if (filterOrder) arr = arr.filter(i => i.order_id === filterOrder)
    if (filterText) {
      const q = filterText.toLowerCase()
      arr = arr.filter(i =>
        (i.title || '').toLowerCase().includes(q) ||
        (i.order_number || '').toLowerCase().includes(q) ||
        (i.customer_name || '').toLowerCase().includes(q) ||
        (i.design_code || '').toLowerCase().includes(q) ||
        (i.model || '').toLowerCase().includes(q)
      )
    }
    return arr
  }, [items, filterOrder, filterText])

  const handleSave = async () => {
    if (!selected) return
    setBusy(true); setErr('')
    try {
      await api.post(`/api/molds/${mold.id}/slots/assign`, {
        kalip_kodu: kalipKodu,
        source: 'order',
        line_item_id: selected,
      })
      onAssigned?.()
    } catch (e) {
      setErr(typeof e?.detail === 'string' ? e.detail : 'Atama başarısız')
      setBusy(false)
    }
  }

  return (
    <>
      <div className="mb-3 flex gap-2 flex-wrap">
        <select
          value={filterOrder}
          onChange={(e) => setFilterOrder(e.target.value)}
          className="input !text-sm !py-1.5 min-w-[180px]"
        >
          <option value="">Tüm siparişler ({orderOptions.length})</option>
          {orderOptions.map(o => (
            <option key={o.id} value={o.id}>
              {o.number}{o.customer ? ` · ${o.customer}` : ''}
            </option>
          ))}
        </select>
        <input
          type="text"
          placeholder="Ara: ürün, model, müşteri, tasarım..."
          value={filterText}
          onChange={(e) => setFilterText(e.target.value)}
          className="input !text-sm !py-1.5 flex-1 min-w-[200px]"
        />
      </div>

      {loading ? (
        <div className="text-gray-500 text-sm text-center py-8">Yükleniyor...</div>
      ) : filtered.length === 0 ? (
        <div className="text-gray-500 text-sm text-center py-8">
          <div className="text-3xl mb-2">📭</div>
          {items.length === 0
            ? <>Bu kalıba uygun atanabilir sipariş kalemi yok.<br/><span className="text-[11px]">(varyasyon: <b>{mold.variation}</b>, tasarım+model çözülmüş, kalıba eklenmemiş)</span></>
            : 'Filtreye uyan kayıt yok.'}
        </div>
      ) : (
        <div className="space-y-1.5 max-h-[400px] overflow-y-auto">
          {filtered.map(it => (
            <label
              key={it.line_item_id}
              className={`block p-2.5 rounded-lg border cursor-pointer transition-colors ${
                selected === it.line_item_id
                  ? 'bg-accent/15 border-accent/50'
                  : 'bg-brand-input border-brand-border hover:border-accent/30'
              }`}
            >
              <input
                type="radio"
                name="li"
                checked={selected === it.line_item_id}
                onChange={() => setSelected(it.line_item_id)}
                className="hidden"
              />
              <div className="flex items-start gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap text-xs mb-0.5">
                    <span className="font-mono text-accent">{it.order_number}</span>
                    {it.customer_name && <span className="text-gray-400 truncate">· {it.customer_name}</span>}
                    <span className="ml-auto text-gray-500 shrink-0">x{it.quantity}</span>
                  </div>
                  <div className="text-sm text-gray-200 truncate">{it.title}</div>
                  <div className="text-xs text-gray-500 mt-1 flex items-center gap-2 flex-wrap">
                    <span>📱 {it.model}</span>
                    {it.design_code && <span className="font-mono">🎨 {it.design_code}</span>}
                    {it.variation && <span className="text-amber-300/70">· {it.variation}</span>}
                  </div>
                </div>
              </div>
            </label>
          ))}
        </div>
      )}

      <div className="flex items-center justify-end gap-2 mt-4 pt-3 border-t border-brand-border">
        <button onClick={onClose} disabled={busy} className="btn-secondary">İptal</button>
        <button
          onClick={handleSave}
          disabled={!selected || busy}
          className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {busy ? 'Atanıyor...' : '✓ Kaydet'}
        </button>
      </div>
    </>
  )
}

function ManualTab({ mold, kalipKodu, busy, setBusy, setErr, onClose, onAssigned }) {
  const [designs, setDesigns] = useState([])
  const [models, setModels] = useState([])
  const [loading, setLoading] = useState(true)
  const [designId, setDesignId] = useState('')
  const [model, setModel] = useState('')
  const [designFilter, setDesignFilter] = useState('')

  useEffect(() => {
    Promise.all([
      api.get(`/api/molds/${mold.id}/assignable/designs`),
      api.get(`/api/molds/${mold.id}/assignable/models`),
    ]).then(([d, m]) => {
      setDesigns(d.items || [])
      setModels(m.items || [])
    }).catch(e => setErr(typeof e?.detail === 'string' ? e.detail : 'Liste yüklenemedi'))
      .finally(() => setLoading(false))
  }, [mold.id])

  const filteredDesigns = useMemo(() => {
    if (!designFilter) return designs
    const q = designFilter.toLowerCase()
    return designs.filter(d =>
      (d.code || '').toLowerCase().includes(q) ||
      (d.name || '').toLowerCase().includes(q)
    )
  }, [designs, designFilter])

  const canSave = designId && model && !busy

  const handleSave = async () => {
    if (!canSave) return
    setBusy(true); setErr('')
    try {
      await api.post(`/api/molds/${mold.id}/slots/assign`, {
        kalip_kodu: kalipKodu,
        source: 'manual',
        design_id: designId,
        model: model.trim(),
      })
      onAssigned?.()
    } catch (e) {
      setErr(typeof e?.detail === 'string' ? e.detail : 'Atama başarısız')
      setBusy(false)
    }
  }

  if (loading) return <div className="text-gray-500 text-sm text-center py-8">Yükleniyor...</div>

  return (
    <>
      <div className="space-y-4">
        {/* Telefon Modeli */}
        <div>
          <label className="block text-xs text-gray-400 mb-1">📱 Telefon Modeli</label>
          <input
            list="phone-models-datalist"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder="örn. iPhone 15 Pro Max"
            className="input w-full"
            autoComplete="off"
          />
          <datalist id="phone-models-datalist">
            {models.map(m => <option key={m} value={m} />)}
          </datalist>
          <p className="text-[10px] text-gray-500 mt-1">
            Listeden seç ya da yazarak ara ({models.length} model)
          </p>
        </div>

        {/* Tasarım */}
        <div>
          <label className="block text-xs text-gray-400 mb-1">🎨 Tasarım</label>
          <input
            type="text"
            placeholder="Tasarım kodu/adı ile ara..."
            value={designFilter}
            onChange={(e) => setDesignFilter(e.target.value)}
            className="input w-full mb-2 !text-xs"
          />
          <div className="border border-brand-border rounded-lg max-h-60 overflow-y-auto bg-brand-input/30">
            {filteredDesigns.length === 0 ? (
              <div className="text-xs text-gray-500 text-center py-6">Eşleşen tasarım yok</div>
            ) : (
              filteredDesigns.map(d => (
                <label
                  key={d.id}
                  className={`flex items-center gap-2 px-2 py-1.5 cursor-pointer text-sm border-b border-brand-border/30 last:border-0 ${
                    designId === d.id ? 'bg-accent/15 text-accent' : 'hover:bg-brand-input/70'
                  }`}
                >
                  <input
                    type="radio"
                    name="design"
                    checked={designId === d.id}
                    onChange={() => setDesignId(d.id)}
                    className="hidden"
                  />
                  {d.thumbnail_url ? (
                    <img
                      src={d.thumbnail_url}
                      alt=""
                      className="w-8 h-8 rounded object-cover shrink-0"
                      onError={(e) => { e.target.style.display = 'none' }}
                    />
                  ) : (
                    <div className="w-8 h-8 rounded bg-brand-border/50 shrink-0" />
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs">{d.code}</span>
                      {d.is_kisiye_ozel && (
                        <span className="text-[9px] px-1 rounded bg-purple-500/15 text-purple-300">kişiye özel</span>
                      )}
                    </div>
                    {d.name && <div className="text-[11px] text-gray-500 truncate">{d.name}</div>}
                  </div>
                  {d.birincil_renk && (
                    <span className="text-[10px] text-gray-500 shrink-0">{d.birincil_renk}</span>
                  )}
                </label>
              ))
            )}
          </div>
          <p className="text-[10px] text-gray-500 mt-1">{filteredDesigns.length}/{designs.length} tasarım</p>
        </div>

        {/* Kılıf Renk (otomatik mold.variation, salt-okunur) */}
        <div>
          <label className="block text-xs text-gray-400 mb-1">🎯 Kılıf Renk</label>
          <div className="input w-full cursor-not-allowed text-gray-400 bg-brand-input/40 flex items-center justify-between">
            <span>{mold.variation}</span>
            <span className="text-[10px] text-gray-500">(kalıbın varyasyonu)</span>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-end gap-2 mt-5 pt-3 border-t border-brand-border">
        <button onClick={onClose} disabled={busy} className="btn-secondary">İptal</button>
        <button
          onClick={handleSave}
          disabled={!canSave}
          className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {busy ? 'Atanıyor...' : '✓ Kaydet'}
        </button>
      </div>
    </>
  )
}

function TabBtn({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2.5 -mb-px border-b-2 text-sm transition-colors ${
        active
          ? 'text-accent border-accent'
          : 'text-gray-400 border-transparent hover:text-gray-200'
      }`}
    >
      {children}
    </button>
  )
}
