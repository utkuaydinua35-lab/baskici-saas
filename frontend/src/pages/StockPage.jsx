import { useEffect, useState } from 'react'
import { api } from '../lib/api'

const CAT_LABELS = {
  bos_kilif: 'Boş Kılıf',
  ekran_koruyucu: 'Ekran Koruyucu',
  lens_koruyucu: 'Lens Koruyucu',
  diger: 'Diğer',
}
const EMPTY = {
  sku: '', name: '', category: 'bos_kilif', variation: '', model: '',
  quantity: '', low_stock_threshold: '', product_id: '', variant_id: '', notes: '',
}

export default function StockPage() {
  const [items, setItems] = useState([])
  const [meta, setMeta] = useState({ categories: [], variations: [] })
  const [stores, setStores] = useState([])
  const [cat, setCat] = useState('')
  const [search, setSearch] = useState('')
  const [lowOnly, setLowOnly] = useState(false)
  const [stats, setStats] = useState({ all_total: 0, low_count: 0, total_quantity: 0 })
  const [loading, setLoading] = useState(true)

  const [form, setForm] = useState(EMPTY)
  const [storeId, setStoreId] = useState('')
  const [editId, setEditId] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState(null)

  const [adjItem, setAdjItem] = useState(null)
  const [moveItem, setMoveItem] = useState(null)

  const loadMeta = async () => {
    try { setMeta(await api.get('/api/stock/_meta')) } catch {}
    try {
      const s = await api.get('/api/stores')
      setStores(Array.isArray(s) ? s : [])
    } catch {}
  }

  const load = async () => {
    setLoading(true)
    try {
      const p = new URLSearchParams()
      if (cat) p.set('category', cat)
      if (search) p.set('search', search)
      if (lowOnly) p.set('low_only', 'true')
      const r = await api.get(`/api/stock?${p}`)
      setItems(r.items || [])
      setStats({ all_total: r.all_total || 0, low_count: r.low_count || 0, total_quantity: r.total_quantity || 0 })
    } catch { setItems([]) } finally { setLoading(false) }
  }

  useEffect(() => { loadMeta() }, [])
  useEffect(() => { load() }, [cat, lowOnly])
  useEffect(() => {
    const t = setTimeout(load, 400)
    return () => clearTimeout(t)
    // eslint-disable-next-line
  }, [search])

  const openCreate = () => { setForm(EMPTY); setStoreId(''); setEditId(null); setShowForm(true); setMsg(null) }
  const openEdit = (it) => {
    setForm({
      sku: it.sku || '', name: it.name || '', category: it.category || 'bos_kilif',
      variation: it.variation || '', model: it.model || '',
      quantity: it.quantity ?? '', low_stock_threshold: it.low_stock_threshold ?? '',
      product_id: it.product_id || '', variant_id: it.variant_id || '', notes: it.notes || '',
    })
    setStoreId(it.store_id || '')
    setEditId(it.id); setShowForm(true); setMsg(null)
  }

  const save = async () => {
    setSaving(true); setMsg(null)
    const payload = {
      sku: form.sku.trim(), name: form.name.trim(), category: form.category,
      variation: form.variation.trim() || null, model: form.model.trim() || null,
      low_stock_threshold: form.low_stock_threshold === '' ? 0 : parseInt(form.low_stock_threshold, 10),
      store_id: storeId || null,
      product_id: form.product_id.trim() || null, variant_id: form.variant_id.trim() || null,
      notes: form.notes.trim() || null,
    }
    if (!editId) payload.quantity = form.quantity === '' ? 0 : parseInt(form.quantity, 10)
    if (!payload.sku || !payload.name) { setMsg({ ok: false, text: 'Stok kodu ve ad zorunlu.' }); setSaving(false); return }
    try {
      if (editId) await api.patch(`/api/stock/${editId}`, payload)
      else await api.post('/api/stock', payload)
      setShowForm(false); setEditId(null); setForm(EMPTY)
      setMsg({ ok: true, text: editId ? 'Güncellendi.' : 'Eklendi.' })
      load()
    } catch (e) {
      setMsg({ ok: false, text: typeof e?.detail === 'string' ? e.detail : 'Kaydedilemedi' })
    } finally { setSaving(false) }
  }

  const remove = async (it) => {
    if (!confirm(`"${it.name}" (${it.sku}) silinecek. Hareket geçmişi de gider. Emin misin?`)) return
    try { await api.del(`/api/stock/${it.id}`); load() }
    catch (e) { alert(typeof e?.detail === 'string' ? e.detail : 'Silinemedi') }
  }

  return (
    <div className="max-w-[1400px]">
      <div className="flex items-start justify-between mb-5 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-gray-100">🗃️ Stok</h1>
          <p className="text-sm text-gray-500 mt-1">
            Boş kılıf, ekran/lens koruyucu ve diğer stok kalemleri. Kalıp basıldığında
            (Tamamlandı) eşleşen boş kılıflar otomatik düşer.
          </p>
        </div>
        <button onClick={openCreate} className="btn-primary !text-sm">+ Yeni Stok Kalemi</button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <Kpi label="KALEM SAYISI" value={stats.all_total} color="gray" />
        <Kpi label="TOPLAM ADET" value={stats.total_quantity} color="accent" />
        <Kpi label="DÜŞÜK STOK" value={stats.low_count} color={stats.low_count > 0 ? 'red' : 'gray'} />
      </div>

      <div className="card mb-4 flex flex-wrap gap-2 !p-3 items-center">
        <select value={cat} onChange={e => setCat(e.target.value)} className="input !text-xs !py-1.5">
          <option value="">Tüm kategoriler</option>
          {(meta.categories || []).map(c => <option key={c} value={c}>{CAT_LABELS[c] || c}</option>)}
        </select>
        <input type="text" placeholder="Ara: kod, ad, model, varyasyon..." value={search}
               onChange={e => setSearch(e.target.value)}
               className="input !text-xs !py-1.5 flex-1 min-w-[200px]" />
        <label className="flex items-center gap-1.5 text-xs text-gray-400 cursor-pointer">
          <input type="checkbox" checked={lowOnly} onChange={e => setLowOnly(e.target.checked)} />
          Sadece düşük stok
        </label>
      </div>

      {msg && (
        <div className={`text-sm rounded-lg px-3 py-2 mb-3 border ${
          msg.ok ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300'
                 : 'bg-red-500/10 border-red-500/20 text-red-300'
        }`}>{msg.ok ? '✓ ' : '✗ '}{msg.text}</div>
      )}

      {showForm && (
        <div className="card mb-4 !p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-200">{editId ? 'Kalemi Düzenle' : 'Yeni Stok Kalemi'}</h2>
            <button onClick={() => { setShowForm(false); setEditId(null) }} className="text-gray-500 hover:text-gray-200 text-xl leading-none">×</button>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <F label="Stok kodu (SKU) *"><input className="input w-full !text-xs !py-1.5" value={form.sku} onChange={e => setForm(f => ({ ...f, sku: e.target.value }))} /></F>
            <F label="Ad *"><input className="input w-full !text-xs !py-1.5" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} /></F>
            <F label="Kategori">
              <select className="input w-full !text-xs !py-1.5" value={form.category} onChange={e => setForm(f => ({ ...f, category: e.target.value }))}>
                {(meta.categories || []).map(c => <option key={c} value={c}>{CAT_LABELS[c] || c}</option>)}
              </select>
            </F>
            <F label="Varyasyon (boş kılıf)">
              <input className="input w-full !text-xs !py-1.5" list="var-list" placeholder="siyah / beyaz / şeffaf..." value={form.variation} onChange={e => setForm(f => ({ ...f, variation: e.target.value }))} />
              <datalist id="var-list">{(meta.variations || []).map(v => <option key={v} value={v} />)}</datalist>
            </F>
            <F label="Telefon modeli (boş kılıf)"><input className="input w-full !text-xs !py-1.5" placeholder="iPhone 15 Pro Max" value={form.model} onChange={e => setForm(f => ({ ...f, model: e.target.value }))} /></F>
            <F label="Uyarı eşiği"><input type="number" className="input w-full !text-xs !py-1.5" placeholder="0" value={form.low_stock_threshold} onChange={e => setForm(f => ({ ...f, low_stock_threshold: e.target.value }))} /></F>
            {!editId && <F label="Başlangıç adedi"><input type="number" className="input w-full !text-xs !py-1.5" placeholder="0" value={form.quantity} onChange={e => setForm(f => ({ ...f, quantity: e.target.value }))} /></F>}
            <F label="Shopify mağaza (eşleşme)">
              <select className="input w-full !text-xs !py-1.5" value={storeId} onChange={e => setStoreId(e.target.value)}>
                <option value="">—</option>
                {stores.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </F>
            <F label="Shopify product_id"><input className="input w-full !text-xs !py-1.5" value={form.product_id} onChange={e => setForm(f => ({ ...f, product_id: e.target.value }))} /></F>
            <F label="Shopify variant_id"><input className="input w-full !text-xs !py-1.5" value={form.variant_id} onChange={e => setForm(f => ({ ...f, variant_id: e.target.value }))} /></F>
            <F label="Not"><input className="input w-full !text-xs !py-1.5" value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} /></F>
          </div>
          <div className="flex justify-end gap-2 mt-3">
            <button onClick={() => { setShowForm(false); setEditId(null) }} className="btn-secondary !text-sm">İptal</button>
            <button onClick={save} disabled={saving} className="btn-primary !text-sm disabled:opacity-50">{saving ? 'Kaydediliyor...' : editId ? 'Güncelle' : 'Ekle'}</button>
          </div>
        </div>
      )}

      {loading && <div className="text-gray-500 text-sm text-center py-8">Yükleniyor...</div>}

      {!loading && items.length === 0 && (
        <div className="card text-center py-12 text-gray-500">
          <div className="text-3xl mb-2">🗃️</div>
          Stok kalemi yok. <br/>
          <span className="text-xs">Boş kılıf, ekran/lens koruyucu veya diğer stok kalemlerini ekle.</span>
        </div>
      )}

      {!loading && items.length > 0 && (
        <div className="card !p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-brand-input border-b border-brand-border">
              <tr className="text-left text-xs text-gray-500">
                <th className="px-3 py-2 font-medium">Stok Kodu</th>
                <th className="px-3 py-2 font-medium">Ad</th>
                <th className="px-3 py-2 font-medium">Kategori</th>
                <th className="px-3 py-2 font-medium">Varyasyon / Model</th>
                <th className="px-3 py-2 font-medium text-center">Adet</th>
                <th className="px-3 py-2 font-medium text-center">Eşik</th>
                <th className="w-32 px-2"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-brand-border/50">
              {items.map(it => (
                <tr key={it.id} className={`hover:bg-brand-input/30 ${!it.is_active ? 'opacity-50' : ''}`}>
                  <td className="px-3 py-2 font-mono text-[11px] text-accent">{it.sku}</td>
                  <td className="px-3 py-2 text-gray-200">{it.name}</td>
                  <td className="px-3 py-2 text-xs text-gray-400">{CAT_LABELS[it.category] || it.category}</td>
                  <td className="px-3 py-2 text-xs text-gray-400">
                    {it.variation && <span className="px-1.5 py-0.5 rounded bg-gray-700 text-gray-200 mr-1">{it.variation}</span>}
                    {it.model || (it.variation ? '' : '—')}
                  </td>
                  <td className="px-3 py-2 text-center">
                    <span className={`font-semibold ${it.is_low ? 'text-red-400' : 'text-gray-100'}`}>{it.quantity}</span>
                    {it.is_low && <span className="ml-1 text-[10px] text-red-400">düşük</span>}
                  </td>
                  <td className="px-3 py-2 text-center text-xs text-gray-500">{it.low_stock_threshold || '—'}</td>
                  <td className="px-2 py-2">
                    <div className="flex items-center gap-1 justify-end">
                      <button onClick={() => setAdjItem(it)} className="px-2 h-7 flex items-center text-[11px] text-emerald-400 hover:bg-emerald-500/10 rounded" title="Stok giriş/çıkış">±</button>
                      <button onClick={() => setMoveItem(it)} className="w-7 h-7 flex items-center justify-center text-gray-500 hover:text-gray-200 hover:bg-brand-input rounded" title="Hareketler">≣</button>
                      <button onClick={() => openEdit(it)} className="w-7 h-7 flex items-center justify-center text-gray-500 hover:text-accent hover:bg-accent/10 rounded" title="Düzenle">✎</button>
                      <button onClick={() => remove(it)} className="w-7 h-7 flex items-center justify-center text-red-400/70 hover:text-red-300 hover:bg-red-500/10 rounded" title="Sil">🗑</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {adjItem && <AdjustDialog item={adjItem} onClose={() => setAdjItem(null)} onSaved={() => { setAdjItem(null); load() }} />}
      {moveItem && <MovementsDialog item={moveItem} onClose={() => setMoveItem(null)} />}
    </div>
  )
}

function AdjustDialog({ item, onClose, onSaved }) {
  const [delta, setDelta] = useState('')
  const [reason, setReason] = useState('manuel_giris')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const submit = async (sign) => {
    const n = parseInt(delta, 10)
    if (isNaN(n) || n <= 0) { setErr('Geçerli bir adet gir'); return }
    setBusy(true); setErr('')
    try {
      await api.post(`/api/stock/${item.id}/adjust`, { delta: sign * n, reason, note: note || null })
      onSaved()
    } catch (e) { setErr(typeof e?.detail === 'string' ? e.detail : 'Hata') } finally { setBusy(false) }
  }

  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-sm p-5">
        <div className="flex justify-between items-center mb-1">
          <h2 className="text-base font-semibold text-gray-100">Stok Giriş / Çıkış</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-200 text-xl">×</button>
        </div>
        <p className="text-xs text-gray-500 mb-3">{item.name} · <span className="font-mono">{item.sku}</span> · mevcut: <span className="text-gray-200">{item.quantity}</span></p>
        <div className="space-y-3">
          <input type="number" min="1" value={delta} onChange={e => setDelta(e.target.value)} placeholder="Adet" className="input w-full" autoFocus />
          <select value={reason} onChange={e => setReason(e.target.value)} className="input w-full !text-sm">
            <option value="manuel_giris">Manuel giriş (satın alma vb.)</option>
            <option value="manuel_cikis">Manuel çıkış (fire, iade vb.)</option>
            <option value="duzeltme">Sayım düzeltmesi</option>
          </select>
          <input value={note} onChange={e => setNote(e.target.value)} placeholder="Not (opsiyonel)" className="input w-full !text-sm" />
          {err && <div className="text-xs text-red-400 bg-red-500/10 rounded p-2">{err}</div>}
          <div className="flex gap-2">
            <button onClick={() => submit(1)} disabled={busy} className="flex-1 px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm disabled:opacity-50">+ Giriş</button>
            <button onClick={() => submit(-1)} disabled={busy} className="flex-1 px-3 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-white text-sm disabled:opacity-50">− Çıkış</button>
          </div>
        </div>
      </div>
    </div>
  )
}

function MovementsDialog({ item, onClose }) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    (async () => {
      try { const r = await api.get(`/api/stock/${item.id}/movements`); setRows(r.items || []) }
      catch { setRows([]) } finally { setLoading(false) }
    })()
  }, [item.id])

  const reasonLabel = r => ({
    ilk_giris: 'İlk giriş', manuel_giris: 'Manuel giriş', manuel_cikis: 'Manuel çıkış',
    duzeltme: 'Düzeltme', mold_basildi: 'Kalıp basıldı',
  }[r] || r)

  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-lg p-5">
        <div className="flex justify-between items-center mb-3">
          <h2 className="text-base font-semibold text-gray-100">Hareket Geçmişi — {item.name}</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-200 text-xl">×</button>
        </div>
        {loading ? <div className="text-gray-500 text-sm py-6 text-center">Yükleniyor...</div>
          : rows.length === 0 ? <div className="text-gray-500 text-sm py-6 text-center">Hareket yok</div>
          : (
            <div className="max-h-96 overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="text-xs text-gray-500 border-b border-brand-border">
                  <tr><th className="px-2 py-1 text-left">Tarih</th><th className="px-2 py-1 text-left">Sebep</th><th className="px-2 py-1 text-right">Değişim</th><th className="px-2 py-1 text-right">Bakiye</th></tr>
                </thead>
                <tbody className="divide-y divide-brand-border/40">
                  {rows.map(m => (
                    <tr key={m.id}>
                      <td className="px-2 py-1.5 text-xs text-gray-500 whitespace-nowrap">{m.created_at ? new Date(m.created_at).toLocaleString('tr-TR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—'}</td>
                      <td className="px-2 py-1.5 text-xs text-gray-300">{reasonLabel(m.reason)}{m.note ? <span className="text-gray-600"> · {m.note}</span> : ''}</td>
                      <td className={`px-2 py-1.5 text-right font-semibold ${m.delta >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>{m.delta >= 0 ? '+' : ''}{m.delta}</td>
                      <td className="px-2 py-1.5 text-right text-gray-300">{m.balance_after}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </div>
    </div>
  )
}

function F({ label, children }) {
  return <div><label className="block text-[10px] uppercase text-gray-500 mb-1">{label}</label>{children}</div>
}
function Kpi({ label, value, color = 'gray' }) {
  const colors = { gray: 'text-gray-100', accent: 'text-accent', red: 'text-red-400' }
  return (
    <div className="bg-brand-card border border-brand-border rounded-lg p-3">
      <div className="text-[10px] uppercase text-gray-500">{label}</div>
      <div className={`text-2xl font-semibold ${colors[color]}`}>{value}</div>
    </div>
  )
}
