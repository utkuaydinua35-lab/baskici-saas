import { useCallback, useEffect, useState } from 'react'
import { api, getToken } from '../lib/api'
import { useStore } from '../lib/store'
import { Modal } from './UrunlerPage'

// Mağaza müşterileri — bu mağazada siparişi olanlar.
export default function MusterilerPage() {
  const { storeId } = useStore()
  const [data, setData] = useState({ items: [], total: 0, page: 1, per_page: 50 })
  const [q, setQ] = useState('')
  const [sort, setSort] = useState('last_order_at')
  const [subscribed, setSubscribed] = useState(false)
  const [segment, setSegment] = useState('')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    if (!storeId) return
    setError('')
    try {
      const params = new URLSearchParams({ sort, page: String(page), store_id: storeId })
      if (q.trim()) params.set('q', q.trim())
      if (subscribed) params.set('subscribed', 'true')
      if (segment) params.set('segment', segment)
      setData(await api.get(`/api/customers?${params}`))
    } catch (e) {
      setError(typeof e?.detail === 'string' ? e.detail : 'Müşteriler yüklenemedi')
    }
  }, [storeId, q, sort, page, subscribed, segment])

  useEffect(() => {
    const t = setTimeout(load, q ? 300 : 0)
    return () => clearTimeout(t)
  }, [load, q])

  const exportSubscribers = async () => {
    try {
      const res = await fetch('/api/customers/export/subscribers.csv', {
        headers: { Authorization: `Bearer ${getToken()}` },
      })
      if (!res.ok) throw new Error()
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = 'bulten-aboneleri.csv'; a.click()
      URL.revokeObjectURL(url)
    } catch { setError('Dışa aktarma başarısız') }
  }

  const openDetail = async (id) => {
    try { setSelected(await api.get(`/api/customers/${id}`)) }
    catch { setError('Müşteri açılamadı') }
  }

  const lastPage = Math.max(1, Math.ceil(data.total / data.per_page))

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <h1 className="text-xl font-semibold">Müşteriler</h1>
        <span className="text-sm text-panel-muted">{data.total} kayıt</span>
        <input value={q} onChange={e => { setQ(e.target.value); setPage(1) }}
          placeholder="Ad veya e-posta ara…" className="input !w-64" />
        <select value={sort} onChange={e => { setSort(e.target.value); setPage(1) }}
          className="input !w-auto">
          <option value="last_order_at">Son sipariş</option>
          <option value="total_spent">Toplam harcama</option>
          <option value="orders_count">Sipariş sayısı</option>
        </select>
        {[['', 'Tümü'], ['vip', '💎 VIP (1000₺+)'], ['tekrar', '🔁 Tekrar alan'], ['tek', 'Tek sipariş']].map(([k, l]) => (
          <button key={k} onClick={() => { setSegment(k); setPage(1) }}
            className={`text-xs px-3 py-1.5 rounded-full border transition ${segment === k
              ? 'border-panel-accent bg-emerald-50 text-emerald-700 font-medium'
              : 'border-panel-border text-panel-muted hover:text-panel-ink'}`}>
            {l}
          </button>
        ))}
        <button onClick={() => { setSubscribed(v => !v); setPage(1) }}
          className={`text-xs px-3 py-1.5 rounded-full border transition ${subscribed
            ? 'border-emerald-500 bg-emerald-50 text-emerald-700 font-medium'
            : 'border-panel-border text-panel-muted hover:text-panel-ink'}`}>
          📮 Bülten aboneleri
        </button>
        {subscribed && (
          <button onClick={exportSubscribers} className="btn-ghost text-xs">⬇ CSV indir</button>
        )}
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="card !p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="text-panel-muted text-xs bg-panel-input">
            <tr>
              <th className="text-left px-4 py-2.5">Müşteri</th>
              <th className="text-right px-4 py-2.5">Sipariş</th>
              <th className="text-right px-4 py-2.5">Toplam Harcama</th>
              <th className="text-left px-4 py-2.5">Son Sipariş</th>
              <th className="px-2 py-2.5"></th>
            </tr>
          </thead>
          <tbody>
            {data.items.map(c => (
              <tr key={c.id} onClick={() => openDetail(c.id)}
                className="border-t border-panel-border cursor-pointer hover:bg-panel-input/50">
                <td className="px-4 py-2.5">
                  <div className="font-medium">
                    {c.name || '—'}
                    {c.accepts_marketing && (
                      <span className="ml-1.5 text-[10px] text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded-full"
                        title="Bülten abonesi">📮</span>
                    )}
                  </div>
                  <div className="text-xs text-panel-muted">{c.email}</div>
                </td>
                <td className="px-4 py-2.5 text-right tabular-nums">
                  {c.orders_count}
                  {c.orders_count > 1 && <span className="ml-1 text-[10px] text-emerald-700">tekrar</span>}
                </td>
                <td className="px-4 py-2.5 text-right tabular-nums font-medium">{fmt(c.total_spent)}</td>
                <td className="px-4 py-2.5 text-xs text-panel-muted">
                  {c.last_order_at ? new Date(c.last_order_at).toLocaleDateString('tr-TR') : '—'}
                </td>
                <td className="px-2 py-2.5 text-panel-muted">›</td>
              </tr>
            ))}
          </tbody>
        </table>
        {data.items.length === 0 && (
          <div className="p-6 text-sm text-panel-muted text-center">
            {q ? 'Sonuç bulunamadı.' : 'Bu mağazada henüz müşteri yok.'}
          </div>
        )}
      </div>

      {lastPage > 1 && (
        <div className="flex justify-center items-center gap-3 text-sm">
          <button disabled={page <= 1} onClick={() => setPage(p => p - 1)} className="btn-ghost !py-1">←</button>
          <span className="text-panel-muted">Sayfa {page} / {lastPage}</span>
          <button disabled={page >= lastPage} onClick={() => setPage(p => p + 1)} className="btn-ghost !py-1">→</button>
        </div>
      )}

      {selected && (
        <CustomerDetail customer={selected} onClose={() => setSelected(null)}
          onSaved={(c) => { setSelected(c); load() }} />
      )}
    </div>
  )
}

const fmt = (v) => new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY' }).format(Number(v || 0))
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
    catch { /* sessiz */ }
    finally { setBusy(false) }
  }

  return (
    <Modal title={customer.name || customer.email} onClose={onClose} wide>
      <div className="text-xs text-panel-muted -mt-3 mb-3">
        {customer.email}{customer.phone ? ` · ${customer.phone}` : ''}
      </div>

      <div className="grid grid-cols-3 gap-3 mb-4">
        <Stat label="Sipariş" value={customer.orders_count} />
        <Stat label="Toplam Harcama" value={fmt(customer.total_spent)} />
        <Stat label="İlk Sipariş" value={customer.first_order_at
          ? new Date(customer.first_order_at).toLocaleDateString('tr-TR') : '—'} />
      </div>

      <label className="block text-sm mb-4">
        <span className="text-panel-muted text-xs">Notlar</span>
        <textarea className="input mt-1" rows={2} maxLength={5000} value={notes}
          onChange={e => setNotes(e.target.value)} onBlur={saveNotes}
          placeholder="Müşteri hakkında iç not…" />
        {busy && <span className="text-[10px] text-panel-muted">kaydediliyor…</span>}
      </label>

      <h3 className="text-sm font-medium mb-2">Sipariş Geçmişi</h3>
      <div className="border border-panel-border rounded-xl overflow-hidden">
        <table className="w-full text-xs">
          <thead className="text-panel-muted bg-panel-input">
            <tr>
              <th className="text-left px-3 py-2">Sipariş</th>
              <th className="text-left px-3 py-2">Tarih</th>
              <th className="text-left px-3 py-2">Durum</th>
              <th className="text-right px-3 py-2">Tutar</th>
            </tr>
          </thead>
          <tbody>
            {customer.orders.map(o => (
              <tr key={o.id} className="border-t border-panel-border">
                <td className="px-3 py-2 font-mono">{o.name || `#${o.order_number}`}</td>
                <td className="px-3 py-2 text-panel-muted">
                  {o.created_at ? new Date(o.created_at).toLocaleDateString('tr-TR') : '—'}
                </td>
                <td className="px-3 py-2">
                  {o.is_iptal ? <span className="text-red-600">İptal</span>
                    : o.is_telafi ? <span className="text-amber-700">Telafi</span>
                    : (STAGE_LABELS[o.current_stage] || '—')}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {o.total_price ? fmt(o.total_price) : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Modal>
  )
}

function Stat({ label, value }) {
  return (
    <div className="bg-panel-input rounded-xl p-3">
      <div className="text-[10px] text-panel-muted uppercase tracking-wide">{label}</div>
      <div className="text-lg font-semibold mt-0.5">{value}</div>
    </div>
  )
}
