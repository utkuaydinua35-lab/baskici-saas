import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { OrderDialog, CariDialog, AddOrderItemsDialog } from './DealersPage'

const STAGE_LABEL = {
  1: 'Yeni', 2: 'Tasarım', 3: 'Barkod', 4: 'Baskı', 5: 'Baskı Tamam',
  6: 'Paketleme', 7: 'Paketlendi', 8: 'Kargoda', 9: 'Teslim',
}

export default function DealerDashboardPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const [ordering, setOrdering] = useState(false)
  const [cari, setCari] = useState(false)
  const [addTo, setAddTo] = useState(null)

  const load = async () => {
    setLoading(true)
    try {
      const [d, o] = await Promise.all([
        api.get(`/api/dealers/${id}/dashboard`),
        api.get(`/api/dealers/${id}/orders`).catch(() => []),
      ])
      setData(d); setOrders(Array.isArray(o) ? o : [])
    } catch { setData(null) }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [id])

  const fmt = (n, cur) => new Intl.NumberFormat('tr-TR', { style: 'currency', currency: cur || 'TRY' }).format(n || 0)

  if (loading) return <div className="mx-auto w-full max-w-[1200px] page-enter"><div className="card">Yükleniyor…</div></div>
  if (!data) return <div className="mx-auto w-full max-w-[1200px] page-enter"><div className="card text-red-300">Bayii bulunamadı.</div></div>

  const cur = data.currency || 'TRY'
  const bal = cur === 'USD' ? data.balance_usd : data.balance

  return (
    <div className="mx-auto w-full max-w-[1200px] page-enter">
      <button onClick={() => navigate('/bayiler')} className="text-accent text-sm hover:underline mb-3">← Bayiler</button>

      <div className="flex items-start justify-between flex-wrap gap-3 mb-4">
        <div>
          <h1 className="text-2xl font-semibold text-gray-100">🤝 {data.name}</h1>
          <p className="text-sm text-gray-500 mt-1">{data.phone || '—'}{data.email ? ` · ${data.email}` : ''}</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setCari(true)} className="btn-secondary !text-sm">💳 Cari</button>
          <button onClick={() => setOrdering(true)} className="btn-primary !text-sm">🛒 Sipariş Ekle</button>
        </div>
      </div>

      {/* Stat kartları */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
        <Stat label={`Bakiye`} value={fmt(bal, cur)} sub={bal > 0 ? 'bayi borçlu' : bal < 0 ? 'alacaklı' : '—'}
          color={bal > 0 ? 'text-red-300' : bal < 0 ? 'text-emerald-300' : 'text-gray-200'} />
        <Stat label={`Bu ay (${data.month_label})`} value={data.month_orders} sub={`${data.month_qty} adet ürün`} />
        <Stat label="Açık sipariş" value={data.open_orders} sub="gönderilmemiş" />
        <Stat label="Toplam sipariş" value={data.total_orders} sub={`${data.total_qty} adet ürün`} />
      </div>

      {/* Sipariş listesi */}
      <div className="card !p-0 overflow-hidden">
        <div className="px-4 py-2.5 border-b border-brand-border flex items-center justify-between">
          <span className="text-sm font-medium text-gray-200">Siparişler</span>
          <span className="text-xs text-gray-500">{orders.length} sipariş</span>
        </div>
        {orders.length === 0 ? (
          <div className="p-8 text-center text-gray-500 text-sm">Henüz sipariş yok. "Sipariş Ekle" ile başla.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="tbl text-sm">
              <thead><tr><th>Sipariş</th><th></th><th>Alıcı</th><th>Adet</th><th>Tutar</th><th>Durum</th><th>Tarih</th></tr></thead>
              <tbody>
                {orders.map(o => (
                  <tr key={o.id} className="cursor-pointer" onClick={() => navigate(`/orders/${o.id}`, { state: { from: `/bayiler/${id}` } })}>
                    <td className="font-medium text-accent whitespace-nowrap">{o.order_number}</td>
                    <td className="whitespace-nowrap">
                      {!o.is_iptal && (
                        <button onClick={e => { e.stopPropagation(); setAddTo(o) }}
                          className="text-[11px] px-2 py-0.5 rounded-lg border border-accent/40 text-accent hover:bg-accent/10" title="Bu siparişe ürün ekle">+ Ürün</button>
                      )}
                    </td>
                    <td className="text-gray-300">{o.customer_name || '—'}</td>
                    <td className="tabular-nums">{o.total_qty}</td>
                    <td className="tabular-nums text-gray-300 whitespace-nowrap">
                      {o.total_price ? fmt(Number(o.total_price), o.currency) : '—'}
                      {Number(o.shipping_fee) > 0 && <span className="block text-[10px] text-gray-500">+ {fmt(Number(o.shipping_fee), 'TRY')} kargo</span>}
                    </td>
                    <td>
                      <span className={`text-[11px] px-2 py-0.5 rounded-full ${o.is_iptal ? 'bg-red-500/15 text-red-300' : (o.fulfillment_status === 'fulfilled' || (o.current_stage || 0) >= 8) ? 'bg-emerald-500/15 text-emerald-300' : 'bg-brand-input text-gray-400'}`}>
                        {o.is_iptal ? 'İptal' : STAGE_LABEL[o.current_stage] || 'Yeni'}
                      </span>
                    </td>
                    <td className="text-gray-500 text-xs whitespace-nowrap">{o.created_at ? new Date(o.created_at).toLocaleDateString('tr-TR') : ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {ordering && <OrderDialog dealer={data} onClose={() => setOrdering(false)} onCreated={() => { setOrdering(false); load() }} />}
      {cari && <CariDialog dealer={data} onClose={() => setCari(false)} onChanged={load} />}
      {addTo && <AddOrderItemsDialog dealer={data} order={addTo} onClose={() => setAddTo(null)} onAdded={() => { setAddTo(null); load() }} />}
    </div>
  )
}

function Stat({ label, value, sub, color = 'text-gray-100' }) {
  return (
    <div className="card !py-3">
      <div className="text-[10px] uppercase tracking-wide text-gray-500">{label}</div>
      <div className={`text-xl font-bold tabular-nums mt-0.5 ${color}`}>{value}</div>
      {sub && <div className="text-[11px] text-gray-600 mt-0.5">{sub}</div>}
    </div>
  )
}
