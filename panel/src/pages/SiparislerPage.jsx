import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { useStore } from '../lib/store'

// Mağaza siparişleri — sade liste (üretim detayları Baskıcı'da kalır).
const STAGE_LABELS = {
  1: 'Yeni', 2: 'İşleniyor', 3: 'Barkod Oluştu', 4: 'Kalıba Alındı', 5: 'Baskıda',
  6: 'Baskı Tamam', 7: 'Paketlendi', 8: 'Kargoda', 9: 'Teslim',
}

export default function SiparislerPage() {
  const { storeId } = useStore()
  const [data, setData] = useState({ items: [], total: 0, page: 1, per_page: 50 })
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    if (!storeId) return
    setLoading(true); setError('')
    try {
      const params = new URLSearchParams({ store_id: storeId, page: String(page) })
      if (search.trim()) params.set('search', search.trim())
      setData(await api.get(`/api/orders?${params}`))
    } catch (e) {
      setError(typeof e?.detail === 'string' ? e.detail : 'Siparişler yüklenemedi')
    } finally { setLoading(false) }
  }, [storeId, page, search])

  useEffect(() => {
    const t = setTimeout(load, search ? 300 : 0)
    return () => clearTimeout(t)
  }, [load, search])

  const lastPage = Math.max(1, Math.ceil((data.total || 0) / (data.per_page || 50)))

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <h1 className="text-xl font-semibold">Siparişler</h1>
        <span className="text-sm text-panel-muted">{data.total ?? 0} sipariş</span>
        <input value={search} onChange={e => { setSearch(e.target.value); setPage(1) }}
          placeholder="Sipariş no veya müşteri ara…" className="input !w-64 ml-auto" />
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="card !p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="text-panel-muted text-xs bg-panel-input">
            <tr>
              <th className="text-left px-4 py-2.5">Sipariş</th>
              <th className="text-left px-4 py-2.5">Müşteri</th>
              <th className="text-right px-4 py-2.5">Tutar</th>
              <th className="text-left px-4 py-2.5">Tarih</th>
              <th className="text-left px-4 py-2.5">Ödeme</th>
              <th className="text-left px-4 py-2.5">Durum</th>
              <th className="px-2 py-2.5"></th>
            </tr>
          </thead>
          <tbody>
            {(data.items || []).map(o => (
              <tr key={o.id} className="border-t border-panel-border hover:bg-panel-input/50">
                <td className="px-4 py-2.5">
                  <Link to={`/siparisler/${o.id}`} className="font-mono font-medium hover:underline">
                    {o.name || `#${o.order_number}`}
                  </Link>
                </td>
                <td className="px-4 py-2.5">
                  <div>{o.customer_name || '—'}</div>
                  <div className="text-[11px] text-panel-muted">{o.item_count} kalem</div>
                </td>
                <td className="px-4 py-2.5 text-right tabular-nums font-medium">
                  {o.total_price ? new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY' }).format(Number(o.total_price)) : '—'}
                </td>
                <td className="px-4 py-2.5 text-xs text-panel-muted whitespace-nowrap">
                  {o.created_at_platform
                    ? new Date(o.created_at_platform).toLocaleString('tr-TR', {
                        day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—'}
                </td>
                <td className="px-4 py-2.5"><FinancialBadge status={o.financial_status} /></td>
                <td className="px-4 py-2.5 text-xs">
                  {o.cancelled_at
                    ? <span className="text-red-600">İptal</span>
                    : <span>{STAGE_LABELS[o.current_stage] || '—'}</span>}
                </td>
                <td className="px-2 py-2.5 text-panel-muted">
                  <Link to={`/siparisler/${o.id}`}>›</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {loading && <div className="p-4 text-sm text-panel-muted">Yükleniyor…</div>}
        {!loading && (data.items || []).length === 0 && (
          <div className="p-6 text-sm text-panel-muted text-center">
            {search ? 'Sonuç bulunamadı.' : 'Henüz sipariş yok — ilk satışına az kaldı!'}
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
    </div>
  )
}

export function FinancialBadge({ status }) {
  const map = {
    paid: ['Ödendi', 'bg-emerald-100 text-emerald-700'],
    refunded: ['İade Edildi', 'bg-red-100 text-red-700'],
    partially_refunded: ['Kısmi İade', 'bg-amber-100 text-amber-700'],
  }
  const [label, cls] = map[status] || [status || '—', 'bg-slate-100 text-slate-600']
  return <span className={`text-[11px] px-2 py-0.5 rounded-full ${cls}`}>{label}</span>
}
