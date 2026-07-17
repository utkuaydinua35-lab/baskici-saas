import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { useStore } from '../lib/store'
import { useToast } from '../components/Toast'
import SaveBar from '../components/SaveBar'

// Envanter — tüm varyantlar tek tabloda, satır içi stok düzenleme (Shopify
// Inventory ekranı). Değişiklikler kaydet çubuğuyla toplu gönderilir.
const FILTERS = [
  ['all', 'Tümü'], ['low', 'Az stok (<5)'], ['out', 'Stoksuz'], ['untracked', 'Takipsiz'],
]

export default function EnvanterPage() {
  const { storeId } = useStore()
  const toast = useToast()
  const [data, setData] = useState({ items: [], total: 0, out_of_stock: 0, low_stock: 0 })
  const [filter, setFilter] = useState('all')
  const [q, setQ] = useState('')
  const [edits, setEdits] = useState({})   // variant_id -> {quantity?, track_stock?}
  const [busy, setBusy] = useState(false)
  const qRef = useRef('')

  const load = useCallback(async () => {
    if (!storeId) return
    try {
      const params = new URLSearchParams({ store_id: storeId, filter })
      if (qRef.current.trim()) params.set('q', qRef.current.trim())
      setData(await api.get(`/api/catalog/inventory?${params}`))
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Envanter yüklenemedi')
    }
  }, [storeId, filter])
  useEffect(() => {
    qRef.current = q
    const t = setTimeout(load, q ? 300 : 0)  // aramada debounce, ilk yüklemede anında
    return () => clearTimeout(t)
  }, [q, load])

  const patch = (id, p) => setEdits(e => ({ ...e, [id]: { ...e[id], ...p } }))
  const dirty = Object.keys(edits).length > 0

  const save = async () => {
    setBusy(true)
    try {
      const updates = Object.entries(edits).map(([variant_id, p]) => ({ variant_id, ...p }))
      const r = await api.post(`/api/catalog/inventory/bulk?store_id=${storeId}`, { updates })
      setEdits({})
      await load()
      toast.success(`${r.updated} varyant güncellendi`)
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Kaydedilemedi')
    } finally { setBusy(false) }
  }

  const val = (row, key) => {
    const e = edits[row.variant_id]
    return e && key in e ? e[key] : row[key]
  }

  return (
    <div className="space-y-4 pb-10">
      <SaveBar dirty={dirty} busy={busy} onSave={save} onDiscard={() => setEdits({})} />
      <div className="flex items-center gap-3 flex-wrap">
        <h1 className="text-xl font-semibold">Envanter</h1>
        <span className="text-sm text-panel-muted">
          {data.total} varyant
          {data.low_stock > 0 && <span className="text-amber-300"> · {data.low_stock} az stok</span>}
          {data.out_of_stock > 0 && <span className="text-red-400"> · {data.out_of_stock} stoksuz</span>}
        </span>
        <input value={q} onChange={e => setQ(e.target.value)}
          placeholder="Ürün, model veya SKU ara…" className="input !w-64 ml-auto" />
      </div>

      <div className="flex gap-1 bg-panel-input rounded-xl p-1 w-fit text-sm">
        {FILTERS.map(([k, l]) => (
          <button key={k} onClick={() => setFilter(k)}
            className={`px-3 py-1.5 rounded-lg transition ${filter === k
              ? 'bg-panel-card shadow-sm font-medium' : 'text-panel-muted hover:text-panel-ink'}`}>
            {l}
          </button>
        ))}
      </div>

      <div className="card !p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="text-panel-muted text-xs bg-panel-input">
            <tr>
              <th className="text-left px-4 py-2.5">Ürün / Varyant</th>
              <th className="text-left px-4 py-2.5">SKU</th>
              <th className="text-center px-4 py-2.5">Stok takibi</th>
              <th className="text-right px-4 py-2.5 w-32">Adet</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map(row => {
              const tracked = val(row, 'track_stock')
              const qty = val(row, 'quantity')
              const changed = !!edits[row.variant_id]
              return (
                <tr key={row.variant_id}
                  className={`border-t border-panel-border ${changed ? 'bg-sky-500/10/60' : ''}`}>
                  <td className="px-4 py-2">
                    <Link to={`/urunler/${row.product_id}`} className="font-medium hover:underline">
                      {row.product_title}
                    </Link>
                    <div className="text-xs text-panel-muted">
                      {row.model_display}{row.variation ? ` · ${row.variation}` : ''}
                      {row.product_status !== 'active' && (
                        <span className="ml-1.5 text-[10px] bg-slate-500/15 text-slate-500 px-1.5 py-0.5 rounded-full">
                          {row.product_status === 'draft' ? 'taslak' : 'arşiv'}
                        </span>
                      )}
                      {!row.is_active && (
                        <span className="ml-1.5 text-[10px] bg-red-500/10 text-red-500 px-1.5 py-0.5 rounded-full">
                          varyant pasif
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-2 font-mono text-xs text-panel-muted">{row.sku || '—'}</td>
                  <td className="px-4 py-2 text-center">
                    <input type="checkbox" checked={!!tracked}
                      onChange={e => patch(row.variant_id, { track_stock: e.target.checked })} />
                  </td>
                  <td className="px-4 py-2 text-right">
                    {tracked ? (
                      <input type="number" min="0" value={qty}
                        onChange={e => patch(row.variant_id, { quantity: Math.max(0, Number(e.target.value) || 0) })}
                        className={`input !w-24 text-right tabular-nums !py-1.5 ${
                          tracked && qty <= 0 ? '!border-red-300' : tracked && qty < 5 ? '!border-amber-300' : ''}`} />
                    ) : (
                      <span className="text-xs text-panel-muted">∞ sınırsız</span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {data.items.length === 0 && (
          <div className="p-6 text-sm text-panel-muted text-center">
            {filter === 'all' && !q ? 'Henüz varyant yok.' : 'Bu filtrede sonuç yok.'}
          </div>
        )}
      </div>

      <p className="text-xs text-panel-muted max-w-2xl">
        Stok takibi kapalı varyantlar her zaman satın alınabilir. Takipli varyantlarda stok,
        vitrinde sipariş verildikçe otomatik düşer; 5'in altına inince üründe "Son N adet" rozeti çıkar.
      </p>
    </div>
  )
}
