import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, getToken } from '../lib/api'
import { useStore } from '../lib/store'
import { useToast } from '../components/Toast'
import { mutlak } from '../lib/taban'

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
  const [showTablo, setShowTablo] = useState(false)
  const [showSets, setShowSets] = useState(false)
  const [showStok, setShowStok] = useState(false)
  const [showBulkSet, setShowBulkSet] = useState(false)
  const [showFixVariants, setShowFixVariants] = useState(false)
  // Arama + filtreler (istemci tarafında — liste zaten tamamı yüklü)
  const [q, setQ] = useState('')
  const [durum, setDurum] = useState('')     // '' | active | draft | archived
  const [ozel, setOzel] = useState('')       // '' | varyantsiz | gorselsiz | maliyetsiz | indirimli
  const [sirala, setSirala] = useState('yeni')
  const noVariantCount = products.filter(p => !p.variant_count).length

  const exportCsv = async () => {
    try {
      const res = await fetch(mutlak(`/api/catalog/export?store_id=${storeId}`), {
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

  // Toplu silme geri alınamaz — bu yüzden iki aşamalı onay: önce ne olacağı
  // anlatılır, sonra ürün sayısı elle yazdırılır (kazara tıklamaya karşı).
  const bulkDelete = async () => {
    if (checked.size === 0) return
    const adet = checked.size
    if (!window.confirm(
      `${adet} ürün KALICI olarak silinecek. Görselleri de silinir ve bu işlem geri alınamaz.\n\n` +
      'Ürünü vitrinden kaldırmak istiyorsanız "Arşivle" daha güvenli — kayıt durur, ' +
      'sadece görünmez olur.\n\nYine de silmek istiyor musunuz?')) return
    const cevap = window.prompt(`Onaylamak için silinecek ürün sayısını yazın: ${adet}`)
    if (String(cevap || '').trim() !== String(adet)) {
      setError('Silme iptal edildi — sayı eşleşmedi')
      return
    }
    setBulkBusy(true); setError('')
    try {
      const r = await api.post('/api/catalog/products/bulk-delete',
        { ids: [...checked], confirm: true })
      setChecked(new Set())
      await load()
      setError(`${r.deleted} ürün silindi`)
    } catch { setError('Toplu silme başarısız') }
    finally { setBulkBusy(false) }
  }

  // Arama: ürün adı, URL (slug) ve etiketlerde geçiyor mu
  const filtreli = useMemo(() => {
    const ara = q.trim().toLocaleLowerCase('tr')
    let liste = products.filter(p => {
      if (durum && p.status !== durum) return false
      if (ozel === 'varyantsiz' && p.variant_count) return false
      if (ozel === 'gorselsiz' && p.cover_image) return false
      if (ozel === 'maliyetsiz' && p.cost_price) return false
      if (ozel === 'indirimli' &&
          !(p.compare_at_price && Number(p.compare_at_price) > Number(p.base_price))) return false
      if (!ara) return true
      return (p.title || '').toLocaleLowerCase('tr').includes(ara)
        || (p.slug || '').toLowerCase().includes(ara)
        || (p.tags || '').toLocaleLowerCase('tr').includes(ara)
    })
    const say = { yeni: (a, b) => (b.created_at || '').localeCompare(a.created_at || ''),
      ad: (a, b) => (a.title || '').localeCompare(b.title || '', 'tr'),
      ucuz: (a, b) => Number(a.base_price) - Number(b.base_price),
      pahali: (a, b) => Number(b.base_price) - Number(a.base_price),
      varyant: (a, b) => (a.variant_count || 0) - (b.variant_count || 0) }
    return [...liste].sort(say[sirala] || say.yeni)
  }, [products, q, durum, ozel, sirala])

  const filtreVar = !!(q.trim() || durum || ozel)
  const temizle = () => { setQ(''); setDurum(''); setOzel('') }

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
      {/* TELEFON: dört düğme tek satıra sığmayıp taşıyordu — sarıyor ve
          "Yeni Ürün" tam genişlik birincil eylem oluyor. */}
      <div className="flex items-center gap-3 flex-wrap">
        <h1 className="text-xl font-semibold">Ürünler</h1>
        <span className="text-sm text-panel-muted">
          {filtreVar ? `${filtreli.length} / ${products.length} ürün` : `${products.length} ürün`}
        </span>
        <Link to="/urunler/yeni"
              className="btn-primary ml-auto order-2 sm:order-none w-full sm:w-auto text-center">
          + Yeni Ürün
        </Link>
        <div className="flex gap-2 flex-wrap w-full sm:w-auto sm:ml-auto
                        [&>button]:!py-2 sm:[&>button]:!py-1.5">
          <button onClick={() => setShowSets(true)} className="btn-ghost text-xs">🧩 Varyant Setleri</button>
          <button onClick={exportCsv} className="btn-ghost text-xs">⬇ Dışa Aktar</button>
          <button onClick={() => setShowImport(true)} className="btn-ghost text-xs">⬆ İçe Aktar</button>
        </div>
      </div>

      {error && <p className="text-sm text-red-300">{error}</p>}
      {loading && <p className="text-sm text-panel-muted">Yükleniyor…</p>}

      {/* Varyantsız ürünler satın ALINAMAZ — sessiz satış kaybı, tek tık düzeltme */}
      {noVariantCount > 0 && (
        <div className="card !py-2.5 border-amber-500/30 bg-amber-500/10 flex items-center gap-3 text-sm">
          <span>⚠️</span>
          <div className="min-w-0">
            <b>{noVariantCount} ürün varyantsız</b> — müşteri telefon modeli
            seçemediği için sepete ekleyemiyor.
          </div>
          <button onClick={() => setShowFixVariants(true)}
            className="ml-auto shrink-0 px-3 py-1 rounded-lg text-xs bg-amber-500/10 text-amber-300">
            🧩 Hepsine set uygula
          </button>
        </div>
      )}

      {/* Arama + filtreler — 600+ ürünlü katalogda aranan ürüne saniyede ulaşım */}
      {products.length > 0 && (
        <div className="card !py-3 space-y-2.5">
          <div className="flex gap-2 flex-wrap items-center">
            <div className="relative flex-1 min-w-[220px]">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-panel-muted text-sm">🔍</span>
              <input className="input !pl-8" value={q} onChange={e => setQ(e.target.value)}
                placeholder="Ürün adı, URL veya etikette ara…" />
              {q && (
                <button onClick={() => setQ('')}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-panel-muted hover:text-panel-ink">×</button>
              )}
            </div>
            <select className="input !w-auto !py-2 text-sm" value={sirala}
              onChange={e => setSirala(e.target.value)}>
              <option value="yeni">Yeni eklenen</option>
              <option value="ad">Ada göre (A→Z)</option>
              <option value="ucuz">Fiyat (artan)</option>
              <option value="pahali">Fiyat (azalan)</option>
              <option value="varyant">Varyant (az→çok)</option>
            </select>
          </div>

          <div className="flex gap-1.5 flex-wrap items-center">
            {[['', 'Tümü'], ['active', 'Yayında'], ['draft', 'Taslak'], ['archived', 'Arşiv']].map(([v, l]) => (
              <button key={v} onClick={() => setDurum(v)}
                className={`px-2.5 py-2 sm:py-1 rounded-lg text-xs border transition ${durum === v
                  ? 'border-panel-accent bg-emerald-500/10 text-emerald-300 font-medium'
                  : 'border-panel-border text-panel-muted hover:text-panel-ink'}`}>
                {l}
                <span className="ml-1 opacity-60">
                  {v ? products.filter(p => p.status === v).length : products.length}
                </span>
              </button>
            ))}
            <span className="w-px h-4 bg-panel-border mx-1" />
            {[['varyantsiz', '⚠️ Varyantsız'], ['gorselsiz', '🖼️ Görselsiz'],
              ['maliyetsiz', '💰 Maliyeti yok'], ['indirimli', '🏷️ İndirimli']].map(([v, l]) => (
              <button key={v} onClick={() => setOzel(ozel === v ? '' : v)}
                className={`px-2.5 py-2 sm:py-1 rounded-lg text-xs border transition ${ozel === v
                  ? 'border-indigo-500/30 bg-indigo-500/10 text-indigo-300 font-medium'
                  : 'border-panel-border text-panel-muted hover:text-panel-ink'}`}>
                {l}
              </button>
            ))}
            {filtreVar && (
              <button onClick={temizle} className="ml-auto text-xs text-panel-muted hover:text-panel-ink">
                Filtreyi temizle
              </button>
            )}
          </div>
        </div>
      )}

      {checked.size > 0 && (
        <div className="card !py-2.5 flex items-center gap-3 text-sm">
          <span className="font-medium">{checked.size} ürün seçili</span>
          <button disabled={bulkBusy} onClick={() => bulkStatus('active')}
            className="px-3 py-1 rounded-lg text-xs bg-emerald-500/10 text-emerald-300 disabled:opacity-50">Yayınla</button>
          <button disabled={bulkBusy} onClick={() => bulkStatus('draft')}
            className="px-3 py-1 rounded-lg text-xs bg-white/5 text-panel-muted disabled:opacity-50">Taslağa Al</button>
          <button disabled={bulkBusy} onClick={() => bulkStatus('archived')}
            className="px-3 py-1 rounded-lg text-xs bg-amber-500/10 text-amber-300 disabled:opacity-50">Arşivle</button>
          <button disabled={bulkBusy} onClick={() => setShowBulkEdit(true)}
            className="px-3 py-1 rounded-lg text-xs bg-indigo-500/10 text-indigo-300 disabled:opacity-50"
            title="Seçili ürünlerin HEPSİNE aynı işlem (ör. %10 zam)">✏️ Toplu Düzenle</button>
          <button disabled={bulkBusy} onClick={() => setShowTablo(true)}
            className="px-3 py-1 rounded-lg text-xs bg-violet-500/10 text-violet-300 disabled:opacity-50"
            title="Her ürünü tabloda tek tek düzenle">📊 Tablo Düzenleyici</button>
          <button disabled={bulkBusy} onClick={() => setShowBulkSet(true)}
            className="px-3 py-1 rounded-lg text-xs bg-teal-500/10 text-teal-300 disabled:opacity-50">🧩 Varyant Seti Uygula</button>
          <button disabled={bulkBusy} onClick={() => setShowStok(true)}
            className="px-3 py-1 rounded-lg text-xs bg-sky-500/10 text-sky-300 disabled:opacity-50"
            title="Siparişe göre üretilen ürünlerde stok takibi kapalı olmalı">📦 Stok Takibi</button>
          <button disabled={bulkBusy} onClick={bulkDelete}
            className="px-3 py-1 rounded-lg text-xs bg-red-500/10 text-red-300 disabled:opacity-50">🗑️ Sil</button>
          <button onClick={() => setChecked(new Set())} className="ml-auto text-xs text-panel-muted">Seçimi bırak</button>
        </div>
      )}

      {showSets && <VariantSetsModal storeId={storeId} onClose={() => setShowSets(false)} />}

      {showStok && (
        <StokTakibiModal storeId={storeId} ids={[...checked]}
          onClose={() => setShowStok(false)}
          onDone={() => { setShowStok(false); setChecked(new Set()); load() }} />
      )}

      {showTablo && (
        <TabloDuzenleyici urunler={products.filter(p => checked.has(p.id))}
          onClose={() => setShowTablo(false)}
          onDone={() => { setShowTablo(false); setChecked(new Set()); load() }} />
      )}

      {showBulkEdit && (
        <BulkEditModal ids={[...checked]} storeId={storeId}
          onClose={() => setShowBulkEdit(false)}
          onDone={() => { setShowBulkEdit(false); setChecked(new Set()); load() }} />
      )}

      {showBulkSet && (
        <BulkApplySetModal ids={[...checked]} storeId={storeId}
          onClose={() => setShowBulkSet(false)}
          onDone={() => { setShowBulkSet(false); setChecked(new Set()); load() }} />
      )}

      {showFixVariants && (
        <BulkApplySetModal ids={[]} storeId={storeId} allWithoutVariants
          onClose={() => setShowFixVariants(false)}
          onDone={() => { setShowFixVariants(false); load() }} />
      )}

      {/* Shopify tarzı liste görünümü — satır tıklanınca detaya gider */}
      {filtreli.length > 0 && (
        <>
      {/* TELEFON: tablo yerine kart; seçim kutusu ve kapak görseli korunuyor. */}
      <div className="sm:hidden space-y-2">
        {filtreli.map(p => (
          <div key={p.id}
               className={`card !p-3 flex items-center gap-3 ${
                 checked.has(p.id) ? 'border border-emerald-500/40 bg-emerald-500/5' : ''}`}>
            <label className="p-1 -m-1 shrink-0 cursor-pointer">
              <input type="checkbox" checked={checked.has(p.id)}
                onClick={e => toggleCheck(p.id, e)} onChange={() => {}}
                aria-label="Ürünü seç" className="w-5 h-5 accent-emerald-600" />
            </label>
            <div onClick={() => navigate(`/urunler/${p.id}`)}
                 className="flex items-center gap-3 min-w-0 flex-1 cursor-pointer">
              <div className="w-12 h-12 rounded-lg bg-panel-input overflow-hidden shrink-0 flex items-center justify-center">
                {p.cover_image
                  ? <img src={p.cover_image} alt={p.title} className="w-full h-full object-cover" />
                  : <span className="opacity-30">🖼️</span>}
              </div>
              <div className="min-w-0 flex-1">
                <div className="font-medium text-sm truncate">{p.title}</div>
                <div className="flex items-center gap-2 mt-1">
                  <StatusBadge status={p.status} />
                  <span className="text-[11.5px] text-panel-muted">
                    {p.variant_count} varyant
                  </span>
                </div>
              </div>
              <div className="tabular-nums text-sm font-medium shrink-0">{fmtPrice(p.base_price)}</div>
            </div>
          </div>
        ))}
      </div>

<div className="card !p-0 overflow-hidden hidden sm:block">
        <table className="w-full text-sm">
          <thead className="text-panel-muted bg-panel-input text-xs">
            <tr>
              <th className="w-10 px-3 py-2.5">
                <input type="checkbox" aria-label="Tümünü seç"
                  checked={filtreli.length > 0 && filtreli.every(p => checked.has(p.id))}
                  onChange={() => setChecked(
                    filtreli.every(p => checked.has(p.id))
                      ? new Set() : new Set(filtreli.map(p => p.id)))}
                  className="w-4 h-4 accent-emerald-600 align-middle" />
              </th>
              <th className="text-left px-2 py-2.5 font-medium">Ürün</th>
              <th className="text-left px-3 py-2.5 font-medium">Durum</th>
              <th className="text-right px-3 py-2.5 font-medium">Fiyat</th>
              <th className="text-right px-3 py-2.5 font-medium">Varyant</th>
            </tr>
          </thead>
          <tbody>
            {filtreli.map(p => (
              <tr key={p.id} onClick={() => navigate(`/urunler/${p.id}`)}
                className="border-t border-panel-border hover:bg-panel-input/50 transition cursor-pointer">
                <td className="px-3 py-2" onClick={e => e.stopPropagation()}>
                  <input type="checkbox" checked={checked.has(p.id)}
                    onClick={e => toggleCheck(p.id, e)} onChange={() => {}}
                    className="w-4 h-4 accent-emerald-600 align-middle" />
                </td>
                <td className="px-2 py-2">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-11 h-11 rounded-lg bg-panel-input overflow-hidden shrink-0 flex items-center justify-center">
                      {p.cover_image
                        ? <img src={p.cover_image} alt={p.title} className="w-full h-full object-cover" />
                        : <span className="opacity-30">🖼️</span>}
                    </div>
                    <span className="font-medium truncate">{p.title}</span>
                  </div>
                </td>
                <td className="px-3 py-2"><StatusBadge status={p.status} /></td>
                <td className="px-3 py-2 text-right tabular-nums">{fmtPrice(p.base_price)}</td>
                <td className="px-3 py-2 text-right tabular-nums text-panel-muted">{p.variant_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
        </>
      )}
      {!loading && products.length === 0 && (
        <div className="card text-center !p-10">
          <div className="text-3xl">🛍️</div>
          <p className="mt-2 text-sm text-panel-muted">
            Henüz ürün yok — ilk ürününü ekleyerek satışa başla.
          </p>
          <Link to="/urunler/yeni" className="btn-primary mt-4 inline-block">+ Yeni Ürün</Link>
        </div>
      )}
      {!loading && products.length > 0 && filtreli.length === 0 && (
        <div className="card text-center !p-10">
          <div className="text-3xl">🔍</div>
          <p className="mt-2 text-sm text-panel-muted">
            Bu filtreyle eşleşen ürün yok.
          </p>
          <button onClick={temizle} className="btn-ghost mt-3">Filtreyi temizle</button>
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
    draft: ['Taslak', 'bg-white/5 text-panel-muted'],
    active: ['Yayında', 'bg-emerald-500/10 text-emerald-300'],
    archived: ['Arşiv', 'bg-amber-500/10 text-amber-300'],
  }
  const [label, cls] = map[status] || [status, 'bg-white/5 text-panel-muted']
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
        {err && <p className="text-sm text-red-300">{err}</p>}
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
            <label className="block border-2 border-dashed border-panel-border rounded-xl p-6 text-center cursor-pointer hover:border-panel-border">
              <input type="file" accept=".csv,text/csv" className="hidden"
                onChange={e => setFile(e.target.files?.[0] || null)} />
              {file ? <span className="text-sm font-medium">{file.name}</span>
                : <span className="text-sm text-panel-muted">CSV dosyası seçin</span>}
            </label>
            <button onClick={() => run(true)} disabled={!file || busy} className="btn-primary w-full">
              {busy ? 'İnceleniyor…' : 'Önizle (henüz uygulanmaz)'}
            </button>
            {/* Görsel aktarımı eskiden YALNIZ sonuç ekranında çıkıyordu; "Tamam"a
                basınca bir daha ulaşılamıyor ve ürünler görselsiz kalıyordu.
                Aynı dosyayla buradan da başlatılabilir. */}
            {file && (
              <div className="border-t border-panel-border pt-3">
                <p className="text-[11px] text-panel-muted mb-1.5">
                  Ürünleri daha önce aktardıysanız, aynı Shopify dosyasıyla
                  <b> yalnız görselleri</b> getirebilirsiniz. Görseli olan ürünler
                  atlanır, tekrar çalıştırmak güvenlidir.
                </p>
                <ShopifyImageImport storeId={storeId} file={file}
                  label="📷 Yalnızca Görselleri Aktar" />
              </div>
            )}
          </>
        )}

        {preview && !result && (
          <>
            {preview.note && (
              <p className={`text-xs rounded-xl px-3 py-2 border ${preview.truncated
                ? 'text-red-300 bg-red-500/10 border-red-500/30'
                : 'text-amber-300 bg-amber-500/10 border-amber-500/30'}`}>
                {preview.note}
              </p>
            )}
            <div className="grid grid-cols-4 gap-2">
              <Stat n={preview.products_created} label="yeni ürün" />
              <Stat n={preview.products_updated} label="güncellenecek ürün" />
              <Stat n={preview.variants_created} label="yeni varyant" />
              <Stat n={preview.variants_updated} label="güncellenecek varyant" />
            </div>
            {preview.errors.length > 0 && (
              <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-3 max-h-32 overflow-y-auto">
                <div className="text-xs font-medium text-amber-300 mb-1">
                  {preview.errors.length} satır atlanacak:
                </div>
                {preview.errors.map((e, i) => (
                  <div key={i} className="text-[11px] text-amber-300">Satır {e.satir}: {e.mesaj}</div>
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
            {result.note && (
              <p className={`text-xs rounded-xl px-3 py-2 border ${result.truncated
                ? 'text-red-300 bg-red-500/10 border-red-500/30'
                : 'text-amber-300 bg-amber-500/10 border-amber-500/30'}`}>
                {result.note}
              </p>
            )}
            {/* Shopify CSV'siyse görselleri de CDN'den indirip bağlayabiliriz */}
            {result.note && file && (
              <ShopifyImageImport storeId={storeId} file={file} />
            )}
            <button onClick={onDone} className="btn-primary">Tamam</button>
          </div>
        )}

        {err && <p className="text-sm text-red-300">{err}</p>}
      </div>
    </Modal>
  )
}

// Shopify görsellerini arka planda indirir — ilerleme çubuğuyla izlenir.
function ShopifyImageImport({ storeId, file, label = "📷 Görselleri de Aktar (Shopify CDN'den indirilir)" }) {
  const [job, setJob] = useState(null)     // {running, total, done, added, skipped, errors}
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const start = async () => {
    setBusy(true); setErr('')
    try {
      const fd = new FormData()
      fd.append('file', file)
      await api.postForm(`/api/catalog/import/shopify-images?store_id=${storeId}`, fd)
      poll()
    } catch (e) {
      setErr(typeof e?.detail === 'string' ? e.detail : 'Başlatılamadı')
      setBusy(false)
    }
  }

  const poll = async () => {
    try {
      const s = await api.get(`/api/catalog/import/shopify-images/status?store_id=${storeId}`)
      setJob(s)
      if (s.running) setTimeout(poll, 2000)
      else setBusy(false)
    } catch { setBusy(false) }
  }

  if (!job && !busy) {
    return (
      <div className="space-y-1.5">
        <button onClick={start} className="btn-ghost w-full !py-2 text-xs">
          {label}
        </button>
        {err && <p className="text-xs text-red-300">{err}</p>}
        <p className="text-[10px] text-panel-muted">
          Arka planda çalışır; görseli olan ürünler atlanır, pencereyi kapatabilirsiniz.
        </p>
      </div>
    )
  }

  const pct = job?.total ? Math.round((job.done / job.total) * 100) : 0
  return (
    <div className="space-y-1.5 text-left">
      <div className="flex justify-between text-xs">
        <span>{job?.running ? '📷 Görseller indiriliyor…' : '✅ Görsel aktarımı bitti'}</span>
        <span className="tabular-nums">{job?.done ?? 0}/{job?.total ?? 0} ürün</span>
      </div>
      <div className="h-2 rounded-full bg-panel-input overflow-hidden">
        <div className="h-full rounded-full bg-panel-accent transition-all duration-500"
          style={{ width: `${pct}%` }} />
      </div>
      <p className="text-[11px] text-panel-muted">
        {job?.added ?? 0} görsel eklendi · {job?.skipped ?? 0} ürün atlandı
        {(job?.errors?.length ?? 0) > 0 && ` · ${job.errors.length} hata`}
      </p>
    </div>
  )
}

// Toplu varyant seti uygulama — seçili ürünlerin HEPSİNE aynı set bağlanır.
function BulkApplySetModal({ ids, storeId, onClose, onDone, allWithoutVariants = false }) {
  const [sets, setSets] = useState(null)
  const [setId, setSetId] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [result, setResult] = useState(null)

  useEffect(() => {
    api.get(`/api/catalog/variant-sets?store_id=${storeId}`)
      .then(setSets).catch(() => setSets([]))
  }, [storeId])

  const submit = async (e) => {
    e.preventDefault()
    if (!setId) { setErr('Bir set seçin'); return }
    setBusy(true); setErr('')
    try {
      const r = await api.post('/api/catalog/products/bulk-apply-variant-set', {
        ids: allWithoutVariants ? [] : ids,
        variant_set_id: setId,
        only_without_variants: allWithoutVariants,
      })
      setResult(r)
    } catch (e2) {
      setErr(typeof e2?.detail === 'string' ? e2.detail : 'Uygulanamadı')
    } finally { setBusy(false) }
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4"
      onClick={onClose}>
      <form onSubmit={submit} onClick={e => e.stopPropagation()}
        className="card w-full max-w-md space-y-3">
        <h2 className="font-semibold">
          🧩 Varyant Seti Uygula {allWithoutVariants
            ? '(varyantsız TÜM ürünler)' : `(${ids.length} ürün)`}
        </h2>
        {allWithoutVariants && (
          <p className="text-[11px] text-amber-300 -mt-1">
            Mağazadaki varyantı olmayan tüm ürünlere uygulanır — bu ürünler şu an
            müşteri tarafından sepete eklenemiyor.
          </p>
        )}
        {result ? (
          <>
            <p className="text-sm">
              ✅ <b>{result.applied}</b> seti {result.products} ürüne uygulandı —
              {' '}{result.created} varyant eklendi, {result.updated} güncellendi
              {result.deleted > 0 && <>, {result.deleted} sette olmayan varyant silindi</>}.
            </p>
            <div className="flex justify-end">
              <button type="button" onClick={onDone} className="btn-primary">Tamam</button>
            </div>
          </>
        ) : (
          <>
            <p className="text-[11px] text-panel-muted -mt-1">
              Seçili ürünlerin tümü bu sete bağlanır: setteki modeller eklenir,
              mevcut varyantların stok bilgisi korunur, sette olmayanlar silinir.
              Sette ileride yapacağınız değişiklikler bağlı ürünlere de yansır.
            </p>
            {sets === null ? (
              <p className="text-sm text-panel-muted">Setler yükleniyor…</p>
            ) : sets.length === 0 ? (
              <p className="text-sm text-panel-muted">
                Henüz varyant seti yok — önce üstteki "🧩 Varyant Setleri" bölümünden oluşturun.
              </p>
            ) : (
              <select className="input" value={setId} onChange={e => setSetId(e.target.value)}>
                <option value="">Set seçin…</option>
                {sets.map(s => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({(s.items || []).length} model)
                  </option>
                ))}
              </select>
            )}
            {err && <p className="text-sm text-red-300">{err}</p>}
            <div className="flex justify-end gap-2">
              <button type="button" onClick={onClose} className="btn-ghost">Vazgeç</button>
              <button disabled={busy || !setId} className="btn-primary">
                {busy ? 'Uygulanıyor…' : 'Uygula'}
              </button>
            </div>
          </>
        )}
      </form>
    </div>
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

        {err && <p className="text-sm text-red-300">{err}</p>}
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

// Varyant Setleri — hazır model listeleri; set düzenlenince bağlı TÜM ürünler
// senkronlanır (Shopify'da olmayan, üretici dostu bir kolaylık).
const trSlug = (t) => t.toLowerCase()
  .replaceAll('ı', 'i').replaceAll('ğ', 'g').replaceAll('ü', 'u')
  .replaceAll('ş', 's').replaceAll('ö', 'o').replaceAll('ç', 'c')
  .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')

export function VariantSetsModal({ storeId, onClose }) {
  const [sets, setSets] = useState([])
  const [editing, setEditing] = useState(null)  // null | 'new' | set
  const [err, setErr] = useState('')

  const load = async () => {
    try { setSets(await api.get(`/api/catalog/variant-sets?store_id=${storeId}`)) }
    catch { setErr('Setler yüklenemedi') }
  }
  useEffect(() => { load() }, [storeId])

  const remove = async (vs) => {
    if (!window.confirm(`"${vs.name}" seti silinecek — ürünlerdeki varyantlar YERİNDE kalır, `
        + `yalnızca bağ kopar. Emin misiniz?`)) return
    try { await api.del(`/api/catalog/variant-sets/${vs.id}`); load() }
    catch { setErr('Silinemedi') }
  }

  if (editing !== null) {
    return <VariantSetEditor storeId={storeId} vset={editing === 'new' ? null : editing}
      onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load() }} />
  }

  return (
    <Modal title="🧩 Varyant Setleri" onClose={onClose}>
      <p className="text-xs text-panel-muted -mt-1 mb-3">
        Model listesini TEK yerden yönetin: seti düzenleyince bağlı tüm ürünlerin
        varyantları otomatik güncellenir (stok adetleri korunur). Sete bağlamayı
        ürün detayından yaparsınız.
      </p>
      {err && <p className="text-sm text-red-300 mb-2">{err}</p>}
      <div className="space-y-2">
        {sets.map(vs => (
          <div key={vs.id} className="flex items-center gap-2 border border-panel-border rounded-xl px-3 py-2.5 text-sm">
            <span className="font-medium">{vs.name}</span>
            <span className="text-xs text-panel-muted">
              {vs.items.length} model · {vs.product_count ?? 0} üründe
            </span>
            <span className="ml-auto flex gap-2">
              <button onClick={() => setEditing(vs)}
                className="text-xs text-panel-muted hover:text-panel-ink">Düzenle</button>
              <button onClick={() => remove(vs)}
                className="text-xs text-red-300 hover:text-red-300">Sil</button>
            </span>
          </div>
        ))}
        {sets.length === 0 && (
          <p className="text-sm text-panel-muted text-center py-4">
            Henüz set yok — örn. "Standart Silikon" ya da "Şeffaf Kılıf" seti oluşturun.
          </p>
        )}
      </div>
      <div className="flex justify-end pt-3">
        <button onClick={() => setEditing('new')} className="btn-primary">+ Yeni Set</button>
      </div>
    </Modal>
  )
}

function VariantSetEditor({ storeId, vset, onClose, onSaved }) {
  const isNew = !vset
  const [name, setName] = useState(vset?.name || '')
  const [items, setItems] = useState(vset?.items?.length ? vset.items : [])
  const [bulkText, setBulkText] = useState('')
  const [bulkBrand, setBulkBrand] = useState('')
  const [newBrand, setNewBrand] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [collapsed, setCollapsed] = useState({})    // {marka: true} — kısaltılmış gruplar
  const [brandEdit, setBrandEdit] = useState(null)  // {old, value} — ana varyant adı düzenleme

  // Ana varyant (marka) → alt varyantlar (modeller) gruplaması
  const brands = [...new Set(items.map(r => r.brand || 'Diğer'))]

  const patchRow = (i, p) => setItems(rows => rows.map((r, j) => j === i ? { ...r, ...p } : r))

  const commitBrandRename = () => {
    if (!brandEdit) return
    const { old, value } = brandEdit
    setBrandEdit(null)
    const next = value.trim()
    if (!next || next === old) return
    setItems(rows => rows.map(r => (r.brand || 'Diğer') === old ? { ...r, brand: next } : r))
    setCollapsed(c => { const n = { ...c }; if (old in n) { n[next] = n[old]; delete n[old] } return n })
  }

  const addBrand = () => {
    const b = newBrand.trim()
    if (!b) return
    setItems(rows => [...rows, { brand: b, model_key: '', model_display: '', variation: '', price_override: '' }])
    setNewBrand('')
  }

  const addModelTo = (brand) => {
    setItems(rows => [...rows,
      { brand: brand === 'Diğer' ? '' : brand, model_key: '', model_display: '', variation: '', price_override: '' }])
  }

  const addBulk = () => {
    const lines = bulkText.split('\n').map(l => l.trim()).filter(Boolean)
    if (!lines.length) return
    setItems(rows => [
      ...rows.filter(r => r.model_display),
      ...lines.map(l => ({ brand: bulkBrand.trim() || '', model_key: trSlug(l),
        model_display: l, variation: '', price_override: '' })),
    ])
    setBulkText('')
  }

  const submit = async (e) => {
    e.preventDefault()
    const cleaned = items
      .filter(r => (r.model_display || '').trim())
      .map(r => ({
        model_key: (r.model_key || trSlug(r.model_display)).trim(),
        model_display: r.model_display.trim(),
        brand: (r.brand || '').trim() || null,
        variation: (r.variation || '').trim() || null,
        price_override: r.price_override ? Number(r.price_override) : null,
      }))
    if (!cleaned.length) { setErr('En az bir model girin'); return }
    setBusy(true); setErr('')
    try {
      if (isNew) {
        await api.post('/api/catalog/variant-sets', { store_id: storeId, name: name.trim(), items: cleaned })
      } else {
        const r = await api.patch(`/api/catalog/variant-sets/${vset.id}`, { name: name.trim(), items: cleaned })
        if (r.synced_products > 0) window.alert(`${r.synced_products} üründeki varyantlar senkronlandı ✓`)
      }
      onSaved()
    } catch (e2) {
      setErr(typeof e2?.detail === 'string' ? e2.detail : 'Kaydedilemedi')
    } finally { setBusy(false) }
  }

  return (
    <Modal title={isNew ? 'Yeni Varyant Seti' : `Set: ${vset.name}`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <label className="block text-sm">
          <span className="text-panel-muted text-xs">Set adı</span>
          <input className="input mt-1" value={name} onChange={e => setName(e.target.value)}
            required minLength={2} maxLength={120} placeholder="Standart Silikon" />
        </label>

        <div className="max-h-80 overflow-y-auto space-y-2.5 border border-panel-border rounded-xl p-2">
          {brands.map(brand => {
            const groupRows = items.map((r, i) => [r, i]).filter(([r]) => (r.brand || 'Diğer') === brand)
            return (
              <div key={brand} className="space-y-1.5">
                <div className="flex items-center gap-2 text-xs font-semibold text-panel-muted uppercase tracking-wide">
                  <button type="button" onClick={() => setCollapsed(c => ({ ...c, [brand]: !c[brand] }))}
                    className="flex items-center gap-1.5 hover:text-panel-ink"
                    title={collapsed[brand] ? 'Grubu aç' : 'Grubu kısalt'}>
                    <span className="inline-block w-3 text-center">{collapsed[brand] ? '▸' : '▾'}</span>
                    📱 {brandEdit?.old === brand ? null : brand}
                  </button>
                  {brandEdit?.old === brand ? (
                    <input autoFocus className="input !py-0.5 !px-1.5 !w-36 text-xs normal-case font-normal"
                      value={brandEdit.value}
                      onChange={e => setBrandEdit({ ...brandEdit, value: e.target.value })}
                      onBlur={commitBrandRename}
                      onKeyDown={e => {
                        if (e.key === 'Enter') { e.preventDefault(); commitBrandRename() }
                        if (e.key === 'Escape') setBrandEdit(null)
                      }} />
                  ) : (
                    <button type="button" onClick={() => setBrandEdit({ old: brand, value: brand === 'Diğer' ? '' : brand })}
                      className="normal-case font-normal hover:text-panel-accent" title="Ana varyant adını düzenle">✎</button>
                  )}
                  <span className="font-normal normal-case">({groupRows.length} model)</span>
                  <button type="button" onClick={() => addModelTo(brand)}
                    className="ml-auto text-emerald-300 normal-case font-normal hover:underline">+ model</button>
                  <button type="button"
                    onClick={() => setItems(rows => rows.filter(r => (r.brand || 'Diğer') !== brand))}
                    className="text-red-300 hover:text-red-300 normal-case font-normal">markayı sil</button>
                </div>
                {!collapsed[brand] && groupRows.map(([r, i]) => (
                  <div key={i} className="flex gap-1.5 pl-3">
                    <input className="input !py-1.5 text-xs flex-1" value={r.model_display || ''}
                      onChange={e => patchRow(i, { model_display: e.target.value, model_key: trSlug(e.target.value) })}
                      placeholder="Model adı (iPhone 15 Pro)" />
                    <input className="input !py-1.5 text-xs !w-24" value={r.variation || ''}
                      onChange={e => patchRow(i, { variation: e.target.value })} placeholder="Renk (ops.)" />
                    <input className="input !py-1.5 text-xs !w-20" type="number" step="0.01" min="0"
                      value={r.price_override ?? ''}
                      onChange={e => patchRow(i, { price_override: e.target.value })} placeholder="₺ (ops.)" />
                    <button type="button" onClick={() => setItems(rows => rows.filter((_, j) => j !== i))}
                      className="text-red-300 hover:text-red-300 px-1">×</button>
                  </div>
                ))}
              </div>
            )
          })}
          {items.length === 0 && (
            <p className="text-xs text-panel-muted text-center py-2">
              Önce ana varyant (marka) ekleyin — altına modelleri dizin.
            </p>
          )}
          <div className="flex gap-1.5 pt-1 border-t border-panel-border">
            <input className="input !py-1.5 text-xs !w-44" value={newBrand}
              onChange={e => setNewBrand(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addBrand() } }}
              placeholder="Ana varyant: Apple, Samsung…" />
            <button type="button" onClick={addBrand} className="btn-ghost !py-1 text-xs">+ Ana Varyant</button>
          </div>
        </div>

        <details className="text-sm">
          <summary className="text-xs text-panel-muted cursor-pointer">
            Toplu ekle (her satıra bir model adı yapıştırın)
          </summary>
          <div className="mt-2 space-y-1.5">
            <input className="input !py-1.5 text-xs !w-44" value={bulkBrand}
              onChange={e => setBulkBrand(e.target.value)}
              placeholder="Bu modellerin markası (ops.)" />
            <div className="flex gap-2">
              <textarea className="input text-xs" rows={4} value={bulkText}
                onChange={e => setBulkText(e.target.value)}
                placeholder={'iPhone 15\niPhone 15 Pro\niPhone 16'} />
              <button type="button" onClick={addBulk} className="btn-ghost !py-1.5 text-xs self-start">Ekle</button>
            </div>
          </div>
        </details>

        {!isNew && (
          <p className="text-[11px] text-amber-300 bg-amber-500/10 border border-amber-500/30 rounded-lg px-2.5 py-1.5">
            ⚠ Kaydedince bu sete bağlı <b>tüm ürünlerin</b> varyantları bu listeye göre güncellenir
            (listeden çıkan modeller ürünlerden silinir; stoklar korunur).
          </p>
        )}
        {err && <p className="text-sm text-red-300">{err}</p>}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="btn-ghost">Geri</button>
          <button disabled={busy} className="btn-primary">
            {busy ? 'Kaydediliyor…' : isNew ? 'Set Oluştur' : 'Kaydet ve Senkronla'}
          </button>
        </div>
      </form>
    </Modal>
  )
}


// ─── Tablo düzenleyici (Shopify bulk editor) ──────────────────
// "Toplu Düzenle" seçili ürünlerin HEPSİNE aynı işlemi uygular (ör. %10 zam).
// Burada ise her ürün KENDİ satırında düzenlenir: başlık, fiyat, indirim öncesi
// fiyat, durum. Yalnız DEĞİŞTİRİLEN hücreler gönderilir; tek istekte kaydedilir.
export function TabloDuzenleyici({ urunler, onClose, onDone }) {
  const [satirlar, setSatirlar] = useState(() => urunler.map(u => ({
    id: u.id,
    title: u.title || '',
    base_price: u.base_price ?? '',
    compare_at_price: u.compare_at_price ?? '',
    status: u.status || 'active',
  })))
  const [ilk] = useState(() => JSON.stringify(urunler.map(u => ({
    id: u.id, title: u.title || '', base_price: u.base_price ?? '',
    compare_at_price: u.compare_at_price ?? '', status: u.status || 'active',
  }))))
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const ilkler = JSON.parse(ilk)
  const degisenSatirlar = satirlar.filter((r, i) => JSON.stringify(r) !== JSON.stringify(ilkler[i]))

  const yaz = (i, alan, deger) =>
    setSatirlar(ls => ls.map((r, j) => (i === j ? { ...r, [alan]: deger } : r)))

  // Bir sütunu tüm satırlara uygula — "hepsine 249 TL" gibi hızlı düzeltmeler
  const sutunaYay = (alan) => {
    const deger = satirlar[0]?.[alan]
    if (deger === undefined) return
    setSatirlar(ls => ls.map(r => ({ ...r, [alan]: deger })))
  }

  const kaydet = async () => {
    if (!degisenSatirlar.length) { onClose(); return }
    setBusy(true); setErr('')
    try {
      const gonder = degisenSatirlar.map((r, idx) => {
        const orj = ilkler.find(o => o.id === r.id)
        const yama = { id: r.id }
        if (r.title !== orj.title) yama.title = r.title
        if (String(r.base_price) !== String(orj.base_price)) yama.base_price = Number(r.base_price)
        if (String(r.compare_at_price) !== String(orj.compare_at_price)) {
          yama.compare_at_price = r.compare_at_price === '' ? null : Number(r.compare_at_price)
        }
        if (r.status !== orj.status) yama.status = r.status
        return yama
      })
      await api.post('/api/catalog/products/bulk-rows', { satirlar: gonder })
      onDone()
    } catch (e) {
      setErr(typeof e?.detail === 'string' ? e.detail : 'Kaydedilemedi')
    } finally { setBusy(false) }
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-3"
      onClick={onClose}>
      <div className="bg-panel-card rounded-2xl w-full max-w-5xl max-h-[92vh] flex flex-col p-4"
        onClick={e => e.stopPropagation()}>
        <div className="flex items-center gap-2 mb-3">
          <h2 className="font-semibold text-sm">📊 Tablo Düzenleyici</h2>
          <span className="text-xs text-panel-muted">
            {satirlar.length} ürün · {degisenSatirlar.length} değişiklik
          </span>
          <button onClick={onClose} className="ml-auto text-panel-muted text-lg leading-none">×</button>
        </div>

        {err && <p className="text-sm text-red-300 mb-2">{err}</p>}

        <div className="flex-1 overflow-auto border border-panel-border rounded-xl">
          <table className="w-full text-sm">
            <thead className="bg-panel-input sticky top-0 z-10">
              <tr className="text-left text-xs text-panel-muted">
                <th className="px-2 py-2 font-medium">Ürün adı</th>
                <th className="px-2 py-2 font-medium w-28">
                  Fiyat
                  <button onClick={() => sutunaYay('base_price')}
                    title="İlk satırdaki değeri tüm satırlara uygula"
                    className="ml-1 text-panel-accent">↓</button>
                </th>
                <th className="px-2 py-2 font-medium w-32">
                  İndirim öncesi
                  <button onClick={() => sutunaYay('compare_at_price')}
                    title="İlk satırdaki değeri tüm satırlara uygula"
                    className="ml-1 text-panel-accent">↓</button>
                </th>
                <th className="px-2 py-2 font-medium w-28">
                  Durum
                  <button onClick={() => sutunaYay('status')}
                    title="İlk satırdaki değeri tüm satırlara uygula"
                    className="ml-1 text-panel-accent">↓</button>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-panel-border">
              {satirlar.map((r, i) => {
                const degisti = JSON.stringify(r) !== JSON.stringify(ilkler[i])
                return (
                  <tr key={r.id} className={degisti ? 'bg-amber-500/10' : ''}>
                    <td className="px-2 py-1">
                      <input value={r.title} maxLength={300}
                        onChange={e => yaz(i, 'title', e.target.value)}
                        className="w-full bg-transparent border border-transparent hover:border-panel-border
                          focus:border-panel-accent rounded px-1.5 py-1 outline-none" />
                    </td>
                    <td className="px-2 py-1">
                      <input type="number" step="0.01" min="0" value={r.base_price}
                        onChange={e => yaz(i, 'base_price', e.target.value)}
                        className="w-full bg-transparent border border-transparent hover:border-panel-border
                          focus:border-panel-accent rounded px-1.5 py-1 outline-none text-right" />
                    </td>
                    <td className="px-2 py-1">
                      <input type="number" step="0.01" min="0" value={r.compare_at_price ?? ''}
                        placeholder="—"
                        onChange={e => yaz(i, 'compare_at_price', e.target.value)}
                        className="w-full bg-transparent border border-transparent hover:border-panel-border
                          focus:border-panel-accent rounded px-1.5 py-1 outline-none text-right" />
                    </td>
                    <td className="px-2 py-1">
                      <select value={r.status} onChange={e => yaz(i, 'status', e.target.value)}
                        className="w-full bg-transparent border border-transparent hover:border-panel-border
                          focus:border-panel-accent rounded px-1 py-1 outline-none">
                        <option value="active">Yayında</option>
                        <option value="draft">Taslak</option>
                        <option value="archived">Arşiv</option>
                      </select>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        <div className="flex items-center gap-2 mt-3">
          <span className="text-[11px] text-panel-muted">
            Sarı satırlar değiştirilmiş olanlar. Başlıktaki ↓ ile ilk satırın değerini
            tüm satırlara yayarsınız.
          </span>
          <button onClick={onClose} className="ml-auto btn-ghost !py-2 text-sm">Vazgeç</button>
          <button onClick={kaydet} disabled={busy || !degisenSatirlar.length}
            className="btn !py-2 text-sm disabled:opacity-40">
            {busy ? 'Kaydediliyor…' : `${degisenSatirlar.length} değişikliği kaydet`}
          </button>
        </div>
      </div>
    </div>
  )
}

// Stok takibi — toplu aç/kapat.
//
// NEDEN GEREKLİ: Shopify'dan içe aktarılan katalogda varyantlar "stok
// takipli ve 0 adet" olarak geldi. Sonuç: ürün sayfasında "Sepete Ekle"
// kapalı, yapısal veride OutOfStock, Meta/Google katalogunda "out of
// stock" — yani reklam yayınlanamıyor. 207 ürün × ~36 model = ~7.400
// varyant olduğu için envanter ekranından tek tek işaretlemek imkânsız;
// bu yüzden sunucuda TEK sorguyla yapılıyor.
function StokTakibiModal({ storeId, ids, onClose, onDone }) {
  const toast = useToast()
  const [kapsam, setKapsam] = useState('secili')   // secili | tumu
  const [acik, setAcik] = useState(false)          // takip açık mı olsun
  const [adet, setAdet] = useState('0')
  const [busy, setBusy] = useState(false)

  const uygula = async () => {
    setBusy(true)
    try {
      const govde = { tumu: kapsam === 'tumu', ids: kapsam === 'tumu' ? [] : ids,
                      track_stock: acik }
      if (acik) govde.quantity = Math.max(0, parseInt(adet, 10) || 0)
      const r = await api.post(
        `/api/catalog/products/stok-takibi?store_id=${storeId}`, govde)
      toast.success(`${r.urun} ürün · ${r.varyant} varyant güncellendi`)
      onDone()
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Güncellenemedi')
    } finally { setBusy(false) }
  }

  return (
    <Modal title="📦 Stok Takibi" onClose={onClose}>
      <div className="space-y-4 text-sm">
        <p className="text-xs text-panel-muted">
          Siparişe göre ürettiğin ürünlerde stok takibi <b>kapalı</b> olmalı.
          Takip açık ve adet 0 ise ürün vitrinde “tükendi” görünür, sepete
          eklenemez ve <b>Meta/Google katalogunda reklam yayınlanmaz</b>.
        </p>

        <div>
          <div className="text-xs text-panel-muted mb-1.5">Kapsam</div>
          <div className="grid grid-cols-2 gap-2">
            <button onClick={() => setKapsam('secili')}
              className={`px-3 py-2 rounded-xl text-xs border transition ${kapsam === 'secili'
                ? 'border-panel-accent bg-panel-accent/15 text-panel-ink'
                : 'border-panel-border bg-white/[0.03] text-panel-muted'}`}>
              Seçili {ids.length} ürün
            </button>
            <button onClick={() => setKapsam('tumu')}
              className={`px-3 py-2 rounded-xl text-xs border transition ${kapsam === 'tumu'
                ? 'border-panel-accent bg-panel-accent/15 text-panel-ink'
                : 'border-panel-border bg-white/[0.03] text-panel-muted'}`}>
              Mağazadaki tüm ürünler
            </button>
          </div>
        </div>

        <div>
          <div className="text-xs text-panel-muted mb-1.5">Stok takibi</div>
          <div className="grid grid-cols-2 gap-2">
            <button onClick={() => setAcik(false)}
              className={`px-3 py-2 rounded-xl text-xs border transition ${!acik
                ? 'border-emerald-500/50 bg-emerald-500/10 text-emerald-300'
                : 'border-panel-border bg-white/[0.03] text-panel-muted'}`}>
              Kapalı — her zaman satılabilir
            </button>
            <button onClick={() => setAcik(true)}
              className={`px-3 py-2 rounded-xl text-xs border transition ${acik
                ? 'border-amber-500/50 bg-amber-500/10 text-amber-300'
                : 'border-panel-border bg-white/[0.03] text-panel-muted'}`}>
              Açık — adede göre
            </button>
          </div>
        </div>

        {acik && (
          <label className="block">
            <span className="text-xs text-panel-muted">Her varyant için başlangıç adedi</span>
            <input className="input mt-1" type="number" min="0" value={adet}
              onChange={e => setAdet(e.target.value)} />
            <span className="text-[11px] text-panel-muted">
              Bu sayı SEÇİLEN her varyantın mevcut adedinin üzerine yazılır.
            </span>
          </label>
        )}

        <div className={`text-xs rounded-xl px-3 py-2 border ${acik
          ? 'bg-amber-500/10 border-amber-500/30 text-amber-300'
          : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'}`}>
          {kapsam === 'tumu' ? 'Mağazadaki tüm ürünlerin' : `Seçili ${ids.length} ürünün`}
          {' '}tüm varyantlarında stok takibi <b>{acik ? 'AÇILACAK' : 'KAPATILACAK'}</b>
          {acik && ` ve adet ${parseInt(adet, 10) || 0} yapılacak`}.
        </div>

        <div className="flex gap-2">
          <button onClick={onClose} className="btn-ghost flex-1">Vazgeç</button>
          <button onClick={uygula} disabled={busy || (kapsam === 'secili' && !ids.length)}
            className="btn-primary flex-1">
            {busy ? 'Uygulanıyor…' : 'Uygula'}
          </button>
        </div>
      </div>
    </Modal>
  )
}
