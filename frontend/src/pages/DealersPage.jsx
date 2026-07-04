import { useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useToast } from '../components/Toast'
import ManualOrderDialog from '../components/ManualOrderDialog'

const KALIP_TIPLERI = [
  { value: '', label: 'Kalıp tipi (belirtilmedi)' },
  { value: 'siyah', label: 'Siyah' },
  { value: 'beyaz', label: 'Beyaz' },
  { value: 'parlak', label: 'Parlak' },
  { value: 'seffaf', label: 'Şeffaf' },
  { value: 'magsafe', label: 'MagSafe' },
]

export default function DealersPage() {
  const toast = useToast()
  const navigate = useNavigate()
  const [dealers, setDealers] = useState([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(null)   // {} yeni, obj duzenle, null kapali
  const [detail, setDetail] = useState(null)      // cari detay acilan bayi
  const [ordering, setOrdering] = useState(null)  // siparis girilen bayi

  const load = async () => {
    setLoading(true)
    try { const d = await api.get('/api/dealers'); setDealers(Array.isArray(d) ? d : []) }
    catch { toast.error('Bayiler yüklenemedi') }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const fmt = (n) => new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY' }).format(n || 0)

  return (
    <div className="mx-auto max-w-5xl animate-fadein">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-5">
        <div>
          <h1 className="text-2xl font-semibold text-gray-100">🤝 Bayiler</h1>
          <p className="text-sm text-gray-500 mt-1">B2B müşteriler ve cari hesaplar</p>
        </div>
        <a href="/ayarlar" className="text-xs text-gray-500 hover:text-gray-300">⚙ Bayi ekle/düzenle → Ayarlar</a>
      </div>

      {loading ? (
        <div className="space-y-2">
          {[0,1,2].map(i => <div key={i} className="card !py-4"><div className="skeleton h-4 w-40 mb-2 rounded" /><div className="skeleton h-3 w-24 rounded" /></div>)}
        </div>
      ) : dealers.length === 0 ? (
        <div className="card text-center py-12 text-gray-500"><div className="text-3xl mb-2">🤝</div>Henüz bayii yok.</div>
      ) : (
        <div className="space-y-2 stagger">
          {dealers.filter(d => d.is_active).map(d => (
            <div key={d.id} className="card !py-3.5 flex items-center gap-3 flex-wrap">
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold text-gray-100">{d.name}</div>
                <div className="text-xs text-gray-500">{d.phone || '—'}{d.email ? ` · ${d.email}` : ''}</div>
              </div>
              <div className="text-right">
                <div className="text-[10px] text-gray-500">BAKİYE</div>
                <div className={`text-sm font-bold tabular-nums ${d.balance > 0 ? 'text-red-300' : d.balance < 0 ? 'text-emerald-300' : 'text-gray-300'}`}>
                  {fmt(d.balance)}
                </div>
                {d.currency === 'USD' && (
                  <span className="text-[9px] px-1 py-0.5 rounded bg-emerald-500/15 text-emerald-300 ml-1">USD</span>
                )}
                {(d.balance_usd || 0) !== 0 && (
                  <div className={`text-xs font-semibold tabular-nums ${d.balance_usd > 0 ? 'text-red-300/80' : 'text-emerald-300/80'}`}>
                    {new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(d.balance_usd || 0)}
                  </div>
                )}
              </div>
              <div className="flex gap-1.5">
                <button onClick={() => navigate(`/bayiler/${d.id}`)} className="btn-primary !text-xs">📋 Bayii menüsü</button>
                <button onClick={() => setDetail(d)} className="btn-secondary !text-xs">Cari</button>
              </div>
            </div>
          ))}
        </div>
      )}
      <p className="text-[11px] text-gray-600 mt-3">Bakiye: <span className="text-red-300">kırmızı</span> = bayi borçlu, <span className="text-emerald-300">yeşil</span> = alacaklı.</p>

      {editing && <DealerDialog dealer={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load() }} />}
      {detail && <CariDialog dealer={detail} onClose={() => setDetail(null)} onChanged={load} />}
      {ordering && (
        <ManualOrderDialog
          open={!!ordering}
          stores={[{ id: ordering.store_id, name: ordering.name }]}
          defaultStoreId={ordering.store_id}
          dealerId={ordering.id}
          applyShipping={(ordering.shipping_fee || 0) > 0}
          onClose={() => setOrdering(null)}
          onCreated={() => { setOrdering(null); load() }}
        />
      )}
    </div>
  )
}

function DealerDialog({ dealer, onClose, onSaved }) {
  const toast = useToast()
  const isNew = !dealer.id
  const [f, setF] = useState({
    name: dealer.name || '', phone: dealer.phone || '', email: dealer.email || '',
    address: dealer.address || '', note: dealer.note || '',
    unit_price: dealer.unit_price ?? '', shipping_fee: dealer.shipping_fee ?? '',
    currency: dealer.currency || 'TRY',
  })
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setF(s => ({ ...s, [k]: e.target.value }))

  const save = async () => {
    if (!f.name.trim()) { toast.error('İsim gerekli'); return }
    setBusy(true)
    try {
      const payload = {
        ...f,
        unit_price: f.unit_price === '' ? 0 : Number(f.unit_price),
        shipping_fee: f.shipping_fee === '' ? 0 : Number(f.shipping_fee),
      }
      if (isNew) await api.post('/api/dealers', payload)
      else await api.patch(`/api/dealers/${dealer.id}`, payload)
      toast.success(isNew ? 'Bayii eklendi' : 'Güncellendi')
      onSaved()
    } catch (e) { toast.error(typeof e?.detail === 'string' ? e.detail : 'Kaydedilemedi'); setBusy(false) }
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4 overflow-y-auto" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-md p-5 my-8 animate-popin">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-100">{isNew ? 'Yeni Bayii' : 'Bayiyi Düzenle'}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-200 text-2xl leading-none">×</button>
        </div>
        {[['name','İsim *'],['phone','Telefon'],['email','E-posta'],['address','Adres'],['note','Not']].map(([k,lbl]) => (
          <label key={k} className="block mb-3"><span className="block text-xs text-gray-400 mb-1">{lbl}</span>
            {k === 'address' || k === 'note'
              ? <textarea className="input w-full" rows={2} value={f[k]} onChange={set(k)} />
              : <input className="input w-full" value={f[k]} onChange={set(k)} />}
          </label>
        ))}
        <label className="block mb-3"><span className="block text-xs text-gray-400 mb-1">Para Birimi</span>
          <div className="flex gap-2">
            <button type="button" onClick={() => setF(s => ({ ...s, currency: 'TRY' }))}
              className={`flex-1 px-3 py-1.5 rounded text-sm border ${f.currency === 'TRY' ? 'bg-accent/20 border-accent text-accent' : 'bg-brand-input border-brand-border text-gray-400'}`}>₺ TL</button>
            <button type="button" onClick={() => setF(s => ({ ...s, currency: 'USD' }))}
              className={`flex-1 px-3 py-1.5 rounded text-sm border ${f.currency === 'USD' ? 'bg-emerald-500/20 border-emerald-500 text-emerald-300' : 'bg-brand-input border-brand-border text-gray-400'}`}>$ USD</button>
          </div>
        </label>
        <div className="grid grid-cols-2 gap-3 mb-3">
          <label className="block"><span className="block text-xs text-gray-400 mb-1">Birim Fiyat {f.currency === 'USD' ? '$' : '₺'} *</span>
            <input className="input w-full" type="number" inputMode="decimal" min="0" step="0.01"
              value={f.unit_price} onChange={set('unit_price')} placeholder={f.currency === 'USD' ? 'örn. 5' : 'örn. 120'} />
          </label>
          <label className="block"><span className="block text-xs text-gray-400 mb-1">Kargo {f.currency === 'USD' ? '$' : '₺'} (0 = yok)</span>
            <input className="input w-full" type="number" inputMode="decimal" min="0" step="0.01"
              value={f.shipping_fee} onChange={set('shipping_fee')} placeholder={f.currency === 'USD' ? 'örn. 3' : 'örn. 93'} />
          </label>
        </div>
        <p className="text-[11px] text-gray-600 mb-2">Birim fiyat: ürün başına bayi fiyatı. Kargo sipariş başına eklenir (0 ise eklenmez).</p>
        <div className="flex justify-end gap-2 mt-4">
          <button onClick={onClose} className="btn-secondary !text-sm">İptal</button>
          <button onClick={save} disabled={busy} className="btn-primary !text-sm">{busy ? '…' : 'Kaydet'}</button>
        </div>
      </div>
    </div>
  )
}

export function CariDialog({ dealer, onClose, onChanged }) {
  const toast = useToast()
  const [txs, setTxs] = useState([])
  const [loading, setLoading] = useState(true)
  const [amount, setAmount] = useState('')
  const [desc, setDesc] = useState('')
  const [busy, setBusy] = useState(false)
  const [bal, setBal] = useState(dealer.balance)
  const [balUsd, setBalUsd] = useState(dealer.balance_usd || 0)
  const [cur, setCur] = useState('TRY')

  const fmtTRY = (n) => new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY' }).format(n || 0)
  const fmtUSD = (n) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n || 0)
  const fmtCur = (n, c) => (c === 'USD' ? fmtUSD : fmtTRY)(n)
  const fmt = fmtTRY

  const load = async () => {
    setLoading(true)
    try { const t = await api.get(`/api/dealers/${dealer.id}/transactions`); setTxs(Array.isArray(t) ? t : []) }
    catch { toast.error('Hareketler yüklenemedi') }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const [pdfBusy, setPdfBusy] = useState(false)
  const downloadPdf = async () => {
    setPdfBusy(true)
    try {
      const token = localStorage.getItem('baskici_token')
      const res = await fetch(`/api/dealers/${dealer.id}/statement.pdf`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) throw new Error()
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `cari-ekstre-${(dealer.name || 'bayi').replace(/[^\w]+/g, '-').toLowerCase()}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      toast.error('PDF indirilemedi')
    } finally {
      setPdfBusy(false)
    }
  }

  const pay = async (direction) => {
    const amt = parseFloat(amount)
    if (!amt || amt <= 0) { toast.error('Geçerli tutar gir'); return }
    setBusy(true)
    try {
      const d = await api.post(`/api/dealers/${dealer.id}/payment`, {
        amount: amt, kind: direction === 'payment' ? 'odeme' : 'duzeltme',
        description: desc || (direction === 'payment' ? 'Ödeme alındı' : 'Borç eklendi'), direction,
        currency: cur,
      })
      setBal(d.balance); setBalUsd(d.balance_usd || 0); setAmount(''); setDesc(''); load(); onChanged?.()
      toast.success(direction === 'payment' ? 'Ödeme işlendi' : 'Borç eklendi')
    } catch (e) { toast.error('İşlenemedi') } finally { setBusy(false) }
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4 overflow-y-auto" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-lg p-5 my-8 animate-popin">
        <div className="flex items-center justify-between mb-1 gap-2">
          <h2 className="text-lg font-semibold text-gray-100 min-w-0 truncate">{dealer.name} — Cari Hesap</h2>
          <div className="flex items-center gap-2 shrink-0">
            <button onClick={downloadPdf} disabled={pdfBusy}
              className="btn-secondary !text-xs disabled:opacity-50"
              title="Cari ekstre PDF indir">
              {pdfBusy ? '⏳' : '📄'} PDF Ekstre
            </button>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-200 text-2xl leading-none">×</button>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2 mb-4">
          <div className="bg-brand-input/40 rounded-lg p-2.5">
            <div className="text-[10px] text-gray-500 mb-0.5">TL Bakiye</div>
            <div className={`text-base font-bold tabular-nums ${bal > 0 ? 'text-red-300' : bal < 0 ? 'text-emerald-300' : 'text-gray-300'}`}>{fmtTRY(bal)}</div>
            <div className="text-[10px] text-gray-600">{bal > 0 ? 'bayi borçlu' : bal < 0 ? 'alacaklı' : '—'}</div>
          </div>
          <div className="bg-brand-input/40 rounded-lg p-2.5">
            <div className="text-[10px] text-gray-500 mb-0.5">USD Bakiye</div>
            <div className={`text-base font-bold tabular-nums ${balUsd > 0 ? 'text-red-300' : balUsd < 0 ? 'text-emerald-300' : 'text-gray-300'}`}>{fmtUSD(balUsd)}</div>
            <div className="text-[10px] text-gray-600">{balUsd > 0 ? 'bayi borçlu' : balUsd < 0 ? 'alacaklı' : '—'}</div>
          </div>
        </div>

        <div className="bg-brand-input/40 rounded-lg p-3 mb-4">
          <div className="flex gap-2 mb-2">
            <select className="input !w-20 shrink-0" value={cur} onChange={e => setCur(e.target.value)}>
              <option value="TRY">₺ TL</option>
              <option value="USD">$ USD</option>
            </select>
            <input className="input flex-1" type="number" inputMode="decimal" placeholder={cur === 'USD' ? 'Tutar $' : 'Tutar ₺'} value={amount} onChange={e => setAmount(e.target.value)} />
            <input className="input flex-1" placeholder="Açıklama (ops.)" value={desc} onChange={e => setDesc(e.target.value)} />
          </div>
          <div className="flex gap-2">
            <button onClick={() => pay('payment')} disabled={busy} className="flex-1 rounded-lg py-2 text-sm font-medium bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-50">💰 Ödeme Al</button>
            <button onClick={() => pay('debt')} disabled={busy} className="flex-1 btn-secondary !text-sm">＋ Borç Ekle</button>
          </div>
        </div>

        <div className="text-xs text-gray-500 mb-2">Hareketler</div>
        {loading ? <div className="text-sm text-gray-500 py-4 text-center">Yükleniyor…</div>
          : txs.length === 0 ? <div className="text-sm text-gray-600 py-4 text-center">Hareket yok.</div>
          : (
            <div className="space-y-1.5 max-h-64 overflow-y-auto">
              {txs.map(t => (
                <div key={t.id} className="flex items-center justify-between text-sm py-1.5 border-b border-brand-border/40">
                  <div className="min-w-0">
                    <div className="text-gray-300 truncate">{t.description || t.kind}</div>
                    <div className="text-[10px] text-gray-600">{t.created_at ? new Date(t.created_at).toLocaleString('tr-TR') : ''}</div>
                  </div>
                  <div className={`tabular-nums font-medium ${t.amount > 0 ? 'text-red-300' : 'text-emerald-300'}`}>
                    {t.amount > 0 ? '+' : ''}{fmtCur(t.amount, t.currency || 'TRY')}
                  </div>
                </div>
              ))}
            </div>
          )}
      </div>
    </div>
  )
}

export function OrderDialog({ dealer, onClose, onCreated }) {
  const toast = useToast()
  const [models, setModels] = useState([])
  const [designs, setDesigns] = useState([])
  const [loadingLists, setLoadingLists] = useState(true)
  const [items, setItems] = useState([{ model: '', design_id: '', design_label: '', quantity: 1 }])
  const [applyShipping, setApplyShipping] = useState((dealer.shipping_fee || 0) > 0)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  // Akıllı sipariş: serbest metin -> alıcı ad/telefon/adres/il/ilçe
  const [rawText, setRawText] = useState('')
  const [parsing, setParsing] = useState(false)
  const [cust, setCust] = useState({ name: '', phone: '', address: '', il: '', ilce: '' })
  const setCustF = (k) => (e) => setCust(c => ({ ...c, [k]: e.target.value }))

  const parseText = async () => {
    if (!rawText.trim()) { toast.error('Önce alıcı bilgilerini yapıştır'); return }
    setParsing(true)
    try {
      const r = await api.post('/api/dealers/parse-contact', { text: rawText })
      setCust({ name: r.name || '', phone: r.phone || '', address: r.address || '', il: r.il || '', ilce: r.ilce || '' })
      if (!r.name && !r.phone && !r.address) toast.error('Bilgi ayrıştırılamadı — elle doldurabilirsin')
      else toast.success('Ayrıştırıldı — kontrol edip düzenleyebilirsin')
    } catch (e) { toast.error(e.detail || 'Ayrıştırılamadı') }
    finally { setParsing(false) }
  }

  useEffect(() => {
    (async () => {
      try {
        const sid = dealer.store_id
        const [m, d] = await Promise.all([
          api.get('/api/phone-models?include_baseline=true').catch(() => ({})),
          sid ? api.get(`/api/designs?store_id=${sid}&per_page=200`).catch(() => ({})) : Promise.resolve({}),
        ])
        const mArr = Array.isArray(m) ? m : (m?.items || m?.models || [])
        const dArr = Array.isArray(d) ? d : (d?.items || d?.designs || [])
        setModels(mArr); setDesigns(dArr)
      } catch { toast.error('Listeler yüklenemedi') }
      finally { setLoadingLists(false) }
    })()
  }, [])

  const modelLabel = (m) => m.display_name || m.spec_key || m.model || m.name || '—'
  const modelVal = (m) => m.display_name || m.spec_key || m.model || m.name || ''
  const designLabel = (d) => d.name || d.code || d.title || ('Tasarım ' + String(d.id).slice(0, 6))

  const unitPrice = Number(dealer.unit_price || 0)
  const shippingFee = Number(dealer.shipping_fee || 0)
  const totalQty = items.reduce((s, it) => s + (Number(it.quantity) || 0), 0)
  const shipping = applyShipping ? shippingFee : 0     // ₺ (her zaman)
  const urunTotal = totalQty * unitPrice               // bayi para birimi
  const _cur = dealer.currency === 'USD' ? 'USD' : 'TRY'
  const fmt = (n) => new Intl.NumberFormat(_cur === 'USD' ? 'en-US' : 'tr-TR', { style: 'currency', currency: _cur }).format(n || 0)
  const fmtTRY = (n) => new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY' }).format(n || 0)

  const setItem = (idx, key, val) => setItems(arr => arr.map((it, i) => i === idx ? { ...it, [key]: val } : it))
  const addItem = () => setItems(arr => [...arr, { model: '', design_id: '', design_label: '', quantity: 1 }])
  const removeItem = (idx) => setItems(arr => arr.length > 1 ? arr.filter((_, i) => i !== idx) : arr)

  const reloadDesigns = async () => {
    const sid = dealer.store_id
    if (!sid) return
    try { const d = await api.get(`/api/designs?store_id=${sid}&per_page=200`); setDesigns(Array.isArray(d) ? d : (d?.items || [])) } catch {}
  }

  const [uploadIdx, setUploadIdx] = useState(null)  // hangi kalem icin yukleme acik

  const onDesignChange = (idx, designId, designObj) => {
    const d = designObj || designs.find(x => String(x.id) === String(designId))
    setItems(arr => arr.map((it, i) => i === idx ? { ...it, design_id: designId, design_label: d ? designLabel(d) : '' } : it))
  }

  const save = async () => {
    const valid = items.filter(it => it.model && (Number(it.quantity) || 0) > 0)
    if (valid.length === 0) { toast.error('En az bir geçerli kalem gir (model + adet)'); return }
    if (unitPrice <= 0) { toast.error('Bu bayiye birim fiyat tanımlı değil — önce fiyat belirle'); return }
    setBusy(true)
    try {
      const r = await api.post(`/api/dealers/${dealer.id}/orders`, {
        items: valid.map(it => ({
          model: it.model, design_id: it.design_id || null,
          design_label: it.design_label || null, quantity: Number(it.quantity),
        })),
        note: note || null, apply_shipping: applyShipping,
        customer_name: cust.name || null, phone: cust.phone || null,
        address: cust.address || null, il: cust.il || null, ilce: cust.ilce || null,
      })
      toast.success(`Sipariş #${r.order_number} oluşturuldu — ${fmt(r.total)}${r.shipping_try > 0 ? ` + kargo ${fmtTRY(r.shipping_try)}` : ''}`)
      onCreated?.()
    } catch (e) { toast.error(typeof e?.detail === 'string' ? e.detail : 'Sipariş oluşturulamadı'); setBusy(false) }
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4 overflow-y-auto" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-2xl p-5 my-8 animate-popin">
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-lg font-semibold text-gray-100">{dealer.name} — Yeni Sipariş</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-200 text-2xl leading-none">×</button>
        </div>
        <p className="text-xs text-gray-500 mb-4">Birim fiyat: <span className="text-gray-300 font-medium">{fmt(unitPrice)}</span>{shippingFee > 0 && <> · Kargo: <span className="text-gray-300 font-medium">{fmtTRY(shippingFee)}</span></>}</p>

        {loadingLists ? <div className="text-sm text-gray-500 py-6 text-center">Listeler yükleniyor…</div> : (
          <>
            {/* Akıllı sipariş: Instagram/WhatsApp'tan yapıştır -> otomatik ayrıştır */}
            <div className="bg-brand-input/30 rounded-lg p-3 mb-4 border border-brand-border/60">
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-xs font-medium text-gray-300">🪄 Akıllı sipariş — alıcı bilgisini yapıştır</span>
                <button type="button" onClick={parseText} disabled={parsing} className="btn-secondary !text-xs disabled:opacity-50">{parsing ? 'Ayrıştırılıyor…' : 'Ayrıştır'}</button>
              </div>
              <textarea className="input w-full !text-sm" rows={3}
                placeholder={'Örn:\nramazan taş\nfırat mah. 96031 sk no 34 Şahinbey Gaziantep\n+90 546 815 91 02'}
                value={rawText} onChange={e => setRawText(e.target.value)} />
              <div className="grid grid-cols-2 gap-2 mt-2">
                <input className="input !text-sm" placeholder="Ad Soyad" value={cust.name} onChange={setCustF('name')} />
                <input className="input !text-sm" placeholder="Telefon" value={cust.phone} onChange={setCustF('phone')} />
                <input className="input !text-sm col-span-2" placeholder="Adres" value={cust.address} onChange={setCustF('address')} />
                <input className="input !text-sm" placeholder="İl" value={cust.il} onChange={setCustF('il')} />
                <input className="input !text-sm" placeholder="İlçe" value={cust.ilce} onChange={setCustF('ilce')} />
              </div>
              <p className="text-[10px] text-gray-600 mt-1.5">Yapıştırıp "Ayrıştır"a bas; sistem yerleştirir, sen kontrol et. Boş bırakırsan alıcı = bayi adı.</p>
            </div>

            <div className="space-y-2 mb-3">
              {items.map((it, idx) => (
                <div key={idx} className="flex gap-2 items-center flex-wrap sm:flex-nowrap bg-brand-input/30 rounded-lg p-2">
                  <ModelSearch models={models} value={it.model}
                    onSelect={(v) => setItem(idx, 'model', v)} modelVal={modelVal} modelLabel={modelLabel} />
                  <DesignSearch designs={designs} value={it.design_id} designLabel={designLabel}
                    onSelect={(v, d) => onDesignChange(idx, v, d)} />
                  <button type="button" onClick={() => setUploadIdx(idx)} className="btn-secondary !text-xs whitespace-nowrap" title="Yeni tasarım yükle">📎</button>
                  <input className="input w-16" type="number" min="1" value={it.quantity} onChange={e => setItem(idx, 'quantity', e.target.value)} />
                  <button onClick={() => removeItem(idx)} className="text-gray-500 hover:text-red-300 px-1 text-lg" title="Kalemi sil">×</button>
                </div>
              ))}
            </div>
            <button onClick={addItem} className="btn-secondary !text-xs mb-4">+ Kalem Ekle</button>

            <textarea className="input w-full mb-3" rows={2} placeholder="Sipariş notu (ops.)" value={note} onChange={e => setNote(e.target.value)} />

            {shippingFee > 0 && (
              <label className="flex items-center gap-2 mb-4 text-sm text-gray-300 cursor-pointer">
                <input type="checkbox" checked={applyShipping} onChange={e => setApplyShipping(e.target.checked)} />
                Kargo ücreti uygula ({fmtTRY(shippingFee)})
              </label>
            )}

            <div className="flex items-center justify-between border-t border-brand-border pt-3 mb-4">
              <span className="text-sm text-gray-400">{totalQty} adet{shipping > 0 ? ' + kargo (₺)' : ''}</span>
              <span className="text-lg font-bold text-accent tabular-nums">
                {fmt(urunTotal)}{shipping > 0 && <span className="text-sm text-gray-400 font-medium"> + {fmtTRY(shipping)}</span>}
              </span>
            </div>

            <div className="flex justify-end gap-2">
              <button onClick={onClose} className="btn-secondary !text-sm">İptal</button>
              <button onClick={save} disabled={busy} className="btn-primary !text-sm">{busy ? 'Oluşturuluyor…' : 'Sipariş Oluştur'}</button>
            </div>
          </>
        )}
      </div>
      {uploadIdx !== null && (
        <UploadDesignModal
          storeId={dealer.store_id}
          onClose={() => setUploadIdx(null)}
          onUploaded={(newDesign) => {
            // Yeni tasarımı HEMEN listeye ekle (option görünsün) + o kaleme seç (stale lookup yok)
            if (newDesign?.id) {
              setDesigns(arr => [newDesign, ...arr.filter(x => String(x.id) !== String(newDesign.id))])
              onDesignChange(uploadIdx, String(newDesign.id), newDesign)
            }
            setUploadIdx(null)
            toast.success('Tasarım yüklendi ve seçildi')
            reloadDesigns()  // arka planda tam listeyi tazele
          }}
        />
      )}
    </div>
  )
}

function UploadDesignModal({ storeId, onClose, onUploaded }) {
  const toast = useToast()
  const [file, setFile] = useState(null)
  const [filePreview, setFilePreview] = useState(null)
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [kalipTipi, setKalipTipi] = useState('')
  const [busy, setBusy] = useState(false)
  const fileInputRef = useRef(null)

  const handleFile = (f) => {
    if (!f) return
    setFile(f)
    if (filePreview) URL.revokeObjectURL(filePreview)
    setFilePreview(URL.createObjectURL(f))
  }
  useEffect(() => () => { if (filePreview) URL.revokeObjectURL(filePreview) }, [filePreview])

  const save = async () => {
    if (!file) { toast.error('Dosya seç'); return }
    if (!code.trim()) { toast.error('Tasarım kodu gir'); return }
    if (!storeId) { toast.error('Bayi mağazası yok'); return }
    setBusy(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('store_id', storeId)
      fd.append('code', code.trim())
      if (name.trim()) fd.append('name', name.trim())
      if (kalipTipi) fd.append('kalip_tipi', kalipTipi)
      const d = await api.postForm('/api/designs', fd)
      onUploaded?.(d)
    } catch (e) { toast.error(typeof e?.detail === 'string' ? e.detail : 'Yüklenemedi'); setBusy(false) }
  }

  const isPdf = file && (file.type === 'application/pdf' || /\.pdf$/i.test(file.name))

  return (
    <div className="fixed inset-0 z-[140] flex items-center justify-center bg-black/70 p-4" onMouseDown={e => e.target === e.currentTarget && !busy && onClose()}>
      <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-md p-5 animate-popin">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold text-gray-100">📎 Yeni Tasarım</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-200 text-2xl leading-none">×</button>
        </div>

        <div onClick={() => fileInputRef.current?.click()}
          className="border-2 border-dashed border-brand-border rounded-lg p-6 text-center cursor-pointer hover:border-accent/50 transition-colors mb-4">
          <input ref={fileInputRef} type="file" accept=".svg,.png,.jpg,.jpeg,.pdf"
            onChange={e => handleFile(e.target.files?.[0])} className="hidden" />
          {file ? (
            <div className="relative min-h-[180px] flex flex-col items-center justify-center">
              {filePreview && (
                <div className="absolute inset-0 overflow-hidden rounded pointer-events-none" style={{ opacity: 0.24 }}>
                  {isPdf
                    ? <embed src={`${filePreview}#toolbar=0&navpanes=0&scrollbar=0&view=Fit`} type="application/pdf" className="w-full h-full" />
                    : <img src={filePreview} alt="" className="w-full h-full object-contain" />}
                </div>
              )}
              <div className="relative space-y-1">
                <div className="text-sm text-gray-300 break-all px-2">{file.name}</div>
                <div className="text-[10px] text-gray-500">{(file.size / 1024 / 1024).toFixed(2)} MB · değiştirmek için tıkla</div>
              </div>
            </div>
          ) : (
            <>
              <div className="text-2xl mb-1">📤</div>
              <div className="text-sm text-gray-300">Dosya seçmek için tıklayın</div>
              <div className="text-[10px] text-gray-500 mt-1">SVG, PNG, JPG veya PDF · max 50 MB</div>
            </>
          )}
        </div>

        <label className="block mb-3">
          <span className="block text-xs text-gray-400 mb-1">Tasarım kodu *</span>
          <input className="input w-full" value={code} onChange={e => setCode(e.target.value)} placeholder="örn. BAYI-001" />
        </label>
        <label className="block mb-3">
          <span className="block text-xs text-gray-400 mb-1">İsim (ops.)</span>
          <input className="input w-full" value={name} onChange={e => setName(e.target.value)} />
        </label>
        <label className="block mb-4">
          <span className="block text-xs text-gray-400 mb-1">Kalıp tipi (kalıba doğru düşmesi için)</span>
          <select className="input w-full" value={kalipTipi} onChange={e => setKalipTipi(e.target.value)}>
            {KALIP_TIPLERI.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </label>
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="btn-secondary !text-sm">İptal</button>
          <button onClick={save} disabled={busy} className="btn-primary !text-sm">{busy ? 'Yükleniyor…' : 'Yükle'}</button>
        </div>
      </div>
    </div>
  )
}

function ModelSearch({ models, value, onSelect, modelVal, modelLabel }) {
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const [hi, setHi] = useState(0)
  const boxRef = useRef(null)

  useEffect(() => {
    const onDoc = (e) => { if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  const term = q.trim().toLowerCase()
  const filtered = !term
    ? models.slice(0, 50)
    : models.filter(m => modelLabel(m).toLowerCase().includes(term)).slice(0, 50)

  const pick = (m) => { onSelect(modelVal(m)); setQ(''); setOpen(false); setHi(0) }

  // Secili degeri goster (input bos degilse value'yu yansit)
  const display = open ? q : (value || '')

  return (
    <div ref={boxRef} className="relative flex-1 min-w-[160px]">
      <input
        className="input w-full" placeholder="Model ara… (örn S24, iPhone 15)"
        value={display}
        onChange={e => { setQ(e.target.value); setOpen(true); setHi(0) }}
        onFocus={() => { setQ(''); setOpen(true) }}
        onKeyDown={e => {
          if (e.key === 'ArrowDown') { e.preventDefault(); setHi(h => Math.min(h + 1, filtered.length - 1)) }
          else if (e.key === 'ArrowUp') { e.preventDefault(); setHi(h => Math.max(h - 1, 0)) }
          else if (e.key === 'Enter' && open && filtered[hi]) { e.preventDefault(); pick(filtered[hi]) }
          else if (e.key === 'Escape') setOpen(false)
        }}
      />
      {value && !open && (
        <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-emerald-400 pointer-events-none">✓</span>
      )}
      {open && filtered.length > 0 && (
        <div className="absolute z-[130] mt-1 w-full max-h-56 overflow-y-auto bg-brand-card border border-brand-border rounded-lg shadow-xl">
          {filtered.map((m, i) => (
            <button key={i} type="button" onMouseDown={(e) => { e.preventDefault(); pick(m) }}
              onMouseEnter={() => setHi(i)}
              className={`block w-full text-left px-3 py-1.5 text-sm ${i === hi ? 'bg-accent/20 text-gray-100' : 'text-gray-300'}`}>
              {modelLabel(m)}
            </button>
          ))}
        </div>
      )}
      {open && term && filtered.length === 0 && (
        <div className="absolute z-[130] mt-1 w-full bg-brand-card border border-brand-border rounded-lg px-3 py-2 text-xs text-gray-500">
          Eşleşen model yok
        </div>
      )}
    </div>
  )
}

// Aranabilir tasarim secici — kod/ad ile arama + kucuk gorsel onizleme.
function DesignSearch({ designs, value, onSelect, designLabel }) {
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const boxRef = useRef(null)
  useEffect(() => {
    const onDoc = (e) => { if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])
  const thumb = (d) => d && (d.thumbnail_url || d.file_url)
  const sel = value ? designs.find(d => String(d.id) === String(value)) : null
  const term = q.trim().toLowerCase()
  const filtered = (!term
    ? designs
    : designs.filter(d => (designLabel(d) || '').toLowerCase().includes(term)
        || (d.code || '').toLowerCase().includes(term))).slice(0, 80)

  return (
    <div ref={boxRef} className="relative flex-1 min-w-[150px]">
      <button type="button" onClick={() => setOpen(o => !o)}
        className="input w-full flex items-center gap-2 text-left">
        {sel ? (
          <>
            {thumb(sel)
              ? <img src={thumb(sel)} alt="" className="w-6 h-6 rounded object-cover shrink-0" />
              : <span className="shrink-0">🎨</span>}
            <span className="truncate text-gray-200">{designLabel(sel)}</span>
          </>
        ) : <span className="text-gray-500">Tasarım seç… (ops.)</span>}
      </button>
      {open && (
        <div className="absolute z-30 mt-1 w-full max-h-72 overflow-y-auto bg-brand-card border border-brand-border rounded-lg shadow-2xl">
          <div className="p-1.5 sticky top-0 bg-brand-card border-b border-brand-border">
            <input autoFocus className="input w-full !text-sm !py-1" placeholder="🔍 Tasarım ara (kod / ad)"
              value={q} onChange={e => setQ(e.target.value)} />
          </div>
          <button type="button" onClick={() => { onSelect('', null); setOpen(false) }}
            className="w-full text-left px-2.5 py-1.5 text-xs text-gray-500 hover:bg-brand-input">— Tasarım yok —</button>
          {filtered.length === 0 ? (
            <div className="p-3 text-xs text-gray-600">{designs.length ? 'Eşleşen tasarım yok' : 'Bu mağazada tasarım yok'}</div>
          ) : filtered.map(d => (
            <button type="button" key={d.id} onClick={() => { onSelect(String(d.id), d); setQ(''); setOpen(false) }}
              className="w-full flex items-center gap-2 px-2.5 py-1.5 hover:bg-brand-input text-left">
              {thumb(d)
                ? <img src={thumb(d)} alt="" className="w-8 h-8 rounded object-cover shrink-0" />
                : <div className="w-8 h-8 rounded bg-brand-input flex items-center justify-center text-xs shrink-0">🎨</div>}
              <div className="min-w-0">
                <div className="text-xs text-gray-200 truncate">{d.name || d.title || '—'}</div>
                <div className="text-[10px] font-mono text-accent">{d.code}</div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

