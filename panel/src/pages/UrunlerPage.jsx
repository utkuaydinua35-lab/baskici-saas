import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, getToken } from '../lib/api'
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
  const [showImport, setShowImport] = useState(false)
  const [showBulkEdit, setShowBulkEdit] = useState(false)

  const exportCsv = async () => {
    try {
      const res = await fetch(`/api/catalog/export?store_id=${storeId}`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      })
      if (!res.ok) throw new Error()
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = 'urunler.csv'; a.click()
      URL.revokeObjectURL(url)
    } catch { setError('Dışa aktarma başarısız') }
  }

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
        <div className="ml-auto flex gap-2">
          <button onClick={exportCsv} className="btn-ghost text-xs">⬇ Dışa Aktar</button>
          <button onClick={() => setShowImport(true)} className="btn-ghost text-xs">⬆ İçe Aktar</button>
          <button onClick={() => setShowCreate(true)} className="btn-primary">+ Yeni Ürün</button>
        </div>
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
          <button disabled={bulkBusy} onClick={() => setShowBulkEdit(true)}
            className="px-3 py-1 rounded-lg text-xs bg-indigo-100 text-indigo-700 disabled:opacity-50">✏️ Toplu Düzenle</button>
          <button onClick={() => setChecked(new Set())} className="ml-auto text-xs text-panel-muted">Seçimi bırak</button>
        </div>
      )}

      {showBulkEdit && (
        <BulkEditModal ids={[...checked]} storeId={storeId}
          onClose={() => setShowBulkEdit(false)}
          onDone={() => { setShowBulkEdit(false); setChecked(new Set()); load() }} />
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

      {showImport && (
        <ImportModal storeId={storeId}
          onClose={() => setShowImport(false)}
          onDone={() => { setShowImport(false); load() }} />
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


// CSV içe aktarma — önce dry-run önizleme, onayla → gerçek import.
function ImportModal({ storeId, onClose, onDone }) {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)   // dry-run sonucu
  const [result, setResult] = useState(null)     // gerçek import sonucu
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const run = async (dryRun) => {
    if (!file) return
    setBusy(true); setErr('')
    try {
      const fd = new FormData()
      fd.append('file', file)
      const r = await api.postForm(
        `/api/catalog/import?store_id=${storeId}&dry_run=${dryRun}`, fd)
      dryRun ? setPreview(r) : setResult(r)
    } catch (e) {
      setErr(typeof e?.detail === 'string' ? e.detail : 'İşlem başarısız')
    } finally { setBusy(false) }
  }

  const Stat = ({ n, label }) => (
    <div className="bg-panel-input rounded-xl p-2.5 text-center">
      <div className="text-lg font-semibold tabular-nums">{n}</div>
      <div className="text-[10px] text-panel-muted">{label}</div>
    </div>
  )

  return (
    <Modal title="CSV İçe Aktar" onClose={onClose} wide>
      <div className="space-y-4">
        <p className="text-xs text-panel-muted">
          Şablon için önce <b>Dışa Aktar</b>'ı kullanın. Eşleştirme: ürün = <code>urun_slug</code>,
          varyant = <code>model_key + renk</code>. Var olanlar güncellenir, olmayanlar oluşturulur.
        </p>

        {!preview && !result && (
          <>
            <label className="block border-2 border-dashed border-panel-border rounded-xl p-6 text-center cursor-pointer hover:border-slate-400">
              <input type="file" accept=".csv,text/csv" className="hidden"
                onChange={e => setFile(e.target.files?.[0] || null)} />
              {file ? <span className="text-sm font-medium">{file.name}</span>
                : <span className="text-sm text-panel-muted">CSV dosyası seçin</span>}
            </label>
            <button onClick={() => run(true)} disabled={!file || busy} className="btn-primary w-full">
              {busy ? 'İnceleniyor…' : 'Önizle (henüz uygulanmaz)'}
            </button>
          </>
        )}

        {preview && !result && (
          <>
            <div className="grid grid-cols-4 gap-2">
              <Stat n={preview.products_created} label="yeni ürün" />
              <Stat n={preview.products_updated} label="güncellenecek ürün" />
              <Stat n={preview.variants_created} label="yeni varyant" />
              <Stat n={preview.variants_updated} label="güncellenecek varyant" />
            </div>
            {preview.errors.length > 0 && (
              <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 max-h-32 overflow-y-auto">
                <div className="text-xs font-medium text-amber-800 mb-1">
                  {preview.errors.length} satır atlanacak:
                </div>
                {preview.errors.map((e, i) => (
                  <div key={i} className="text-[11px] text-amber-700">Satır {e.satir}: {e.mesaj}</div>
                ))}
              </div>
            )}
            <div className="flex gap-2">
              <button onClick={() => setPreview(null)} className="btn-ghost flex-1">Geri</button>
              <button onClick={() => run(false)} disabled={busy} className="btn-primary flex-1">
                {busy ? 'Uygulanıyor…' : 'Onayla ve Uygula'}
              </button>
            </div>
          </>
        )}

        {result && (
          <div className="text-center space-y-3">
            <div className="text-3xl">✅</div>
            <p className="text-sm">
              {result.products_created} yeni + {result.products_updated} güncellenen ürün,{' '}
              {result.variants_created} yeni + {result.variants_updated} güncellenen varyant.
            </p>
            <button onClick={onDone} className="btn-primary">Tamam</button>
          </div>
        )}

        {err && <p className="text-sm text-red-600">{err}</p>}
      </div>
    </Modal>
  )
}

// Toplu düzenleme (Shopify bulk editor) — seçili ürünlere fiyat/koleksiyon/etiket.
export function BulkEditModal({ ids, storeId, onClose, onDone }) {
  const [collections, setCollections] = useState([])
  const [priceMode, setPriceMode] = useState('')     // '' | percent | set
  const [priceValue, setPriceValue] = useState('')
  const [compareFromOld, setCompareFromOld] = useState(true)
  const [collectionId, setCollectionId] = useState('')
  const [tags, setTags] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  useEffect(() => {
    api.get(`/api/catalog/collections?store_id=${storeId}`)
      .then(c => setCollections(c.filter(x => x.is_active))).catch(() => {})
  }, [storeId])

  const submit = async (e) => {
    e.preventDefault()
    if (!priceMode && !collectionId && !tags.trim()) {
      setErr('En az bir işlem seçin'); return
    }
    setBusy(true); setErr('')
    try {
      const r = await api.post('/api/catalog/products/bulk-edit', {
        ids,
        price_mode: priceMode || null,
        price_value: priceMode ? Number(priceValue) : null,
        compare_at_from_old: priceMode === 'percent' && compareFromOld,
        add_collection_id: collectionId || null,
        add_tags: tags.trim() || null,
      })
      onDone(r.updated)
    } catch (e2) {
      setErr(typeof e2?.detail === 'string' ? e2.detail : 'Toplu düzenleme başarısız')
    } finally { setBusy(false) }
  }

  return (
    <Modal title={`Toplu Düzenle — ${ids.length} ürün`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <fieldset className="space-y-2">
          <legend className="text-sm font-medium">💰 Fiyat</legend>
          <div className="flex gap-2 items-center flex-wrap">
            <select className="input !w-44" value={priceMode} onChange={e => setPriceMode(e.target.value)}>
              <option value="">Değiştirme</option>
              <option value="percent">Yüzde değiştir (±%)</option>
              <option value="set">Sabit fiyat yap (₺)</option>
            </select>
            {priceMode && (
              <input className="input !w-28" type="number" step="0.01" required
                value={priceValue} onChange={e => setPriceValue(e.target.value)}
                placeholder={priceMode === 'percent' ? 'örn -15' : 'örn 399.90'} />
            )}
          </div>
          {priceMode === 'percent' && (
            <label className="flex items-center gap-2 text-xs text-panel-muted">
              <input type="checkbox" checked={compareFromOld}
                onChange={e => setCompareFromOld(e.target.checked)} />
              İndirimde eski fiyatı "indirim öncesi" olarak göster (%X İNDİRİM rozeti çıkar)
            </label>
          )}
        </fieldset>

        <fieldset className="space-y-2">
          <legend className="text-sm font-medium">🗂️ Koleksiyona ekle</legend>
          <select className="input" value={collectionId} onChange={e => setCollectionId(e.target.value)}>
            <option value="">Ekleme</option>
            {collections.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}
          </select>
        </fieldset>

        <fieldset className="space-y-2">
          <legend className="text-sm font-medium">🏷️ Etiket ekle</legend>
          <input className="input" value={tags} onChange={e => setTags(e.target.value)}
            placeholder="yaz-koleksiyonu, indirim (virgülle)" maxLength={300} />
        </fieldset>

        {err && <p className="text-sm text-red-600">{err}</p>}
        <div className="flex justify-end gap-2 pt-1">
          <button type="button" onClick={onClose} className="btn-ghost">Vazgeç</button>
          <button disabled={busy} className="btn-primary">
            {busy ? 'Uygulanıyor…' : `${ids.length} Ürüne Uygula`}
          </button>
        </div>
      </form>
    </Modal>
  )
}
