import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useStore } from '../lib/store'
import { Modal } from './UrunlerPage'

// Koleksiyonlar — ürün grupları (vitrinde sayfa + filtre olarak görünür).
// İki tür: elle seçilen (ürün detayındaki çipler) ve AKILLI (kural bazlı —
// ürün eklendikçe/fiyat değiştikçe üyelik kendiliğinden güncellenir).

// Kural alanları — backend'deki smart_collections.FIELDS ile birebir
const FIELDS = [
  { key: 'title', label: 'Ürün adı', ops: ['contains', 'not_contains', 'starts_with'], input: 'text' },
  { key: 'tag', label: 'Etiket', ops: ['contains', 'not_contains'], input: 'text' },
  { key: 'price', label: 'Fiyat', ops: ['gt', 'lt', 'eq'], input: 'number' },
  { key: 'discounted', label: 'İndirimli ürün', ops: ['is_true', 'is_false'], input: 'none' },
  { key: 'stock', label: 'Stokta var', ops: ['is_true', 'is_false'], input: 'none' },
  { key: 'created_days', label: 'Son N günde eklendi', ops: ['within'], input: 'number' },
]
const OP_LABEL = {
  contains: 'içeriyor', not_contains: 'içermiyor', starts_with: 'ile başlıyor',
  gt: 'büyüktür', lt: 'küçüktür', eq: 'eşittir',
  is_true: 'evet', is_false: 'hayır', within: 'gün içinde',
}

export default function KoleksiyonlarPage() {
  const { storeId } = useStore()
  const [collections, setCollections] = useState([])
  const [title, setTitle] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [editing, setEditing] = useState(null)   // kural editörü açık koleksiyon
  const [creatingSmart, setCreatingSmart] = useState(false)

  const load = useCallback(async () => {
    if (!storeId) return
    try { setCollections(await api.get(`/api/catalog/collections?store_id=${storeId}`)) }
    catch { setErr('Koleksiyonlar yüklenemedi') }
  }, [storeId])
  useEffect(() => { load() }, [load])

  const create = async (e) => {
    e.preventDefault()
    if (!title.trim()) return
    setBusy(true); setErr('')
    try {
      await api.post('/api/catalog/collections', { store_id: storeId, title: title.trim() })
      setTitle(''); load()
    } catch (e2) {
      setErr(typeof e2?.detail === 'string' ? e2.detail : 'Oluşturulamadı')
    } finally { setBusy(false) }
  }

  const toggle = async (c) => {
    try { await api.patch(`/api/catalog/collections/${c.id}`, { is_active: !c.is_active }); load() }
    catch { setErr('Güncellenemedi') }
  }
  const rename = async (c) => {
    const t = window.prompt('Yeni koleksiyon adı:', c.title)
    if (!t || t === c.title) return
    try { await api.patch(`/api/catalog/collections/${c.id}`, { title: t }); load() }
    catch { setErr('Yeniden adlandırılamadı') }
  }
  const resync = async (c) => {
    setBusy(true)
    try {
      const r = await api.post(`/api/catalog/collections/${c.id}/sync`, {})
      setErr(''); load()
      window.alert(`Yenilendi — ${r.product_count} ürün eşleşiyor.`)
    } catch { setErr('Yenilenemedi') } finally { setBusy(false) }
  }
  const uploadImage = async (c, file) => {
    if (!file) return
    setBusy(true); setErr('')
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('kind', 'collection')
      const r = await api.postForm(`/api/store-settings/${storeId}/assets`, fd)
      await api.patch(`/api/catalog/collections/${c.id}`, { image_path: r.url })
      load()
    } catch (e2) {
      setErr(typeof e2?.detail === 'string' ? e2.detail : 'Görsel yüklenemedi')
    } finally { setBusy(false) }
  }
  const clearImage = async (c) => {
    try { await api.patch(`/api/catalog/collections/${c.id}`, { image_path: '' }); load() }
    catch { setErr('Görsel kaldırılamadı') }
  }

  const remove = async (c) => {
    if (!window.confirm(`"${c.title}" silinecek (ürünler silinmez). Emin misiniz?`)) return
    try { await api.del(`/api/catalog/collections/${c.id}`); load() }
    catch { setErr('Silinemedi') }
  }

  return (
    <div className="space-y-4 max-w-2xl">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-semibold">Koleksiyonlar</h1>
        <button onClick={() => setCreatingSmart(true)} className="ml-auto btn-ghost text-sm">
          ⚙️ Akıllı koleksiyon
        </button>
      </div>
      <form onSubmit={create} className="flex gap-2">
        <input className="input flex-1" value={title} onChange={e => setTitle(e.target.value)}
          maxLength={200} placeholder="Yeni koleksiyon adı (örn: Retro, Minimal)" />
        <button disabled={busy || !title.trim()} className="btn-primary">Ekle</button>
      </form>
      {err && <p className="text-sm text-red-600">{err}</p>}

      <div className="card !p-0 divide-y divide-panel-border overflow-hidden">
        {collections.map(c => (
          <div key={c.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
            {c.image_url ? (
              <img src={c.image_url} alt={c.title}
                className="w-10 h-10 rounded-lg object-cover border border-panel-border shrink-0" />
            ) : (
              <label className="w-10 h-10 rounded-lg border border-dashed border-panel-border
                flex items-center justify-center text-panel-muted text-xs cursor-pointer shrink-0"
                title="Koleksiyon görseli yükle">
                📷
                <input type="file" accept="image/*" className="hidden"
                  onChange={e => uploadImage(c, e.target.files?.[0])} />
              </label>
            )}
            <span className="font-medium">{c.title}</span>
            {c.is_smart && (
              <span className="text-[10px] font-medium text-indigo-700 bg-indigo-50 px-1.5 py-0.5 rounded-full"
                title="Ürünler kurala göre otomatik seçilir">⚙️ akıllı</span>
            )}
            <span className="text-xs text-panel-muted">/{c.slug} · {c.product_count ?? 0} ürün</span>
            <div className="ml-auto flex items-center gap-2">
              <button onClick={() => toggle(c)}
                className={`text-xs px-2 py-0.5 rounded-full ${c.is_active
                  ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
                {c.is_active ? 'Aktif' : 'Pasif'}
              </button>
              {c.is_smart && (
                <>
                  <button onClick={() => setEditing(c)} className="text-xs text-panel-muted hover:text-panel-ink">Kurallar</button>
                  <button onClick={() => resync(c)} disabled={busy}
                    className="text-xs text-panel-muted hover:text-panel-ink">Yenile</button>
                </>
              )}
              {c.image_url && (
                <button onClick={() => clearImage(c)}
                  className="text-xs text-panel-muted hover:text-red-600">Görseli kaldır</button>
              )}
              <button onClick={() => rename(c)} className="text-xs text-panel-muted hover:text-panel-ink">Adlandır</button>
              <button onClick={() => remove(c)} className="text-xs text-red-600 hover:text-red-600">Sil</button>
            </div>
          </div>
        ))}
        {collections.length === 0 && (
          <div className="p-6 text-sm text-panel-muted text-center">
            Henüz koleksiyon yok. Ürünleri koleksiyona, ürün detayındaki çiplerden atarsınız —
            ya da "⚙️ Akıllı koleksiyon" ile kural yazıp otomatik doldurun.
          </div>
        )}
      </div>

      {(editing || creatingSmart) && (
        <SmartModal
          storeId={storeId}
          collection={editing}
          onClose={() => { setEditing(null); setCreatingSmart(false) }}
          onSaved={() => { setEditing(null); setCreatingSmart(false); load() }}
        />
      )}
    </div>
  )
}

// ─── Kural editörü ────────────────────────────────────────────
function SmartModal({ storeId, collection, onClose, onSaved }) {
  const isNew = !collection
  const [name, setName] = useState(collection?.title || '')
  const [match, setMatch] = useState(collection?.rules_match || 'all')
  const [rules, setRules] = useState(
    collection?.rules?.length ? collection.rules : [{ field: 'title', op: 'contains', value: '' }])
  const [prev, setPrev] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  // Kurallar değiştikçe "kaç ürün eşleşiyor" önizlemesi (kaydetmez)
  useEffect(() => {
    if (!storeId) return
    const t = setTimeout(() => {
      api.post('/api/catalog/collections/preview', { store_id: storeId, rules, rules_match: match })
        .then(setPrev).catch(() => setPrev(null))
    }, 400)
    return () => clearTimeout(t)
  }, [storeId, rules, match])

  const setRule = (i, patch) => setRules(rs => rs.map((r, j) => {
    if (j !== i) return r
    const next = { ...r, ...patch }
    // Alan değişince o alanın desteklediği ilk işleci seç
    if (patch.field) {
      const f = FIELDS.find(x => x.key === patch.field)
      next.op = f.ops[0]
      next.value = ''
    }
    return next
  }))
  const addRule = () => setRules(rs => [...rs, { field: 'title', op: 'contains', value: '' }])
  const delRule = (i) => setRules(rs => rs.filter((_, j) => j !== i))

  const save = async (e) => {
    e.preventDefault()
    setBusy(true); setErr('')
    const payload = { rules, rules_match: match, is_smart: true }
    try {
      if (isNew) {
        await api.post('/api/catalog/collections', {
          store_id: storeId, title: name.trim(), ...payload })
      } else {
        await api.patch(`/api/catalog/collections/${collection.id}`, payload)
      }
      onSaved()
    } catch (e2) {
      setErr(typeof e2?.detail === 'string' ? e2.detail : 'Kaydedilemedi')
    } finally { setBusy(false) }
  }

  return (
    <Modal title={isNew ? 'Akıllı Koleksiyon' : `Kurallar: ${collection.title}`} onClose={onClose}>
      <form onSubmit={save} className="space-y-3">
        {isNew && (
          <label className="block text-sm">
            <span className="text-panel-muted text-xs">Koleksiyon adı</span>
            <input className="input mt-1" value={name} onChange={e => setName(e.target.value)}
              required maxLength={200} placeholder="örn. İndirimdekiler" />
          </label>
        )}
        <label className="block text-sm">
          <span className="text-panel-muted text-xs">Ürün şu koşulu sağlarsa koleksiyona girer</span>
          <select className="input mt-1" value={match} onChange={e => setMatch(e.target.value)}>
            <option value="all">Tüm kuralları sağlıyorsa (ve)</option>
            <option value="any">Kurallardan herhangi birini sağlıyorsa (veya)</option>
          </select>
        </label>

        <div className="space-y-2">
          {rules.map((r, i) => {
            const f = FIELDS.find(x => x.key === r.field) || FIELDS[0]
            return (
              <div key={i} className="flex gap-1.5 items-center">
                <select className="input !py-1.5 text-sm flex-1" value={r.field}
                  onChange={e => setRule(i, { field: e.target.value })}>
                  {FIELDS.map(x => <option key={x.key} value={x.key}>{x.label}</option>)}
                </select>
                <select className="input !py-1.5 text-sm !w-32" value={r.op}
                  onChange={e => setRule(i, { op: e.target.value })}>
                  {f.ops.map(o => <option key={o} value={o}>{OP_LABEL[o]}</option>)}
                </select>
                {f.input !== 'none' && (
                  <input className="input !py-1.5 text-sm flex-1"
                    type={f.input === 'number' ? 'number' : 'text'}
                    value={r.value || ''} onChange={e => setRule(i, { value: e.target.value })}
                    placeholder={f.input === 'number' ? '0' : 'değer'} />
                )}
                <button type="button" onClick={() => delRule(i)}
                  disabled={rules.length === 1}
                  className="text-panel-muted hover:text-red-600 px-1 disabled:opacity-30">×</button>
              </div>
            )
          })}
          <button type="button" onClick={addRule} disabled={rules.length >= 10}
            className="btn-ghost text-xs disabled:opacity-40">+ Kural ekle</button>
        </div>

        <div className="rounded-lg bg-panel-input px-3 py-2 text-sm">
          {prev == null ? (
            <span className="text-panel-muted">Eşleşme hesaplanıyor…</span>
          ) : (
            <>
              <b>{prev.count} ürün</b> eşleşiyor
              {prev.samples?.length > 0 && (
                <span className="block text-xs text-panel-muted mt-0.5 truncate">
                  {prev.samples.map(s => s.title).join(' · ')}
                </span>
              )}
              {prev.count === 0 && (
                <span className="block text-xs text-amber-700 mt-0.5">
                  Hiçbir ürün eşleşmiyor — koleksiyon vitrinde boş görünür.
                </span>
              )}
            </>
          )}
        </div>
        <p className="text-[11px] text-panel-muted">
          Üyelik ürün her kaydedildiğinde kendiliğinden güncellenir. Akıllı koleksiyonda
          ürünleri elle ekleyip çıkaramazsınız — kuralı değiştirin.
        </p>

        {err && <p className="text-sm text-red-600">{err}</p>}
        <div className="flex justify-end gap-2 pt-1">
          <button type="button" onClick={onClose} className="btn-ghost">Vazgeç</button>
          <button disabled={busy} className="btn-primary">
            {busy ? 'Kaydediliyor…' : isNew ? 'Oluştur' : 'Kaydet'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
