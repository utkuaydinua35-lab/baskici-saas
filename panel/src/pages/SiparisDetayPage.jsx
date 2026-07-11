import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../lib/api'

// Sipariş detayı — Shopify düzeni: solda ürünler + ödeme + zaman çizelgesi,
// sağda müşteri/adres/kargo/üretim durumu. Veri: zengin /detail endpoint'i.
const STAGES = [
  [1, 'Yeni'], [2, 'İşleniyor'], [3, 'Barkod Oluştu'], [4, 'Kalıba Alındı'],
  [5, 'Baskıda'], [6, 'Baskı Tamam'], [7, 'Paketlendi'], [8, 'Kargoda'], [9, 'Teslim'],
]
const STAGE_LABELS = Object.fromEntries(STAGES)

const ACTION_LABELS = {
  stage_change: 'aşama değişti', acil: 'acil işaretlendi', acil_geri: 'acil kaldırıldı',
  iptal: 'iptal edildi', iptal_geri: 'iptal geri alındı', paketlendi: 'paketlendi',
  kargoya_verildi: 'kargoya verildi', teslim_edildi: 'teslim edildi',
  musteri_onay: 'müşteri onayı', iade: 'para iadesi yapıldı', not: 'not eklendi',
}

export default function SiparisDetayPage() {
  const { orderId } = useParams()
  const [d, setD] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    api.get(`/api/orders/${orderId}/detail`)
      .then(setD)
      .catch(e => setError(typeof e?.detail === 'string' ? e.detail : 'Sipariş yüklenemedi'))
  }, [orderId])
  useEffect(() => { load() }, [load])

  if (error) return <p className="text-sm text-red-600">{error}</p>
  if (!d) return <SkeletonDetail />

  const fin = d.financial || {}
  const ship = d.shipping_address || {}
  const isStorefront = !!d.raw?.payment
  const stage = d.current_stage || 1

  return (
    <div className="max-w-5xl space-y-4 pb-10">
      {/* Başlık çubuğu */}
      <div className="flex items-center gap-3 flex-wrap">
        <Link to="/siparisler" className="w-8 h-8 flex items-center justify-center rounded-xl border border-panel-border text-panel-muted hover:text-panel-ink">←</Link>
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-semibold font-mono">{d.name || `#${d.order_number}`}</h1>
            <FinancialBadge status={fin.payment_status} />
            {d.cancelled_at
              ? <Badge cls="bg-red-100 text-red-700">İptal Edildi</Badge>
              : <Badge cls="bg-indigo-50 text-indigo-700">{STAGE_LABELS[stage] || '—'}</Badge>}
            {d.is_acil && <Badge cls="bg-amber-100 text-amber-700">⚡ Acil</Badge>}
          </div>
          <div className="text-xs text-panel-muted mt-0.5">
            {d.created_at_platform && new Date(d.created_at_platform).toLocaleString('tr-TR', {
              day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit',
            })}
            {d.store_name && ` · ${d.store_name}`}
          </div>
        </div>
      </div>

      <div className="grid lg:grid-cols-[1fr_320px] gap-4 items-start">
        {/* ── Sol kolon ── */}
        <div className="space-y-4 min-w-0">
          {/* Ürünler */}
          <div className="card !p-0 overflow-hidden">
            <div className="px-4 py-3 border-b border-panel-border flex items-center">
              <h2 className="text-sm font-semibold">
                Ürünler <span className="text-panel-muted font-normal">({d.line_items?.length || 0})</span>
              </h2>
            </div>
            <div className="divide-y divide-panel-border">
              {(d.line_items || []).map(li => (
                <div key={li.id} className="flex items-center gap-3 px-4 py-3">
                  <div className="w-14 h-14 rounded-xl bg-panel-input overflow-hidden shrink-0 border border-panel-border">
                    {li.image_url ? (
                      <img src={li.image_url} alt="" className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-xl opacity-30">📱</div>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium truncate">{li.title}</div>
                    {li.variant_title && (
                      <div className="text-xs text-panel-muted">{li.variant_title}</div>
                    )}
                    {li.sku && <div className="text-[10px] text-panel-muted font-mono">{li.sku}</div>}
                  </div>
                  <div className="text-right text-sm whitespace-nowrap">
                    {li.price ? (
                      <>
                        <div className="text-panel-muted text-xs">{fmt(li.price)} × {li.quantity}</div>
                        <div className="font-medium">{fmt(Number(li.price) * li.quantity)}</div>
                      </>
                    ) : (
                      <div className="text-panel-muted">×{li.quantity}</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Ödeme özeti */}
          <div className="card !p-0 overflow-hidden">
            <div className="px-4 py-3 border-b border-panel-border flex items-center gap-2">
              <h2 className="text-sm font-semibold">Ödeme</h2>
              <FinancialBadge status={fin.payment_status} />
              {isStorefront && (
                <span className="text-[11px] text-panel-muted ml-auto">
                  {d.raw.payment.provider} ile ödendi
                </span>
              )}
            </div>
            <div className="px-4 py-3 space-y-1.5 text-sm">
              <Row label="Ara toplam" value={fin.subtotal != null ? fmt(fin.subtotal) : '—'} />
              {Number(fin.total_discount) > 0 && (
                <Row label={`İndirim${d.raw?.discount?.code ? ` (${d.raw.discount.code})` : ''}`}
                  value={`−${fmt(fin.total_discount)}`} cls="text-emerald-700" />
              )}
              <Row label="Kargo"
                value={fin.shipping != null ? (Number(fin.shipping) > 0 ? fmt(fin.shipping) : 'Ücretsiz') : '—'} />
              <div className="border-t border-panel-border pt-1.5 mt-1.5">
                <Row label={<b>Toplam</b>} value={<b>{fin.total != null ? fmt(fin.total) : '—'}</b>} />
              </div>
            </div>
            {isStorefront && <RefundBlock orderId={d.id} onDone={load} />}
          </div>

          {/* Müşteri talepleri (iade/değişim/sorun) */}
          <RequestsCard orderId={d.id} />

          {/* Zaman çizelgesi — üstte personel yorum kutusu (Shopify gibi) */}
          <div className="card">
            <h2 className="text-sm font-semibold mb-3">Zaman Akışı</h2>
            <CommentBox orderId={d.id} onSent={load} />
            <Timeline detail={d} />
          </div>
        </div>

        {/* ── Sağ kolon ── */}
        <div className="space-y-4">
          {/* Notlar — müşterinin ödeme sırasında bıraktığı not */}
          <div className="card">
            <h2 className="text-sm font-semibold mb-1.5">Notlar</h2>
            {d.note ? (
              <p className="text-xs text-amber-900 bg-amber-50 border border-amber-200 rounded-xl px-2.5 py-2 whitespace-pre-line">
                {d.note}
              </p>
            ) : (
              <p className="text-xs text-panel-muted">Müşteriden not yok</p>
            )}
          </div>

          {/* Müşteri */}
          <div className="card">
            <h2 className="text-sm font-semibold mb-2.5">Müşteri</h2>
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center text-sm font-semibold shrink-0">
                {(d.customer_name || '?').charAt(0).toUpperCase()}
              </div>
              <div className="min-w-0">
                <div className="text-sm font-medium truncate">{d.customer_name || '—'}</div>
                {d.customer_email && (
                  <Link to={`/musteriler?q=${encodeURIComponent(d.customer_email)}`}
                    className="text-xs text-panel-accent hover:underline truncate block">
                    Müşteri profili →
                  </Link>
                )}
              </div>
            </div>
            <div className="mt-2.5 pt-2.5 border-t border-panel-border space-y-1 text-xs">
              <div className="text-[10px] font-semibold uppercase tracking-wide text-panel-muted">İletişim bilgileri</div>
              {d.customer_email ? (
                <a href={`mailto:${d.customer_email}`} className="text-panel-accent hover:underline block truncate">
                  {d.customer_email}
                </a>
              ) : <span className="text-panel-muted">E-posta yok</span>}
              <div className="text-panel-muted">
                {ship.phone ? `📞 ${ship.phone}` : 'Telefon numarası girilmemiş.'}
              </div>
            </div>
          </div>

          {/* Teslimat adresi */}
          {(ship.address1 || ship.city) && (
            <div className="card">
              <h2 className="text-sm font-semibold mb-2">Teslimat Adresi</h2>
              <div className="text-xs text-panel-muted leading-relaxed">
                {ship.name && <div className="text-panel-ink font-medium">{ship.name}</div>}
                {ship.address1}<br />
                {[ship.province, ship.city, ship.zip].filter(Boolean).join(' / ')}
              </div>
            </div>
          )}

          {/* Kurumsal fatura */}
          {d.invoice && (d.invoice.company || d.invoice.tax_no) && (
            <div className="card">
              <h2 className="text-sm font-semibold mb-2">🧾 Fatura Bilgisi</h2>
              <div className="text-xs text-panel-muted leading-relaxed">
                {d.invoice.company && <div className="text-panel-ink font-medium">{d.invoice.company}</div>}
                {d.invoice.tax_office && <div>Vergi Dairesi: {d.invoice.tax_office}</div>}
                {d.invoice.tax_no && <div>VKN/TCKN: <span className="font-mono">{d.invoice.tax_no}</span></div>}
              </div>
            </div>
          )}

          {/* Kargo */}
          <div className="card">
            <h2 className="text-sm font-semibold mb-2">Kargo</h2>
            {d.kargo_info?.takip_no ? (
              <div className="text-sm space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-lg">🚚</span>
                  <div>
                    {d.kargo_info.handler_name && (
                      <div className="text-xs text-panel-muted">{d.kargo_info.handler_name}</div>
                    )}
                    {d.kargo_info.takip_url ? (
                      <a href={d.kargo_info.takip_url} target="_blank" rel="noopener noreferrer"
                        className="font-mono text-panel-accent hover:underline">
                        {d.kargo_info.takip_no}
                      </a>
                    ) : (
                      <span className="font-mono">{d.kargo_info.takip_no}</span>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-xs text-panel-muted">Henüz kargoya verilmedi.</p>
            )}
            {d.kargo_deadline && (
              <div className="mt-2 text-[11px] text-panel-muted">
                Kargo sözü: {new Date(d.kargo_deadline).toLocaleDateString('tr-TR')}
              </div>
            )}
          </div>

          {/* Üretim durumu */}
          {!d.cancelled_at && (
            <div className="card">
              <h2 className="text-sm font-semibold mb-2.5">Üretim Durumu</h2>
              <div className="flex items-center justify-between text-xs mb-1.5">
                <span className="font-medium">{STAGE_LABELS[stage]}</span>
                <span className="text-panel-muted">{stage}/9</span>
              </div>
              <div className="h-2 rounded-full bg-panel-input overflow-hidden">
                <div className="h-full rounded-full bg-panel-accent transition-all"
                  style={{ width: `${(stage / 9) * 100}%` }} />
              </div>
              <ol className="mt-3 space-y-1">
                {STAGES.map(([no, label]) => (
                  <li key={no} className={`flex items-center gap-2 text-[11px] ${
                    no <= stage ? 'text-panel-ink' : 'text-panel-muted/60'}`}>
                    <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[9px] ${
                      no < stage ? 'bg-emerald-100 text-emerald-700'
                        : no === stage ? 'bg-panel-accent text-white'
                        : 'bg-panel-input'}`}>
                      {no < stage ? '✓' : no}
                    </span>
                    {label}
                  </li>
                ))}
              </ol>
              <p className="mt-2.5 text-[10px] text-panel-muted">
                Üretim işlemleri Baskıcı Paneli'nde yürütülür.
              </p>
            </div>
          )}

          {/* Etiketler */}
          <TagsCard orderId={d.id} initial={d.tags} />
        </div>
      </div>
    </div>
  )
}

const fmt = (v) => new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY' }).format(Number(v || 0))

function Badge({ cls, children }) {
  return <span className={`text-[11px] px-2 py-0.5 rounded-full whitespace-nowrap ${cls}`}>{children}</span>
}

export function FinancialBadge({ status }) {
  const map = {
    paid: ['● Ödendi', 'bg-emerald-100 text-emerald-700'],
    refunded: ['İade Edildi', 'bg-red-100 text-red-700'],
    partially_refunded: ['Kısmi İade', 'bg-amber-100 text-amber-700'],
    pending: ['Ödeme Bekliyor', 'bg-slate-100 text-slate-600'],
  }
  const [label, cls] = map[status] || [status || 'Bilinmiyor', 'bg-slate-100 text-slate-600']
  return <Badge cls={cls}>{label}</Badge>
}

function Row({ label, value, cls = '' }) {
  return (
    <div className={`flex justify-between ${cls}`}>
      <span className="text-panel-muted">{label}</span>
      <span className="tabular-nums">{value}</span>
    </div>
  )
}

// Zaman çizelgesi — sipariş oluşturma + durum geçmişi, en yeni üstte.
function Timeline({ detail }) {
  const events = [
    ...(detail.status_history || []).map(h => ({
      at: h.created_at,
      who: h.created_by,
      // Personel yorumu: metnin kendisi olay olarak gösterilir (Shopify gibi)
      comment: h.action === 'not',
      text: h.action === 'not'
        ? h.note
        : h.action === 'stage_change' && h.to_label
          ? `Aşama: ${h.from_label ? h.from_label + ' → ' : ''}${h.to_label}`
          : (ACTION_LABELS[h.action] || h.action),
      note: h.action === 'not' ? null : h.note,
    })),
    detail.created_at_platform && {
      at: detail.created_at_platform,
      who: null,
      text: 'Sipariş oluşturuldu',
      note: detail.raw?.payment
        ? `${detail.raw.payment.provider} ile ${fmt(detail.raw.payment.amount)} ödendi`
        : null,
    },
  ].filter(Boolean).sort((a, b) => new Date(b.at || 0) - new Date(a.at || 0))

  if (events.length === 0) {
    return <p className="text-xs text-panel-muted">Henüz kayıt yok.</p>
  }
  return (
    <ol className="relative border-l border-panel-border ml-1.5 space-y-4">
      {events.map((e, i) => (
        <li key={i} className="ml-4">
          <span className="absolute -left-[5px] mt-1 w-2.5 h-2.5 rounded-full bg-panel-accent/70 border-2 border-white" />
          {e.comment ? (
            <div className="text-sm bg-panel-input/70 border border-panel-border rounded-xl px-3 py-2 whitespace-pre-line">
              💬 {e.text}
            </div>
          ) : (
            <div className="text-sm">{e.text}</div>
          )}
          {e.note && <div className="text-xs text-panel-muted mt-0.5">{e.note}</div>}
          <div className="text-[11px] text-panel-muted mt-0.5">
            {e.at && new Date(e.at).toLocaleString('tr-TR', {
              day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
            })}
            {e.who && ` · ${e.who}`}
          </div>
        </li>
      ))}
    </ol>
  )
}

// Personel yorumu — zaman akışına düşer, yalnızca panelde görünür.
function CommentBox({ orderId, onSent }) {
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const send = async () => {
    const msg = text.trim()
    if (!msg) return
    setBusy(true); setError('')
    try {
      await api.post(`/api/orders/${orderId}/comment`, { message: msg })
      setText('')
      onSent?.()
    } catch (e) {
      setError(typeof e?.detail === 'string' ? e.detail : 'Yorum gönderilemedi')
    } finally { setBusy(false) }
  }

  return (
    <div className="mb-4">
      <div className="flex gap-2">
        <input className="input !py-2 text-sm" value={text} maxLength={2000}
          placeholder="Yorum yazın…"
          onChange={e => setText(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }} />
        <button onClick={send} disabled={busy || !text.trim()}
          className="btn-primary !py-2 text-xs whitespace-nowrap">
          {busy ? '…' : 'Gönder'}
        </button>
      </div>
      {error && <p className="text-xs text-red-600 mt-1">{error}</p>}
      <p className="text-[10px] text-panel-muted mt-1 text-right">
        Yorumları yalnızca siz ve diğer personel görebilir.
      </p>
    </div>
  )
}

// Etiketler — virgüllü Order.tags; ekle/çıkar anında kaydedilir.
function TagsCard({ orderId, initial }) {
  const [tags, setTags] = useState(() =>
    (initial || '').split(',').map(t => t.trim()).filter(Boolean))
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const persist = async (next) => {
    setBusy(true); setError('')
    try {
      const r = await api.put(`/api/orders/${orderId}/tags`, { tags: next })
      setTags((r.tags || '').split(',').map(t => t.trim()).filter(Boolean))
    } catch {
      setError('Etiketler kaydedilemedi')
    } finally { setBusy(false) }
  }

  const add = () => {
    const t = draft.trim()
    if (!t) return
    setDraft('')
    if (tags.some(x => x.toLowerCase() === t.toLowerCase())) return
    persist([...tags, t])
  }

  return (
    <div className="card">
      <h2 className="text-sm font-semibold mb-2">Etiketler</h2>
      <input className="input !py-1.5 text-xs" value={draft} maxLength={40}
        placeholder="Etiket yazıp Enter'a basın" disabled={busy}
        onChange={e => setDraft(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); add() } }} />
      {tags.length > 0 && (
        <div className="flex gap-1.5 flex-wrap mt-2">
          {tags.map(t => (
            <span key={t} className="inline-flex items-center gap-1 text-[11px] bg-panel-input
              border border-panel-border rounded-full px-2 py-0.5">
              {t}
              <button onClick={() => persist(tags.filter(x => x !== t))} disabled={busy}
                className="text-panel-muted hover:text-red-600">×</button>
            </span>
          ))}
        </div>
      )}
      {error && <p className="text-xs text-red-600 mt-1.5">{error}</p>}
    </div>
  )
}

// Para iadesi — ödeme kartının alt bölümü (yalnızca vitrin siparişleri).
function RefundBlock({ orderId, onDone }) {
  const [info, setInfo] = useState(null)
  const [amount, setAmount] = useState('')
  const [reason, setReason] = useState('')
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)
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
      await load(); onDone?.()
    } catch (e) {
      setMsg({ ok: false, text: typeof e?.detail === 'string' ? e.detail : 'İade başarısız' })
    } finally { setBusy(false) }
  }

  return (
    <div className="px-4 py-3 border-t border-panel-border bg-panel-input/40">
      {info.refunds.length > 0 && (
        <div className="space-y-1 mb-2">
          {info.refunds.map(r => (
            <div key={r.id} className="text-[11px] flex justify-between">
              <span className={r.status === 'succeeded' ? 'text-emerald-700' : 'text-red-600'}>
                {r.status === 'succeeded' ? '✓ İade' : '✗ Başarısız iade'}: {r.amount} ₺
                {r.reason && <span className="text-panel-muted"> — {r.reason}</span>}
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
          <div className="flex items-center gap-2">
            <input type="number" step="0.01" min="0.01" max={refundable} value={amount}
              onChange={e => setAmount(e.target.value)}
              className="input !py-1.5 !w-32 text-xs" />
            <input value={reason} onChange={e => setReason(e.target.value)} maxLength={500}
              placeholder="Sebep (ops.)" className="input !py-1.5 text-xs flex-1" />
            <button onClick={() => {
              const n = Number(amount)
              if (!n || n <= 0 || n > refundable) { setMsg({ ok: false, text: `Tutar 0 ile ${refundable} arasında olmalı` }); return }
              setConfirming(true)
            }} className="px-3 py-1.5 rounded-xl text-xs bg-white border border-red-200 text-red-700 whitespace-nowrap hover:bg-red-50">
              İade Et
            </button>
          </div>
        ) : (
          <div className="bg-red-50 border border-red-200 rounded-xl p-2.5 flex items-center gap-3">
            <p className="text-xs text-red-700 flex-1">
              <b>{Number(amount).toFixed(2)} ₺</b> müşteriye iade edilecek. Geri alınamaz.
            </p>
            <button onClick={doRefund} disabled={busy}
              className="px-3 py-1.5 rounded-xl text-xs bg-red-600 text-white disabled:opacity-50 whitespace-nowrap">
              {busy ? 'İade ediliyor…' : 'Onaylıyorum'}
            </button>
            <button onClick={() => setConfirming(false)} disabled={busy}
              className="text-xs text-panel-muted">Vazgeç</button>
          </div>
        )
      ) : (
        <p className="text-[11px] text-panel-muted italic">Tutarın tamamı iade edildi.</p>
      )}
    </div>
  )
}

// Yüklenirken iskelet — boş beyaz ekran yerine düzenin silueti.
function SkeletonDetail() {
  const sk = 'animate-pulse bg-panel-input rounded-xl'
  return (
    <div className="max-w-5xl space-y-4">
      <div className={`${sk} h-10 w-64`} />
      <div className="grid lg:grid-cols-[1fr_320px] gap-4">
        <div className="space-y-4">
          <div className={`${sk} h-44`} />
          <div className={`${sk} h-36`} />
          <div className={`${sk} h-40`} />
        </div>
        <div className="space-y-4">
          <div className={`${sk} h-24`} />
          <div className={`${sk} h-28`} />
          <div className={`${sk} h-52`} />
        </div>
      </div>
    </div>
  )
}

// Müşteri talepleri — vitrindeki takip sayfasından gelen iade/değişim/sorun
// kayıtları; çözülünce işaretlenir.
const REQ_LABELS = { iade: ['İade', 'bg-red-50 text-red-700'],
  degisim: ['Değişim', 'bg-amber-50 text-amber-700'],
  sorun: ['Sorun', 'bg-sky-50 text-sky-700'] }

function RequestsCard({ orderId }) {
  const [reqs, setReqs] = useState(null)
  const [busyId, setBusyId] = useState(null)

  const load = useCallback(() => {
    api.get(`/api/orders/${orderId}/requests`)
      .then(d => setReqs(d.requests || []))
      .catch(() => setReqs([]))
  }, [orderId])
  useEffect(() => { load() }, [load])

  const resolve = async (id) => {
    setBusyId(id)
    try { await api.post(`/api/orders/requests/${id}/resolve`, {}); load() }
    finally { setBusyId(null) }
  }

  if (!reqs || reqs.length === 0) return null
  const open = reqs.filter(r => r.status === 'acik').length

  return (
    <div className="card border-amber-200">
      <h2 className="text-sm font-semibold mb-3">
        📨 Müşteri Talepleri {open > 0 && <span className="text-amber-600">({open} açık)</span>}
      </h2>
      <div className="space-y-2.5">
        {reqs.map(r => {
          const [label, cls] = REQ_LABELS[r.request_type] || [r.request_type, 'bg-slate-100 text-slate-600']
          return (
            <div key={r.id} className={`rounded-xl border p-3 text-sm ${
              r.status === 'acik' ? 'border-amber-200 bg-amber-50/40' : 'border-panel-border opacity-70'}`}>
              <div className="flex items-center gap-2">
                <span className={`text-[11px] px-2 py-0.5 rounded-full ${cls}`}>{label}</span>
                <span className="text-xs text-panel-muted">
                  {r.created_at && new Date(r.created_at).toLocaleString('tr-TR', {
                    day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                </span>
                {r.status === 'acik' ? (
                  <button onClick={() => resolve(r.id)} disabled={busyId === r.id}
                    className="ml-auto btn-ghost !py-0.5 text-xs">
                    {busyId === r.id ? '…' : '✓ Çözüldü işaretle'}
                  </button>
                ) : (
                  <span className="ml-auto text-xs text-emerald-700">✓ Çözüldü</span>
                )}
              </div>
              <p className="mt-1.5 text-panel-ink whitespace-pre-line">{r.message}</p>
            </div>
          )
        })}
      </div>
    </div>
  )
}
