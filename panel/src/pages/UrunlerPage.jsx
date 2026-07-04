import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useStore } from '../lib/store'

// Ürünler — katalog yönetimi (Faz 4'te tam sayfa editöre genişleyecek).
export default function UrunlerPage() {
  const navigate = useNavigate()
  const { storeId } = useStore()
  const [products, setProducts] = useState([])
  const [checked, setChecked] = useState(new Set())
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [bulkBusy, setBulkBusy] = useState(false)

  const load = useCallback(async () => {
    if (!storeId) return
    setLoading(true); setError('')
    try {
      setProducts(await api.get(`/api/catalog/products?store_id=${storeId}`))
      setChecked(new Set())
    } catch (e) {
      setError(typeof e?.detail === 'string' ? e.detail : 'Ürünler yüklenemedi')
    } finally { setLoading(false) }
  }, [storeId])

  useEffect(() => { load() }, [load])

  const bulkStatus = async (status) => {
    if (checked.size === 0) return
    setBulkBusy(true); setError('')
    try {
      await api.post('/api/catalog/products/bulk-status', { ids: [...checked], status })
      await load()
    } catch { setError('Toplu güncelleme başarısız') }
    finally { setBulkBusy(false) }
  }

  const toggleCheck = (id, e) => {
    e.stopPropagation()
    setChecked(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-semibold">Ürünler</h1>
        <span className="text-sm text-panel-muted">{products.length} ürün</span>
        <button onClick={() => setShowCreate(true)} className="btn-primary ml-auto">+ Yeni Ürün</button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {loading && <p className="text-sm text-panel-muted">Yükleniyor…</p>}

      {checked.size > 0 && (
        <div className="card !py-2.5 flex items-center gap-3 text-sm">
          <span className="font-medium">{checked.size} ürün seçili</span>
          <button disabled={bulkBusy} onClick={() => bulkStatus('active')}
            className="px-3 py-1 rounded-lg text-xs bg-emerald-100 text-emerald-700 disabled:opacity-50">Yayınla</button>
          <button disabled={bulkBusy} onClick={() => bulkStatus('draft')}
            className="px-3 py-1 rounded-lg text-xs bg-slate-100 text-slate-600 disabled:opacity-50">Taslağa Al</button>
          <button disabled={bulkBusy} onClick={() => bulkStatus('archived')}
            className="px-3 py-1 rounded-lg text-xs bg-amber-100 text-amber-700 disabled:opacity-50">Arşivle</button>
          <button onClick={() => setChecked(new Set())} className="ml-auto text-xs text-panel-muted">Seçimi bırak</button>
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {products.map(p => (
          <div key={p.id} onClick={() => navigate(`/urunler/${p.id}`)}
            className="relative text-left card !p-0 overflow-hidden hover:shadow-md hover:border-panel-accent/40 transition cursor-pointer">
            <input type="checkbox" checked={checked.has(p.id)}
              onClick={e => toggleCheck(p.id, e)} onChange={() => {}}
              className="absolute top-2 left-2 z-10 w-4 h-4 accent-emerald-600 bg-white rounded" />
            <div className="aspect-square bg-panel-input flex items-center justify-center">
              {p.cover_image
                ? <img src={p.cover_image} alt={p.title} className="w-full h-full object-cover" />
                : <span className="text-3xl opacity-30">🖼️</span>}
            </div>
            <div className="p-3">
              <div className="flex items-center gap-2">
                <span className="font-medium text-sm truncate">{p.title}</span>
                <StatusBadge status={p.status} />
              </div>
              <div className="text-xs text-panel-muted mt-1">
                {fmtPrice(p.base_price)} · {p.variant_count} varyant
              </div>
            </div>
          </div>
        ))}
      </div>
      {!loading && products.length === 0 && (
        <div className="card text-center !p-10">
          <div className="text-3xl">🛍️</div>
          <p className="mt-2 text-sm text-panel-muted">
            Henüz ürün yok — ilk ürününü ekleyerek satışa başla.
          </p>
          <button onClick={() => setShowCreate(true)} className="btn-primary mt-4">+ Yeni Ürün</button>
        </div>
      )}

      {showCreate && (
        <CreateProductModal storeId={storeId}
          onClose={() => setShowCreate(false)}
          onCreated={(p) => { setShowCreate(false); navigate(`/urunler/${p.id}`) }} />
      )}
    </div>
  )
}

export function StatusBadge({ status }) {
  const map = {
    draft: ['Taslak', 'bg-slate-100 text-slate-600'],
    active: ['Yayında', 'bg-emerald-100 text-emerald-700'],
    archived: ['Arşiv', 'bg-amber-100 text-amber-700'],
  }
  const [label, cls] = map[status] || [status, 'bg-slate-100 text-slate-600']
  return <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${cls} shrink-0`}>{label}</span>
}

export function fmtPrice(v) {
  const n = Number(v)
  if (Number.isNaN(n)) return v
  return new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY' }).format(n)
}

export function Modal({ title, children, onClose, wide }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40" onClick={onClose}>
      <div className={`card w-full ${wide ? 'max-w-2xl' : 'max-w-md'} max-h-[85vh] overflow-y-auto !p-5`}
        onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold truncate">{title}</h2>
          <button onClick={onClose} className="text-panel-muted hover:text-panel-ink text-lg leading-none">×</button>
        </div>
        {children}
      </div>
    </div>
  )
}

function CreateProductModal({ storeId, onClose, onCreated }) {
  const [title, setTitle] = useState('')
  const [price, setPrice] = useState('')
  const [description, setDescription] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setErr('')
    try {
      const p = await api.post('/api/catalog/products', {
        store_id: storeId, title, base_price: price, description: description || null,
      })
      onCreated(p)
    } catch (e2) {
      setErr(typeof e2?.detail === 'string' ? e2.detail : 'Ürün oluşturulamadı')
    } finally { setBusy(false) }
  }

  return (
    <Modal title="Yeni Ürün" onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <label className="block text-sm">
          <span className="text-panel-muted text-xs">Ürün adı</span>
          <input className="input mt-1" value={title} onChange={e => setTitle(e.target.value)}
            required maxLength={300} placeholder="Örn: Retro Dalga Telefon Kılıfı" />
        </label>
        <label className="block text-sm">
          <span className="text-panel-muted text-xs">Fiyat (₺)</span>
          <input className="input mt-1" value={price} onChange={e => setPrice(e.target.value)}
            required type="number" min="0" step="0.01" placeholder="349.90" />
        </label>
        <label className="block text-sm">
          <span className="text-panel-muted text-xs">Açıklama</span>
          <textarea className="input mt-1" rows={4} value={description}
            onChange={e => setDescription(e.target.value)} maxLength={20000} />
        </label>
        {err && <p className="text-sm text-red-600">{err}</p>}
        <div className="flex justify-end gap-2 pt-1">
          <button type="button" onClick={onClose} className="btn-ghost">Vazgeç</button>
          <button disabled={busy} className="btn-primary">
            {busy ? 'Kaydediliyor…' : 'Oluştur'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

