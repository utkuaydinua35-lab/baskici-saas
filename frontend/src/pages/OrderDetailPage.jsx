import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { api } from '../lib/api'
import { useToast } from '../components/Toast'
import { AddOrderItemsDialog } from './DealersPage'
import { usePhoneModels } from '../lib/phoneModels'


/** Line item'tan telefon modelini çıkar.
 * Öncelik: device_model_override > properties (Marka + Model birlikte) > variant_title.
 * Properties pattern: [{name: 'Marka', value: 'Samsung'}, {name: 'Samsung Model', value: 'Galaxy A21S'}]
 */
function resolveDeviceModel(item) {
  if (item.device_model_override) return item.device_model_override
  const props = item.properties || []
  // 1) Direkt 'Model' / 'Telefon Modeli' property'si
  const direct = props.find(p => {
    const n = (p?.name || '').toLowerCase()
    return n === 'model' || n === 'telefon modeli' || n === 'cihaz modeli'
  })
  if (direct?.value) return direct.value
  // 2) Marka + '{Marka} Model' kombinasyonu
  const marka = props.find(p => (p?.name || '').toLowerCase() === 'marka')?.value
  if (marka) {
    const markaModel = props.find(p => {
      const n = (p?.name || '').toLowerCase()
      return n === `${marka.toLowerCase()} model` || n.endsWith(' model')
    })?.value
    if (markaModel) return `${marka} ${markaModel}`
  }
  // 3) Variant title (örn 'iPhone 13 / Siyah')
  if (item.variant_title) {
    const part = item.variant_title.split('/')[0].trim()
    if (part) return part
  }
  return null
}

/** Couple ürünlerde 2. telefon modeli (örn 'Apple Model copy' / 'Model 2').
 * Sadece 2. bir model kaydı varsa döner, yoksa null. */
function resolveSecondModel(item) {
  if (item.device_model_override_2) return item.device_model_override_2
  const props = item.properties || []
  const marka = props.find(p => (p?.name || '').toLowerCase() === 'mark' || (p?.name || '').toLowerCase() === 'marka 2')?.value
  const second = props.find(p => {
    const n = (p?.name || '').toLowerCase()
    return n.includes('model') && (n.endsWith('copy') || n.includes('copy') || n.endsWith(' 2') || n.endsWith('2'))
  })?.value
  if (second) return marka ? `${marka} ${second}` : second
  return null
}

export default function OrderDetailPage() {
  const { orderId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const toast = useToast()

  const [detail, setDetail] = useState(null)
  const [stages, setStages] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [rightTab, setRightTab] = useState('musteri')
  const [emailOpen, setEmailOpen] = useState(false)
  const [addDealer, setAddDealer] = useState(null)  // AddOrderItemsDialog için bayii objesi
  const [lightbox, setLightbox] = useState(null)  // büyütülen görsel url
  const [neighbors, setNeighbors] = useState({ prev: null, next: null })

  // Komsu siparisleri (onceki/sonraki) ayni filtreyle hesapla
  useEffect(() => {
    const sid = localStorage.getItem('orders_store_id') || ''
    const tb = localStorage.getItem('orders_tab') || 'tumu'
    const params = new URLSearchParams({ page: 1, per_page: 200, tab: tb })
    if (sid) params.set('store_id', sid)
    api.get(`/api/orders?${params}`).then(r => {
      const ids = (r.items || []).map(o => o.id)
      const idx = ids.indexOf(orderId)
      if (idx === -1) { setNeighbors({ prev: null, next: null }); return }
      // Liste en yeni -> eski sirali. "next/sonraki" = listede asagi (daha eski), "prev/onceki" = yukari (daha yeni)
      setNeighbors({
        prev: idx > 0 ? ids[idx - 1] : null,
        next: idx < ids.length - 1 ? ids[idx + 1] : null,
      })
    }).catch(() => setNeighbors({ prev: null, next: null }))
  }, [orderId])

  // Klavye kısayolu (vim tarzı): j = sonraki sipariş, k = önceki sipariş.
  // Form alanında yazarken ya da modal/kısayol tuşlarıyla birlikte çalışmaz.
  useEffect(() => {
    const onKey = (e) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return
      const t = e.target
      const tag = (t?.tagName || '').toLowerCase()
      if (tag === 'input' || tag === 'textarea' || tag === 'select' || t?.isContentEditable) return
      const k = (e.key || '').toLowerCase()
      if (k === 'j' && neighbors.next) {
        e.preventDefault(); navigate(`/orders/${neighbors.next}`, { state: location.state })
      } else if (k === 'k' && neighbors.prev) {
        e.preventDefault(); navigate(`/orders/${neighbors.prev}`, { state: location.state })
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [neighbors, navigate, location.state])

  const load = async () => {
    try {
      const [d, st] = await Promise.all([
        api.get(`/api/orders/${orderId}/detail`),
        api.get('/api/orders/_meta/stages'),
      ])
      setDetail(d)
      setStages(st.stages || [])
    } catch (e) {
      setError(errMsg(e, 'Sipariş yüklenemedi'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [orderId])

  const patchStage = async (body) => {
    try {
      const d = await api.patch(`/api/orders/${orderId}/stage`, body)
      setDetail(d)
    } catch (e) {
      toast.error(errMsg(e, 'Durum güncellenemedi'))
    }
  }

  const patchFlags = async (body) => {
    try {
      const d = await api.patch(`/api/orders/${orderId}/flags`, body)
      setDetail(d)
    } catch (e) {
      toast.error(errMsg(e, 'Güncellenemedi'))
    }
  }

  const saveAddress = async (body) => {
    try {
      const d = await api.patch(`/api/orders/${orderId}/address`, body)
      setDetail(d)
      toast.success('Adres güncellendi')
      return true
    } catch (e) {
      toast.error(errMsg(e, 'Adres güncellenemedi'))
      return false
    }
  }

  // Bayii siparişine ürün ekle — önce bayi bilgisini (birim fiyat/mağaza) çek, dialog aç
  const openAddItems = async () => {
    if (!detail?.dealer_id) return
    try {
      const d = await api.get(`/api/dealers/${detail.dealer_id}`)
      setAddDealer(d)
    } catch (e) {
      toast.error(errMsg(e, 'Bayii bilgisi alınamadı'))
    }
  }

  const toggleKalipHaric = async () => {
    try {
      await api.patch(`/api/orders/${orderId}/kalip-haric`, { haric: !detail.kalip_haric })
      setDetail(d => ({ ...d, kalip_haric: !d.kalip_haric }))
      toast.success(detail.kalip_haric ? 'Sipariş kalıba dahil edilecek' : 'Sipariş kalıptan hariç tutuldu')
    } catch (e) {
      toast.error(errMsg(e, 'Güncellenemedi'))
    }
  }

  const patchLineItem = async (liId, body) => {
    try {
      await api.patch(`/api/orders/${orderId}/line-items/${liId}`, body)
      load()
    } catch (e) {
      toast.error(errMsg(e, 'Güncellenemedi'))
    }
  }

  const removeFromMolds = async (liId) => {
    try { await api.post(`/api/orders/${orderId}/line-items/${liId}/remove-from-molds`, {}) }
    catch (e) { toast.error(errMsg(e, 'Kalıptan çıkarılamadı')) }
  }

  const cancelKargo = async () => {
    if (!confirm('Kargo gönderisi iptal edilsin mi?\nBasit Kargo barkodu + Shopify fulfillment iptal edilir, sipariş "Paketleme" aşamasına döner.')) return
    try {
      const r = await api.post(`/api/packaging/order/${orderId}/kargo-iptal`, {})
      if (r.shopify_err) toast.info('Kargo iptal edildi · Shopify: ' + r.shopify_err)
      else toast.success('Kargo gönderisi iptal edildi')
      load()
    } catch (e) { toast.error(errMsg(e, 'Kargo iptal edilemedi')) }
  }

  const handleDuplicate = async () => {
    if (!confirm('Bu siparişi yeni bir sipariş olarak çoğalt?')) return
    try {
      const r = await api.post(`/api/orders/${orderId}/duplicate`, {})
      navigate(`/orders/${r.id}`)
    } catch (e) {
      toast.error(errMsg(e, 'Kopyalanamadı'))
    }
  }

  if (loading) {
    return <div className="text-gray-500 text-sm text-center py-16">Yükleniyor...</div>
  }
  if (error) {
    return (
      <div className="mx-auto max-w-2xl">
        <button onClick={() => navigate(location.state?.from || '/orders')} className="text-accent text-sm hover:underline mb-3">← Geri</button>
        <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{error}</div>
      </div>
    )
  }
  if (!detail) return null

  const f = detail.financial || {}
  const cur = f.currency || 'TRY'

  // Geri hedefi: NEREDEN geldiysen oraya (location.state.from). Yoksa /orders.
  const backTo = location.state?.from || '/orders'

  return (
    <div className="max-w-[1400px]">
      {/* Üst bar */}
      <div className="flex items-start justify-between mb-5 flex-wrap gap-3">
        <div className="flex items-start gap-3">
          <button onClick={() => navigate(backTo)} title="← Geri" className="text-gray-400 hover:text-gray-200 text-xl mt-0.5">←</button>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-semibold text-gray-100">Sipariş #{detail.order_number}</h1>
                <div className="flex flex-col gap-0.5">
                  <button onClick={() => neighbors.next && navigate(`/orders/${neighbors.next}`, { state: location.state })} disabled={!neighbors.next}
                    title="Sonraki sipariş (J)" className="px-2.5 py-1.5 sm:px-1.5 sm:py-0.5 rounded bg-brand-input text-gray-400 hover:text-gray-100 disabled:opacity-30 text-xs leading-none">▲</button>
                  <button onClick={() => neighbors.prev && navigate(`/orders/${neighbors.prev}`, { state: location.state })} disabled={!neighbors.prev}
                    title="Önceki sipariş (K)" className="px-2.5 py-1.5 sm:px-1.5 sm:py-0.5 rounded bg-brand-input text-gray-400 hover:text-gray-100 disabled:opacity-30 text-xs leading-none">▼</button>
                </div>
              </div>
              {detail.is_acil && <Badge color="red">⚠ ACİL</Badge>}
              {detail.is_iptal && <Badge color="gray">İPTAL</Badge>}
              {detail.kalip_haric && <Badge color="amber">🚫 KALIP DIŞI</Badge>}
              {detail.is_hatali_gonderildi && <Badge color="amber">HATALI GÖNDERİLDİ</Badge>}
              {detail.is_tedarik_bekleme && <Badge color="purple">⏸ TEDARİK BEKLİYOR</Badge>}
              {detail.approval_status === 'bekliyor' && <Badge color="amber">⏳ ONAY BEKLİYOR</Badge>}
              {detail.approval_status === 'onaylandi' && <Badge color="green">✅ ONAYLANDI</Badge>}
              {detail.approval_status === 'revizyon' && <Badge color="red">✏️ REVİZYON</Badge>}
            </div>
            <p className="text-xs text-gray-500 mt-1">{formatDate(detail.created_at_platform)}</p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <TedarikToggle
            value={detail.is_tedarik_bekleme}
            onChange={v => patchFlags({ is_tedarik_bekleme: v })}
          />
          <button onClick={toggleKalipHaric}
            className={`px-2.5 py-1 rounded text-xs font-medium border transition-colors ${detail.kalip_haric ? 'bg-amber-500/20 border-amber-500 text-amber-300' : 'bg-brand-input border-brand-border text-gray-400 hover:text-gray-200'}`}
            title="Bu siparisi kalip olusturucuya dahil etme">
            {detail.kalip_haric ? '🚫 Kalıp Dışı' : '🚫 Kalıba Dahil Etme'}
          </button>
          <IsaretleDropdown detail={detail} onFlag={patchFlags} onStage={patchStage} />
          <StatusDropdown
            stages={stages}
            current={detail.current_stage}
            isIptal={detail.is_iptal}
            onSelect={patchStage}
          />
          {detail.is_bayii && detail.dealer_id && !detail.is_iptal && (
            <button onClick={openAddItems}
              className="px-3 py-1.5 rounded-lg border border-accent/40 text-accent hover:bg-accent/10 text-sm whitespace-nowrap"
              title="Bu bayii siparişine ürün ekle (tutar + cari güncellenir)">
              + Ürün Ekle
            </button>
          )}
          <IslemlerDropdown detail={detail} onFlag={patchFlags} onDuplicate={handleDuplicate} onEmail={() => setEmailOpen(true)} />
        </div>
      </div>

      {/* KPI kartları */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
        <KpiCard label="TOPLAM" value={fmtMoney(f.total, cur)} icon="🛍" color="gray" />
        <KpiCard label="ÖDEME" value={paymentLabel(f.payment_status)} icon="💳" color="emerald" small />
        <KpiCard label="İNDİRİM" value={f.total_discount ? `-${fmtMoney(f.total_discount, cur)}` : '—'} icon="%" color="emerald" />
        <KpiCard label="KARGO" value={fmtMoney(f.shipping, cur)} icon="🚚" color="accent" />
      </div>

      {/* Pipeline */}
      <div className="card mb-5">
        <StagePipeline stages={stages} current={detail.current_stage} progress={detail.progress_percent} isIptal={detail.is_iptal} />
        {detail.barkod_kodu ? (
          <div className="mt-3 text-xs text-gray-400 flex items-center gap-2">
            <span>🏷</span> BK Barkod: <span className="font-mono text-gray-200">{detail.barkod_kodu}</span>
          </div>
        ) : (
          <div className="mt-3 text-xs text-gray-600 flex items-center gap-2">
            <span>🏷</span> Henüz BK kargo barkodu oluşturulmadı.
          </div>
        )}
        <TakipSatiri detail={detail} />
      </div>

      {/* Telafi durumu */}
      {detail.is_telafi && (
        <div className="card mb-5 border-amber-500/30 bg-amber-500/5">
          <div className="text-sm text-amber-300 font-medium">♻️ Bu bir TELAFİ siparişidir</div>
          {detail.telafi_sebep && <div className="text-xs text-amber-400/80 mt-1">Sebep: {detail.telafi_sebep}</div>}
        </div>
      )}
      {detail.telafiler && detail.telafiler.length > 0 && (
        <div className="card mb-5">
          <div className="text-sm font-medium text-gray-200 mb-2">♻️ Bu siparişin telafileri</div>
          <div className="space-y-2">
            {detail.telafiler.map(t => (
              <a key={t.id} href={`/telafiler`}
                className="flex items-center justify-between gap-3 px-2 py-1.5 rounded bg-brand-input/50 hover:bg-brand-input text-sm">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300">TELAFİ</span>
                  <span className="text-gray-200">{t.order_number}</span>
                  <span className="text-gray-500 text-xs">{t.item_count} ürün{t.telafi_sebep ? ` · ${t.telafi_sebep}` : ''}</span>
                </div>
                <span className="text-xs text-gray-300 shrink-0">{t.current_stage_label} · %{t.progress_percent}</span>
              </a>
            ))}
          </div>
        </div>
      )}

      {/* İki kolon */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Sol: ürünler */}
        <div className="lg:col-span-2 space-y-5">
          <KalipOzeti lineItems={detail.line_items} />

          <div className="card">
            <h2 className="text-sm font-medium text-gray-200 mb-3 flex items-center gap-2">
              <span>📦</span> Ürünler <span className="text-gray-500">({detail.line_items.length})</span>
            </h2>
            <div className="space-y-2">
              {detail.line_items.map(li => (
                <ProductRow
                  key={li.id}
                  item={li}
                  onPatch={body => patchLineItem(li.id, body)}
                  onZoom={setLightbox}
                  onOpenMold={(mid) => navigate(`/kalip/${mid}`, { state: { from: location.pathname } })}
                  onRemoveFromMolds={() => removeFromMolds(li.id)}
                />
              ))}
            </div>
          </div>
        </div>

        {/* Sağ: panel */}
        <div className="space-y-3">
          <div className="flex gap-1 bg-brand-card border border-brand-border rounded-lg p-1">
            <RightTab active={rightTab === 'musteri'} onClick={() => setRightTab('musteri')}>👤 Müşteri</RightTab>
            <RightTab active={rightTab === 'finansal'} onClick={() => setRightTab('finansal')}>💳 Finansal</RightTab>
            <RightTab active={rightTab === 'kargo'} onClick={() => setRightTab('kargo')}>🚚 Kargo</RightTab>
            <RightTab active={rightTab === 'onay'} onClick={() => setRightTab('onay')}>✅ Onay</RightTab>
            <RightTab active={rightTab === 'diger'} onClick={() => setRightTab('diger')}>💬 Diğer</RightTab>
          </div>

          {rightTab === 'musteri' && <MusteriTab detail={detail} onEmail={() => setEmailOpen(true)} />}
          {rightTab === 'finansal' && <FinansalTab f={f} cur={cur} bayii={detail.bayii_tutar} />}
          {rightTab === 'kargo' && <KargoTab detail={detail} onPatchBarkod={v => patchFlags({ barkod_kodu: v })} onPatchDeadline={v => patchFlags({ kargo_deadline: v })} onCancelKargo={cancelKargo} onSaveAddress={saveAddress} />}
          {rightTab === 'onay' && <OnayTab orderId={orderId} />}
          {rightTab === 'diger' && <DigerTab detail={detail} />}
        </div>
      </div>

      {lightbox && <Lightbox url={lightbox} onClose={() => setLightbox(null)} />}
      {emailOpen && (
        <EmailModal orderRef={detail.id || detail.order_number} orderNo={detail.order_number}
          customer={detail.customer_name} email={detail.customer_email || ''} onClose={() => setEmailOpen(false)} />
      )}
      {addDealer && (
        <AddOrderItemsDialog dealer={addDealer} order={{ id: detail.id, order_number: detail.order_number }}
          onClose={() => setAddDealer(null)}
          onAdded={() => { setAddDealer(null); load() }} />
      )}
    </div>
  )
}


// ═══════════════════════════════════════════════════════════
// Pipeline timeline
// ═══════════════════════════════════════════════════════════

function StagePipeline({ stages, current, progress, isIptal }) {
  const icons = {
    inbox: '📥', loader: '🔄', barcode: '|||', layers: '🧩',
    printer: '🖨', 'printer-check': '🖨', package: '📦', truck: '🚚', 'check-circle': '✓',
  }
  const currentStage = stages.find(s => s.no === current)

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-xl bg-accent/15 flex items-center justify-center text-xl">
            {currentStage ? icons[currentStage.icon] || '•' : '•'}
          </div>
          <div>
            <div className="text-[10px] uppercase text-gray-500">Şu Anki Aşama</div>
            <div className="text-base font-semibold text-gray-100">
              {isIptal ? 'İptal Edildi' : (currentStage?.label || '?')}
              {!isIptal && <span className="text-gray-500 text-sm ml-1">({current}/{stages.length})</span>}
            </div>
          </div>
        </div>
        <div className="text-right">
          <div className="text-[10px] text-gray-500">{current - 1}/{stages.length} aşama bitti</div>
          <div className="text-sm font-semibold text-accent bg-accent/10 px-2 py-0.5 rounded mt-0.5">%{progress}</div>
        </div>
      </div>

      <div className="flex items-center gap-1 overflow-x-auto pb-2">
        {stages.map((s, i) => {
          const done = s.no < current
          const active = s.no === current
          return (
            <div key={s.no} className="flex items-center shrink-0">
              <div className="flex flex-col items-center gap-1 w-[72px]">
                <div className={`w-11 h-11 rounded-full flex items-center justify-center text-sm border-2 relative ${
                  active ? 'bg-accent border-accent text-white'
                  : done ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-300'
                  : 'bg-brand-input border-brand-border text-gray-600'
                }`}>
                  {icons[s.icon] || '•'}
                  <span className={`absolute -top-1 -right-1 w-4 h-4 rounded-full text-[8px] flex items-center justify-center ${
                    active ? 'bg-white text-accent' : done ? 'bg-emerald-500 text-white' : 'bg-brand-border text-gray-500'
                  }`}>{s.no}</span>
                </div>
                <div className={`text-[9px] text-center leading-tight ${
                  active ? 'text-accent font-medium' : done ? 'text-emerald-300' : 'text-gray-600'
                }`}>{s.label}</div>
              </div>
              {i < stages.length - 1 && (
                <div className={`h-0.5 w-4 ${done ? 'bg-emerald-500/50' : 'bg-brand-border'}`} />
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}


// ═══════════════════════════════════════════════════════════
// Durumu Güncelle dropdown
// ═══════════════════════════════════════════════════════════

function StatusDropdown({ stages, current, isIptal, onSelect }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return
    const onClick = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [open])

  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(o => !o)} className="btn-secondary !text-sm flex items-center gap-1.5">
        Durumu Güncelle <span className="text-xs">⌄</span>
      </button>
      {open && (
        <div className="absolute right-0 mt-1 w-52 bg-brand-card border border-brand-border rounded-lg shadow-2xl z-50 py-1 max-h-80 overflow-y-auto">
          {stages.map(s => (
            <button
              key={s.no}
              onClick={() => { onSelect({ stage: s.no }); setOpen(false) }}
              className={`w-full px-3 py-2 text-left text-sm flex items-center gap-2 hover:bg-brand-input ${
                s.no === current && !isIptal ? 'text-accent font-medium' : 'text-gray-300'
              }`}
            >
              <span className="w-5 text-center text-gray-500 text-xs">{s.no}</span>
              {s.label}
              {s.no === current && !isIptal && <span className="ml-auto">✓</span>}
            </button>
          ))}
          <div className="border-t border-brand-border my-1" />
          <button
            onClick={() => { onSelect({ is_iptal: !isIptal }); setOpen(false) }}
            className={`w-full px-3 py-2 text-left text-sm flex items-center gap-2 hover:bg-red-500/10 ${
              isIptal ? 'text-amber-400' : 'text-red-400'
            }`}
          >
            <span className="w-5 text-center">⊘</span>
            {isIptal ? 'İptali Geri Al' : 'İptal Et'}
            {isIptal && <span className="ml-auto">✓</span>}
          </button>
        </div>
      )}
    </div>
  )
}


function MenuShell({ label, children, width = 'w-64' }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  useEffect(() => {
    if (!open) return
    const onClick = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [open])
  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(o => !o)} className="btn-secondary !text-sm flex items-center gap-1.5">
        {label} <span className="text-xs">⌄</span>
      </button>
      {open && (
        <div className={`absolute right-0 mt-1 ${width} bg-brand-card border border-brand-border rounded-lg shadow-2xl z-50 py-1 max-h-[70vh] overflow-y-auto`}
             onClick={() => setOpen(false)}>
          {children}
        </div>
      )}
    </div>
  )
}

function MenuLabel({ children }) {
  return <div className="text-[9px] uppercase tracking-wider text-gray-600 px-3 pt-2 pb-1">{children}</div>
}

function MenuItem({ icon, children, onClick, active, danger }) {
  return (
    <button onClick={onClick}
      className={`w-full px-3 py-2 text-left text-sm flex items-center gap-2 hover:bg-brand-input ${
        danger ? 'text-red-400 hover:bg-red-500/10' : active ? 'text-accent' : 'text-gray-300'
      }`}>
      <span className="w-5 text-center">{icon}</span>
      <span className="flex-1">{children}</span>
      {active && <span>✓</span>}
    </button>
  )
}

function IsaretleDropdown({ detail, onFlag, onStage }) {
  const lists = detail.internal_lists || []
  const has = k => lists.includes(k)
  const toggleList = k => onFlag(has(k) ? { remove_from_list: k } : { add_to_list: k })
  return (
    <MenuShell label="🔖 İşaretle">
      <MenuLabel>Acil</MenuLabel>
      <MenuItem icon="⚠" active={detail.is_acil} onClick={() => onFlag({ is_acil: !detail.is_acil })}>
        Acil Olarak İşaretle
      </MenuItem>
      <MenuLabel>Listeler</MenuLabel>
      <MenuItem icon="✓" active={has('isaretlenenler')} onClick={() => toggleList('isaretlenenler')}>İşaretlenenler'e Ekle</MenuItem>
      <MenuItem icon="📅" active={has('bugun')} onClick={() => toggleList('bugun')}>Bugün Yapılacaklara Ekle</MenuItem>
      <MenuItem icon="🕒" active={has('sonra')} onClick={() => toggleList('sonra')}>Sonra Bakılacaklara Ekle</MenuItem>
      <MenuItem icon="🔍" active={has('kontrol')} onClick={() => toggleList('kontrol')}>Kontrol Listesine Ekle</MenuItem>
      <MenuItem icon="📄" active={has('export')} onClick={() => toggleList('export')}>Export Listesine Ekle</MenuItem>
      <MenuLabel>Durum</MenuLabel>
      <MenuItem icon="✓✓" onClick={() => onStage({ stage: 9 })}>Tamamlandı Olarak İşaretle</MenuItem>
      <MenuItem icon="🖨" active={has('baski')} onClick={() => toggleList('baski')}>Baskı Listesine Ekle</MenuItem>
    </MenuShell>
  )
}

function IslemlerDropdown({ detail, onFlag, onDuplicate, onEmail }) {
  return (
    <MenuShell label="⋯ İşlemler">
      <MenuLabel>Sipariş Kopyala</MenuLabel>
      <MenuItem icon="⧉" onClick={onDuplicate}>Yeni sipariş olarak çoğalt</MenuItem>
      <MenuLabel>E-posta</MenuLabel>
      <MenuItem icon="✉" onClick={onEmail}>Şablonlu e-posta yolla</MenuItem>
      <MenuLabel>Tedarik</MenuLabel>
      <MenuItem icon="⏸" active={detail.is_tedarik_bekleme}
        onClick={() => onFlag({ is_tedarik_bekleme: !detail.is_tedarik_bekleme })}>
        Tedarik Bekleme Modu
      </MenuItem>
      <MenuLabel>Hata</MenuLabel>
      <MenuItem icon="📦" danger active={detail.is_hatali_gonderildi}
        onClick={() => onFlag({ is_hatali_gonderildi: !detail.is_hatali_gonderildi })}>
        Hatalı Gönderildi
      </MenuItem>
    </MenuShell>
  )
}

function TedarikToggle({ value, onChange }) {
  return (
    <button
      onClick={() => onChange(!value)}
      className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm transition-colors ${
        value ? 'bg-purple-500/15 border-purple-500/40 text-purple-300' : 'bg-brand-card border-brand-border text-gray-400'
      }`}
    >
      <span>⏸</span> Tedarik Bekle
      <span className={`w-8 h-4 rounded-full relative transition-colors ${value ? 'bg-purple-500' : 'bg-brand-border'}`}>
        <span className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-all ${value ? 'left-4' : 'left-0.5'}`} />
      </span>
    </button>
  )
}


// ═══════════════════════════════════════════════════════════
// Kalıp Özeti + Ürünler
// ═══════════════════════════════════════════════════════════

function KalipOzeti({ lineItems }) {
  // Aksesuar ve işleme girmeyen ürünler (magsafe düz kılıf, ekran koruyucu)
  // kalıba girmez — kalıp planlayıcı da bunları atlıyor. Eksik sayılmamalılar,
  // aksi halde sipariş hiçbir zaman "tüm ürünler kalıpta" durumuna gelmiyor.
  const kalipluk = lineItems.filter(li => !li.is_aksesuar)
  // Hazır işaretli kalemler kalıp gerektirmez -> eksik sayılmaz
  const eksik = kalipluk.filter(li => !li.is_kaliba_eklendi && !li.is_hazir).length

  return (
    <div className="card">
      <h2 className="text-sm font-medium text-gray-200 mb-2 flex items-center gap-2">
        <span>🧩</span> Kalıp Özeti
      </h2>
      {kalipluk.length === 0 ? (
        <div className="flex items-center gap-2 text-sm text-gray-400 bg-brand-input/40 border border-brand-border rounded-lg px-3 py-2">
          <span>—</span> Bu siparişte kalıp gerektiren ürün yok.
        </div>
      ) : eksik > 0 ? (
        <div className="flex items-center gap-2 text-sm text-amber-300 bg-amber-500/10 border border-amber-500/20 rounded-lg px-3 py-2">
          <span>⚠</span> Bu siparişin {eksik} ürünü için henüz kalıp atanmamış.
        </div>
      ) : (
        <div className="flex items-center gap-2 text-sm text-emerald-300 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2">
          <span>✓</span> Tüm ürünler kalıba eklenmiş.
        </div>
      )}
    </div>
  )
}


function ProductRow({ item, onPatch, onZoom, onOpenMold, onRemoveFromMolds }) {
  const phoneModels = usePhoneModels()
  const [editModel, setEditModel] = useState(false)
  // Couple ürün: 2 ayrı telefon modeli (1. ve 2. kılıf) ayrı ayrı değiştirilebilir.
  const isCouple = !!(item.is_couple || item.device_model_override_2 || (item.couple_models || [])[1] || resolveSecondModel(item))
  const _cm = item.couple_models || []
  const [modelVal, setModelVal] = useState(item.device_model_override || '')
  const [modelVal2, setModelVal2] = useState(item.device_model_override_2 || '')
  const listId = `pm-${item.id}`

  const openEdit = () => {
    // Boşsa mevcut çözülen modellerle ön-doldur (kullanıcı sıfırdan yazmasın)
    setModelVal(item.device_model_override || resolveDeviceModel(item) || '')
    setModelVal2(item.device_model_override_2 || _cm[1] || resolveSecondModel(item) || '')
    setEditModel(true)
  }
  const cancelEdit = () => {
    setEditModel(false)
    setModelVal(item.device_model_override || '')
    setModelVal2(item.device_model_override_2 || '')
  }
  const saveModel = () => {
    const changed = modelVal !== (item.device_model_override || '') ||
                    (isCouple && modelVal2 !== (item.device_model_override_2 || ''))
    // Kalıptaki kayıt modelin SNAPSHOT'ını tutar; sonradan model değişirse kalıp
    // eski modelle basılır. Kullanıcıyı uyar — sessizce yanlış baskıya izin verme.
    if (changed && item.is_kaliba_eklendi) {
      const ok = window.confirm(
        'Bu ürün zaten KALIBA EKLENMİŞ.\n\n' +
        'Kalıptaki kayıt eski telefon modeliyle kalır — bu haliyle basılırsa yanlış model üretilir.\n\n' +
        'Modeli değiştirdikten sonra Kalıplar sayfasından bu kalemi "plana geri döndür" yapıp ' +
        'yeniden kalıba almalısın.\n\nDevam edilsin mi?'
      )
      if (!ok) return
    }
    const fields = ['device_model_override']
    const body = { device_model_override: modelVal }
    if (isCouple) {
      fields.push('device_model_override_2')
      body.device_model_override_2 = modelVal2
    }
    onPatch({ ...body, fields_to_update: fields })
    setEditModel(false)
  }

  return (
    <div className="bg-brand-input/40 border border-brand-border/60 rounded-lg p-3">
      <div className="flex gap-3">
        {item.image_url ? (
          <button
            type="button"
            onClick={() => onZoom && onZoom(item.image_url)}
            className="relative w-16 h-16 rounded-lg overflow-hidden border border-brand-border shrink-0 group/img"
            title="Büyütmek için tıkla"
          >
            <img src={item.image_url} alt="" className="w-full h-full object-cover"
                 onError={e => { e.target.style.display = 'none' }} />
            <span className="absolute inset-0 bg-black/45 opacity-0 group-hover/img:opacity-100 transition-opacity flex items-center justify-center text-white text-lg">
              🔍
            </span>
          </button>
        ) : (
          <div className="w-16 h-16 rounded-lg bg-brand-card border border-brand-border flex items-center justify-center text-gray-600 shrink-0">📱</div>
        )}

        <div className="flex-1 min-w-0">
          <div className="text-sm text-gray-200 font-medium leading-tight">{item.title}</div>
          {(() => {
            const model = resolveDeviceModel(item)
            const model2 = resolveSecondModel(item)
            return model ? <div className="text-xs text-accent font-medium mt-0.5">📱 {model}{model2 ? <span className="text-pink-300"> + {model2}</span> : null}</div> : null
          })()}
          <div className="flex items-center gap-1.5 mt-1 flex-wrap">
            {item.variant_title && <span className="text-[10px] bg-gray-700/40 text-gray-300 px-1.5 py-0.5 rounded">{item.variant_title}</span>}
            {item.device_model_override && <span className="text-[10px] bg-accent/15 text-accent px-1.5 py-0.5 rounded">↳ Override: {item.device_model_override}</span>}
            {item.device_model_override_2 && <span className="text-[10px] bg-pink-500/15 text-pink-300 px-1.5 py-0.5 rounded">↳ 2. kılıf: {item.device_model_override_2}</span>}
          </div>
          {!editModel ? (
            <button onClick={openEdit} className="text-[10px] text-gray-500 hover:text-accent mt-1 flex items-center gap-1">
              ✎ Cihaz Modelini Değiştir{isCouple ? ' (2 kılıf)' : ''}
            </button>
          ) : (
            <div className="mt-1 space-y-1">
              <datalist id={listId}>
                {phoneModels.map(m => <option key={m} value={m} />)}
              </datalist>
              <div className="flex items-center gap-1">
                {isCouple && <span className="text-[10px] text-gray-500 w-12 shrink-0">1. kılıf</span>}
                <input list={listId} value={modelVal} onChange={e => setModelVal(e.target.value)}
                       placeholder="Model seç / ara — örn: iPhone 15 Pro"
                       className="input !text-xs !py-1 flex-1" autoFocus />
              </div>
              {isCouple && (
                <div className="flex items-center gap-1">
                  <span className="text-[10px] text-pink-300 w-12 shrink-0">2. kılıf</span>
                  <input list={listId} value={modelVal2} onChange={e => setModelVal2(e.target.value)}
                         placeholder="2. kılıfın modeli"
                         className="input !text-xs !py-1 flex-1" />
                </div>
              )}
              <div className="flex items-center gap-1 justify-end">
                <button onClick={saveModel} className="btn-primary !text-[10px] !py-1 !px-2">Kaydet</button>
                <button onClick={cancelEdit} className="text-gray-500 text-xs px-1">×</button>
              </div>
            </div>
          )}
        </div>

        <div className="text-right shrink-0">
          <div className="text-xs text-gray-400">x{item.quantity}</div>
          {item.assigned_design && (
            <div className="flex items-center gap-1 mt-1 justify-end">
              {item.assigned_design.thumbnail_url ? (
                <img src={item.assigned_design.thumbnail_url} alt="" className="w-7 h-7 rounded object-cover border border-emerald-500/30" />
              ) : <span className="text-emerald-400 text-xs">📄</span>}
              <span className="text-[10px] font-mono text-emerald-300">{item.assigned_design.code}</span>
            </div>
          )}
        </div>
      </div>

      {/* Çift kılıf: 2 ALT ÜRÜN — her kılıfın kendi tasarımı/modeli/kalıbı ve baskı durumu */}
      {Array.isArray(item.parcalar) && item.parcalar.length > 0 && (
        <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-2">
          {item.parcalar.map(p => (
            <div key={p.slot}
                 className={`rounded-lg border p-2 ${p.basildi
                   ? 'bg-emerald-500/5 border-emerald-500/25'
                   : 'bg-brand-input/30 border-brand-border/60'}`}>
              <div className="flex items-center justify-between gap-2">
                <span className="text-[11px] font-medium text-gray-300">{p.baslik}</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded ${p.basildi
                  ? 'bg-emerald-500/15 text-emerald-300'
                  : p.kaliba_eklendi
                    ? 'bg-amber-500/15 text-amber-300'
                    : 'bg-gray-600/20 text-gray-400'}`}>
                  {p.basildi ? '✓ Basıldı' : p.kaliba_eklendi ? '⏳ Kalıpta, basılmadı' : '○ Kalıba girmedi'}
                </span>
              </div>
              <div className="flex items-center gap-2 mt-1.5">
                {p.design?.thumbnail_url
                  ? <img src={p.design.thumbnail_url} alt="" className="w-8 h-8 rounded object-cover border border-emerald-500/30 shrink-0" />
                  : <span className="w-8 h-8 rounded bg-brand-card border border-brand-border flex items-center justify-center text-gray-600 text-xs shrink-0">—</span>}
                <div className="min-w-0 text-[10px] leading-tight">
                  <div className="font-mono text-emerald-300 truncate">{p.design?.code || 'tasarım yok'}</div>
                  <div className="text-accent truncate">📱 {p.model || '—'}</div>
                </div>
              </div>
              <div className="mt-1.5 text-[10px] text-gray-500">
                Varyasyon: <b className="text-gray-300">{p.varyasyon || '—'}</b>
                {p.varyasyon_kaynak === 'urun_adi' && <span className="text-amber-300"> · ürün adından</span>}
                {p.varyasyon_kaynak === 'elle' && <span className="text-emerald-300"> · elle</span>}
              </div>
              <div className="mt-1 text-[10px] text-gray-500">
                Kalıp:{' '}
                {p.kaliplar.length > 0
                  ? p.kaliplar.map((k, i) => (
                      <a key={k.mold_id + i} href={`/kaliplar?mold=${k.mold_id}`}
                         className="text-accent hover:underline mr-1">{k.kalip_kodu}</a>
                    ))
                  : <span className="text-gray-600">—</span>}
              </div>
              <div className="mt-1.5 pt-1.5 border-t border-brand-border/40">
                <CheckPill
                  checked={!!p.elle_hazir}
                  onChange={c => {
                    const f = p.slot === 2 ? 'is_hazir_2' : 'is_hazir'
                    onPatch({ [f]: c, fields_to_update: [f] })
                  }}
                  label={`📦 ${p.slot}. kılıf hazır`}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Alt aksiyon barı */}
      <div className="flex items-center gap-3 mt-2 pt-2 border-t border-brand-border/50 flex-wrap">
        <span className="text-[10px] uppercase text-gray-600">Durum:</span>
        <CheckPill
          checked={item.tedarik_status === 'tedarik'}
          onChange={c => onPatch({ tedarik_status: c ? 'tedarik' : 'bekliyor', fields_to_update: ['tedarik_status'] })}
          label="⏰ Tedarik"
        />
        {!(Array.isArray(item.parcalar) && item.parcalar.length > 0) && (
        <CheckPill
          checked={item.is_hazir}
          onChange={async c => {
            if (c && item.molds && item.molds.length > 0) {
              const kods = item.molds.map(m => m.kod).join(', ')
              if (confirm(`Bu ürün ${kods} kalıbına ekli. Hazır işaretlenince kalıptan çıkarılsın mı?`)) {
                await onRemoveFromMolds?.()
              }
            }
            onPatch({ is_hazir: c, fields_to_update: ['is_hazir'] })
          }}
          label="📦 Hazır"
        />
        )}
        <button
          onClick={async () => {
            if (!confirm("Bu ürünü askıya atmak istediğine emin misin?")) return
            try {
              const r = await api.post(`/api/aski/from-line-item/${item.id}`, {})
              toast.success(r.message || "Askıya eklendi")
            } catch (e) {
              toast.error(typeof e?.detail === "string" ? e.detail : "Askıya alınamadı")
            }
          }}
          className="text-[10px] text-purple-400/80 hover:text-purple-300 hover:bg-purple-500/10 rounded px-2 py-0.5 border border-purple-500/20 hover:border-purple-500/40 flex items-center gap-1"
          title="Bu ürünü askıya at (hatalı üretildi, stokta hazır bekliyor olarak işaretle)"
        >🎁 Askıya At</button>
        <div className="ml-auto flex items-center gap-2">
          <span className="text-[10px] uppercase text-gray-600">Kalıp:</span>
          {(item.molds && item.molds.length > 0) ? (
            item.molds.map(m => (
              <a
                key={m.id}
                href={`/kalip/${m.id}`}
                onClick={e => { e.preventDefault(); onOpenMold?.(m.id) }}
                title={`${m.kod} kalıbını aç`}
                className="text-[11px] bg-accent/15 text-accent border border-accent/30 px-2 py-1 rounded flex items-center gap-1 font-mono hover:bg-accent/25"
              >🧩 {m.kod}</a>
            ))
          ) : item.is_aksesuar ? (
            // Aksesuar / işleme girmeyen ürün — hiçbir zaman kalıba girmez.
            <span className="text-[11px] bg-sky-500/15 text-sky-300 border border-sky-500/30 px-2 py-1 rounded flex items-center gap-1">
              🎁 Aksesuar (kalıp gerekmiyor)
            </span>
          ) : item.is_hazir ? (
            <span className="text-[11px] bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 px-2 py-1 rounded flex items-center gap-1">
              ✓ Hazır (kalıp gerekmiyor)
            </span>
          ) : item.is_kaliba_eklendi ? (
            // Bayrak "kalıba eklendi" diyor ama HİÇBİR kalıp kaydı yok = kayıp kalem.
            // Planlayıcı bunu atlar (üretime girmez) — yeşil onay yerine UYARI göster.
            <span title="Bu kalem kalıba eklenmiş görünüyor ama hiçbir kalıpta değil — üretime girmez. Kalıp Oluşturucu'da '🔧 Kayıp siparişleri tara' ile plana geri döndür."
              className="text-[11px] bg-amber-500/15 text-amber-300 border border-amber-500/40 px-2 py-1 rounded flex items-center gap-1">
              ⚠ Kalıpta yok (kayıp)
            </span>
          ) : (
            <span className="text-[11px] border border-brand-border text-gray-500 px-2 py-1 rounded flex items-center gap-1">
              ⏳ Kalıp bekliyor
            </span>
          )}
        </div>
      </div>
    </div>
  )
}


function CheckPill({ checked, onChange, label }) {
  return (
    <label className="flex items-center gap-1.5 cursor-pointer text-[11px] text-gray-300">
      <input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} className="accent-accent" />
      {label}
    </label>
  )
}


// ═══════════════════════════════════════════════════════════
// Sağ panel tab'ları
// ═══════════════════════════════════════════════════════════

function MusteriTab({ detail, onEmail }) {
  const ship = detail.shipping_address || {}
  const bill = detail.billing_address || {}
  return (
    <div className="space-y-3">
      <PanelCard title="Müşteri" icon="👤">
        <div className="text-sm text-gray-200">{detail.customer_name || '?'}</div>
        {detail.customer_email && <div className="text-xs text-gray-400 mt-0.5">{detail.customer_email}</div>}
        {detail.customer_email && (
          <button onClick={onEmail} className="mt-2 text-xs text-accent hover:underline">📧 Şablonlu e-posta gönder</button>
        )}
      </PanelCard>

      {detail.raw?.payment && <RefundPanel detail={detail} />}

      {(ship.address1 || ship.city) && (
        <PanelCard title="Kargo Adresi" icon="📍">
          <AddressBlock addr={ship} />
        </PanelCard>
      )}

      {(bill.address1 || bill.city) && (
        <PanelCard title="Fatura Adresi" icon="📍">
          <AddressBlock addr={bill} />
        </PanelCard>
      )}

      <PanelCard title="Müşteri Talepleri" icon="💬">
        {detail.customer_requests && detail.customer_requests.length > 0 ? (
          <div className="space-y-1.5">
            {detail.customer_requests.map(r => (
              <div key={r.id} className="text-xs text-gray-300 bg-brand-input rounded p-2">
                <div className="flex justify-between">
                  <span className="text-gray-500">{r.request_type}</span>
                  <span className={r.status === 'acik' ? 'text-amber-400' : 'text-emerald-400'}>{r.status}</span>
                </div>
                <div className="mt-1">{r.message}</div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-gray-500 italic">Bu sipariş için müşteri talebi bulunmuyor.</p>
        )}
      </PanelCard>

      <PanelCard title="E-posta Geçmişi" icon="✉">
        {detail.email_logs && detail.email_logs.length > 0 ? (
          <div className="space-y-1.5">
            {detail.email_logs.map(e => (
              <div key={e.id} className="text-xs text-gray-300 bg-brand-input rounded p-2">
                <div className="font-medium">{e.subject}</div>
                <div className="text-gray-500 mt-0.5">{e.to_email} · {formatDate(e.created_at)}</div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-gray-500 italic">Bu siparişe gönderilmiş e-posta bulunmuyor.</p>
        )}
      </PanelCard>
    </div>
  )
}

function AddrField({ label, value, onChange }) {
  return (
    <div>
      <label className="text-[10px] text-gray-500 block mb-0.5">{label}</label>
      <input value={value} onChange={e => onChange(e.target.value)} className="input w-full !text-xs !py-1" />
    </div>
  )
}

// Kargo takip numarası — sekme açmadan, boru hattı kartında görünsün.
// Kısmi kargolamada birden fazla gönderi olabilir; hepsi listelenir.
function TakipSatiri({ detail }) {
  const toast = useToast()
  const ki = detail.kargo_info || {}
  const gonderiler = (detail.shipping?.shipments || []).filter(s => s.takip_no)

  // Gönderi kaydı yoksa tek gönderi alanındaki numara gösterilir (Basit Kargo
  // akışı gönderi kaydı açmıyor). Aynı numara iki yerde varsa bir kez yazılır.
  const liste = gonderiler.length
    ? gonderiler.map(s => ({ takip_no: s.takip_no, firma: s.kargo_firma, url: s.takip_url }))
    : (ki.takip_no ? [{ takip_no: ki.takip_no, firma: ki.handler_name, url: ki.takip_url }] : [])

  const kopyala = async (v) => {
    try { await navigator.clipboard.writeText(v); toast.success('Takip no kopyalandı') }
    catch { toast.error('Kopyalanamadı') }
  }

  if (!liste.length) {
    return (
      <div className="mt-1.5 text-xs text-gray-600 flex items-center gap-2">
        <span>📦</span> Henüz kargo takip numarası yok.
      </div>
    )
  }
  return (
    <div className="mt-1.5 space-y-1">
      {liste.map((t, i) => (
        <div key={`${t.takip_no}-${i}`} className="text-xs text-gray-400 flex items-center gap-2 flex-wrap">
          <span>📦</span> Takip No:
          {/* Numaranın kendisi doğrudan kargo firmasının takip sayfasına gider.
              Firma tanınmazsa link üretilemiyor; o zaman düz metin kalır. */}
          {t.url ? (
            <a href={t.url} target="_blank" rel="noopener noreferrer"
               title={`${t.firma || 'Kargo'} takip sayfasında aç`}
               className="font-mono text-accent hover:underline underline-offset-2">
              {t.takip_no} ↗
            </a>
          ) : (
            <span className="font-mono text-gray-200 select-all">{t.takip_no}</span>
          )}
          {t.firma && <span className="text-gray-500">· {t.firma}</span>}
          <button onClick={() => kopyala(t.takip_no)}
                  className="text-gray-500 hover:text-gray-300" title="Kopyala">⧉</button>
        </div>
      ))}
      {/* Basit Kargo gerçek takip kodunu dönmediğinde kendi barkodunu yazıyor;
          müşteri onunla takip yapamaz — numara sanılmasın. */}
      {ki.takip_bekliyor && (
        <div className="text-[11px] text-amber-400/90">
          ⚠ Bu, Basit Kargo'nun kendi barkodu — gerçek kargo takip numarası henüz gelmedi.
        </div>
      )}
      {/* ⚠ Shopify'a fulfillment yazılamadıysa sipariş ORADA hâlâ
          "gönderilmemiş" görünür ve Shopify kendi kargo mailini müşteriye HİÇ
          göndermez. Eskiden bu yalnız durum geçmişindeki bir not satırındaydı,
          yani ancak elle bakınca fark ediliyordu. */}
      {ki.shopify_yazilamadi && (
        <div className="mt-1.5 rounded-lg border border-red-500/30 bg-red-500/10 px-2.5 py-2 text-[11px] text-red-200 leading-relaxed">
          <b>⚠ Shopify'a yazılamadı.</b> Sipariş Shopify'da hâlâ "gönderilmemiş"
          görünüyor; Shopify kendi kargo e-postasını göndermez. Kargo gerçekte
          verildi — Shopify tarafını elle işaretlemen gerekebilir.
          {ki.shopify_hata && (
            <div className="mt-1 text-red-300/80 break-words font-mono text-[10px]">{ki.shopify_hata}</div>
          )}
        </div>
      )}
    </div>
  )
}

function AddressBlock({ addr }) {
  return (
    <div className="text-xs text-gray-400 leading-relaxed">
      {addr.name && <div className="text-gray-300">{addr.name}</div>}
      {addr.address1 && <div>{addr.address1}</div>}
      {addr.address2 && <div>{addr.address2}</div>}
      <div>
        {addr.city}{addr.province && ` / ${addr.province}`}
        {addr.zip && ` ${addr.zip}`}
      </div>
      {addr.country && <div>{addr.country}</div>}
      {addr.phone && <div className="text-gray-500 mt-1">{addr.phone}</div>}
    </div>
  )
}

function FinansalTab({ f, cur, bayii }) {
  // Bayii siparişi: tutar dökümü ürün (bayi para birimi) + kargo (₺) ayrı tutulur.
  if (bayii) {
    const bcur = bayii.currency || 'TRY'
    const urun = Number(bayii.product_total || 0)
    const kargo = Number(bayii.shipping_fee || 0)
    const sameCur = bcur === 'TRY'
    return (
      <div className="space-y-3">
        <PanelCard title="Bayii Tutarı" icon="🤝">
          <Row label="Ürün bedeli" value={fmtMoney(urun, bcur)} />
          <Row label="Kargo" value={kargo > 0 ? fmtMoney(kargo, 'TRY') : '—'} />
          <div className="border-t border-brand-border my-2" />
          {sameCur ? (
            <Row label="Genel Toplam" value={fmtMoney(urun + kargo, 'TRY')} bold />
          ) : (
            <>
              <Row label="Ürün (toplam)" value={fmtMoney(urun, bcur)} bold />
              {kargo > 0 && <Row label="Kargo (toplam)" value={fmtMoney(kargo, 'TRY')} bold />}
            </>
          )}
          <p className="text-[10px] text-gray-500 mt-2">
            Ürün bedeli cariye {bcur} olarak, kargo her zaman ₺ olarak ayrı işlenir. Sipariş iptal edilirse ikisi de geri alınır.
          </p>
        </PanelCard>
      </div>
    )
  }
  return (
    <div className="space-y-3">
      <PanelCard title="Ödeme" icon="💳">
        <Row label="Yöntem" value={f.payment_method || '—'} />
        <Row label="Durum" value={paymentLabel(f.payment_status)} />
      </PanelCard>
      <PanelCard title="Sipariş Özeti" icon="🧾">
        <Row label="Ara Toplam" value={fmtMoney(f.subtotal, cur)} />
        <Row label="Kargo" value={fmtMoney(f.shipping, cur)} />
        <Row label="Vergi" value={fmtMoney(f.total_tax, cur)} />
        {f.total_discount > 0 && <Row label="İndirim" value={`-${fmtMoney(f.total_discount, cur)}`} green />}
        <div className="border-t border-brand-border my-2" />
        <Row label="Toplam" value={fmtMoney(f.total, cur)} bold />
      </PanelCard>
    </div>
  )
}

function KargoTab({ detail, onPatchBarkod, onPatchDeadline, onCancelKargo, onSaveAddress }) {
  const ship = detail.shipping_address || {}
  const [editAddr, setEditAddr] = useState(false)
  const [af, setAf] = useState({})
  const [savingAddr, setSavingAddr] = useState(false)
  const startEditAddr = () => {
    setAf({ name: ship.name || '', phone: ship.phone || '', address1: ship.address1 || '',
            province: ship.province || '', city: ship.city || '', zip: ship.zip || '' })
    setEditAddr(true)
  }
  const submitAddr = async () => {
    setSavingAddr(true)
    const ok = await onSaveAddress(af)
    setSavingAddr(false)
    if (ok) setEditAddr(false)
  }
  const [barkod, setBarkod] = useState(detail.barkod_kodu || '')
  const dlIso = detail.kargo_deadline ? new Date(detail.kargo_deadline).toISOString().slice(0, 10) : ''
  const [deadline, setDeadline] = useState(dlIso)
  return (
    <div className="space-y-3">
      <PanelCard title="Kargo Adresi" icon="🚚">
        {!editAddr && (
          <>
            {(ship.address1 || ship.city) ? <AddressBlock addr={ship} /> : <p className="text-xs text-gray-500 italic">Adres bilgisi yok.</p>}
            {detail.address_editable && (
              <button onClick={startEditAddr} className="mt-2 text-xs text-accent hover:underline">✏️ Adresi düzenle</button>
            )}
          </>
        )}
        {editAddr && (
          <div className="space-y-1.5">
            <AddrField label="Ad Soyad" value={af.name} onChange={v => setAf(s => ({ ...s, name: v }))} />
            <AddrField label="Telefon" value={af.phone} onChange={v => setAf(s => ({ ...s, phone: v }))} />
            <AddrField label="Adres" value={af.address1} onChange={v => setAf(s => ({ ...s, address1: v }))} />
            <div className="grid grid-cols-2 gap-1.5">
              <AddrField label="İl" value={af.province} onChange={v => setAf(s => ({ ...s, province: v }))} />
              <AddrField label="İlçe" value={af.city} onChange={v => setAf(s => ({ ...s, city: v }))} />
            </div>
            <AddrField label="Posta Kodu" value={af.zip} onChange={v => setAf(s => ({ ...s, zip: v }))} />
            <div className="flex gap-2 pt-1">
              <button onClick={submitAddr} disabled={savingAddr} className="btn-primary !text-xs flex-1 disabled:opacity-50">{savingAddr ? 'Kaydediliyor…' : 'Kaydet'}</button>
              <button onClick={() => setEditAddr(false)} disabled={savingAddr} className="btn-secondary !text-xs">İptal</button>
            </div>
          </div>
        )}
      </PanelCard>
      <PanelCard title="Kargo Sözü (SLA)" icon="⏰">
        {detail.kargo_deadline && (
          <p className="text-xs text-gray-400 mb-1.5">
            Söz tarihi: <span className="text-gray-200 font-medium">{formatDate(detail.kargo_deadline)}</span>
          </p>
        )}
        <div className="flex gap-1">
          <input type="date" value={deadline} onChange={e => setDeadline(e.target.value)}
                 className="input !text-xs flex-1" />
          <button onClick={() => onPatchDeadline(deadline)} className="btn-primary !text-xs !px-3">Kaydet</button>
          {detail.kargo_deadline && (
            <button onClick={() => { setDeadline(''); onPatchDeadline('') }}
                    className="btn-secondary !text-xs !px-2" title="Söz tarihini kaldır">✕</button>
          )}
        </div>
        <p className="text-[10px] text-gray-600 mt-1">Mağaza SLA gününden otomatik hesaplanır; buradan elle değiştirilebilir.</p>
      </PanelCard>
      <PanelCard title="BK Kargo Barkodu" icon="🏷">
        <div className="flex gap-1">
          <input value={barkod} onChange={e => setBarkod(e.target.value)} placeholder="Barkod kodu"
                 className="input !text-xs flex-1" />
          <button onClick={() => onPatchBarkod(barkod)} className="btn-primary !text-xs !px-3">Kaydet</button>
        </div>
      </PanelCard>
      {detail.current_stage === 8 && (
        <PanelCard title="Kargo İşlemi" icon="🚚">
          <p className="text-[11px] text-gray-500 mb-2">Sipariş kargoya verildi. Yanlış gönderildiyse iptal edip "Paketleme" aşamasına döndür.</p>
          <button onClick={onCancelKargo}
            className="w-full text-sm px-3 py-2 rounded-lg border bg-red-500/10 text-red-300 border-red-500/30 hover:bg-red-500/20 transition-colors">
            ✕ Kargoyu iptal et
          </button>
        </PanelCard>
      )}
    </div>
  )
}

function DigerTab({ detail }) {
  return (
    <div className="space-y-3">
      {detail.note && (
        <PanelCard title="Müşteri Notu" icon="📝">
          <p className="text-xs text-gray-300 italic">{detail.note}</p>
        </PanelCard>
      )}
      {detail.tags && (
        <PanelCard title="Etiketler" icon="🏷">
          <div className="flex flex-wrap gap-1">
            {detail.tags.split(',').map((t, i) => t.trim() && (
              <span key={i} className="text-[10px] bg-brand-input text-gray-300 px-1.5 py-0.5 rounded">{t.trim()}</span>
            ))}
          </div>
        </PanelCard>
      )}
      <PanelCard title="Durum Geçmişi" icon="🕐">
        {detail.status_history && detail.status_history.length > 0 ? (
          <div className="space-y-1.5">
            {detail.status_history.map(h => {
              const { etiket, not: notMetni } = gecmisSatiri(h)
              return (
                <div key={h.id} className="text-xs border-l-2 border-brand-border pl-2">
                  <div className="text-gray-300">{etiket}</div>
                  {notMetni && (
                    <div className="text-[11px] text-gray-400 whitespace-pre-line break-words mt-0.5">
                      {notMetni}
                    </div>
                  )}
                  <div className="text-[10px] text-gray-500">
                    {h.created_by} · {formatDate(h.created_at)}
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <p className="text-xs text-gray-500 italic">Henüz durum değişikliği yok.</p>
        )}
      </PanelCard>
    </div>
  )
}

// Geçmiş satırı: başlık + notu AYRI döner.
// ⚠ Eskiden not yalnız haritada yeri olan işlemlerde gösteriliyordu; haritada
// olmayan her işlem ham anahtarıyla ("musteri_model_degisikligi" gibi) ve
// NOTU DÜŞÜRÜLEREK basılıyordu — yani "eski model → yeni model" bilgisi
// veritabanında dururken panelde hiç görünmüyordu.
const GECMIS_ETIKET = {
  acil: '⚠ Acil olarak işaretlendi',
  acil_kaldir: 'Acil işareti kaldırıldı',
  iptal: '⊘ İptal edildi',
  iptal_geri: 'İptal geri alındı',
  iptal_edildi: '⊘ Sipariş iptal edildi',
  silindi: '🗑 Silindi',
  hatali_gonderildi: 'Hatalı gönderildi olarak işaretlendi',
  tedarik_bekle: '⏸ Tedarik bekleme açıldı',
  tedarik_devam: 'Tedarik bekleme kapatıldı',
  list_add: 'Listeye eklendi',
  list_remove: 'Listeden çıkarıldı',
  onay_gonderildi: '📤 Müşteri onayına gönderildi',
  musteri_onay: '✅ Müşteri tasarımı onayladı',
  musteri_revizyon: '✏️ Müşteri revizyon istedi',
  kalem_model_degisti: '✎ Cihaz modeli değiştirildi',
  kargo_iptal: '✕ Kargo iptal edildi',
  kargoya_verildi: '🚚 Kargoya verildi',
  kargo_durumu: '🚚 Kargo durumu güncellendi',
  kismi_kargo_geri: '↩ Gönderi geri alındı',
  address_update: '🏠 Kargo adresi güncellendi',
  iade: '💸 İade işlendi',
  // Müşterinin kendi yaptığı değişiklikler (tokenli bağlantı)
  musteri_model_degisikligi: '📱 Müşteri telefon modelini/ürününü değiştirdi',
  musteri_adres_degisikligi: '🏠 Müşteri teslimat adresini değiştirdi',
  adres_baglantisi: '🔗 Adres değişikliği bağlantısı üretildi',
  // E-posta / davet
  stok_eksik_email: '📧 Eksik stok bildirimi gönderildi',
  musteri_email: '📧 Müşteriye e-posta gönderildi',
  yorum_daveti: '📧 Yorum daveti gönderildi',
  // Bayi portalı
  bayii_siparis: '🏬 Bayi portalinden açıldı',
  bayii_onay: '🏬 Bayi siparişi onaylandı',
  bayii_tasarim_degisti: '🏬 Bayi tasarımı değiştirdi',
  bayii_kalem_duzeltildi: '🏬 Bayi kalemi düzeltildi',
}

function gecmisSatiri(h) {
  if (h.action === 'stage_change') {
    // Notu GÖSTERME: "Kalıp durumundan otomatik (Baskı Tamam)" başlığın aynısını
    // tekrarlıyor ve 6000 satırlık geçmişi okunmaz hale getirir.
    return { etiket: `${h.from_label || '?'} → ${h.to_label || '?'}`, not: null }
  }
  // Etiketi bilinmeyen işlemde bile NOT gösterilir: bilgi kaybetmektense
  // ham anahtarı göstermek yeğdir.
  return { etiket: GECMIS_ETIKET[h.action] || h.action, not: h.note }
}

const ONAY_STATUS = {
  bekliyor: { label: 'Onay bekliyor', cls: 'bg-amber-500/15 text-amber-300 border-amber-500/30' },
  onaylandi: { label: 'Onaylandı', cls: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30' },
  revizyon: { label: 'Revizyon istendi', cls: 'bg-red-500/15 text-red-300 border-red-500/30' },
}

function CopyField({ label, value, mono }) {
  const [copied, setCopied] = useState(false)
  if (!value) return null
  const copy = async () => {
    try { await navigator.clipboard.writeText(value); setCopied(true); setTimeout(() => setCopied(false), 1500) } catch {}
  }
  return (
    <div>
      <div className="text-[10px] text-gray-500 mb-1">{label}</div>
      <div className="flex gap-1.5 items-stretch">
        <div className={`flex-1 min-w-0 bg-brand-input border border-brand-border rounded-lg px-2.5 py-2 text-xs text-gray-200 ${mono ? 'font-mono break-all' : 'whitespace-pre-line'} max-h-24 overflow-y-auto`}>{value}</div>
        <button onClick={copy} className={`shrink-0 px-3 rounded-lg text-xs font-medium transition-colors ${copied ? 'bg-emerald-500/20 text-emerald-300' : 'bg-accent/15 text-accent hover:bg-accent/25'}`}>
          {copied ? '✓' : 'Kopyala'}
        </button>
      </div>
    </div>
  )
}

function OnayTab({ orderId }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const toast = useToast()

  const load = async () => {
    try { const r = await api.get(`/api/orders/${orderId}/approvals`); setData(r) }
    catch { setData({ items: [], phone: null }) }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [orderId])

  const create = async () => {
    setCreating(true)
    try {
      await api.post(`/api/orders/${orderId}/approval`, {})
      await load()
      toast.success('Onay linki oluşturuldu')
    } catch (e) {
      toast.error(errMsg(e, 'Oluşturulamadı'))
    } finally { setCreating(false) }
  }

  if (loading) return <PanelCard title="Müşteri Onayı" icon="✅"><div className="skeleton h-4 w-32 rounded" /></PanelCard>

  const items = data?.items || []
  const latest = items[0]

  return (
    <div className="space-y-3">
      <PanelCard title="Müşteri Tasarım Onayı" icon="✅">
        <p className="text-[11px] text-gray-500 mb-3 leading-relaxed">
          Baskı öncesi müşteriye tasarım onay linki. Aşağıdaki <b>telefon</b> ve <b>hazır mesajı</b> kopyalayıp
          WhatsApp/Instagram'dan elle gönder.
        </p>
        <button onClick={create} disabled={creating}
          className="btn-primary !text-xs w-full disabled:opacity-50">
          {creating ? 'Oluşturuluyor…' : latest ? '🔄 Yeni Versiyon Gönder' : '📤 Onaya Gönder'}
        </button>
      </PanelCard>

      {latest && (
        <PanelCard title={`Güncel Onay (v${latest.version})`} icon="🔗">
          <div className="space-y-2.5">
            <span className={`inline-block text-[11px] px-2 py-0.5 rounded-full border ${(ONAY_STATUS[latest.status] || ONAY_STATUS.bekliyor).cls}`}>
              {(ONAY_STATUS[latest.status] || ONAY_STATUS.bekliyor).label}
            </span>
            {latest.status === 'revizyon' && latest.customer_note && (
              <div className="text-xs bg-red-500/10 border border-red-500/20 rounded-lg px-2.5 py-2 text-red-200">
                <b>Müşteri notu:</b> {latest.customer_note}
              </div>
            )}
            {latest.status === 'bekliyor' && (
              <>
                <CopyField label="Müşteri telefonu" value={data.phone || ''} mono />
                {!data.phone && <div className="text-[10px] text-amber-400">⚠ Telefon bulunamadı — siparişten kontrol et</div>}
                <CopyField label="Hazır mesaj (link dahil)" value={latest.message} />
                <CopyField label="Yalnızca link" value={latest.link} mono />
              </>
            )}
            {latest.status !== 'bekliyor' && (
              <CopyField label="Onay linki" value={latest.link} mono />
            )}
          </div>
        </PanelCard>
      )}

      <MusteriBaglantilari orderId={orderId} />

      <EpostaGecmisi orderId={orderId} />

      {items.length > 1 && (
        <PanelCard title="Geçmiş Versiyonlar" icon="🕐">
          <div className="space-y-2">
            {items.slice(1).map(a => (
              <div key={a.id} className="text-xs border-l-2 border-brand-border pl-2 py-0.5">
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">v{a.version} · {(ONAY_STATUS[a.status] || ONAY_STATUS.bekliyor).label}</span>
                  <span className="text-[10px] text-gray-600">{formatDate(a.created_at)}</span>
                </div>
                {a.status === 'revizyon' && a.customer_note && (
                  <div className="mt-1 text-[11px] bg-red-500/10 border border-red-500/20 rounded px-2 py-1 text-red-200">
                    <b>Müşteri notu:</b> {a.customer_note}
                  </div>
                )}
              </div>
            ))}
          </div>
        </PanelCard>
      )}
    </div>
  )
}


const EPOSTA_DURUM = {
  iletildi: { cls: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30', ikon: '✓' },
  gonderildi: { cls: 'bg-sky-500/15 text-sky-300 border-sky-500/30', ikon: '↗' },
  gecikti: { cls: 'bg-amber-500/15 text-amber-300 border-amber-500/30', ikon: '⏳' },
  sekti: { cls: 'bg-red-500/15 text-red-300 border-red-500/30', ikon: '✕' },
  sikayet: { cls: 'bg-red-500/15 text-red-300 border-red-500/30', ikon: '⚠' },
  basarisiz: { cls: 'bg-red-500/15 text-red-300 border-red-500/30', ikon: '✕' },
}

// Siparişe giden e-postalar + teslimat durumu.
// ⚠ NEDEN VAR: müşteri "mail gelmedi" dediğinde elimizde hiçbir kanıt yoktu.
// "Ulaştı" ile "bilmiyoruz" ayrı gösterilir — ikisini karıştırmak, olmayan
// bilgiyi varmış gibi sunmak olurdu.
function EpostaGecmisi({ orderId }) {
  const [d, setD] = useState(null)

  useEffect(() => {
    let iptal = false
    api.get(`/api/orders/${orderId}/eposta-gecmisi`)
      .then(r => { if (!iptal) setD(r) })
      .catch(() => { if (!iptal) setD({ items: [] }) })
    return () => { iptal = true }
  }, [orderId])

  if (!d) return null
  const items = d.items || []

  return (
    <PanelCard title="E-posta Geçmişi" icon="📧">
      {items.length === 0 ? (
        <p className="text-[11px] text-gray-600">
          Bu siparişe henüz e-posta gönderilmedi.
          {d.eposta ? '' : ' (Siparişte e-posta adresi de yok.)'}
        </p>
      ) : (
        <div className="space-y-2">
          {items.map(m => {
            const st = EPOSTA_DURUM[m.durum] || EPOSTA_DURUM.gonderildi
            return (
              <div key={m.id} className="border border-brand-border rounded-lg p-2.5">
                <div className="flex items-start justify-between gap-2">
                  <span className="text-xs text-gray-200 min-w-0 break-words">{m.subject}</span>
                  <span className={`shrink-0 text-[10px] px-2 py-0.5 rounded-full border ${st.cls}`}>
                    {st.ikon} {m.durum_etiket}
                  </span>
                </div>
                <div className="text-[10px] text-gray-500 mt-1 break-all">{m.to}</div>
                <div className="text-[10px] text-gray-600 mt-0.5">
                  {formatDate(m.gonderildi_at)}
                  {m.iletildi_at && ` · ulaştı ${formatDate(m.iletildi_at)}`}
                  {m.acildi_at && ` · açıldı ${formatDate(m.acildi_at)}`}
                </div>
                {m.hata && (
                  <div className="text-[10px] text-red-300 mt-1 break-words">{m.hata}</div>
                )}
                {m.geri_bildirim_bekleniyor && (
                  <div className="text-[10px] text-gray-500 mt-1">
                    Sağlayıcıdan teslimat bilgisi henüz gelmedi
                    {d.webhook_acik ? '' : ' — teslimat bildirimi kurulu değil'}.
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
      {!d.webhook_acik && items.length > 0 && (
        <div className="text-[10px] text-gray-600 mt-2 leading-relaxed">
          ⓘ Teslimat bildirimi (Resend webhook) kurulu değil; durumlar
          "Gönderildi"de kalır. Kurulunca ulaştı / geri döndü bilgisi buraya düşer.
        </div>
      )}
    </PanelCard>
  )
}

function kalanSure(iso) {
  if (!iso) return ''
  const dk = Math.ceil((new Date(iso) - new Date()) / 60000)
  if (dk <= 0) return 'süresi doldu'
  if (dk < 60) return `${dk} dk kaldı`
  const s = Math.floor(dk / 60)
  return s < 24 ? `${s} sa ${dk % 60} dk kaldı` : `${Math.floor(s / 24)} gün kaldı`
}

const BAGLANTI_DURUM = {
  bekliyor: { label: 'Bekliyor', cls: 'bg-amber-500/15 text-amber-300 border-amber-500/30' },
  uygulandi: { label: 'Kullanıldı', cls: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30' },
  iptal: { label: 'İptal', cls: 'bg-gray-500/15 text-gray-400 border-gray-500/30' },
}

// Müşteriye gönderilen model/adres değişikliği bağlantıları.
// NEDEN VAR: bağlantı yalnız üretildiği anda (kalıptan çıkarma penceresinde)
// görünüyordu. WhatsApp sekmesi kapanırsa operatörün tek çıkışı kalemi tekrar
// kalıptan çıkarmaktı — yani üretimi bozmak. Bağlantı zaten geçerli; burada
// tekrar açılabiliyor.
function MusteriBaglantilari({ orderId }) {
  const [d, setD] = useState(null)
  const [busy, setBusy] = useState(false)
  const toast = useToast()

  const load = async () => {
    try { setD(await api.get(`/api/orders/${orderId}/musteri-baglantilari`)) }
    catch { setD({ model: [], adres: [] }) }
  }
  useEffect(() => { load() }, [orderId])

  const ac = (url) => {
    if (!url) return toast.error('Siparişte geçerli bir cep telefonu yok')
    const w = window.open(url, '_blank', 'noopener')
    if (!w) toast.error('WhatsApp açılamadı — tarayıcı pencereyi engelledi')
  }

  const adresUret = async () => {
    setBusy(true)
    try {
      const r = await api.post(`/api/orders/${orderId}/adres-degisim`, {})
      await load()
      ac(r.wa_url)
    } catch (e) { toast.error(errMsg(e, 'Bağlantı üretilemedi')) }
    finally { setBusy(false) }
  }

  if (!d) return null
  const model = d.model || []
  const adres = d.adres || []
  const adresAcik = d.adres_uretilebilir?.acik

  const Kart = ({ t, baslik, alt }) => (
    <div className="border border-brand-border rounded-lg p-2.5 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-gray-200 truncate">{baslik}</span>
        <span className={`shrink-0 text-[10px] px-2 py-0.5 rounded-full border ${(BAGLANTI_DURUM[t.durum] || BAGLANTI_DURUM.iptal).cls}`}>
          {(BAGLANTI_DURUM[t.durum] || BAGLANTI_DURUM.iptal).label}
        </span>
      </div>
      {alt && <div className="text-[10px] text-gray-500">{alt}</div>}
      {t.gecerli ? (
        <>
          <div className="text-[10px] text-gray-500">{kalanSure(t.expires_at)}</div>
          <button onClick={() => ac(t.wa_url)}
            className="w-full text-xs py-1.5 rounded-lg bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/25 transition-colors">
            💬 WhatsApp'tan gönder
          </button>
          <CopyField label="Hazır mesaj" value={t.message} />
          <CopyField label="Yalnızca link" value={t.link} mono />
        </>
      ) : (
        <div className="text-[10px] text-gray-600">
          {t.durum === 'uygulandi' ? 'Müşteri kullandı — bağlantı kapandı.' : 'Süresi doldu.'}
        </div>
      )}
    </div>
  )

  return (
    <PanelCard title="Müşteri Değişiklik Bağlantıları" icon="🔗">
      <p className="text-[11px] text-gray-500 mb-2.5 leading-relaxed">
        Kalıptan çıkarırken üretilen bağlantılar burada durur; mesaj gönderilemediyse
        tekrar açabilirsin. Kalemi yeniden kalıptan çıkarmana gerek yok.
      </p>

      {!d.phone && (
        <div className="text-[10px] text-amber-400 mb-2">⚠ Siparişte geçerli bir cep telefonu yok — yalnızca link kopyalanabilir.</div>
      )}

      <div className="space-y-2">
        {model.map(t => (
          <Kart key={t.id} t={t}
            baslik={`📱 Model — ${t.urun_adi || 'ürün'}`}
            alt={t.durum === 'uygulandi'
              ? `Seçilen: ${t.secilen_model || '—'}${t.secilen_varyasyon ? ' · ' + t.secilen_varyasyon : ''}`
              : (t.mevcut_model || '')} />
        ))}
        {adres.map(t => (
          <Kart key={t.id} t={t} baslik="🏠 Teslimat adresi" />
        ))}
        {!model.length && !adres.length && (
          <div className="text-[11px] text-gray-600">Bu sipariş için henüz bağlantı üretilmedi.</div>
        )}
      </div>

      <button onClick={adresUret} disabled={busy || !adresAcik}
        title={adresAcik ? '' : (d.adres_uretilebilir?.sebep || '')}
        className="mt-2.5 w-full text-xs py-1.5 rounded-lg bg-accent/15 text-accent hover:bg-accent/25 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
        {busy ? 'Üretiliyor…' : '🏠 Adres değişikliği bağlantısı gönder'}
      </button>
      {!adresAcik && d.adres_uretilebilir?.sebep && (
        <div className="text-[10px] text-gray-600 mt-1">{d.adres_uretilebilir.sebep}</div>
      )}
    </PanelCard>
  )
}


// ═══════════════════════════════════════════════════════════
// Yardımcı bileşenler
// ═══════════════════════════════════════════════════════════

function PanelCard({ title, icon, children }) {
  return (
    <div className="card !p-3">
      <h3 className="text-xs font-medium text-gray-300 mb-2 flex items-center gap-1.5">
        <span>{icon}</span> {title}
      </h3>
      {children}
    </div>
  )
}

function Row({ label, value, bold, green }) {
  return (
    <div className="flex justify-between items-center py-0.5">
      <span className="text-xs text-gray-500">{label}</span>
      <span className={`text-xs ${bold ? 'font-semibold text-gray-100 text-sm' : green ? 'text-emerald-400' : 'text-gray-300'}`}>{value}</span>
    </div>
  )
}

function KpiCard({ label, value, icon, color = 'gray', small }) {
  const colors = {
    gray: 'text-gray-100', emerald: 'text-emerald-400', accent: 'text-accent',
  }
  return (
    <div className="bg-brand-card border border-brand-border rounded-lg p-3 flex items-center gap-3">
      <div className="w-9 h-9 rounded-lg bg-brand-input flex items-center justify-center text-base shrink-0">{icon}</div>
      <div className="min-w-0">
        <div className="text-[10px] uppercase text-gray-500">{label}</div>
        <div className={`${small ? 'text-sm' : 'text-lg'} font-semibold ${colors[color]} truncate`}>{value}</div>
      </div>
    </div>
  )
}

function Badge({ color, children }) {
  const colors = {
    red: 'bg-red-500/15 text-red-300 border-red-500/30',
    amber: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    gray: 'bg-gray-500/15 text-gray-300 border-gray-500/30',
    purple: 'bg-purple-500/15 text-purple-300 border-purple-500/30',
    green: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  }
  return <span className={`text-[10px] px-2 py-0.5 rounded-full border ${colors[color]}`}>{children}</span>
}

function RightTab({ active, onClick, children }) {
  return (
    <button onClick={onClick}
      className={`flex-1 px-2 py-1.5 rounded-md text-[11px] transition-colors ${
        active ? 'bg-accent/15 text-accent' : 'text-gray-400 hover:text-gray-200'
      }`}>{children}</button>
  )
}

function errMsg(e, fallback) {
  if (typeof e?.detail === 'string') return e.detail
  if (Array.isArray(e?.detail)) return e.detail.map(x => x?.msg || JSON.stringify(x)).join(', ')
  if (typeof e?.message === 'string') return e.message
  return fallback
}

function Lightbox({ url, onClose }) {
  useEffect(() => {
    const onKey = e => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/85 p-6"
      onClick={onClose}
    >
      <button
        onClick={onClose}
        className="absolute top-4 right-5 text-white/80 hover:text-white text-3xl leading-none"
      >×</button>
      <img
        src={url}
        alt=""
        onClick={e => e.stopPropagation()}
        className="max-w-[90vw] max-h-[90vh] object-contain rounded-lg shadow-2xl"
      />
    </div>
  )
}

function formatDate(iso) {
  if (!iso) return '?'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return '?'
  return d.toLocaleDateString('tr-TR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function fmtMoney(v, cur) {
  if (v === null || v === undefined) return '—'
  const sym = cur === 'TRY' ? '₺' : (cur === 'USD' ? '$' : (cur === 'EUR' ? '€' : ''))
  return `${sym}${Number(v).toLocaleString('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function paymentLabel(status) {
  const map = { paid: 'Ödendi', pending: 'Bekliyor', refunded: 'İade', partially_paid: 'Kısmi', voided: 'İptal' }
  return map[status] || status || '—'
}

// ─── Müşteriye şablonlu e-posta ─────────────────────────────
const ORDER_EMAIL_TEMPLATES = [
  {
    name: 'Telefon modeli stokta yok',
    subject: 'Sipariş #{siparis} — Ürün tedarik durumu',
    body: 'Merhaba {musteri},\n\n#{siparis} numaralı siparişinizdeki telefon modeli şu anda stoklarımızda bulunmamaktadır. Tedarik süreci hakkında sizi en kısa sürede bilgilendireceğiz.\n\nAnlayışınız için teşekkür ederiz.',
  },
  {
    name: 'Kişiye özel tasarım hazır (onay bekliyor)',
    subject: 'Sipariş #{siparis} — Tasarımınız hazır, onayınızı bekliyoruz',
    body: 'Merhaba {musteri},\n\n#{siparis} numaralı siparişiniz için kişiye özel tasarımınız hazırlandı. Onay sayfasından tasarımı inceleyip onaylayabilir ya da revizyon talep edebilirsiniz.\n\nYanıtınızı bekliyoruz 🌸',
  },
  {
    name: 'Kargoya verildi',
    subject: 'Sipariş #{siparis} kargoya verildi',
    body: 'Merhaba {musteri},\n\n#{siparis} numaralı siparişiniz kargoya verildi. Takip numaranız: ... \n\nSağlıkla kullanın 😊',
  },
  {
    name: 'Adres teyidi',
    subject: 'Sipariş #{siparis} — Adres teyidi',
    body: 'Merhaba {musteri},\n\nSiparişinizi göndermeden önce teslimat adresinizi teyit etmek istiyoruz: ...\n\nDoğru mudur? Bilginizi rica ederiz.',
  },
]

function EmailModal({ orderRef, orderNo, customer, email, onClose }) {
  const toast = useToast()
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [sending, setSending] = useState(false)

  const fill = (t) => (t || '')
    .replaceAll('{siparis}', orderNo || '...')
    .replaceAll('{musteri}', (customer || '').split(' ')[0] || 'Merhaba')
  const applyTpl = (tpl) => { setSubject(fill(tpl.subject)); setBody(fill(tpl.body)) }

  const send = async () => {
    if (!subject.trim() || !body.trim()) { toast.error('Konu ve içerik gerekli'); return }
    setSending(true)
    try {
      const html = body.split('\n\n').map(p => `<p>${p.replace(/\n/g, '<br>')}</p>`).join('')
      await api.post(`/api/orders/${orderRef}/send-email`, { subject: subject.trim(), body_html: html, title: subject.trim() })
      toast.success('E-posta gönderildi')
      onClose()
    } catch (e) {
      const d = e?.detail
      toast.error(typeof d === 'string' ? d : (Array.isArray(d) ? 'Geçersiz alan' : 'E-posta gönderilemedi'))
    }
    finally { setSending(false) }
  }

  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/60 p-4" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-lg p-5 animate-popin max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-lg font-semibold text-gray-100">📧 Şablonlu e-posta</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-200 text-2xl leading-none">×</button>
        </div>
        <p className="text-xs text-gray-500 mb-3">Alıcı: <span className="text-gray-300">{email}</span></p>
        <div className="text-[11px] text-gray-500 mb-1">Hazır şablonlar:</div>
        <div className="flex flex-wrap gap-1.5 mb-3">
          {ORDER_EMAIL_TEMPLATES.map((t, i) => (
            <button key={i} onClick={() => applyTpl(t)} className="text-xs px-2 py-1 rounded bg-brand-input text-gray-300 hover:text-white">{t.name}</button>
          ))}
        </div>
        <input className="input w-full !text-sm mb-2" placeholder="Konu" value={subject} onChange={e => setSubject(e.target.value)} />
        <textarea className="input w-full !text-sm" rows={8} placeholder="İçerik — şablon seçip düzenle; '...' kısımlarını doldur." value={body} onChange={e => setBody(e.target.value)} />
        <div className="flex justify-end gap-2 mt-3">
          <button onClick={onClose} className="btn-secondary !text-sm">İptal</button>
          <button onClick={send} disabled={sending} className="btn-primary !text-sm disabled:opacity-50">{sending ? 'Gönderiliyor…' : 'Gönder'}</button>
        </div>
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════
// İade paneli — yalnızca vitrin (kendi mağaza) ödemeli siparişlerde.
// Para hareketi: backend yönetici yetkisi arar; iki adımlı onay.
// ═══════════════════════════════════════════════════════════

function RefundPanel({ detail }) {
  const toast = useToast()
  const [info, setInfo] = useState(null)      // {paid_amount, refunded_total, refundable, refunds}
  const [amount, setAmount] = useState('')
  const [reason, setReason] = useState('')
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [denied, setDenied] = useState(false)

  const load = async () => {
    try {
      const r = await api.get(`/api/orders/${detail.id}/refunds`)
      setInfo(r)
      if (!amount) setAmount(r.refundable)
    } catch (e) {
      if (e?.status === 403) setDenied(true)
      // 404 → vitrin ödemesi değil; panel zaten raw.payment koşuluyla açılır
    }
  }
  useEffect(() => { load() }, [detail.id])  // eslint-disable-line

  if (denied || !info) return null
  const refundable = Number(info.refundable)

  const doRefund = async () => {
    setBusy(true)
    try {
      const r = await api.post(`/api/orders/${detail.id}/refund`, {
        amount: Number(amount), reason: reason || null,
      })
      toast.success(`${r.amount} TL iade edildi (${r.financial_status === 'refunded' ? 'tam' : 'kısmi'})`)
      setConfirming(false); setReason(''); setAmount('')
      await load()
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'İade başarısız')
    } finally { setBusy(false) }
  }

  return (
    <PanelCard title="Para İadesi" icon="💸">
      <div className="text-xs text-gray-400 space-y-0.5 mb-2">
        <div>Ödenen: <span className="text-gray-200 tabular-nums">{info.paid_amount} ₺</span>
          <span className="text-gray-600"> · {info.provider}</span></div>
        {Number(info.refunded_total) > 0 && (
          <div>İade edilen: <span className="text-amber-400 tabular-nums">{info.refunded_total} ₺</span></div>
        )}
      </div>

      {info.refunds.length > 0 && (
        <div className="space-y-1 mb-2">
          {info.refunds.map(r => (
            <div key={r.id} className="text-[11px] bg-brand-input rounded px-2 py-1 flex justify-between">
              <span className={r.status === 'succeeded' ? 'text-emerald-400' : 'text-red-400'}>
                {r.status === 'succeeded' ? '✓' : '✗'} {r.amount} ₺
              </span>
              <span className="text-gray-500">
                {r.created_at ? new Date(r.created_at).toLocaleDateString('tr-TR') : ''}
              </span>
            </div>
          ))}
        </div>
      )}

      {refundable > 0 ? (
        !confirming ? (
          <div className="space-y-2">
            <div className="flex gap-2">
              <input type="number" step="0.01" min="0.01" max={refundable} value={amount}
                onChange={e => setAmount(e.target.value)}
                className="flex-1 bg-brand-input border border-brand-border rounded-lg px-2 py-1.5 text-xs" />
              <button
                onClick={() => {
                  const n = Number(amount)
                  if (!n || n <= 0 || n > refundable) { toast.error(`Tutar 0 ile ${refundable} arasında olmalı`); return }
                  setConfirming(true)
                }}
                className="px-3 py-1.5 rounded-lg text-xs bg-red-600/25 text-red-300 border border-red-500/30">
                İade Et
              </button>
            </div>
            <input value={reason} onChange={e => setReason(e.target.value)} maxLength={500}
              placeholder="Sebep (opsiyonel)"
              className="w-full bg-brand-input border border-brand-border rounded-lg px-2 py-1.5 text-xs" />
          </div>
        ) : (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-2.5 space-y-2">
            <p className="text-xs text-red-300">
              <b>{Number(amount).toFixed(2)} ₺</b> müşteriye iade edilecek. Bu işlem geri alınamaz.
            </p>
            <div className="flex gap-2">
              <button onClick={doRefund} disabled={busy}
                className="px-3 py-1.5 rounded-lg text-xs bg-red-600 text-white disabled:opacity-50">
                {busy ? 'İade ediliyor…' : 'Onaylıyorum, iade et'}
              </button>
              <button onClick={() => setConfirming(false)} disabled={busy}
                className="px-3 py-1.5 rounded-lg text-xs text-gray-400">Vazgeç</button>
            </div>
          </div>
        )
      ) : (
        <p className="text-[11px] text-gray-500 italic">Tutarın tamamı iade edildi.</p>
      )}
    </PanelCard>
  )
}
