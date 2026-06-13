import { useEffect, useState, useRef } from 'react'
import { api } from '../lib/api'
import { useToast } from '../components/Toast'

export default function DealersPage() {
  const toast = useToast()
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
    <div className="max-w-5xl animate-fadein">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-5">
        <div>
          <h1 className="text-2xl font-semibold text-gray-100">🤝 Bayiler</h1>
          <p className="text-sm text-gray-500 mt-1">B2B müşteriler ve cari hesaplar</p>
        </div>
        <button onClick={() => setEditing({})} className="btn-primary">+ Bayii Ekle</button>
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
              </div>
              <div className="flex gap-1.5">
                <button onClick={() => setOrdering(d)} className="btn-primary !text-xs">🛒 Sipariş</button>
                <button onClick={() => setDetail(d)} className="btn-secondary !text-xs">Cari</button>
                <button onClick={() => setEditing(d)} className="btn-secondary !text-xs">Düzenle</button>
              </div>
            </div>
          ))}
        </div>
      )}
      <p className="text-[11px] text-gray-600 mt-3">Bakiye: <span className="text-red-300">kırmızı</span> = bayi borçlu, <span className="text-emerald-300">yeşil</span> = alacaklı.</p>

      {editing && <DealerDialog dealer={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load() }} />}
      {detail && <CariDialog dealer={detail} onClose={() => setDetail(null)} onChanged={load} />}
      {ordering && <OrderDialog dealer={ordering} onClose={() => setOrdering(null)} onCreated={() => { setOrdering(null); load() }} />}
    </div>
  )
}

function DealerDialog({ dealer, onClose, onSaved }) {
  const toast = useToast()
  const isNew = !dealer.id
  const [f, setF] = useState({
    name: dealer.name || '', phone: dealer.phone || '', email: dealer.email || '',
    address: dealer.address || '', note: dealer.note || '',
  })
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setF(s => ({ ...s, [k]: e.target.value }))

  const save = async () => {
    if (!f.name.trim()) { toast.error('İsim gerekli'); return }
    setBusy(true)
    try {
      if (isNew) await api.post('/api/dealers', f)
      else await api.patch(`/api/dealers/${dealer.id}`, f)
      toast.success(isNew ? 'Bayii eklendi' : 'Güncellendi')
      onSaved()
    } catch (e) { toast.error(typeof e?.detail === 'string' ? e.detail : 'Kaydedilemedi'); setBusy(false) }
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 overflow-y-auto" onMouseDown={e => e.target === e.currentTarget && onClose()}>
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
        <div className="flex justify-end gap-2 mt-4">
          <button onClick={onClose} className="btn-secondary !text-sm">İptal</button>
          <button onClick={save} disabled={busy} className="btn-primary !text-sm">{busy ? '…' : 'Kaydet'}</button>
        </div>
      </div>
    </div>
  )
}

function CariDialog({ dealer, onClose, onChanged }) {
  const toast = useToast()
  const [txs, setTxs] = useState([])
  const [loading, setLoading] = useState(true)
  const [amount, setAmount] = useState('')
  const [desc, setDesc] = useState('')
  const [busy, setBusy] = useState(false)
  const [bal, setBal] = useState(dealer.balance)

  const fmt = (n) => new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY' }).format(n || 0)

  const load = async () => {
    setLoading(true)
    try { const t = await api.get(`/api/dealers/${dealer.id}/transactions`); setTxs(Array.isArray(t) ? t : []) }
    catch { toast.error('Hareketler yüklenemedi') }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const pay = async (direction) => {
    const amt = parseFloat(amount)
    if (!amt || amt <= 0) { toast.error('Geçerli tutar gir'); return }
    setBusy(true)
    try {
      const d = await api.post(`/api/dealers/${dealer.id}/payment`, {
        amount: amt, kind: direction === 'payment' ? 'odeme' : 'duzeltme',
        description: desc || (direction === 'payment' ? 'Ödeme alındı' : 'Borç eklendi'), direction,
      })
      setBal(d.balance); setAmount(''); setDesc(''); load(); onChanged?.()
      toast.success(direction === 'payment' ? 'Ödeme işlendi' : 'Borç eklendi')
    } catch (e) { toast.error('İşlenemedi') } finally { setBusy(false) }
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 overflow-y-auto" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-lg p-5 my-8 animate-popin">
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-lg font-semibold text-gray-100">{dealer.name} — Cari Hesap</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-200 text-2xl leading-none">×</button>
        </div>
        <div className="mb-4">
          <span className="text-xs text-gray-500">Güncel bakiye: </span>
          <span className={`text-base font-bold tabular-nums ${bal > 0 ? 'text-red-300' : bal < 0 ? 'text-emerald-300' : 'text-gray-300'}`}>{fmt(bal)}</span>
          <span className="text-[11px] text-gray-600 ml-2">{bal > 0 ? '(bayi borçlu)' : bal < 0 ? '(alacaklı)' : ''}</span>
        </div>

        <div className="bg-brand-input/40 rounded-lg p-3 mb-4">
          <div className="flex gap-2 mb-2">
            <input className="input flex-1" type="number" inputMode="decimal" placeholder="Tutar ₺" value={amount} onChange={e => setAmount(e.target.value)} />
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
                    {t.amount > 0 ? '+' : ''}{fmt(t.amount)}
                  </div>
                </div>
              ))}
            </div>
          )}
      </div>
    </div>
  )
}

function OrderDialog({ dealer, onClose, onCreated }) {
  const toast = useToast()
  const [models, setModels] = useState([])
  const [designs, setDesigns] = useState([])
  const [loadingLists, setLoadingLists] = useState(true)
  const [items, setItems] = useState([{ model: '', design_id: '', design_label: '', quantity: 1 }])
  const [applyShipping, setApplyShipping] = useState((dealer.shipping_fee || 0) > 0)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    (async () => {
      try {
        const sid = dealer.store_id
        const [m, d] = await Promise.all([
          api.get('/api/phone-models?include_baseline=true').catch(() => ({})),
          sid ? api.get(`/api/designs?store_id=${sid}&per_page=500`).catch(() => ({})) : Promise.resolve({}),
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
  const shipping = applyShipping ? shippingFee : 0
  const total = totalQty * unitPrice + shipping
  const fmt = (n) => new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY' }).format(n || 0)

  const setItem = (idx, key, val) => setItems(arr => arr.map((it, i) => i === idx ? { ...it, [key]: val } : it))
  const addItem = () => setItems(arr => [...arr, { model: '', design_id: '', design_label: '', quantity: 1 }])
  const removeItem = (idx) => setItems(arr => arr.length > 1 ? arr.filter((_, i) => i !== idx) : arr)

  const onDesignChange = (idx, designId) => {
    const d = designs.find(x => String(x.id) === String(designId))
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
      })
      toast.success(`Sipariş #${r.order_number} oluşturuldu — ${fmt(r.total)}`)
      onCreated?.()
    } catch (e) { toast.error(typeof e?.detail === 'string' ? e.detail : 'Sipariş oluşturulamadı'); setBusy(false) }
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 overflow-y-auto" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-2xl p-5 my-8 animate-popin">
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-lg font-semibold text-gray-100">{dealer.name} — Yeni Sipariş</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-200 text-2xl leading-none">×</button>
        </div>
        <p className="text-xs text-gray-500 mb-4">Birim fiyat: <span className="text-gray-300 font-medium">{fmt(unitPrice)}</span>{shippingFee > 0 && <> · Kargo: {fmt(shippingFee)}</>}</p>

        {loadingLists ? <div className="text-sm text-gray-500 py-6 text-center">Listeler yükleniyor…</div> : (
          <>
            <div className="space-y-2 mb-3">
              {items.map((it, idx) => (
                <div key={idx} className="flex gap-2 items-center flex-wrap sm:flex-nowrap bg-brand-input/30 rounded-lg p-2">
                  <ModelSearch models={models} value={it.model}
                    onSelect={(v) => setItem(idx, 'model', v)} modelVal={modelVal} modelLabel={modelLabel} />
                  <select className="input flex-1 min-w-[140px]" value={it.design_id} onChange={e => onDesignChange(idx, e.target.value)}>
                    <option value="">Tasarım (ops.)…</option>
                    {designs.map((d, i) => <option key={i} value={d.id}>{designLabel(d)}</option>)}
                  </select>
                  <input className="input w-20" type="number" min="1" value={it.quantity} onChange={e => setItem(idx, 'quantity', e.target.value)} />
                  <button onClick={() => removeItem(idx)} className="text-gray-500 hover:text-red-300 px-1 text-lg" title="Kalemi sil">×</button>
                </div>
              ))}
            </div>
            <button onClick={addItem} className="btn-secondary !text-xs mb-4">+ Kalem Ekle</button>

            <textarea className="input w-full mb-3" rows={2} placeholder="Sipariş notu (ops.)" value={note} onChange={e => setNote(e.target.value)} />

            {shippingFee > 0 && (
              <label className="flex items-center gap-2 mb-4 text-sm text-gray-300 cursor-pointer">
                <input type="checkbox" checked={applyShipping} onChange={e => setApplyShipping(e.target.checked)} />
                Kargo ücreti uygula ({fmt(shippingFee)})
              </label>
            )}

            <div className="flex items-center justify-between border-t border-brand-border pt-3 mb-4">
              <span className="text-sm text-gray-400">{totalQty} adet{shipping > 0 ? ` + kargo` : ''}</span>
              <span className="text-lg font-bold text-accent tabular-nums">{fmt(total)}</span>
            </div>

            <div className="flex justify-end gap-2">
              <button onClick={onClose} className="btn-secondary !text-sm">İptal</button>
              <button onClick={save} disabled={busy} className="btn-primary !text-sm">{busy ? 'Oluşturuluyor…' : 'Sipariş Oluştur'}</button>
            </div>
          </>
        )}
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

