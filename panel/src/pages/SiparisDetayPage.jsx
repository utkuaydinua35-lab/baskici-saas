import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../lib/api'
import { FinancialBadge } from './SiparislerPage'

// Sipariş detayı — özet + kalemler + para iadesi (üretim akışı Baskıcı'da).
export default function SiparisDetayPage() {
  const { orderId } = useParams()
  const [detail, setDetail] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    api.get(`/api/orders/${orderId}`)
      .then(setDetail)
      .catch(e => setError(typeof e?.detail === 'string' ? e.detail : 'Sipariş yüklenemedi'))
  }, [orderId])
  useEffect(() => { load() }, [load])

  if (error) return <p className="text-sm text-red-600">{error}</p>
  if (!detail) return <p className="text-sm text-panel-muted">Yükleniyor…</p>

  const ship = detail.raw?.shipping_address || {}
  const payment = detail.raw?.payment
  const total = detail.raw?.total_price
  const discount = detail.raw?.discount

  return (
    <div className="space-y-4 max-w-3xl">
      <div className="flex items-center gap-3">
        <Link to="/siparisler" className="text-panel-muted hover:text-panel-ink">←</Link>
        <h1 className="text-xl font-semibold font-mono">{detail.name || `#${detail.order_number}`}</h1>
        <FinancialBadge status={detail.financial_status} />
        {detail.cancelled_at && (
          <span className="text-[11px] px-2 py-0.5 rounded-full bg-red-100 text-red-700">İptal</span>
        )}
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="card">
          <h2 className="text-sm font-semibold mb-2">Sipariş İçeriği</h2>
          <ul className="space-y-1.5 text-sm">
            {(detail.line_items || []).map(li => (
              <li key={li.id} className="flex justify-between gap-2">
                <span className="text-panel-ink">
                  {li.title}
                  {li.variant_title && <span className="text-panel-muted"> — {li.variant_title}</span>}
                </span>
                <span className="text-panel-muted whitespace-nowrap">×{li.quantity}</span>
              </li>
            ))}
          </ul>
          {discount && (
            <div className="mt-2 pt-2 border-t border-panel-border text-sm text-emerald-700 flex justify-between">
              <span>İndirim ({discount.code})</span><span>−{discount.amount} ₺</span>
            </div>
          )}
          {total && (
            <div className="mt-2 pt-2 border-t border-panel-border font-semibold text-sm flex justify-between">
              <span>Toplam</span><span>{fmtTl(total)}</span>
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className="card">
            <h2 className="text-sm font-semibold mb-2">Müşteri</h2>
            <div className="text-sm">{detail.customer_name || '—'}</div>
            {detail.customer_email && (
              <div className="text-xs text-panel-muted">{detail.customer_email}</div>
            )}
            {(ship.address1 || ship.city) && (
              <div className="mt-2 text-xs text-panel-muted leading-relaxed">
                {ship.address1}<br />
                {[ship.city, ship.province, ship.zip].filter(Boolean).join(' / ')}
                {ship.phone && <><br />{ship.phone}</>}
              </div>
            )}
            {detail.note && (
              <div className="mt-2 text-xs bg-amber-50 border border-amber-200 rounded-lg p-2">
                📝 {detail.note}
              </div>
            )}
          </div>

          {payment && <RefundCard orderId={detail.id} />}
        </div>
      </div>

      <p className="text-xs text-panel-muted">
        Üretim durumu, kalıp ve kargo işlemleri <b>Baskıcı Paneli</b>nde yönetilir.
      </p>
    </div>
  )
}

const fmtTl = (v) => new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY' }).format(Number(v || 0))

// Para iadesi — backend yönetici yetkisi arar; iki adımlı onay.
function RefundCard({ orderId }) {
  const [info, setInfo] = useState(null)
  const [amount, setAmount] = useState('')
  const [reason, setReason] = useState('')
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)   // {ok, text}
  const [denied, setDenied] = useState(false)

  const load = useCallback(async () => {
    try {
      const r = await api.get(`/api/orders/${orderId}/refunds`)
      setInfo(r)
      setAmount(a => a || r.refundable)
    } catch (e) {
      if (e?.status === 403) setDenied(true)
    }
  }, [orderId])
  useEffect(() => { load() }, [load])

  if (denied || !info) return null
  const refundable = Number(info.refundable)

  const doRefund = async () => {
    setBusy(true); setMsg(null)
    try {
      const r = await api.post(`/api/orders/${orderId}/refund`, {
        amount: Number(amount), reason: reason || null,
      })
      setMsg({ ok: true, text: `${r.amount} ₺ iade edildi` })
      setConfirming(false); setReason(''); setAmount('')
      await load()
    } catch (e) {
      setMsg({ ok: false, text: typeof e?.detail === 'string' ? e.detail : 'İade başarısız' })
    } finally { setBusy(false) }
  }

  return (
    <div className="card">
      <h2 className="text-sm font-semibold mb-2">Para İadesi</h2>
      <div className="text-xs text-panel-muted space-y-0.5 mb-2">
        <div>Ödenen: <b className="text-panel-ink">{info.paid_amount} ₺</b> · {info.provider}</div>
        {Number(info.refunded_total) > 0 && <div>İade edilen: {info.refunded_total} ₺</div>}
      </div>
      {info.refunds.length > 0 && (
        <div className="space-y-1 mb-2">
          {info.refunds.map(r => (
            <div key={r.id} className="text-[11px] bg-panel-input rounded-lg px-2 py-1 flex justify-between">
              <span className={r.status === 'succeeded' ? 'text-emerald-700' : 'text-red-600'}>
                {r.status === 'succeeded' ? '✓' : '✗'} {r.amount} ₺
              </span>
              <span className="text-panel-muted">
                {r.created_at ? new Date(r.created_at).toLocaleDateString('tr-TR') : ''}
              </span>
            </div>
          ))}
        </div>
      )}
      {msg && <p className={`text-xs mb-2 ${msg.ok ? 'text-emerald-700' : 'text-red-600'}`}>{msg.text}</p>}

      {refundable > 0 ? (
        !confirming ? (
          <div className="space-y-2">
            <div className="flex gap-2">
              <input type="number" step="0.01" min="0.01" max={refundable} value={amount}
                onChange={e => setAmount(e.target.value)} className="input !py-1.5 text-xs" />
              <button onClick={() => {
                const n = Number(amount)
                if (!n || n <= 0 || n > refundable) { setMsg({ ok: false, text: `Tutar 0 ile ${refundable} arasında olmalı` }); return }
                setConfirming(true)
              }} className="px-3 py-1.5 rounded-xl text-xs bg-red-50 text-red-700 border border-red-200 whitespace-nowrap">
                İade Et
              </button>
            </div>
            <input value={reason} onChange={e => setReason(e.target.value)} maxLength={500}
              placeholder="Sebep (opsiyonel)" className="input !py-1.5 text-xs" />
          </div>
        ) : (
          <div className="bg-red-50 border border-red-200 rounded-xl p-2.5 space-y-2">
            <p className="text-xs text-red-700">
              <b>{Number(amount).toFixed(2)} ₺</b> müşteriye iade edilecek. Geri alınamaz.
            </p>
            <div className="flex gap-2">
              <button onClick={doRefund} disabled={busy}
                className="px-3 py-1.5 rounded-xl text-xs bg-red-600 text-white disabled:opacity-50">
                {busy ? 'İade ediliyor…' : 'Onaylıyorum, iade et'}
              </button>
              <button onClick={() => setConfirming(false)} disabled={busy}
                className="px-3 py-1.5 rounded-xl text-xs text-panel-muted">Vazgeç</button>
            </div>
          </div>
        )
      ) : (
        <p className="text-[11px] text-panel-muted italic">Tutarın tamamı iade edildi.</p>
      )}
    </div>
  )
}
