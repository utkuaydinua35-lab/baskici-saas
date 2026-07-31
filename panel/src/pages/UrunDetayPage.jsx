import { Fragment, useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../lib/api'
import { useStore } from '../lib/store'
import { useToast } from '../components/Toast'
import { StatusBadge } from './UrunlerPage'
import RichTextEditor from '../components/RichTextEditor'

// Tam sayfa ürün editörü — görsel sıralama (drag), inline varyant editi, SEO.
export default function UrunDetayPage() {
  const { productId } = useParams()
  const navigate = useNavigate()
  const { storeId, store } = useStore()
  const [p, setP] = useState(null)
  const [vsets, setVsets] = useState([])
  const [collections, setCollections] = useState([])
  const [form, setForm] = useState(null)
  const [busy, setBusy] = useState(false)
  const toast = useToast()
  // Alt bölümler setMsg({ok,text}) imzasını kullanıyor — toast köprüsü
  const setMsg = (m) => m && (m.ok ? toast.success(m.text) : toast.error(m.text))
  const [variations, setVariations] = useState('')

  const draftKey = `urun-taslak-${productId}`

  const load = useCallback(async () => {
    try {
      const prod = await api.get(`/api/catalog/products/${productId}`)
      setP(prod)
      api.get(`/api/catalog/variant-sets?store_id=${prod.store_id}`)
        .then(setVsets).catch(() => {})
      const base = {
        title: prod.title, slug: prod.slug,
        base_price: prod.base_price, compare_at_price: prod.compare_at_price || '',
        cost_price: prod.cost_price || '',
        description: prod.description || '', tags: prod.tags || '',
        seo_title: prod.seo_title || '', seo_description: prod.seo_description || '',
      }
      // Kaydedilmemiş taslak varsa GERİ YÜKLE — koleksiyon ekleme gibi ara
      // işlemler ya da yanlışlıkla kapatma, yazılanları kaybettirmesin.
      let restored = false
      try {
        const raw = localStorage.getItem(draftKey)
        if (raw) {
          const draft = JSON.parse(raw)
          if (JSON.stringify(draft) !== JSON.stringify(base)) {
            setForm(draft)
            restored = true
            toast.info('Kaydedilmemiş değişiklikleriniz geri yüklendi — Kaydet ile kalıcılaşır')
          } else {
            localStorage.removeItem(draftKey)
          }
        }
      } catch { /* bozuk taslak yok sayılır */ }
      if (!restored) setForm(base)
      if (storeId) {
        setCollections((await api.get(`/api/catalog/collections?store_id=${storeId}`))
          .filter(c => c.is_active))
      }
    } catch (e) {
      setMsg({ ok: false, text: typeof e?.detail === 'string' ? e.detail : 'Ürün yüklenemedi' })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId, storeId])
  useEffect(() => { load() }, [load])

  // Form değiştikçe taslağı önbelleğe yaz (Kaydet'te temizlenir)
  useEffect(() => {
    if (!form) return
    try { localStorage.setItem(draftKey, JSON.stringify(form)) } catch { /* dolu */ }
  }, [form, draftKey])

  // Koleksiyon/görsel gibi FORM DIŞI işlemler sonrası: ürünü tazele ama
  // formdaki kaydedilmemiş değişikliklere DOKUNMA.
  const reloadMeta = useCallback(async () => {
    try {
      const prod = await api.get(`/api/catalog/products/${productId}`)
      setP(prod)
      if (storeId) {
        setCollections((await api.get(`/api/catalog/collections?store_id=${storeId}`))
          .filter(c => c.is_active))
      }
    } catch { /* sessiz */ }
  }, [productId, storeId])

  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }))

  const save = async () => {
    setBusy(true); setMsg(null)
    try {
      await api.patch(`/api/catalog/products/${p.id}`, {
        title: form.title, slug: form.slug || null,
        base_price: Number(form.base_price),
        compare_at_price: form.compare_at_price ? Number(form.compare_at_price) : null,
        cost_price: form.cost_price ? Number(form.cost_price) : null,
        description: form.description || null, tags: form.tags || null,
        seo_title: form.seo_title || null, seo_description: form.seo_description || null,
      })
      try { localStorage.removeItem(draftKey) } catch { /* yok */ }
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
                className="px-3 py-1.5 rounded-xl text-xs bg-emerald-50 text-emerald-700">Yayınla</button>
            : <button disabled={busy} onClick={() => patchStatus('draft')}
                className="px-3 py-1.5 rounded-xl text-xs bg-slate-100 text-slate-600">Taslağa Al</button>}
          <button disabled={busy} onClick={duplicate} className="btn-ghost !py-1.5 text-xs">Çoğalt</button>
          <button disabled={busy} onClick={removeProduct}
            className="px-3 py-1.5 rounded-xl text-xs bg-red-50 text-red-700">Sil</button>
          <button disabled={busy} onClick={save} className="btn-primary !py-1.5">Kaydet</button>
        </div>
      </div>

      {p.status === 'draft' && (
        <div className="card !py-2.5 flex items-center gap-3 text-sm border-indigo-500/30 bg-indigo-50">
          <span>⏰</span>
          {p.publish_at ? (
            <>
              <span className="text-indigo-700">
                <b>{new Date(p.publish_at).toLocaleString('tr-TR', {
                  day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })}</b>'de
                otomatik yayınlanacak
              </span>
              <button onClick={() => schedulePublish(null)} disabled={busy}
                className="ml-auto text-xs text-indigo-700 underline">Planı kaldır</button>
            </>
          ) : (
            <>
              <span className="text-indigo-700">Yayın zamanı planla:</span>
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
        <div className="grid grid-cols-3 gap-3">
          <Field label="Birim maliyet (₺, ops.)">
            <input className="input mt-1" type="number" step="0.01" min="0"
              value={form.cost_price} onChange={set('cost_price')} placeholder="kâr raporu için" />
            <span className="block text-[11px] text-panel-muted mt-0.5">
              Müşteriye görünmez. Boşsa Ayarlar'daki varsayılan birim maliyet kullanılır.
              {form.cost_price && form.base_price ? ` Marj: %${Math.round(100*(form.base_price-form.cost_price)/form.base_price)}` : ''}
            </span>
          </Field>
        </div>
        <Field label="Açıklama">
          <RichTextEditor value={form.description}
            onChange={v => setForm(f => ({ ...f, description: v }))}
            placeholder="Ürün açıklaması — kalın, başlık, liste ve bağlantı kullanabilirsiniz…" />
        </Field>
        <div className="text-sm">
          <span className="text-panel-muted text-xs">
            🎬 Ürün videosu (mp4/webm, max 100MB — galeride ▶ karesi, kartta hover'da oynar)
          </span>
          <div className="mt-1 flex items-center gap-3">
            {p.video_url ? (
              <>
                <video src={p.video_url} muted loop playsInline
                  onMouseEnter={e => e.target.play()} onMouseLeave={e => e.target.pause()}
                  className="h-20 rounded-lg border border-panel-border bg-black" />
                <button type="button" disabled={busy}
                  onClick={async () => {
                    try { await api.del(`/api/catalog/products/${p.id}/video`); await load() }
                    catch { setMsg({ ok: false, text: 'Video kaldırılamadı' }) }
                  }}
                  className="text-xs text-red-600 hover:text-red-600">Videoyu Kaldır</button>
              </>
            ) : (
              <label className="btn-ghost !py-1.5 text-xs cursor-pointer">
                {busy ? 'Yükleniyor…' : '⬆ Video Yükle'}
                <input type="file" accept="video/mp4,video/webm,video/quicktime" className="hidden"
                  disabled={busy}
                  onChange={async e => {
                    const file = e.target.files?.[0]
                    if (!file) return
                    setBusy(true)
                    try {
                      const fd = new FormData()
                      fd.append('file', file)
                      await api.postForm(`/api/catalog/products/${p.id}/video`, fd)
                      await load()
                      setMsg({ ok: true, text: 'Video yüklendi 🎬' })
                    } catch (e2) {
                      setMsg({ ok: false, text: typeof e2?.detail === 'string' ? e2.detail : 'Video yüklenemedi' })
                    } finally { setBusy(false) }
                  }} />
              </label>
            )}
          </div>
        </div>
        <Field label="Etiketler (virgülle)">
          <input className="input mt-1" value={form.tags} onChange={set('tags')} maxLength={500}
            placeholder="retro, minimal, yaz" />
        </Field>
      </section>

      <ImagesSection product={p} onChanged={reloadMeta} setMsg={setMsg} />

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

      <section className="card space-y-2">
          <h2 className="text-sm font-semibold">Koleksiyonlar</h2>
          <div className="flex gap-2 flex-wrap items-center">
            {collections.map(c => {
              const active = (p.collection_ids || []).includes(c.id)
              // Akıllı koleksiyon üyeliği kuralın sonucudur — elle değiştirilemez
              if (c.is_smart) {
                return (
                  <span key={c.id}
                    title="Akıllı koleksiyon — üyelik kurala göre otomatik belirlenir"
                    className={`px-3 py-1 rounded-full text-xs border ${active
                      ? 'border-indigo-200 bg-indigo-50 text-indigo-700'
                      : 'border-panel-border text-panel-muted opacity-60'}`}>
                    ⚙️ {c.title}
                  </span>
                )
              }
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
            <InlineCollectionCreate storeId={storeId} productId={p.id}
              currentIds={p.collection_ids || []} onDone={reloadMeta} setMsg={setMsg} />
          </div>
        </section>

      <section className="card space-y-3">
        <h2 className="text-sm font-semibold">🎨 Kişiye Özel Alanlar ve Set Ürünü</h2>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={(p.models_per_item || 1) >= 2}
            onChange={async e => {
              try {
                await api.patch(`/api/catalog/products/${p.id}`,
                  { models_per_item: e.target.checked ? 2 : 1 })
                await load()
              } catch { setMsg({ ok: false, text: 'Güncellenemedi' }) }
            }} />
          👫 Çift kılıf seti (couple) — müşteri <b>2 telefon modeli</b> seçer,
          üretime iki kalem düşer
        </label>
        <CustomFieldsEditor product={p} onChanged={reloadMeta} setMsg={setMsg} />
      </section>

      <CrossSellEditor product={p} onChanged={reloadMeta} setMsg={setMsg} />

      <section className="card space-y-3">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold">Varyantlar ({p.variants.length})</h2>
          <span className="text-[11px] text-panel-muted">— fiyat/stok hücresine tıklayıp düzenleyin</span>
        </div>
        <div className="flex items-center gap-2 text-sm bg-panel-input rounded-xl px-3 py-2">
          <span className="text-xs text-panel-muted">🧩 Hazır set:</span>
          <select className="input !py-1.5 !w-56 text-xs" value={p.variant_set_id || ''}
            onChange={async e => {
              const v = e.target.value
              if (v && !window.confirm('Set uygulanınca mevcut varyantlar set listesine göre '
                  + 'güncellenir (sette olmayanlar silinir). Devam?')) { load(); return }
              try {
                const r = await api.post(`/api/catalog/products/${p.id}/apply-variant-set`,
                  { variant_set_id: v || null })
                setMsg({ ok: true, text: v
                  ? `"${r.applied}" uygulandı — ${r.created} yeni, ${r.updated} güncel, ${r.deleted} silindi`
                  : 'Set bağlantısı kaldırıldı (varyantlar yerinde)' })
                await load()
              } catch { setMsg({ ok: false, text: 'Set uygulanamadı' }) }
            }}>
            <option value="">Sete bağlı değil</option>
            {vsets.map(vs => <option key={vs.id} value={vs.id}>{vs.name} ({vs.items.length} model)</option>)}
          </select>
          {p.variant_set_id && (
            <span className="text-[11px] text-emerald-700">
              ✓ Set düzenlenince bu ürün otomatik güncellenir
            </span>
          )}
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
              } catch (e2) {
                setMsg({ ok: false, text: typeof e2?.detail === 'string'
                  ? e2.detail : 'Varyantlar oluşturulamadı' })
              }
              finally { setBusy(false) }
            }}>
            Telefon modellerinden üret
          </button>
        </div>
        <VariantTable product={p} basePrice={form.base_price} onChanged={reloadMeta} setMsg={setMsg} />
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
      className={`card space-y-3 transition ${dropActive ? 'ring-2 ring-panel-accent ring-offset-2 !bg-emerald-50' : ''}`}
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
  const [collapsed, setCollapsed] = useState({})   // {marka: true} — kapalı gruplar
  const [brandEdit, setBrandEdit] = useState(null) // {old, value} — marka adı düzenleme

  const commit = async () => {
    if (!edit) return
    const { id, field, value } = edit
    setEdit(null)
    const payload = field === 'price_override'
      ? { price_override: value === '' ? null : Number(value) }
      : field === 'model_display'
        ? { model_display: String(value).trim() }
        : { quantity: Math.max(0, parseInt(value || '0', 10)) }
    if (field === 'model_display' && !payload.model_display) return
    try { await api.patch(`/api/catalog/variants/${id}`, payload); await onChanged() }
    catch { setMsg({ ok: false, text: 'Varyant güncellenemedi' }) }
  }

  const commitBrand = async () => {
    if (!brandEdit) return
    const { old, value } = brandEdit
    setBrandEdit(null)
    const next = String(value).trim()
    if (!next || next === old) return
    try {
      await api.post(`/api/catalog/products/${product.id}/variants/rename-brand`, { old, new: next })
      await onChanged()
    } catch { setMsg({ ok: false, text: 'Marka adı güncellenemedi' }) }
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
    const isText = field === 'model_display'
    return editing ? (
      <input autoFocus type={isText ? 'text' : 'number'}
        step={field === 'price_override' ? '0.01' : '1'} min="0"
        className={`input !py-0.5 !px-1.5 text-xs ${isText ? '!w-full text-left' : '!w-24 text-right'}`}
        value={edit.value}
        onChange={e => setEdit({ ...edit, value: e.target.value })}
        onBlur={commit}
        onKeyDown={e => { if (e.key === 'Enter') commit(); if (e.key === 'Escape') setEdit(null) }} />
    ) : (
      <button className={`w-full hover:bg-panel-input rounded px-1.5 py-0.5 ${isText ? 'text-left' : 'text-right'}`}
        title={isText ? 'Adı düzenlemek için tıkla' : undefined}
        onClick={() => setEdit({
          id: v.id, field,
          value: field === 'price_override' ? (v.price_override ?? '')
            : field === 'model_display' ? v.model_display
            : String(v.quantity),
        })}>
        {display}
      </button>
    )
  }

  // Marka bazlı gruplar — başlık satırı tıklayınca grup kapanıp açılır
  const groups = []
  for (const v of product.variants) {
    const key = v.brand || 'Diğer'
    const g = groups.find(x => x.brand === key)
    if (g) g.items.push(v)
    else groups.push({ brand: key, items: [v] })
  }

  return (
    <div className="max-h-96 overflow-y-auto border border-panel-border rounded-xl">
      <table className="w-full text-xs">
        <thead className="text-panel-muted bg-panel-input sticky top-0">
          <tr>
            <th className="text-left px-3 py-2">Model</th>
            <th className="text-left px-3 py-2">Renk</th>
            <th className="text-right px-3 py-2">Fiyat (₺)</th>
            <th className="text-right px-3 py-2">Stok</th>
            <th className="text-center px-2 py-2">Aktif</th>
            <th className="px-2 py-2"></th>
          </tr>
        </thead>
        <tbody>
          {groups.map(g => (
            <Fragment key={g.brand}>
              <tr className="border-t border-panel-border bg-panel-input/60">
                <td colSpan={6} className="px-2 py-1">
                  <div className="flex items-center gap-1.5">
                    <button onClick={() => setCollapsed(c => ({ ...c, [g.brand]: !c[g.brand] }))}
                      className="flex items-center gap-1.5 font-medium hover:text-panel-accent"
                      title={collapsed[g.brand] ? 'Grubu aç' : 'Grubu kısalt'}>
                      <span className="inline-block w-3 text-center">{collapsed[g.brand] ? '▸' : '▾'}</span>
                      {brandEdit?.old === g.brand ? null : g.brand}
                      <span className="text-panel-muted font-normal">({g.items.length})</span>
                    </button>
                    {brandEdit?.old === g.brand ? (
                      <input autoFocus className="input !py-0.5 !px-1.5 !w-40 text-xs"
                        value={brandEdit.value}
                        onChange={e => setBrandEdit({ ...brandEdit, value: e.target.value })}
                        onBlur={commitBrand}
                        onKeyDown={e => { if (e.key === 'Enter') commitBrand(); if (e.key === 'Escape') setBrandEdit(null) }} />
                    ) : (
                      <button onClick={() => setBrandEdit({ old: g.brand, value: g.brand })}
                        className="text-panel-muted hover:text-panel-accent" title="Marka adını düzenle">✎</button>
                    )}
                  </div>
                </td>
              </tr>
              {!collapsed[g.brand] && g.items.map(v => (
                <tr key={v.id} className={`border-t border-panel-border ${!v.is_active ? 'opacity-50' : ''}`}>
                  <td className="px-1 py-1 pl-5">{cell(v, 'model_display', v.model_display)}</td>
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
                    <button onClick={() => remove(v)} className="text-red-600 hover:text-red-600">×</button>
                  </td>
                </tr>
              ))}
            </Fragment>
          ))}
        </tbody>
      </table>
      {product.variants.length === 0 && (
        <div className="text-xs text-panel-muted p-3">Henüz varyant yok.</div>
      )}
    </div>
  )
}

// Kişiye özel alanlar — müşteriden checkout'ta istenecek girdiler.
// Sepette "bunu da ekleyin" — bu ürün sepetteyken önerilecek ürünler.
// Boş bırakılırsa sistem birlikte satılanlardan otomatik seçer.
function CrossSellEditor({ product, onChanged, setMsg }) {
  const { storeId } = useStore()
  const [all, setAll] = useState([])
  const [picked, setPicked] = useState(product.cross_sell_slugs || [])
  const [q, setQ] = useState('')
  const [dirty, setDirty] = useState(false)

  useEffect(() => { setPicked(product.cross_sell_slugs || []); setDirty(false) }, [product.id])
  useEffect(() => {
    if (!storeId) return
    api.get(`/api/catalog/products?store_id=${storeId}&status=active`)
      .then(r => setAll(r.filter(x => x.id !== product.id))).catch(() => {})
  }, [storeId, product.id])

  const toggle = (slug) => {
    setPicked(p => p.includes(slug) ? p.filter(s => s !== slug) : [...p, slug].slice(0, 6))
    setDirty(true)
  }

  const save = async () => {
    try {
      await api.patch(`/api/catalog/products/${product.id}`, { cross_sell_slugs: picked })
      setMsg({ ok: true, text: 'Öneriler kaydedildi' })
      setDirty(false); onChanged()
    } catch { setMsg({ ok: false, text: 'Kaydedilemedi' }) }
  }

  const results = q.trim()
    ? all.filter(p => p.title.toLowerCase().includes(q.trim().toLowerCase())).slice(0, 8)
    : []
  const bySlug = Object.fromEntries(all.map(p => [p.slug, p]))

  return (
    <section className="card space-y-2.5">
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-semibold">✨ Sepette Öner (Cross-sell)</h2>
        {dirty && <button onClick={save} className="ml-auto btn-primary !py-1 text-xs">Kaydet</button>}
      </div>
      <p className="text-[11px] text-panel-muted -mt-1">
        Bu ürün sepetteyken müşteriye önerilecek ürünler. Boş bırakırsanız sistem
        <b> birlikte satılanlardan</b> otomatik seçer.
      </p>
      {picked.length > 0 && (
        <div className="flex gap-2 flex-wrap">
          {picked.map(slug => (
            <span key={slug}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 text-xs">
              {bySlug[slug]?.title?.slice(0, 30) || slug}
              <button onClick={() => toggle(slug)} className="hover:text-red-600">×</button>
            </span>
          ))}
        </div>
      )}
      {picked.length < 6 && (
        <>
          <input className="input" value={q} onChange={e => setQ(e.target.value)}
            placeholder="Ürün ara ve ekle…" />
          {results.length > 0 && (
            <div className="space-y-1">
              {results.map(p => (
                <button key={p.id} onClick={() => { toggle(p.slug); setQ('') }}
                  className="w-full flex items-center gap-2 text-left text-sm px-3 py-1.5 rounded-lg hover:bg-panel-input">
                  <span className="truncate">{p.title}</span>
                  <span className="ml-auto text-xs text-panel-muted">+ ekle</span>
                </button>
              ))}
            </div>
          )}
        </>
      )}
    </section>
  )
}

function CustomFieldsEditor({ product, onChanged, setMsg }) {
  const { storeId } = useStore()
  const [fields, setFields] = useState(product.custom_fields || [])
  const [dirtyF, setDirtyF] = useState(false)
  const [presets, setPresets] = useState([])
  useEffect(() => { setFields(product.custom_fields || []); setDirtyF(false) }, [product.id])
  useEffect(() => {
    if (!storeId) return
    api.get(`/api/store-settings/${storeId}/custom-field-presets`)
      .then(r => setPresets(r.presets || [])).catch(() => {})
  }, [storeId])

  const patchF = (i, p2) => { setFields(f => f.map((x, j) => j === i ? { ...x, ...p2 } : x)); setDirtyF(true) }

  const save = async () => {
    try {
      await api.patch(`/api/catalog/products/${product.id}`, { custom_fields: fields })
      setMsg({ ok: true, text: 'Kişiye özel alanlar kaydedildi' })
      setDirtyF(false)
      onChanged()
    } catch { setMsg({ ok: false, text: 'Kaydedilemedi' }) }
  }

  return (
    <div className="space-y-2">
      <p className="text-[11px] text-panel-muted">
        Müşteriden istenecek ek bilgiler — yazı, fotoğraf ya da renk seçimi.
        Cevaplar sipariş detayında ve üretim kaleminde görünür.
      </p>
      {presets.length > 0 && (
        <select className="input !py-1.5 text-xs" value=""
          onChange={e => {
            const p = presets[Number(e.target.value)]
            if (p) { setFields(structuredClone(p.fields)); setDirtyF(true) }
          }}>
          <option value="">📋 Hazır düzen uygula… (Uygulamalar sayfasından yönetilir)</option>
          {presets.map((p, i) => (
            <option key={i} value={i}>{p.name} — {p.fields.map(f => f.label).join(', ')}</option>
          ))}
        </select>
      )}
      {fields.map((f, i) => (
        <div key={i} className="border border-panel-border rounded-xl p-2 space-y-1.5">
          <div className="flex gap-1.5">
            <input className="input !py-1.5 text-xs flex-1" value={f.label || ''} maxLength={80}
              onChange={e => patchF(i, { label: e.target.value })}
              placeholder="Alan adı (örn: Kılıf Üzeri Yazı)" />
            <select className="input !py-1.5 text-xs !w-28" value={f.type || 'text'}
              onChange={e => patchF(i, { type: e.target.value })}>
              <option value="text">Yazı</option>
              <option value="image">Fotoğraf</option>
              <option value="color">Renk seçimi</option>
            </select>
            <label className="text-[11px] flex items-center gap-1 whitespace-nowrap">
              <input type="checkbox" checked={!!f.required}
                onChange={e => patchF(i, { required: e.target.checked })} /> zorunlu
            </label>
            <button onClick={() => { setFields(fl => fl.filter((_, j) => j !== i)); setDirtyF(true) }}
              className="text-red-600 hover:text-red-600 px-1">×</button>
          </div>
          {f.type === 'color' && (
            <input className="input !py-1.5 text-xs" value={(f.options || []).join(', ')}
              onChange={e => patchF(i, { options: e.target.value.split(',').map(x => x.trim()).filter(Boolean) })}
              placeholder="Seçenekler (virgülle): Beyaz, Siyah, Altın" />
          )}
        </div>
      ))}
      <div className="flex gap-2">
        {fields.length < 6 && (
          <button onClick={() => { setFields(f => [...f, { label: '', type: 'text', required: false }]); setDirtyF(true) }}
            className="btn-ghost !py-1 text-xs">+ Alan Ekle</button>
        )}
        {dirtyF && (
          <button onClick={save} className="btn-primary !py-1 text-xs ml-auto">Alanları Kaydet</button>
        )}
      </div>
    </div>
  )
}

// Üründen ayrılmadan yeni koleksiyon oluştur + ürünü içine at.
function InlineCollectionCreate({ storeId, productId, currentIds, onDone, setMsg }) {
  const [open, setOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [busy, setBusy] = useState(false)

  const create = async () => {
    if (!title.trim()) return
    setBusy(true)
    try {
      const c = await api.post('/api/catalog/collections',
        { store_id: storeId, title: title.trim() })
      await api.put(`/api/catalog/products/${productId}/collections`,
        { collection_ids: [...currentIds, c.id] })
      setMsg({ ok: true, text: `"${c.title}" koleksiyonu oluşturuldu ve ürün eklendi ✓` })
      setTitle(''); setOpen(false)
      onDone()
    } catch (e) {
      setMsg({ ok: false, text: typeof e?.detail === 'string' ? e.detail : 'Oluşturulamadı' })
    } finally { setBusy(false) }
  }

  if (!open) {
    return (
      <button onClick={() => setOpen(true)}
        className="px-3 py-1 rounded-full text-xs border border-dashed border-panel-border
          text-panel-muted hover:text-panel-ink hover:border-panel-accent transition">
        + Yeni Koleksiyon
      </button>
    )
  }
  return (
    <span className="inline-flex gap-1.5 items-center">
      <input autoFocus className="input !py-1 !w-40 text-xs" value={title} maxLength={200}
        onChange={e => setTitle(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); create() }
          if (e.key === 'Escape') setOpen(false) }}
        placeholder="Koleksiyon adı" />
      <button onClick={create} disabled={busy || !title.trim()}
        className="text-xs text-emerald-700 font-medium disabled:opacity-40">Oluştur</button>
      <button onClick={() => setOpen(false)} className="text-xs text-panel-muted">Vazgeç</button>
    </span>
  )
}
