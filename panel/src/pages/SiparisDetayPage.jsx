import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, fetchYetkili } from '../lib/api'
import { mutlak } from '../lib/taban'

// Katalog ürün kimliği (UUID) — Shopify'dan kalan sayısal kimliklerden ayırır
const URUN_KIMLIGI = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

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
  duzenlendi: 'sipariş düzenlendi',
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

  if (error) return <p className="text-sm text-red-300">{error}</p>
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
              ? <Badge cls="bg-red-500/10 text-red-300">İptal Edildi</Badge>
              : <Badge cls="bg-indigo-500/10 text-indigo-300">{STAGE_LABELS[stage] || '—'}</Badge>}
            {d.is_acil && <Badge cls="bg-amber-500/10 text-amber-300">⚡ Acil</Badge>}
          </div>
          <div className="text-xs text-panel-muted mt-0.5">
            {d.created_at_platform && new Date(d.created_at_platform).toLocaleString('tr-TR', {
              day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit',
            })}
            {d.store_name && ` · ${d.store_name}`}
          </div>
        </div>
        {/* Üst aksiyonlar (Shopify: Para iadesi yap sağ üstte) */}
        {isStorefront && fin.payment_status === 'paid' && (
          <button onClick={() => document.getElementById('iade-blok')
              ?.scrollIntoView({ behavior: 'smooth', block: 'center' })}
            className="ml-auto btn-ghost !py-1.5 text-xs">
            ↩️ Para İadesi Yap
          </button>
        )}
      </div>

      <div className="grid lg:grid-cols-[1fr_320px] gap-4 items-start">
        {/* ── Sol kolon ── */}
        <div className="space-y-4 min-w-0">
          {/* Ürünler — vitrin siparişi kargolanmadıysa düzenlenebilir */}
          <ItemsCard d={d} isStorefront={isStorefront} stage={stage} onChanged={load} />

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
                  value={`−${fmt(fin.total_discount)}`} cls="text-emerald-300" />
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
              <p className="text-xs text-amber-300 bg-amber-500/10 border border-amber-500/30 rounded-xl px-2.5 py-2 whitespace-pre-line">
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
              <div className="w-9 h-9 rounded-full bg-emerald-500/10 text-emerald-300 flex items-center justify-center text-sm font-semibold shrink-0">
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

          {/* Kurumsal fatura + e-fatura durumu (entegratör geri yazar) */}
          {((d.invoice && (d.invoice.company || d.invoice.tax_no)) || d.fatura_durum) && (
            <div className="card">
              <h2 className="text-sm font-semibold mb-2">🧾 Fatura</h2>
              {d.invoice && (d.invoice.company || d.invoice.tax_no) && (
                <div className="text-xs text-panel-muted leading-relaxed">
                  {d.invoice.company && <div className="text-panel-ink font-medium">{d.invoice.company}</div>}
                  {d.invoice.tax_office && <div>Vergi Dairesi: {d.invoice.tax_office}</div>}
                  {d.invoice.tax_no && <div>VKN/TCKN: <span className="font-mono">{d.invoice.tax_no}</span></div>}
                </div>
              )}
              <FaturaDurumu d={d} />
            </div>
          )}

          {/* Kargo — kısmi gönderiler dahil */}
          <ShippingCard d={d} onChanged={load} />

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
                      no < stage ? 'bg-emerald-500/10 text-emerald-300'
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
    paid: ['● Ödendi', 'bg-emerald-500/10 text-emerald-300'],
    refunded: ['İade Edildi', 'bg-red-500/10 text-red-300'],
    partially_refunded: ['Kısmi İade', 'bg-amber-500/10 text-amber-300'],
    pending: ['Ödeme Bekliyor', 'bg-white/5 text-panel-muted'],
  }
  const [label, cls] = map[status] || [status || 'Bilinmiyor', 'bg-white/5 text-panel-muted']
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

// Ürünler kartı — Shopify order editing: adet değiştir / çıkar / ekle.
// Kaydedince backend toplamları yeniden hesaplar, tahsilatla FARKI döner.
function ItemsCard({ d, isStorefront, stage, onChanged }) {
  const [editing, setEditing] = useState(false)
  const [edits, setEdits] = useState({})     // line_item_id -> {qty} | {remove:true}
  const [added, setAdded] = useState([])     // {variant_id, label, qty, price}
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)       // {ok, text}
  const [fark, setFark] = useState(null)

  const canEdit = isStorefront && !d.cancelled_at && stage < 8
  const items = d.line_items || []

  const reset = () => { setEditing(false); setEdits({}); setAdded([]); setMsg(null) }

  const save = async () => {
    const changes = []
    for (const [id, e] of Object.entries(edits)) {
      if (e.remove) changes.push({ op: 'remove', line_item_id: id })
      else if (e.qty != null) changes.push({ op: 'set_qty', line_item_id: id, quantity: e.qty })
    }
    for (const a of added) changes.push({ op: 'add', variant_id: a.variant_id, quantity: a.qty })
    if (changes.length === 0) { reset(); return }
    setBusy(true); setMsg(null)
    try {
      const r = await api.post(`/api/orders/${d.id}/edit-items`, { changes })
      setFark(Number(r.fark))
      setMsg({ ok: true, text: `Sipariş güncellendi — yeni toplam ${fmt(r.yeni_toplam)}` })
      setEditing(false); setEdits({}); setAdded([])
      onChanged()
    } catch (e) {
      setMsg({ ok: false, text: typeof e?.detail === 'string' ? e.detail : 'Güncellenemedi' })
    } finally { setBusy(false) }
  }

  return (
    <div className="card !p-0 overflow-hidden">
      <div className="px-4 py-3 border-b border-panel-border flex items-center gap-2">
        <h2 className="text-sm font-semibold">
          Ürünler <span className="text-panel-muted font-normal">({items.length})</span>
        </h2>
        {canEdit && !editing && (
          <button onClick={() => setEditing(true)}
            className="ml-auto btn-ghost !py-1 text-xs">✏️ Düzenle</button>
        )}
        {editing && (
          <span className="ml-auto flex gap-1.5">
            <button onClick={reset} className="btn-ghost !py-1 text-xs">Vazgeç</button>
            <button onClick={save} disabled={busy}
              className="btn-primary !py-1 !px-3 text-xs">
              {busy ? '…' : 'Kaydet'}
            </button>
          </span>
        )}
      </div>
      <div className="divide-y divide-panel-border">
        {items.map(li => {
          const e = edits[li.id] || {}
          const qty = e.qty ?? li.quantity
          if (e.remove) {
            return (
              <div key={li.id} className="flex items-center gap-3 px-4 py-2 opacity-50">
                <span className="text-xs line-through flex-1 truncate">{li.title}</span>
                <button onClick={() => setEdits(x => { const n = { ...x }; delete n[li.id]; return n })}
                  className="text-xs underline text-panel-muted">geri al</button>
              </div>
            )
          }
          // Vitrin ürünü ise (katalog kimliği UUID) ürün detayına gidilir.
          // Eski Shopify siparişlerinde kimlik Shopify'ındır — bağlantı yok.
          const urunYolu = URUN_KIMLIGI.test(String(li.product_id || '')) ? `/urunler/${li.product_id}` : null
          const gorsel = li.image_url ? (
            <img src={li.image_url} alt="" className="w-full h-full object-cover" />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-xl opacity-30">📱</div>
          )
          const kutu = 'w-14 h-14 rounded-xl bg-panel-input overflow-hidden shrink-0 border border-panel-border'
          return (
            <div key={li.id} className="flex items-center gap-3 px-4 py-3">
              {urunYolu
                ? <Link to={urunYolu} title="Ürün detayına git"
                    className={`${kutu} block hover:border-panel-accent transition-colors`}>{gorsel}</Link>
                : <div className={kutu}>{gorsel}</div>}
              <div className="flex-1 min-w-0">
                {urunYolu
                  ? <Link to={urunYolu} title="Ürün detayına git"
                      className="block text-sm font-medium truncate hover:text-panel-accent hover:underline">{li.title}</Link>
                  : <div className="text-sm font-medium truncate">{li.title}</div>}
                {li.variant_title && (
                  <div className="text-xs text-panel-muted">{li.variant_title}</div>
                )}
                {li.sku && <div className="text-[10px] text-panel-muted font-mono">{li.sku}</div>}
                <TasarimKarti li={li} />
              </div>
              {editing ? (
                <div className="flex items-center gap-1.5">
                  <button onClick={() => setEdits(x => ({ ...x, [li.id]: { qty: Math.max(1, qty - 1) } }))}
                    className="w-6 h-6 rounded-lg border border-panel-border text-xs">−</button>
                  <span className="w-6 text-center text-sm tabular-nums">{qty}</span>
                  <button onClick={() => setEdits(x => ({ ...x, [li.id]: { qty: Math.min(20, qty + 1) } }))}
                    className="w-6 h-6 rounded-lg border border-panel-border text-xs">+</button>
                  <button onClick={() => setEdits(x => ({ ...x, [li.id]: { remove: true } }))}
                    title="Kalemi çıkar"
                    className="w-6 h-6 rounded-lg text-xs text-red-300 hover:text-red-300">×</button>
                </div>
              ) : (
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
              )}
            </div>
          )
        })}
        {added.map((a, i) => (
          <div key={`add-${i}`} className="flex items-center gap-3 px-4 py-2 bg-emerald-500/10">
            <span className="text-xs text-emerald-300 flex-1 truncate">+ {a.label} ×{a.qty}</span>
            <span className="text-xs text-emerald-300">{fmt(a.price * a.qty)}</span>
            <button onClick={() => setAdded(x => x.filter((_, j) => j !== i))}
              className="text-xs text-red-300">×</button>
          </div>
        ))}
      </div>
      {editing && <AddItemRow storeId={d.store_id} onAdd={a => setAdded(x => [...x, a])} />}
      {msg && (
        <div className={`px-4 py-2.5 text-xs border-t border-panel-border ${
          msg.ok ? 'text-emerald-300' : 'text-red-300'}`}>
          {msg.text}
          {msg.ok && fark != null && fark !== 0 && (
            <span className="block mt-1 text-amber-300">
              {fark < 0
                ? `İade önerilir: ${fmt(Math.abs(fark))} — aşağıdaki Para İadesi bölümünü kullanın.`
                : `Ek tahsilat gerekir: ${fmt(fark)} — Siparişler → "Sipariş Oluştur" ile fark için ödeme linki gönderin.`}
            </span>
          )}
        </div>
      )}
    </div>
  )
}

// Düzenleme modunda katalogdan kalem ekleme satırı.
function AddItemRow({ storeId, onAdd }) {
  const [products, setProducts] = useState([])
  const [productId, setProductId] = useState('')
  const [detail, setDetail] = useState(null)
  const [variantId, setVariantId] = useState('')
  const [qty, setQty] = useState(1)

  useEffect(() => {
    api.get(`/api/catalog/products?store_id=${storeId}&status=active&slim=1`)
      .then(setProducts).catch(() => {})
  }, [storeId])
  useEffect(() => {
    if (!productId) { setDetail(null); return }
    api.get(`/api/catalog/products/${productId}`).then(setDetail).catch(() => {})
    setVariantId('')
  }, [productId])

  const add = () => {
    const v = detail?.variants?.find(x => x.id === variantId)
    if (!detail || !v) return
    onAdd({
      variant_id: v.id, qty,
      label: `${detail.title} (${v.model_display}${v.variation ? ` / ${v.variation}` : ''})`,
      price: Number(v.price_override ?? detail.base_price),
    })
    setProductId(''); setVariantId(''); setQty(1)
  }

  return (
    <div className="px-4 py-2.5 border-t border-panel-border flex gap-1.5 items-center flex-wrap">
      <select className="input !py-1.5 text-xs flex-1 min-w-40" value={productId}
        onChange={e => setProductId(e.target.value)}>
        <option value="">+ Ürün ekle…</option>
        {products.map(p => <option key={p.id} value={p.id}>{p.title}</option>)}
      </select>
      {detail && (
        <select className="input !py-1.5 text-xs !w-44" value={variantId}
          onChange={e => setVariantId(e.target.value)}>
          <option value="">Model seçin…</option>
          {(detail.variants || []).filter(v => v.is_active).map(v => (
            <option key={v.id} value={v.id}>
              {v.model_display}{v.variation ? ` / ${v.variation}` : ''}
            </option>
          ))}
        </select>
      )}
      {variantId && (
        <>
          <input type="number" min="1" max="20" value={qty}
            onChange={e => setQty(Math.max(1, Math.min(20, Number(e.target.value) || 1)))}
            className="input !py-1.5 text-xs !w-16" />
          <button onClick={add} className="btn-ghost !py-1.5 text-xs">Ekle</button>
        </>
      )}
    </div>
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
      {error && <p className="text-xs text-red-300 mt-1">{error}</p>}
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
                className="text-panel-muted hover:text-red-300">×</button>
            </span>
          ))}
        </div>
      )}
      {error && <p className="text-xs text-red-300 mt-1.5">{error}</p>}
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
    <div id="iade-blok" className="px-4 py-3 border-t border-panel-border bg-panel-input/40">
      <div className="text-xs font-semibold mb-2">↩️ Para İadesi</div>
      {info.refunds.length > 0 && (
        <div className="space-y-1 mb-2">
          {info.refunds.map(r => (
            <div key={r.id} className="text-[11px] flex justify-between">
              <span className={r.status === 'succeeded' ? 'text-emerald-300' : 'text-red-300'}>
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
      {msg && <p className={`text-xs mb-2 ${msg.ok ? 'text-emerald-300' : 'text-red-300'}`}>{msg.text}</p>}

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
            }} className="px-3 py-1.5 rounded-xl text-xs bg-panel-card border border-red-500/30 text-red-300 whitespace-nowrap hover:bg-red-500/10">
              İade Et
            </button>
          </div>
        ) : (
          <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-2.5 flex items-center gap-3">
            <p className="text-xs text-red-300 flex-1">
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
        <p className="text-[11px] text-panel-muted italic">
          {info.refunds.length > 0
            ? 'Tutarın tamamı iade edildi.'
            : 'İade edilebilir tutar yok — ödeme henüz tamamlanmamış olabilir.'}
        </p>
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
const REQ_LABELS = { iade: ['İade', 'bg-red-500/10 text-red-300'],
  degisim: ['Değişim', 'bg-amber-500/10 text-amber-300'],
  sorun: ['Sorun', 'bg-sky-500/10 text-sky-300'] }

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
    <div className="card border-amber-500/30">
      <h2 className="text-sm font-semibold mb-3">
        📨 Müşteri Talepleri {open > 0 && <span className="text-amber-300">({open} açık)</span>}
      </h2>
      <div className="space-y-2.5">
        {reqs.map(r => {
          const [label, cls] = REQ_LABELS[r.request_type] || [r.request_type, 'bg-white/5 text-panel-muted']
          return (
            <div key={r.id} className={`rounded-xl border p-3 text-sm ${
              r.status === 'acik' ? 'border-amber-500/30 bg-amber-500/10' : 'border-panel-border opacity-70'}`}>
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
                  <span className="ml-auto text-xs text-emerald-300">✓ Çözüldü</span>
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

// ─── Kargo kartı — kısmi kargolama (Shopify fulfillment) ───────
// Sipariş tek seferde de, parça parça da gönderilebilir. Kalan adet
// sunucuda hesaplanır; buradaki adetler yalnızca öneridir, sunucu doğrular.
function ShippingCard({ d, onChanged }) {
  const [acik, setAcik] = useState(false)
  const sh = d.shipping || { shipments: [], remaining: {}, fully_shipped: false }
  const bekleyen = (d.line_items || [])
    .map(li => ({ ...li, kalan: sh.remaining?.[li.id] ?? li.quantity }))
    .filter(li => li.kalan > 0)
  const ki = d.kargo_info || {}

  const geriAl = async (sid) => {
    if (!window.confirm('Bu gönderi kaydı silinecek, ürünler tekrar "bekliyor" olacak. Emin misiniz?')) return
    try { await api.del(`/api/orders/${d.id}/shipments/${sid}`); onChanged() }
    catch { window.alert('Gönderi geri alınamadı') }
  }

  return (
    <div className="card">
      <div className="flex items-center gap-2 mb-2">
        <h2 className="text-sm font-semibold">Kargo</h2>
        {sh.partial && <Badge cls="bg-amber-500/10 text-amber-300">Kısmi</Badge>}
        {sh.fully_shipped && <Badge cls="bg-emerald-500/10 text-emerald-300">Tümü gönderildi</Badge>}
      </div>

      {/* Gönderiler */}
      {sh.shipments?.length > 0 ? (
        <div className="space-y-2">
          {sh.shipments.map((s, i) => (
            <div key={s.id} className="text-xs border border-panel-border rounded-xl px-2.5 py-2">
              <div className="flex items-center gap-2">
                <span>🚚</span>
                <div className="min-w-0 flex-1">
                  <div className="text-panel-muted">
                    {i + 1}. gönderi{s.kargo_firma ? ` · ${s.kargo_firma}` : ''}
                    {s.created_at && ` · ${new Date(s.created_at).toLocaleDateString('tr-TR')}`}
                  </div>
                  {s.takip_no && (
                    s.takip_url
                      ? <a href={s.takip_url} target="_blank" rel="noopener noreferrer"
                          className="font-mono text-panel-accent hover:underline">{s.takip_no}</a>
                      : <span className="font-mono">{s.takip_no}</span>
                  )}
                </div>
                <button onClick={() => geriAl(s.id)}
                  className="text-panel-muted hover:text-red-300 text-[11px]">geri al</button>
              </div>
              <ul className="mt-1 text-panel-muted space-y-0.5">
                {(s.items || []).map((it, j) => (
                  <li key={j} className="truncate">
                    · {it.title}{it.variant_title ? ` — ${it.variant_title}` : ''} × {it.quantity}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      ) : ki.takip_no ? (
        <div className="text-sm flex items-center gap-2">
          <span className="text-lg">🚚</span>
          <div>
            {ki.handler_name && <div className="text-xs text-panel-muted">{ki.handler_name}</div>}
            {ki.takip_url
              ? <a href={ki.takip_url} target="_blank" rel="noopener noreferrer"
                  className="font-mono text-panel-accent hover:underline">{ki.takip_no}</a>
              : <span className="font-mono">{ki.takip_no}</span>}
          </div>
        </div>
      ) : (
        <p className="text-xs text-panel-muted">Henüz kargoya verilmedi.</p>
      )}

      {bekleyen.length > 0 && !d.cancelled_at && (
        <>
          <div className="mt-2.5 pt-2.5 border-t border-panel-border text-xs text-panel-muted">
            Bekleyen: {bekleyen.map(li => `${li.title} × ${li.kalan}`).join(' · ')}
          </div>
          <button onClick={() => setAcik(true)} className="btn-ghost text-xs mt-2 w-full">
            📦 {sh.shipments?.length ? 'Kalanı kargola' : 'Kargola'}
          </button>
        </>
      )}

      {d.kargo_deadline && (
        <div className="mt-2 text-[11px] text-panel-muted">
          Kargo sözü: {new Date(d.kargo_deadline).toLocaleDateString('tr-TR')}
        </div>
      )}

      {acik && (
        <ShipmentModal orderId={d.id} bekleyen={bekleyen}
          onClose={() => setAcik(false)}
          onSaved={() => { setAcik(false); onChanged() }} />
      )}
    </div>
  )
}

function ShipmentModal({ orderId, bekleyen, onClose, onSaved }) {
  const [adet, setAdet] = useState(() =>
    Object.fromEntries(bekleyen.map(li => [li.id, li.kalan])))
  const [takipNo, setTakipNo] = useState('')
  const [firma, setFirma] = useState('')
  const [mail, setMail] = useState(true)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const secili = bekleyen.filter(li => Number(adet[li.id]) > 0)
  const kaydet = async (e) => {
    e.preventDefault()
    setBusy(true); setErr('')
    try {
      await api.post(`/api/orders/${orderId}/shipments`, {
        items: secili.map(li => ({ line_item_id: li.id, quantity: Number(adet[li.id]) })),
        takip_no: takipNo.trim() || null,
        kargo_firma: firma.trim() || null,
        send_email: mail,
      })
      onSaved()
    } catch (e2) {
      setErr(typeof e2?.detail === 'string' ? e2.detail : 'Kaydedilemedi')
    } finally { setBusy(false) }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="absolute inset-0 bg-black/30" />
      <form onSubmit={kaydet}
        className="relative bg-panel-card rounded-2xl shadow-xl w-full max-w-md p-4 space-y-3">
        <h3 className="text-sm font-semibold">Kargoya Ver</h3>
        <p className="text-xs text-panel-muted -mt-1.5">
          Yalnız hazır olanları gönderin; kalanlar için sonra ikinci gönderi
          oluşturabilirsiniz. Müşteri her gönderiyi ayrı takip eder.
        </p>

        <div className="space-y-1.5 max-h-56 overflow-y-auto">
          {bekleyen.map(li => (
            <div key={li.id} className="flex items-center gap-2 text-sm">
              <input type="number" min="0" max={li.kalan} value={adet[li.id]}
                onChange={e => setAdet(a => ({ ...a, [li.id]: e.target.value }))}
                className="input !py-1 !w-16 text-center" />
              <span className="text-panel-muted text-xs">/ {li.kalan}</span>
              <span className="truncate flex-1 text-xs">
                {li.title}{li.variant_title ? ` — ${li.variant_title}` : ''}
              </span>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-2">
          <label className="block text-sm">
            <span className="text-panel-muted text-xs">Takip numarası</span>
            <input className="input mt-1 font-mono" value={takipNo}
              onChange={e => setTakipNo(e.target.value)} maxLength={100} />
          </label>
          <label className="block text-sm">
            <span className="text-panel-muted text-xs">Kargo firması</span>
            <input className="input mt-1" value={firma} onChange={e => setFirma(e.target.value)}
              maxLength={100} placeholder="örn. Yurtiçi" list="kargo-firmalari" />
            <datalist id="kargo-firmalari">
              {['Yurtiçi', 'Aras', 'MNG', 'Sürat', 'PTT', 'UPS', 'Trendyol Express'].map(k =>
                <option key={k} value={k} />)}
            </datalist>
          </label>
        </div>

        <label className="flex items-center gap-2 text-xs">
          <input type="checkbox" checked={mail} onChange={e => setMail(e.target.checked)} />
          Müşteriye kargo bilgilendirme e-postası gönder
        </label>

        {err && <p className="text-sm text-red-300">{err}</p>}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="btn-ghost">Vazgeç</button>
          <button disabled={busy || secili.length === 0} className="btn-primary">
            {busy ? 'Kaydediliyor…' : `${secili.reduce((t, li) => t + Number(adet[li.id]), 0)} ürünü gönder`}
          </button>
        </div>
      </form>
    </div>
  )
}

// ─── Müşteri tasarımı kartı ───────────────────────────────────
// Tasarım stüdyosunda hazırlanan işlerde sipariş kaleminin altında görünür:
// önizleme, BASKIYA HAZIR dosya ve müşterinin yüklediği ORİJİNAL dosyalar
// (CMYK/rötuş bunlardan yapılır — önizleme baskıya gitmez).
function TasarimKarti({ li }) {
  const [d, setD] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const tasarimId = (li.properties || [])
    .find(p => p.name === 'Tasarım No')?.value

  useEffect(() => {
    if (!tasarimId) return
    api.get(`/api/case-templates/designs/${tasarimId}`)
      .then(setD).catch(() => setErr('Tasarım yüklenemedi'))
  }, [tasarimId])

  if (!tasarimId) return null
  if (err) return <div className="text-[11px] text-red-300 mt-1">{err}</div>
  if (!d) return <div className="text-[11px] text-panel-muted mt-1">Tasarım yükleniyor…</div>

  const numuneYukle = async (file) => {
    if (!file) return
    setBusy(true); setErr('')
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await fetchYetkili(mutlak(`/api/case-templates/designs/${d.id}/proof`), {
        method: 'POST', body: fd,
      })
      if (!res.ok) throw new Error()
      const r = await res.json()
      setD(x => ({ ...x, proof_url: r.proof_url }))
    } catch { setErr('Numune yüklenemedi') }
    finally { setBusy(false) }
  }

  const yenidenUret = async () => {
    setBusy(true); setErr('')
    try {
      const r = await api.post(`/api/case-templates/designs/${d.id}/render`, {})
      setD(x => ({ ...x, print_url: r.print_url, print_pdf_url: r.print_pdf_url }))
      if (r.pdf_hata) setErr(`PNG hazır ama PDF üretilemedi: ${r.pdf_hata}`)
    } catch { setErr('Baskı dosyası üretilemedi') }
    finally { setBusy(false) }
  }

  return (
    <div className="mt-2 flex gap-2.5 items-start bg-indigo-500/10 border border-indigo-500/30 rounded-xl p-2">
      {(d.proof_url || d.preview_url) && (
        <a href={d.proof_url || d.preview_url} target="_blank" rel="noopener noreferrer" className="shrink-0">
          <img src={d.proof_url || d.preview_url} alt={d.name}
            className="w-12 rounded-lg border border-indigo-500/30 bg-white" />
        </a>
      )}
      <div className="min-w-0 flex-1 text-[11px]">
        <div className="font-medium text-indigo-300">🎨 {d.name}</div>
        <div className="text-panel-muted">
          {d.template} · {d.layer_count} katman
          {d.proof_url
            ? <span className="text-emerald-300"> · numune hazır ✓</span>
            : <span className="text-amber-300"> · numune yüklenmedi</span>}
          {d.print_size && ` · ${d.print_size.mm} @ ${d.print_size.dpi} DPI`}
        </div>
        <div className="flex gap-2 flex-wrap mt-1">
          {d.print_url ? (
            <a href={d.print_url} download className="text-indigo-300 underline"
              title="Ekrandakiyle birebir raster dosya (RGB)">
              ⬇ PNG{d.print_size ? ` (${d.print_size.px_w}×${d.print_size.px_h})` : ''}
            </a>
          ) : (
            <span className="text-amber-300">Baskı dosyası yok</span>
          )}
          {d.print_pdf_url && (
            <a href={d.print_pdf_url} download className="text-indigo-300 underline"
              title="Matbaa/RIP için: yazılar vektörel, renkler CMYK, gerçek mm ölçüsünde">
              ⬇ PDF (vektörel · CMYK)
            </a>
          )}
          <button onClick={yenidenUret} disabled={busy} className="text-panel-muted underline">
            {busy ? 'üretiliyor…' : 'yeniden üret'}
          </button>
          <label className="text-panel-muted underline cursor-pointer">
            {d.proof_url ? '🔄 numuneyi değiştir' : '📤 numune yükle'}
            <input type="file" accept="image/*" className="hidden"
              onChange={e => numuneYukle(e.target.files?.[0])} />
          </label>
          {(d.assets || []).map((a, i) => (
            <a key={a.id} href={a.original_url} download className="text-panel-muted underline"
              title={`${a.width}×${a.height} px${a.filename ? ` · ${a.filename}` : ''}`}>
              ⬇ orijinal {(d.assets.length > 1 ? i + 1 : '')}
            </a>
          ))}
        </div>
      </div>
    </div>
  )
}


// e-Fatura durumu — faturayı entegratör keser, sonucu entegrasyon API'sinden
// geri yazar (backend/app/routers/entegrasyon.py). Panel yalnız gösterir.
function FaturaDurumu({ d }) {
  if (!d.fatura_durum) {
    return (
      <p className="text-[11px] text-panel-muted mt-2">
        e-Fatura henüz kesilmedi — entegratör siparişi çektiğinde burada görünür.
      </p>
    )
  }
  const f = d.fatura || {}
  const stil = {
    kesildi: 'bg-emerald-500/10 text-emerald-300',
    beklemede: 'bg-amber-500/10 text-amber-300',
    hata: 'bg-red-500/10 text-red-300',
    iptal: 'bg-white/5 text-panel-muted',
  }[d.fatura_durum] || 'bg-white/5 text-panel-muted'
  const etiket = { kesildi: 'Fatura kesildi', beklemede: 'Sırada',
                   hata: 'Hata', iptal: 'İptal' }[d.fatura_durum] || d.fatura_durum
  return (
    <div className="mt-2 space-y-1 text-xs">
      <div className="flex items-center gap-2">
        <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${stil}`}>{etiket}</span>
        {f.no && <span className="font-mono text-panel-ink">{f.no}</span>}
        {f.kaynak && <span className="text-[11px] text-panel-muted">· {f.kaynak}</span>}
      </div>
      {f.ettn && <div className="text-[11px] text-panel-muted font-mono">ETTN: {f.ettn}</div>}
      {f.hata && <div className="text-[11px] text-red-300">{f.hata}</div>}
      {f.pdf_url && (
        <a href={f.pdf_url} target="_blank" rel="noreferrer"
          className="text-[11px] text-panel-accent underline">Faturayı aç (PDF)</a>
      )}
    </div>
  )
}
