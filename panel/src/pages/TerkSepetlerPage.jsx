import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useStore } from '../lib/store'

// Terk edilmiş sepetler — tamamlanmamış checkout'lar + tek seferlik hatırlatma.
export default function TerkSepetlerPage() {
  const { storeId } = useStore()
  const [data, setData] = useState({ items: [], total: 0, total_amount: '0', page: 1, per_page: 50 })
  const [page, setPage] = useState(1)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(null)

  const load = useCallback(async () => {
    if (!storeId) return
    setError('')
    try { setData(await api.get(`/api/checkout-sessions?store_id=${storeId}&page=${page}`)) }
    catch (e) { setError(typeof e?.detail === 'string' ? e.detail : 'Yüklenemedi') }
  }, [storeId, page])
  useEffect(() => { load() }, [load])

  const sendReminder = async (s) => {
    setBusyId(s.id); setError('')
    try { await api.post(`/api/checkout-sessions/${s.id}/reminder`, {}); await load() }
    catch (e) { setError(typeof e?.detail === 'string' ? e.detail : 'Hatırlatma gönderilemedi') }
    finally { setBusyId(null) }
  }

  const lastPage = Math.max(1, Math.ceil(data.total / data.per_page))
  const STATUS = {
    pending: ['Beklemede', 'text-amber-600'],
    expired: ['Süresi doldu', 'text-panel-muted'],
    failed: ['Başarısız', 'text-red-600'],
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <h1 className="text-xl font-semibold">Terk Edilmiş Sepetler</h1>
        <span className="text-sm text-panel-muted">
          {data.total} sepet · {fmt(data.total_amount)} potansiyel ciro
        </span>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="card !p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="text-panel-muted text-xs bg-panel-input">
            <tr>
              <th className="text-left px-4 py-2.5">Müşteri</th>
              <th className="text-right px-4 py-2.5">Tutar</th>
              <th className="text-right px-4 py-2.5">Kalem</th>
              <th className="text-left px-4 py-2.5">Durum</th>
              <th className="text-left px-4 py-2.5">Tarih</th>
              <th className="text-left px-4 py-2.5">Hatırlatma</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map(s => {
              const [label, cls] = STATUS[s.status] || [s.status, 'text-panel-muted']
              return (
                <tr key={s.id} className="border-t border-panel-border">
                  <td className="px-4 py-2.5">
                    <div className="font-medium">{s.customer_name || '—'}</div>
                    <div className="text-xs text-panel-muted">{s.email}</div>
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums font-medium">
                    {fmt(s.amount)}
                    {s.discount_code && (
                      <div className="text-[10px] text-emerald-700 font-mono">{s.discount_code}</div>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{s.item_count}</td>
                  <td className={`px-4 py-2.5 text-xs ${cls}`}>{label}</td>
                  <td className="px-4 py-2.5 text-xs text-panel-muted">
                    {s.created_at ? new Date(s.created_at).toLocaleString('tr-TR', {
                      day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
                    }) : '—'}
                  </td>
                  <td className="px-4 py-2.5">
                    {s.reminder_sent_at ? (
                      <span className="text-xs text-emerald-700"
                        title={new Date(s.reminder_sent_at).toLocaleString('tr-TR')}>✓ Gönderildi</span>
                    ) : (
                      <button onClick={() => sendReminder(s)} disabled={busyId === s.id}
                        className="btn-ghost !py-1 text-xs">
                        {busyId === s.id ? 'Gönderiliyor…' : '✉ Hatırlat'}
                      </button>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {data.items.length === 0 && (
          <div className="p-6 text-sm text-panel-muted text-center">Terk edilmiş sepet yok — harika! 🎉</div>
        )}
      </div>

      {lastPage > 1 && (
        <div className="flex justify-center items-center gap-3 text-sm">
          <button disabled={page <= 1} onClick={() => setPage(p => p - 1)} className="btn-ghost !py-1">←</button>
          <span className="text-panel-muted">Sayfa {page} / {lastPage}</span>
          <button disabled={page >= lastPage} onClick={() => setPage(p => p + 1)} className="btn-ghost !py-1">→</button>
        </div>
      )}

      <p className="text-xs text-panel-muted max-w-2xl">
        Hatırlatma sepet başına <b>1 kez</b> gönderilebilir (KVKK). Otomatik gönderim
        Ayarlar sayfasından açılır.
      </p>
    </div>
  )
}

const fmt = (v) => new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY' }).format(Number(v || 0))
