import { useState, useEffect, useMemo } from 'react'
import { api } from '../lib/api'

/**
 * Askı kaydı oluşturma / düzenleme dialog'u.
 *
 * Props:
 *   open: boolean
 *   mode: 'create' | 'edit'
 *   item: AskiItem | null  (edit modunda)
 *   storeId: uuid           (varsayılan mağaza)
 *   stores: array
 *   onClose: () => void
 *   onSaved: () => void
 */
export default function AskiItemDialog({ open, mode, item, storeId, stores, onClose, onSaved }) {
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const [selectedStoreId, setSelectedStoreId] = useState('')
  const [designId, setDesignId] = useState('')
  const [model, setModel] = useState('')
  const [variation, setVariation] = useState('')
  const [quantity, setQuantity] = useState(1)
  const [note, setNote] = useState('')

  const [designs, setDesigns] = useState([])
  const [designFilter, setDesignFilter] = useState('')
  const [showDesignList, setShowDesignList] = useState(false)

  useEffect(() => {
    if (open) {
      setBusy(false); setErr('')
      if (mode === 'edit' && item) {
        setSelectedStoreId(item.store_id)
        setDesignId(item.design_id)
        setModel(item.model)
        setVariation(item.variation || '')
        setQuantity(item.quantity)
        setNote(item.note || '')
      } else {
        setSelectedStoreId(storeId || (stores?.[0]?.id || ''))
        setDesignId(''); setModel(''); setVariation('')
        setQuantity(1); setNote('')
      }
      setDesignFilter(''); setShowDesignList(false)
    }
  }, [open, mode, item, storeId, stores])

  useEffect(() => {
    if (!selectedStoreId || mode === 'edit') { return }
    api.get(`/api/orders/_meta/store-designs?store_id=${selectedStoreId}`)
      .then(r => setDesigns(r?.items || []))
      .catch(() => setDesigns([]))
  }, [selectedStoreId, mode])

  const selectedDesign = designs.find(d => d.id === designId)

  const filteredDesigns = useMemo(() => {
    if (!designFilter) return designs.slice(0, 50)
    const q = designFilter.toLowerCase()
    return designs.filter(d =>
      (d.code || '').toLowerCase().includes(q) ||
      (d.name || '').toLowerCase().includes(q)
    ).slice(0, 50)
  }, [designs, designFilter])

  if (!open) return null

  const canSave = (
    mode === 'edit' ? true : (selectedStoreId && designId && model.trim())
  ) && quantity > 0 && !busy

  const handleSave = async () => {
    if (!canSave) return
    setBusy(true); setErr('')
    try {
      if (mode === 'create') {
        await api.post('/api/aski', {
          store_id: selectedStoreId,
          design_id: designId,
          model: model.trim(),
          variation: variation || null,
          quantity: parseInt(quantity) || 1,
          note: note.trim() || null,
        })
      } else {
        await api.patch(`/api/aski/${item.id}`, {
          quantity: parseInt(quantity) || 1,
          note: note.trim() || null,
        })
      }
      onSaved?.()
    } catch (e) {
      setErr(typeof e?.detail === 'string' ? e.detail : 'Kaydetme başarısız')
      setBusy(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onMouseDown={(e) => e.target === e.currentTarget && !busy && onClose()}
    >
      <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-lg overflow-hidden flex flex-col">
        <div className="px-5 py-3 border-b border-brand-border flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-100">
            {mode === 'edit' ? '🎁 Askı Kaydını Düzenle' : '🎁 Yeni Askıya Ekle'}
          </h2>
          <button
            onClick={onClose}
            disabled={busy}
            className="text-gray-400 hover:text-gray-200 text-2xl leading-none px-2 disabled:opacity-50"
          >×</button>
        </div>

        <div className="p-5 space-y-3 max-h-[70vh] overflow-y-auto">
          {err && (
            <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded px-3 py-2">{err}</div>
          )}

          {mode === 'edit' && item && (
            <div className="text-xs text-gray-500 bg-brand-input/30 rounded p-2 border border-brand-border">
              <div>Tasarım: <span className="font-mono text-gray-300">{item.design_code}</span></div>
              <div>Model: <span className="text-gray-300">{item.model}</span></div>
              {item.variation && <div>Varyasyon: <span className="text-gray-300">{item.variation}</span></div>}
              <div className="text-[10px] mt-1 opacity-70">Düzenleme: sadece miktar ve not</div>
            </div>
          )}

          {mode === 'create' && (
            <>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Mağaza *</label>
                <select
                  value={selectedStoreId}
                  onChange={(e) => setSelectedStoreId(e.target.value)}
                  className="input w-full !text-sm"
                  disabled={busy}
                >
                  {stores.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>

              <div className="relative">
                <label className="text-xs text-gray-500 mb-1 block">Tasarım *</label>
                {selectedDesign ? (
                  <div className="input w-full !text-sm flex items-center gap-2 !py-1.5">
                    {selectedDesign.thumbnail_url && (
                      <img src={selectedDesign.thumbnail_url} alt="" className="w-6 h-6 rounded object-cover shrink-0"
                           onError={e => { e.target.style.display = 'none' }} />
                    )}
                    <span className="font-mono text-xs flex-1 truncate">{selectedDesign.code}</span>
                    {selectedDesign.name && (
                      <span className="text-[10px] text-gray-500 truncate">{selectedDesign.name}</span>
                    )}
                    <button
                      onClick={() => { setDesignId(''); setDesignFilter('') }}
                      type="button"
                      disabled={busy}
                      className="text-gray-500 hover:text-gray-300 text-xs shrink-0"
                    >×</button>
                  </div>
                ) : (
                  <>
                    <input
                      value={designFilter}
                      onChange={(e) => { setDesignFilter(e.target.value); setShowDesignList(true) }}
                      onFocus={() => setShowDesignList(true)}
                      onBlur={() => setTimeout(() => setShowDesignList(false), 150)}
                      placeholder="Tasarım ara..."
                      className="input w-full !text-sm"
                      disabled={busy}
                    />
                    {showDesignList && filteredDesigns.length > 0 && (
                      <div className="absolute z-50 top-full left-0 right-0 mt-1 bg-brand-card border border-brand-border rounded-lg max-h-48 overflow-y-auto shadow-2xl">
                        {filteredDesigns.map(d => (
                          <button
                            key={d.id}
                            type="button"
                            onMouseDown={(e) => {
                              e.preventDefault()
                              setDesignId(d.id)
                              setShowDesignList(false)
                              setDesignFilter('')
                            }}
                            className="w-full px-2 py-1.5 text-left text-sm hover:bg-brand-input flex items-center gap-2"
                          >
                            {d.thumbnail_url ? (
                              <img src={d.thumbnail_url} alt="" className="w-6 h-6 rounded object-cover shrink-0"
                                   onError={e => { e.target.style.display = 'none' }} />
                            ) : (
                              <div className="w-6 h-6 rounded bg-brand-border/50 shrink-0" />
                            )}
                            <span className="font-mono text-xs">{d.code}</span>
                            {d.name && <span className="text-xs text-gray-500 truncate flex-1">{d.name}</span>}
                          </button>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Telefon Modeli *</label>
                  <input
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    placeholder="iPhone 15 Pro Max"
                    className="input w-full !text-sm"
                    disabled={busy}
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Varyasyon</label>
                  <select
                    value={variation}
                    onChange={(e) => setVariation(e.target.value)}
                    className="input w-full !text-sm"
                    disabled={busy}
                  >
                    <option value="">— Yok —</option>
                    <option value="SİYAH">SİYAH</option>
                    <option value="BEYAZ">BEYAZ</option>
                    <option value="ŞEFFAF">ŞEFFAF</option>
                    <option value="PARLAK">PARLAK</option>
                    <option value="MAGSAFE">MAGSAFE</option>
                  </select>
                </div>
              </div>
            </>
          )}

          <div>
            <label className="text-xs text-gray-500 mb-1 block">Miktar *</label>
            <input
              type="number" min="1" value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              className="input w-full !text-sm"
              disabled={busy}
            />
          </div>

          <div>
            <label className="text-xs text-gray-500 mb-1 block">Not</label>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={2}
              placeholder="Hatalı baskı nedeni vb."
              className="input w-full !text-sm resize-none"
              disabled={busy}
            />
          </div>
        </div>

        <div className="px-5 py-3 border-t border-brand-border flex items-center justify-end gap-2">
          <button onClick={onClose} disabled={busy} className="btn-secondary">Vazgeç</button>
          <button
            onClick={handleSave}
            disabled={!canSave}
            className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {busy ? 'Kaydediliyor...' : '✓ Kaydet'}
          </button>
        </div>
      </div>
    </div>
  )
}
