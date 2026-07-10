import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../lib/api'
import { useStore } from '../lib/store'
import { useToast } from '../components/Toast'
import { StatusBadge } from './UrunlerPage'

// Tam sayfa ürün editörü — görsel sıralama (drag), inline varyant editi, SEO.
export default function UrunDetayPage() {
  const { productId } = useParams()
  const navigate = useNavigate()
  const { storeId, store } = useStore()
  const [p, setP] = useState(null)
  const [collections, setCollections] = useState([])
  const [form, setForm] = useState(null)
  const [busy, setBusy] = useState(false)
  const toast = useToast()
  // Alt bölümler setMsg({ok,text}) imzasını kullanıyor — toast köprüsü
  const setMsg = (m) => m && (m.ok ? toast.success(m.text) : toast.error(m.text))
  const [variations, setVariations] = useState('')

  const load = useCallback(async () => {
    try {
      const prod = await api.get(`/api/catalog/products/${productId}`)
      setP(prod)
      setForm({
        title: prod.title, slug: prod.slug,
        base_price: prod.base_price, compare_at_price: prod.compare_at_price || '',
        description: prod.description || '', tags: prod.tags || '',
        seo_title: prod.seo_title || '', seo_description: prod.seo_description || '',
      })
      if (storeId) {
        setCollections((await api.get(`/api/catalog/collections?store_id=${storeId}`))
          .filter(c => c.is_active))
      }
    } catch (e) {
      setMsg({ ok: false, text: typeof e?.detail === 'string' ? e.detail : 'Ürün yüklenemedi' })
    }
  }, [productId, storeId])
  useEffect(() => { load() }, [load])

  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }))

  const save = async () => {
    setBusy(true); setMsg(null)
    try {
      await api.patch(`/api/catalog/products/${p.id}`, {
        title: form.title, slug: form.slug || null,
        base_price: Number(form.base_price),
        compare_at_price: form.compare_at_price ? Number(form.compare_at_price) : null,
        description: form.description || null, tags: form.tags || null,
        seo_title: form.seo_title || null, seo_description: form.seo_description || null,
      })
      await load()
      setMsg({ ok: true, text: 'Kaydedildi ✓' })
    } catch (e) {
      setMsg({ ok: false, text: typeof e?.detail === 'string' ? e.detail : 'Kaydedilemedi' })
    } finally { setBusy(false) }
  }

  const patchStatus = async (status) => {
    setBusy(true)
    try { await api.patch(`/api/catalog/products/${p.id}`, { status, publish_at: null }); await load() }
    catch { setMsg({ ok: false, text: 'Durum değiştirilemedi' }) }
    finally { setBusy(false) }
  }

  const schedulePublish = async (val) => {
    setBusy(true)
    try {
      await api.patch(`/api/catalog/products/${p.id}`,
        { publish_at: val ? new Date(val).toISOString() : null })
      await load()
      setMsg({ ok: true, text: val ? 'Yayın zamanı planlandı ⏰' : 'Plan kaldırıldı' })
    } catch { setMsg({ ok: false, text: 'Planlanamadı' }) }
    finally { setBusy(false) }
  }

  const duplicate = async () => {
    setBusy(true)
    try {
      const copy = await api.post(`/api/catalog/products/${p.id}/duplicate`, {})
      navigate(`/urunler/${copy.id}`)
      setMsg({ ok: true, text: 'Kopya oluşturuldu — şu an kopyayı düzenliyorsunuz' })
    } catch { setMsg({ ok: false, text: 'Çoğaltılamadı' }) }
    finally { setBusy(false) }
  }

  const removeProduct = async () => {
    if (!window.confirm('Bu ürün tüm varyant ve görselleriyle silinecek. Emin misiniz?')) return
    try { await api.del(`/api/catalog/products/${p.id}`); navigate('/urunler') }
    catch { setMsg({ ok: false, text: 'Silinemedi' }) }
  }

  if (!p || !form) return <p className="text-sm text-panel-muted">Yükleniyor…</p>

  return (
    <div className="max-w-4xl space-y-4 pb-10">
      <div className="flex items-center gap-3 flex-wrap sticky top-0 bg-panel-bg py-2 z-10">
        <Link to="/urunler" className="text-panel-muted hover:text-panel-ink">←</Link>
        <h1 className="text-xl font-semibold truncate max-w-md">{p.title}</h1>
        <StatusBadge status={p.status} />
        <div className="ml-auto flex gap-2 items-center">
          {p.status === 'active' && (
            <a href={`${(store?.config?.storefront_url
                || (store?.config?.shop_domain ? `https://${store.config.shop_domain}` : '')
              ).replace(/\/$/, '')}/urun/${p.slug}`}
              target="_blank" rel="noopener noreferrer"
              className="btn-ghost !py-1.5 text-xs">👁 Vitrinde Gör</a>
          )}
          {p.status !== 'active'
            ? <button disabled={busy} onClick={() => patchStatus('active')}
                className="px-3 py-1.5 rounded-xl text-xs bg-emerald-100 text-emerald-700">Yayınla</button>
            : <button disabled={busy} onClick={() => patchStatus('draft')}
                className="px-3 py-1.5 rounded-xl text-xs bg-slate-100 text-slate-600">Taslağa Al</button>}
          <button disabled={busy} onClick={duplicate} className="btn-ghost !py-1.5 text-xs">Çoğalt</button>
          <button disabled={busy} onClick={removeProduct}
            className="px-3 py-1.5 rounded-xl text-xs bg-red-50 text-red-700">Sil</button>
          <button disabled={busy} onClick={save} className="btn-primary !py-1.5">Kaydet</button>
        </div>
      </div>

      {p.status === 'draft' && (
        <div className="card !py-2.5 flex items-center gap-3 text-sm border-indigo-200 bg-indigo-50/50">
          <span>⏰</span>
          {p.publish_at ? (
            <>
              <span className="text-indigo-800">
                <b>{new Date(p.publish_at).toLocaleString('tr-TR', {
                  day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })}</b>'de
                otomatik yayınlanacak
              </span>
              <button onClick={() => schedulePublish(null)} disabled={busy}
                className="ml-auto text-xs text-indigo-700 underline">Planı kaldır</button>
            </>
          ) : (
            <>
              <span className="text-indigo-800">Yayın zamanı planla:</span>
              <input type="datetime-local" className="input !w-56 !py-1.5"
                min={new Date().toISOString().slice(0, 16)}
                onChange={e => e.target.value && schedulePublish(e.target.value)} />
              <span className="text-[11px] text-panel-muted ml-auto">
                Saati gelince ürün kendiliğinden yayına girer
              </span>
            </>
          )}
        </div>
      )}

      <section className="card space-y-3">
        <h2 className="text-sm font-semibold">Temel Bilgiler</h2>
        <Field label="Ürün adı">
          <input className="input mt-1" value={form.title} onChange={set('title')} maxLength={300} />
        </Field>
        <div className="grid grid-cols-3 gap-3">
          <Field label="Fiyat (₺)">
            <input className="input mt-1" type="number" step="0.01" min="0"
              value={form.base_price} onChange={set('base_price')} />
          </Field>
          <Field label="İndirim öncesi fiyat (₺, ops.)">
            <input className="input mt-1" type="number" step="0.01" min="0"
              value={form.compare_at_price} onChange={set('compare_at_price')} placeholder="üstü çizili görünür" />
          </Field>
          <Field label="URL (slug)">
            <input className="input mt-1 font-mono text-xs" value={form.slug} onChange={set('slug')} />
          </Field>
        </div>
        <Field label="Açıklama">
          <textarea className="input mt-1" rows={5} value={form.description}
            onChange={set('description')} maxLength={20000} />
        </Field>
        <Field label="Etiketler (virgülle)">
          <input className="input mt-1" value={form.tags} onChange={set('tags')} maxLength={500}
            placeholder="retro, minimal, yaz" />
        </Field>
      </section>

      <ImagesSection product={p} onChanged={load} setMsg={setMsg} />

      <section className="card space-y-3">
        <h2 className="text-sm font-semibold">SEO</h2>
        <Field label="SEO başlığı (Google'da görünen)">
          <input className="input mt-1" value={form.seo_title} onChange={set('seo_title')}
            maxLength={200} placeholder={form.title} />
        </Field>
        <Field label="SEO açıklaması">
          <textarea className="input mt-1" rows={2} value={form.seo_description}
            onChange={set('seo_description')} maxLength={400}
            placeholder="Arama sonuçlarında görünen 1-2 cümlelik özet" />
        </Field>
        <p className="text-[11px] text-panel-muted">
          Boş bırakılırsa ürün adı ve açıklamasından otomatik üretilir.
        </p>
      </section>

      {collections.length > 0 && (
        <section className="card space-y-2">
          <h2 className="text-sm font-semibold">Koleksiyonlar</h2>
          <div className="flex gap-2 flex-wrap">
            {collections.map(c => {
              const active = (p.collection_ids || []).includes(c.id)
              return (
                <button key={c.id} disabled={busy}
                  onClick={async () => {
                    const next = new Set(p.collection_ids || [])
                    next.has(c.id) ? next.delete(c.id) : next.add(c.id)
                    try {
                      await api.put(`/api/catalog/products/${p.id}/collections`,
                        { collection_ids: [...next] })
                      await load()
                    } catch { setMsg({ ok: false, text: 'Koleksiyon güncellenemedi' }) }
                  }}
                  className={`px-3 py-1 rounded-full text-xs border transition ${active
                    ? 'border-panel-accent bg-emerald-50 text-emerald-700'
                    : 'border-panel-border text-panel-muted hover:text-panel-ink'}`}>
                  {c.title}
                </button>
              )
            })}
          </div>
        </section>
      )}

      <section className="card space-y-3">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold">Varyantlar ({p.variants.length})</h2>
          <span className="text-[11px] text-panel-muted">— fiyat/stok hücresine tıklayıp düzenleyin</span>
        </div>
        <div className="flex gap-2">
          <input className="input flex-1" value={variations}
            onChange={e => setVariations(e.target.value)}
            placeholder="Renkler (virgülle): SİYAH, ŞEFFAF — boş = renksiz" />
          <button disabled={busy} className="btn-ghost text-xs whitespace-nowrap"
            onClick={async () => {
              setBusy(true)
              try {
                const vars = variations.split(',').map(s => s.trim().toUpperCase()).filter(Boolean)
                await api.post(`/api/catalog/products/${p.id}/variants/bulk`, { variations: vars })
                await load()
              } catch { setMsg({ ok: false, text: 'Varyantlar oluşturulamadı' }) }
              finally { setBusy(false) }
            }}>
            Telefon modellerinden üret
          </button>
        </div>
        <VariantTable product={p} basePrice={form.base_price} onChanged={load} setMsg={setMsg} />
      </section>
    </div>
  )
}

function Field({ label, children }) {
  return (
    <label className="block text-sm">
      <span className="text-panel-muted text-xs">{label}</span>
      {children}
    </label>
  )
}

// ── Görseller: yükleme + HTML5 drag-to-reorder (ilk görsel = kapak) ──
function ImagesSection({ product, onChanged, setMsg }) {
  const [order, setOrder] = useState(product.images.map(im => im.id))
  const [busy, setBusy] = useState(false)
  const [progress, setProgress] = useState(null)   // "3/5"
  const [dropActive, setDropActive] = useState(false)
  const dragId = useRef(null)

  useEffect(() => { setOrder(product.images.map(im => im.id)) }, [product.images])
  const byId = Object.fromEntries(product.images.map(im => [im.id, im]))

  const onDrop = async () => {
    dragId.current = null
    if (order.join() === product.images.map(im => im.id).join()) return
    try {
      await api.put(`/api/catalog/products/${product.id}/images/order`, { image_ids: order })
      await onChanged()
    } catch { setMsg({ ok: false, text: 'Sıralama kaydedilemedi' }) }
  }

  const upload = async (files) => {
    const list = [...(files || [])].filter(f => f.type.startsWith('image/'))
    if (!list.length) return
    setBusy(true)
    try {
      // 5'erli gruplar halinde tek istekte yükle (sunucu optimize eder — 25MB'a kadar)
      const CHUNK = 5
      let done = 0
      const allErrors = []
      for (let i = 0; i < list.length; i += CHUNK) {
        const chunk = list.slice(i, i + CHUNK)
        setProgress(`${done + 1}-${done + chunk.length}/${list.length}`)
        const fd = new FormData()
        for (const f of chunk) fd.append('files', f)
        const r = await api.postForm(`/api/catalog/products/${product.id}/images`, fd)
        allErrors.push(...(r.errors || []))
        done += chunk.length
      }
      await onChanged()
      if (allErrors.length) {
        setMsg({ ok: false, text: `${allErrors.length} dosya yüklenemedi: ${allErrors[0].mesaj}` })
      } else {
        setMsg({ ok: true, text: `${list.length} görsel yüklendi ✓ (otomatik optimize edildi)` })
      }
    } catch (e) {
      setMsg({ ok: false, text: typeof e?.detail === 'string' ? e.detail : 'Görsel yüklenemedi' })
    } finally { setBusy(false); setProgress(null) }
  }

  const remove = async (id) => {
    try { await api.del(`/api/catalog/images/${id}`); await onChanged() }
    catch { setMsg({ ok: false, text: 'Görsel silinemedi' }) }
  }

  return (
    <section
      className={`card space-y-3 transition ${dropActive ? 'ring-2 ring-panel-accent ring-offset-2 !bg-emerald-50/50' : ''}`}
      onDragOver={(e) => {
        if (e.dataTransfer?.types?.includes('Files')) { e.preventDefault(); setDropActive(true) }
      }}
      onDragLeave={() => setDropActive(false)}
      onDrop={(e) => {
        if (!e.dataTransfer?.files?.length) return
        e.preventDefault(); setDropActive(false)
        upload(e.dataTransfer.files)
      }}>
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-semibold">Görseller</h2>
        <span className="text-[11px] text-panel-muted">
          — sürükleyip bırakın veya seçin; ilk görsel kapaktır · 25MB'a kadar, otomatik küçültülür
        </span>
        {progress && <span className="text-[11px] text-panel-accent ml-auto">Yükleniyor {progress}…</span>}
      </div>
      <div className="flex gap-2.5 flex-wrap">
        {order.map((id, idx) => {
          const im = byId[id]
          if (!im) return null
          return (
            <div key={id} draggable
              onDragStart={() => { dragId.current = id }}
              onDragOver={(e) => {
                e.preventDefault()
                const from = order.indexOf(dragId.current)
                const to = order.indexOf(id)
                if (from === -1 || to === -1 || from === to) return
                const next = [...order]
                next.splice(from, 1)
                next.splice(to, 0, dragId.current)
                setOrder(next)
              }}
              onDragEnd={onDrop}
              className="relative group cursor-grab active:cursor-grabbing">
              <img src={im.url} alt={im.alt || ''}
                className={`w-24 h-24 object-cover rounded-xl border-2 ${idx === 0
                  ? 'border-panel-accent' : 'border-panel-border'}`} />
              {idx === 0 && (
                <span className="absolute bottom-1 left-1 text-[9px] bg-panel-accent text-white px-1.5 py-0.5 rounded">
                  KAPAK
                </span>
              )}
              <button onClick={() => remove(id)}
                className="absolute -top-1.5 -right-1.5 hidden group-hover:flex bg-red-600 text-white rounded-full w-5 h-5 text-xs items-center justify-center">×</button>
            </div>
          )
        })}
        <label className="w-24 h-24 rounded-xl border-2 border-dashed border-panel-border flex flex-col items-center justify-center cursor-pointer text-panel-muted hover:text-panel-ink hover:border-slate-400">
          <span className="text-xl">+</span>
          <span className="text-[10px]">{busy ? 'Yükleniyor…' : 'Görsel ekle'}</span>
          <input type="file" multiple accept="image/png,image/jpeg,image/webp" className="hidden"
            onChange={e => upload([...e.target.files])} />
        </label>
      </div>
    </section>
  )
}

// ── Varyant tablosu: inline fiyat + stok editi ──
function VariantTable({ product, basePrice, onChanged, setMsg }) {
  const [edit, setEdit] = useState(null)   // {id, field, value}

  const commit = async () => {
    if (!edit) return
    const { id, field, value } = edit
    setEdit(null)
    const payload = field === 'price_override'
      ? { price_override: value === '' ? null : Number(value) }
      : { quantity: Math.max(0, parseInt(value || '0', 10)) }
    try { await api.patch(`/api/catalog/variants/${id}`, payload); await onChanged() }
    catch { setMsg({ ok: false, text: 'Varyant güncellenemedi' }) }
  }

  const toggleActive = async (v) => {
    try { await api.patch(`/api/catalog/variants/${v.id}`, { is_active: !v.is_active }); await onChanged() }
    catch { setMsg({ ok: false, text: 'Güncellenemedi' }) }
  }

  const remove = async (v) => {
    try { await api.del(`/api/catalog/variants/${v.id}`); await onChanged() }
    catch { setMsg({ ok: false, text: 'Silinemedi' }) }
  }

  const cell = (v, field, display) => {
    const editing = edit?.id === v.id && edit?.field === field
    return editing ? (
      <input autoFocus type="number" step={field === 'price_override' ? '0.01' : '1'} min="0"
        className="input !py-0.5 !px-1.5 !w-24 text-right text-xs"
        value={edit.value}
        onChange={e => setEdit({ ...edit, value: e.target.value })}
        onBlur={commit}
        onKeyDown={e => { if (e.key === 'Enter') commit(); if (e.key === 'Escape') setEdit(null) }} />
    ) : (
      <button className="w-full text-right hover:bg-panel-input rounded px-1.5 py-0.5"
        onClick={() => setEdit({
          id: v.id, field,
          value: field === 'price_override' ? (v.price_override ?? '') : String(v.quantity),
        })}>
        {display}
      </button>
    )
  }

  return (
    <div className="max-h-96 overflow-y-auto border border-panel-border rounded-xl">
      <table className="w-full text-xs">
        <thead className="text-panel-muted bg-panel-input sticky top-0">
          <tr>
            <th className="text-left px-3 py-2">Marka</th>
            <th className="text-left px-3 py-2">Model</th>
            <th className="text-left px-3 py-2">Renk</th>
            <th className="text-right px-3 py-2">Fiyat (₺)</th>
            <th className="text-right px-3 py-2">Stok</th>
            <th className="text-center px-2 py-2">Aktif</th>
            <th className="px-2 py-2"></th>
          </tr>
        </thead>
        <tbody>
          {product.variants.map(v => (
            <tr key={v.id} className={`border-t border-panel-border ${!v.is_active ? 'opacity-50' : ''}`}>
              <td className="px-3 py-1.5 text-panel-muted">{v.brand || '—'}</td>
              <td className="px-3 py-1.5">{v.model_display}</td>
              <td className="px-3 py-1.5">{v.variation || '—'}</td>
              <td className="px-1 py-1 tabular-nums">
                {cell(v, 'price_override',
                  v.price_override != null
                    ? Number(v.price_override).toFixed(2)
                    : <span className="text-panel-muted">{Number(basePrice || 0).toFixed(2)}</span>)}
              </td>
              <td className="px-1 py-1 tabular-nums">
                {cell(v, 'quantity', v.track_stock ? v.quantity : '∞')}
              </td>
              <td className="px-2 py-1.5 text-center">
                <input type="checkbox" checked={v.is_active} onChange={() => toggleActive(v)} />
              </td>
              <td className="px-2 py-1.5 text-right">
                <button onClick={() => remove(v)} className="text-red-400 hover:text-red-600">×</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {product.variants.length === 0 && (
        <div className="text-xs text-panel-muted p-3">Henüz varyant yok.</div>
      )}
    </div>
  )
}
