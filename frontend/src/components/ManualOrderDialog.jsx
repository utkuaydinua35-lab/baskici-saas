import { useState, useEffect, useMemo } from 'react'
import { api } from '../lib/api'

/**
 * Manuel Sipariş — WhatsApp/telefon vb. platform dışı siparişleri elle gir.
 *
 * Props:
 *   open: boolean
 *   stores: array — mağaza listesi
 *   defaultStoreId: uuid — varsayılan seçili mağaza
 *   onClose: () => void
 *   onCreated: (result) => void
 */
export default function ManualOrderDialog({ open, stores, defaultStoreId, onClose, onCreated, dealerId = null, applyShipping = true }) {
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const [storeId, setStoreId] = useState('')
  const [externalId, setExternalId] = useState('')
  const [customerName, setCustomerName] = useState('')
  const [customerPhone, setCustomerPhone] = useState('')
  const [customerEmail, setCustomerEmail] = useState('')
  const [note, setNote] = useState('')
  const [showAddress, setShowAddress] = useState(false)
  const [address, setAddress] = useState('')
  const [city, setCity] = useState('')
  const [province, setProvince] = useState('')
  const [zip, setZip] = useState('')
  const [lineItems, setLineItems] = useState([])
  const [nextId, setNextId] = useState(1)
  const [designs, setDesigns] = useState([])

  const emptyItem = (id) => ({
    id, title: 'Telefon Kılıfı', design_id: '', device_model: '', quantity: 1, color: '', notes: ''
  })

  useEffect(() => {
    if (open) {
      setBusy(false); setErr('')
      setStoreId(defaultStoreId || (stores[0]?.id || ''))
      setExternalId(''); setCustomerName(''); setCustomerPhone(''); setCustomerEmail('')
      setNote(''); setShowAddress(false)
      setAddress(''); setCity(''); setProvince(''); setZip('')
      setLineItems([emptyItem(1)])
      setNextId(2)
    }
  }, [open, defaultStoreId, stores])

  useEffect(() => {
    if (!storeId) { setDesigns([]); return }
    api.get(`/api/orders/_meta/store-designs?store_id=${storeId}`)
      .then(r => setDesigns(r?.items || []))
      .catch(() => setDesigns([]))
  }, [storeId])

  if (!open) return null

  const addLineItem = () => {
    setLineItems([...lineItems, emptyItem(nextId)])
    setNextId(nextId + 1)
  }
  const removeLineItem = (id) => {
    if (lineItems.length <= 1) return
    setLineItems(lineItems.filter(li => li.id !== id))
  }
  const updateLineItem = (id, patch) => {
    setLineItems(lineItems.map(li => li.id === id ? { ...li, ...patch } : li))
  }

  const allItemsValid = lineItems.every(li => li.title?.trim() && li.device_model?.trim())
  const canSave = storeId && externalId.trim() && customerName.trim() && allItemsValid && !busy

  const handleSave = async () => {
    if (!canSave) return
    setBusy(true); setErr('')
    try {
      const r = await api.post('/api/orders/manual', {
        store_id: storeId,
        dealer_id: dealerId || null,
        apply_shipping: applyShipping,
        external_id: externalId.trim(),
        customer_name: customerName.trim(),
        customer_phone: customerPhone.trim() || null,
        customer_email: customerEmail.trim() || null,
        note: note.trim() || null,
        address: showAddress ? (address.trim() || null) : null,
        city: showAddress ? (city.trim() || null) : null,
        province: showAddress ? (province.trim() || null) : null,
        zip: showAddress ? (zip.trim() || null) : null,
        line_items: lineItems.map(li => ({
          title: li.title.trim(),
          design_id: li.design_id || null,
          device_model: li.device_model.trim(),
          quantity: parseInt(li.quantity) || 1,
          color: li.color.trim() || null,
          notes: li.notes.trim() || null,
        })),
      })
      onCreated?.(r)
    } catch (e) {
      setErr(typeof e?.detail === 'string' ? e.detail : 'Oluşturma başarısız')
      setBusy(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onMouseDown={(e) => e.target === e.currentTarget && !busy && onClose()}
    >
      <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
        <div className="px-5 py-3 border-b border-brand-border flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-100">📝 Manuel Sipariş</h2>
          <button
            onClick={onClose}
            disabled={busy}
            className="text-gray-400 hover:text-gray-200 text-2xl leading-none px-2 disabled:opacity-50"
          >×</button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {err && (
            <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded px-3 py-2">
              {err}
            </div>
          )}

          {/* Sipariş bilgileri */}
          <div>
            <h3 className="text-sm font-medium text-gray-300 mb-2">🧾 Sipariş Bilgileri</h3>
            <div className="grid grid-cols-2 gap-2">
              {!dealerId && (
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Mağaza *</label>
                <select
                  value={storeId}
                  onChange={(e) => setStoreId(e.target.value)}
                  className="input w-full !text-sm"
                  disabled={busy}
                >
                  {stores.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>
              )}
              <div>
                <label className="text-xs text-gray-500 mb-1 block">
                  Sipariş Kodu * <span className="text-gray-600 font-normal">(örn. wa_001)</span>
                </label>
                <input
                  value={externalId}
                  onChange={(e) => setExternalId(e.target.value)}
                  placeholder="wa_001"
                  className="input w-full !text-sm font-mono"
                  disabled={busy}
                />
              </div>
            </div>
          </div>

          {/* Müşteri */}
          <div>
            <h3 className="text-sm font-medium text-gray-300 mb-2">👤 Müşteri</h3>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Ad Soyad *</label>
                <input
                  value={customerName}
                  onChange={(e) => setCustomerName(e.target.value)}
                  placeholder="Müşteri adı"
                  className="input w-full !text-sm"
                  disabled={busy}
                />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-1 block">Telefon</label>
                <input
                  value={customerPhone}
                  onChange={(e) => setCustomerPhone(e.target.value)}
                  placeholder="+90..."
                  className="input w-full !text-sm"
                  disabled={busy}
                />
              </div>
              <div className="col-span-2">
                <label className="text-xs text-gray-500 mb-1 block">E-posta (opsiyonel)</label>
                <input
                  value={customerEmail}
                  onChange={(e) => setCustomerEmail(e.target.value)}
                  type="email"
                  className="input w-full !text-sm"
                  disabled={busy}
                />
              </div>
              <div className="col-span-2">
                <label className="text-xs text-gray-500 mb-1 block">Müşteri Notu</label>
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  rows={2}
                  placeholder="Özel istek vb."
                  className="input w-full !text-sm resize-none"
                  disabled={busy}
                />
              </div>
            </div>
          </div>

          {/* Adres (collapsible) */}
          <div>
            <button
              onClick={() => setShowAddress(!showAddress)}
              type="button"
              className="text-sm text-gray-400 hover:text-gray-200 flex items-center gap-1"
            >
              <span className="text-xs">{showAddress ? '▼' : '▶'}</span>
              📍 Kargo Adresi {!showAddress && <span className="text-xs text-gray-600">(eklemek için tıkla)</span>}
            </button>
            {showAddress && (
              <div className="grid grid-cols-3 gap-2 mt-2">
                <div className="col-span-3">
                  <label className="text-xs text-gray-500 mb-1 block">Açık Adres</label>
                  <input
                    value={address}
                    onChange={(e) => setAddress(e.target.value)}
                    placeholder="Mahalle, sokak, bina, daire..."
                    className="input w-full !text-sm"
                    disabled={busy}
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">İlçe</label>
                  <input
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                    className="input w-full !text-sm"
                    disabled={busy}
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">İl</label>
                  <input
                    value={province}
                    onChange={(e) => setProvince(e.target.value)}
                    className="input w-full !text-sm"
                    disabled={busy}
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500 mb-1 block">Posta K.</label>
                  <input
                    value={zip}
                    onChange={(e) => setZip(e.target.value)}
                    className="input w-full !text-sm"
                    disabled={busy}
                  />
                </div>
              </div>
            )}
          </div>

          {/* Ürünler */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-gray-300">
                📦 Ürünler ({lineItems.length})
              </h3>
              <button
                onClick={addLineItem}
                type="button"
                disabled={busy}
                className="text-xs text-accent hover:underline"
              >+ Ürün Ekle</button>
            </div>
            <div className="space-y-2">
              {lineItems.map((li, i) => (
                <LineItemRow
                  key={li.id}
                  item={li}
                  index={i}
                  designs={designs}
                  canDelete={lineItems.length > 1}
                  busy={busy}
                  onUpdate={(patch) => updateLineItem(li.id, patch)}
                  onDelete={() => removeLineItem(li.id)}
                />
              ))}
            </div>
          </div>
        </div>

        <div className="px-5 py-3 border-t border-brand-border flex items-center justify-end gap-2">
          <button onClick={onClose} disabled={busy} className="btn-secondary">Vazgeç</button>
          <button
            onClick={handleSave}
            disabled={!canSave}
            className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {busy ? 'Oluşturuluyor...' : '✓ Siparişi Oluştur'}
          </button>
        </div>
      </div>
    </div>
  )
}

function LineItemRow({ item, index, designs, canDelete, busy, onUpdate, onDelete }) {
  const [designFilter, setDesignFilter] = useState('')
  const [showDesignList, setShowDesignList] = useState(false)

  const filteredDesigns = useMemo(() => {
    if (!designFilter) return designs.slice(0, 50)
    const q = designFilter.toLowerCase()
    return designs.filter(d =>
      (d.code || '').toLowerCase().includes(q) ||
      (d.name || '').toLowerCase().includes(q)
    ).slice(0, 50)
  }, [designs, designFilter])

  const selectedDesign = designs.find(d => d.id === item.design_id)

  return (
    <div className="border border-brand-border rounded-lg p-3 bg-brand-input/30">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-gray-500">Ürün #{index + 1}</span>
        {canDelete && (
          <button
            onClick={onDelete}
            type="button"
            disabled={busy}
            className="text-red-400/70 hover:text-red-300 text-xs"
          >✕ Sil</button>
        )}
      </div>

      <div className="grid grid-cols-3 gap-2">
        <div className="col-span-3">
          <label className="text-xs text-gray-500 mb-1 block">Ürün Adı *</label>
          <input
            value={item.title}
            onChange={(e) => onUpdate({ title: e.target.value })}
            className="input w-full !text-sm"
            placeholder="Telefon Kılıfı"
            disabled={busy}
          />
        </div>

        <div className="col-span-2 relative">
          <label className="text-xs text-gray-500 mb-1 block">
            Tasarım <span className="text-gray-600 font-normal">(opsiyonel)</span>
          </label>
          {selectedDesign ? (
            <div className="input w-full !text-sm flex items-center gap-2 !py-1.5">
              {selectedDesign.thumbnail_url && (
                <img src={selectedDesign.thumbnail_url} alt="" className="w-6 h-6 rounded object-cover shrink-0" />
              )}
              <span className="font-mono text-xs flex-1 truncate">{selectedDesign.code}</span>
              {selectedDesign.name && (
                <span className="text-[10px] text-gray-500 truncate">{selectedDesign.name}</span>
              )}
              <button
                onClick={() => { onUpdate({ design_id: '' }); setShowDesignList(false); setDesignFilter('') }}
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
                placeholder="Tasarım ara veya boş bırak..."
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
                        onUpdate({ design_id: d.id })
                        setShowDesignList(false)
                        setDesignFilter('')
                      }}
                      className="w-full px-2 py-1.5 text-left text-sm hover:bg-brand-input flex items-center gap-2"
                    >
                      {d.thumbnail_url ? (
                        <img src={d.thumbnail_url} alt="" className="w-6 h-6 rounded object-cover shrink-0" />
                      ) : (
                        <div className="w-6 h-6 rounded bg-brand-border/50 shrink-0" />
                      )}
                      <span className="font-mono text-xs">{d.code}</span>
                      {d.name && <span className="text-xs text-gray-500 truncate flex-1">{d.name}</span>}
                      {d.is_kisiye_ozel && (
                        <span className="text-[9px] px-1 rounded bg-purple-500/15 text-purple-300 shrink-0">kişiye özel</span>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </>
          )}
        </div>

        <div>
          <label className="text-xs text-gray-500 mb-1 block">Miktar</label>
          <input
            type="number"
            min="1"
            value={item.quantity}
            onChange={(e) => onUpdate({ quantity: e.target.value })}
            className="input w-full !text-sm"
            disabled={busy}
          />
        </div>

        <div className="col-span-2">
          <label className="text-xs text-gray-500 mb-1 block">Telefon Modeli *</label>
          <input
            value={item.device_model}
            onChange={(e) => onUpdate({ device_model: e.target.value })}
            className="input w-full !text-sm"
            placeholder="iPhone 15 Pro Max"
            disabled={busy}
          />
        </div>

        <div>
          <label className="text-xs text-gray-500 mb-1 block">Renk</label>
          <input
            value={item.color}
            onChange={(e) => onUpdate({ color: e.target.value })}
            className="input w-full !text-sm"
            placeholder="Siyah"
            disabled={busy}
          />
        </div>

        <div className="col-span-3">
          <label className="text-xs text-gray-500 mb-1 block">Notlar (ürüne özel)</label>
          <input
            value={item.notes}
            onChange={(e) => onUpdate({ notes: e.target.value })}
            className="input w-full !text-sm"
            placeholder="örn. parlak yüzeyli"
            disabled={busy}
          />
        </div>
      </div>
    </div>
  )
}
