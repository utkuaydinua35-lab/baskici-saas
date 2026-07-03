import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'

// Müşteriler (CRM) — siparişlerden türetilen birleşik görünüm.
export default function MusterilerPage() {
  const [data, setData] = useState({ items: [], total: 0, page: 1, per_page: 50 })
  const [q, setQ] = useState('')
  const [sort, setSort] = useState('last_order_at')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [backfilling, setBackfilling] = useState(false)

  const load = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const params = new URLSearchParams({ sort, page: String(page) })
      if (q.trim()) params.set('q', q.trim())
      setData(await api.get(`/api/customers?${params}`))
    } catch (e) {
      setError(typeof e?.detail === 'string' ? e.detail : 'Müşteriler yüklenemedi')
    } finally { setLoading(false) }
  }, [q, sort, page])

  useEffect(() => {
    const t = setTimeout(load, q ? 300 : 0)  // aramada debounce
    return () => clearTimeout(t)
  }, [load, q])

  const backfill = async () => {
    setBackfilling(true); setError('')
    try {
      const r = await api.post('/api/customers/backfill', {})
      await load()
      setError('')
      window.alert(`${r.customers} müşteri kaydı güncellendi.`)
    } catch { setError('Toplu güncelleme başarısız') }
    finally { setBackfilling(false) }
  }

  const openDetail = async (id) => {
    try { setSelected(await api.get(`/api/customers/${id}`)) }
    catch { setError('Müşteri açılamadı') }
  }

  const lastPage = Math.max(1, Math.ceil(data.total / data.per_page))

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <h1 className="text-xl font-semibold">Müşteriler</h1>
        <span className="text-sm text-gray-400">{data.total} kayıt</span>
        <input
          value={q} onChange={e => { setQ(e.target.value); setPage(1) }}
          placeholder="Ad veya e-posta ara…"
          className="bg-brand-input border border-brand-border rounded-lg px-3 py-1.5 text-sm w-64"
        />
        <select value={sort} onChange={e => { setSort(e.target.value); setPage(1) }}
          className="bg-brand-input border border-brand-border rounded-lg px-3 py-1.5 text-sm">
          <option value="last_order_at">Son sipariş</option>
          <option value="total_spent">Toplam harcama</option>
          <option value="orders_count">Sipariş sayısı</option>
          <option value="created_at">Eklenme</option>
        </select>
        <button onClick={backfill} disabled={backfilling}
          className="ml-auto px-3 py-1.5 rounded-lg text-xs bg-brand-input border border-brand-border text-gray-300 disabled:opacity-50"
          title="Mevcut tüm siparişlerden müşteri kayıtlarını yeniden türet">
          {backfilling ? 'Güncelleniyor…' : '↻ Siparişlerden Güncelle'}
        </button>
      </div>

      {error && <div className="text-sm text-red-400">{error}</div>}

      <div className="bg-brand-card border border-brand-border rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="text-gray-400 text-xs bg-brand-input">
            <tr>
              <th className="text-left px-4 py-2.5">Müşteri</th>
              <th className="text-left px-4 py-2.5">Telefon</th>
              <th className="text-right px-4 py-2.5">Sipariş</th>
              <th className="text-right px-4 py-2.5">Toplam Harcama</th>
              <th className="text-left px-4 py-2.5">Son Sipariş</th>
              <th className="px-2 py-2.5"></th>
            </tr>
          </thead>
          <tbody>
            {data.items.map(c => (
              <tr key={c.id} onClick={() => openDetail(c.id)}
                className="border-t border-brand-border/50 cursor-pointer hover:bg-brand-input/50">
                <td className="px-4 py-2.5">
                  <div className="font-medium">{c.name || '—'}</div>
                  <div className="text-xs text-gray-400">{c.email}</div>
                </td>
                <td className="px-4 py-2.5 text-gray-400 text-xs">{c.phone || '—'}</td>
                <td className="px-4 py-2.5 text-right tabular-nums">
                  {c.orders_count}
                  {c.orders_count > 1 && <span className="ml-1 text-[10px] text-emerald-400">tekrar</span>}
                </td>
                <td className="px-4 py-2.5 text-right tabular-nums font-medium">{fmt(c.total_spent)}</td>
                <td className="px-4 py-2.5 text-xs text-gray-400">
                  {c.last_order_at ? new Date(c.last_order_at).toLocaleDateString('tr-TR') : '—'}
                </td>
                <td className="px-2 py-2.5 text-gray-500">›</td>
              </tr>
            ))}
          </tbody>
        </table>
        {loading && <div className="p-4 text-sm text-gray-400">Yükleniyor…</div>}
        {!loading && data.items.length === 0 && (
          <div className="p-6 text-sm text-gray-400 text-center">
            {q ? 'Sonuç bulunamadı.' : 'Henüz müşteri kaydı yok — "Siparişlerden Güncelle" ile başlayın.'}
          </div>
        )}
      </div>

      {lastPage > 1 && (
        <div className="flex justify-center items-center gap-3 text-sm">
          <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}
            className="px-3 py-1 rounded-lg bg-brand-input border border-brand-border disabled:opacity-40">←</button>
          <span className="text-gray-400">Sayfa {page} / {lastPage}</span>
          <button disabled={page >= lastPage} onClick={() => setPage(p => p + 1)}
            className="px-3 py-1 rounded-lg bg-brand-input border border-brand-border disabled:opacity-40">→</button>
        </div>
      )}

      {selected && (
        <CustomerDetail customer={selected} onClose={() => setSelected(null)}
          onSaved={(c) => { setSelected(c); load() }} />
      )}
    </div>
  )
}

function fmt(v) {
  return new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY' }).format(Number(v || 0))
}

const STAGE_LABELS = {
  1: 'Yeni', 2: 'İşleniyor', 3: 'Barkod Oluştu', 4: 'Kalıba Alındı', 5: 'Baskıda',
  6: 'Baskı Tamam', 7: 'Paketlendi', 8: 'Kargoda', 9: 'Teslim',
}

function CustomerDetail({ customer, onClose, onSaved }) {
  const [notes, setNotes] = useState(customer.notes || '')
  const [busy, setBusy] = useState(false)

  const saveNotes = async () => {
    setBusy(true)
    try { onSaved(await api.patch(`/api/customers/${customer.id}`, { notes: notes || null })) }
    catch { /* toast yok — hata sessiz geçilmez ama minimal tutuldu */ }
    finally { setBusy(false) }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60" onClick={onClose}>
      <div className="bg-brand-card border border-brand-border rounded-2xl p-5 w-full max-w-2xl max-h-[85vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}>
        <div className="flex items-start justify-between mb-1">
          <div>
            <h2 className="font-semibold text-lg">{customer.name || customer.email}</h2>
            <div className="text-xs text-gray-400">{customer.email}{customer.phone ? ` · ${customer.phone}` : ''}</div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-lg leading-none">×</button>
        </div>

        <div className="grid grid-cols-3 gap-3 my-4">
          <Stat label="Sipariş" value={customer.orders_count} />
          <Stat label="Toplam Harcama" value={fmt(customer.total_spent)} />
          <Stat label="İlk Sipariş" value={customer.first_order_at
            ? new Date(customer.first_order_at).toLocaleDateString('tr-TR') : '—'} />
        </div>

        <label className="block text-sm mb-4">
          <span className="text-gray-400 text-xs">Notlar</span>
          <textarea
            className="mt-1 w-full bg-brand-input border border-brand-border rounded-lg px-3 py-2 text-sm"
            rows={2} maxLength={5000} value={notes} onChange={e => setNotes(e.target.value)}
            onBlur={saveNotes} placeholder="Müşteri hakkında iç not…" />
          {busy && <span className="text-[10px] text-gray-500">kaydediliyor…</span>}
        </label>

        <h3 className="text-sm font-medium mb-2">Sipariş Geçmişi</h3>
        <div className="border border-brand-border rounded-lg overflow-hidden">
          <table className="w-full text-xs">
            <thead className="text-gray-400 bg-brand-input">
              <tr>
                <th className="text-left px-3 py-2">Sipariş</th>
                <th className="text-left px-3 py-2">Tarih</th>
                <th className="text-left px-3 py-2">Durum</th>
                <th className="text-right px-3 py-2">Tutar</th>
              </tr>
            </thead>
            <tbody>
              {customer.orders.map(o => (
                <tr key={o.id} className="border-t border-brand-border/50 hover:bg-brand-input/40 cursor-pointer"
                  onClick={() => window.open(`/orders/${o.id}`, '_blank')}>
                  <td className="px-3 py-2 font-mono">{o.name || `#${o.order_number}`}</td>
                  <td className="px-3 py-2 text-gray-400">
                    {o.created_at ? new Date(o.created_at).toLocaleDateString('tr-TR') : '—'}
                  </td>
                  <td className="px-3 py-2">
                    {o.is_iptal ? <span className="text-red-400">İptal</span>
                      : o.is_telafi ? <span className="text-amber-400">Telafi</span>
                      : <span className="text-gray-300">{STAGE_LABELS[o.current_stage] || '—'}</span>}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {o.total_price ? fmt(o.total_price) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function Stat({ label, value }) {
  return (
    <div className="bg-brand-input rounded-xl p-3">
      <div className="text-[10px] text-gray-400 uppercase tracking-wide">{label}</div>
      <div className="text-lg font-semibold mt-0.5">{value}</div>
    </div>
  )
}
