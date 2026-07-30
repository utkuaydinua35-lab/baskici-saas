import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useStore } from '../lib/store'
import { useToast } from '../components/Toast'

// Terk edilmiş sepetler + panelden oluşturulan taslak siparişler (ödeme linkli).
export default function TerkSepetlerPage() {
  const { storeId, store } = useStore()
  const toast = useToast()
  const [tab, setTab] = useState('abandoned')   // abandoned | draft
  const [data, setData] = useState({ items: [], total: 0, total_amount: '0', page: 1, per_page: 50 })
  const [page, setPage] = useState(1)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(null)
  const [detailId, setDetailId] = useState(null)   // açık sepet detayı

  const storefrontUrl = (store?.config?.storefront_url
    || (store?.config?.shop_domain ? `https://${store.config.shop_domain}` : '')).replace(/\/$/, '')

  const load = useCallback(async () => {
    if (!storeId) return
    setError('')
    try { setData(await api.get(`/api/checkout-sessions?store_id=${storeId}&page=${page}&kind=${tab}`)) }
    catch (e) { setError(typeof e?.detail === 'string' ? e.detail : 'Yüklenemedi') }
  }, [storeId, page, tab])
  useEffect(() => { load() }, [load])

  const copyLink = async (s, e) => {
    e?.stopPropagation?.()
    try {
      await navigator.clipboard.writeText(`${storefrontUrl}/sepet?restore=${s.lookup_token}`)
      toast.success('Ödeme linki kopyalandı')
    } catch { toast.error('Kopyalanamadı') }
  }

  const sendReminder = async (s, e) => {
    e?.stopPropagation?.()   // satır tıklaması detayı açmasın
    setBusyId(s.id); setError('')
    try { await api.post(`/api/checkout-sessions/${s.id}/reminder`, {}); await load() }
    catch (e) { setError(typeof e?.detail === 'string' ? e.detail : 'Hatırlatma gönderilemedi') }
    finally { setBusyId(null) }
  }

  const lastPage = Math.max(1, Math.ceil(data.total / data.per_page))
  const STATUS = {
    pending: ['Beklemede', 'text-amber-300'],
    expired: ['Süresi doldu', 'text-panel-muted'],
    failed: ['Başarısız', 'text-red-400'],
    draft: ['Taslak', 'text-sky-600'],
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <h1 className="text-xl font-semibold">Terk Edilmiş Sepetler</h1>
        <span className="text-sm text-panel-muted">
          {data.total} {tab === 'draft' ? 'taslak' : 'sepet'} · {fmt(data.total_amount)} potansiyel ciro
        </span>
      </div>

      <div className="flex gap-1 bg-panel-input rounded-xl p-1 w-fit text-sm">
        {[['abandoned', 'Terk Edilenler'], ['draft', '🧾 Taslak Siparişler']].map(([k, l]) => (
          <button key={k} onClick={() => { setTab(k); setPage(1) }}
            className={`px-3 py-1.5 rounded-lg transition ${tab === k
              ? 'bg-panel-card shadow-sm font-medium' : 'text-panel-muted hover:text-panel-ink'}`}>
            {l}
          </button>
        ))}
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}

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
                <tr key={s.id} onClick={() => setDetailId(s.id)}
                  className="border-t border-panel-border hover:bg-panel-input/50 cursor-pointer transition">
                  <td className="px-4 py-2.5">
                    <div className="font-medium">{s.customer_name || '—'}</div>
                    <div className="text-xs text-panel-muted">{s.email}</div>
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums font-medium">
                    {fmt(s.amount)}
                    {s.discount_code && (
                      <div className="text-[10px] text-emerald-300 font-mono">{s.discount_code}</div>
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
                    {s.status === 'draft' ? (
                      <div className="flex items-center gap-1.5">
                        {s.reminder_sent_at && <span className="text-xs text-emerald-300" title="Ödeme linki e-postalandı">✉✓</span>}
                        <button onClick={e => copyLink(s, e)} className="btn-ghost !py-1 text-xs">🔗 Linki Kopyala</button>
                      </div>
                    ) : s.reminder_sent_at ? (
                      <span className="text-xs text-emerald-300"
                        title={new Date(s.reminder_sent_at).toLocaleString('tr-TR')}>✓ Gönderildi</span>
                    ) : (
                      <button onClick={e => sendReminder(s, e)} disabled={busyId === s.id}
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
          <div className="p-6 text-sm text-panel-muted text-center">
            {tab === 'draft'
              ? 'Henüz taslak sipariş yok — Siparişler sayfasından "＋ Sipariş Oluştur" ile başlayın.'
              : 'Terk edilmiş sepet yok — harika! 🎉'}
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

      <p className="text-xs text-panel-muted max-w-2xl">
        Satıra tıklayarak sepetin içeriğini, müşteri bilgilerini ve
        <b> müşterinin hangi aşamada vazgeçtiğini</b> görebilirsiniz.
        Hatırlatma sepet başına <b>1 kez</b> gönderilebilir (KVKK).
      </p>

      {detailId && (
        <AbandonedDetail id={detailId} storefrontUrl={storefrontUrl}
          onClose={() => setDetailId(null)} />
      )}
    </div>
  )
}

// Terk edilen sepetin dökümü + NEREDE VAZGEÇTİ analizi
function AbandonedDetail({ id, storefrontUrl, onClose }) {
  const [d, setD] = useState(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    api.get(`/api/checkout-sessions/${id}`).then(setD)
      .catch(e => setErr(typeof e?.detail === 'string' ? e.detail : 'Yüklenemedi'))
  }, [id])

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4"
      onClick={onClose}>
      <div onClick={e => e.stopPropagation()}
        className="card w-full max-w-2xl max-h-[88vh] overflow-y-auto space-y-3">
        <div className="flex items-center gap-2">
          <h2 className="font-semibold">🛒 Terk Edilen Sepet</h2>
          <button onClick={onClose} className="ml-auto text-panel-muted hover:text-panel-ink">×</button>
        </div>
        {err && <p className="text-sm text-red-400">{err}</p>}
        {!d ? <p className="text-sm text-panel-muted">Yükleniyor…</p> : (
          <>
            {/* NEREDE VAZGEÇTİ — huni şeridi */}
            <div className="rounded-xl bg-panel-input/60 p-3 space-y-2">
              <div className="flex items-center gap-1">
                {d.funnel.steps.map((st, i) => (
                  <div key={st.key} className="flex-1 flex items-center gap-1">
                    <div className={`flex-1 h-1.5 rounded-full ${
                      st.done ? 'bg-emerald-500/100' : 'bg-panel-border'}`}
                      title={st.label} />
                    {i === d.funnel.steps.length - 1 && (
                      <span className="text-[10px] text-panel-muted whitespace-nowrap">ödeme</span>
                    )}
                  </div>
                ))}
              </div>
              <div className="text-sm">
                <b>Son aşama: {d.funnel.label}</b>
                <span className="text-panel-muted"> — burada vazgeçti</span>
              </div>
              {d.funnel.reason && (
                <p className="text-xs text-panel-muted">🔍 {d.funnel.reason}</p>
              )}
              {d.funnel.action && (
                <p className="text-xs text-emerald-300">💡 {d.funnel.action}</p>
              )}
            </div>

            {/* Müşteri */}
            <div className="grid sm:grid-cols-2 gap-3 text-sm">
              <div className="space-y-1">
                <div className="text-xs text-panel-muted">Müşteri</div>
                <div className="font-medium">{d.customer.name || '—'}</div>
                {d.customer.email && (
                  <a href={`mailto:${d.customer.email}`} className="block text-xs text-panel-accent hover:underline">
                    ✉️ {d.customer.email}
                  </a>
                )}
                {d.customer.phone && (
                  <a href={`https://wa.me/9${d.customer.phone.replace(/\D/g, '')}`}
                    target="_blank" rel="noreferrer"
                    className="block text-xs text-emerald-300 hover:underline">
                    💬 WhatsApp: {d.customer.phone}
                  </a>
                )}
                {(d.customer.city || d.customer.province) && (
                  <div className="text-xs text-panel-muted">
                    📍 {[d.customer.province, d.customer.city].filter(Boolean).join(' / ')}
                  </div>
                )}
              </div>
              <div className="space-y-1">
                <div className="text-xs text-panel-muted">Tutar</div>
                <div className="font-medium tabular-nums">{fmt(d.amount)}</div>
                <div className="text-xs text-panel-muted">
                  kargo {fmt(d.shipping_amount)}
                  {Number(d.discount_amount) > 0 && ` · indirim ${fmt(d.discount_amount)}`}
                  {d.discount_code && ` (${d.discount_code})`}
                </div>
                <div className="text-xs text-panel-muted">
                  {d.created_at && new Date(d.created_at).toLocaleString('tr-TR')}
                </div>
              </div>
            </div>

            {/* Sepet içeriği */}
            <div>
              <div className="text-xs text-panel-muted mb-1">Sepetteki ürünler</div>
              <div className="space-y-1">
                {d.items.map((it, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm border border-panel-border rounded-xl px-3 py-2">
                    <div className="min-w-0">
                      <div className="truncate">{it.title}</div>
                      <div className="text-xs text-panel-muted">
                        {[it.model, it.variation].filter(Boolean).join(' · ')}
                      </div>
                    </div>
                    <div className="ml-auto text-xs text-panel-muted whitespace-nowrap">
                      {it.quantity} × {fmt(it.unit_price)}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex gap-2 pt-1">
              <button onClick={() => {
                navigator.clipboard.writeText(`${storefrontUrl}${d.restore_url}`)
              }} className="btn-ghost !py-1.5 text-xs">🔗 Sepeti geri yükleme linkini kopyala</button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

const fmt = (v) => new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY' }).format(Number(v || 0))
