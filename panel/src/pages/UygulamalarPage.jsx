import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { useStore } from '../lib/store'
import { useToast } from '../components/Toast'
import { VariantSetsModal } from './UrunlerPage'

// Uygulamalar — sistem içi "uygulama" gibi çalışan gelişmiş özelliklerin
// merkezi: varyant setleri, kişiye özel alanlar (+ hazır düzenler), couple
// ürünler ve tasarım talepleri tek yerden yönetilir.
export default function UygulamalarPage() {
  const { storeId } = useStore()
  const [products, setProducts] = useState([])
  const [openApp, setOpenApp] = useState(null)   // null | 'sets' | 'fields' | 'couple'

  const load = useCallback(async () => {
    if (!storeId) return
    try { setProducts(await api.get(`/api/catalog/products?store_id=${storeId}`)) }
    catch { /* kartlar sayaçsız görünür */ }
  }, [storeId])
  useEffect(() => { load() }, [load])

  const withFields = products.filter(p => (p.custom_fields || []).length > 0)
  const couples = products.filter(p => (p.models_per_item || 1) === 2)
  const withSet = products.filter(p => p.variant_set_id)

  return (
    <div className="max-w-4xl space-y-5">
      <div>
        <h1 className="text-xl font-semibold">🧩 Uygulamalar</h1>
        <p className="text-xs text-panel-muted mt-1">
          Mağazanıza güç katan yerleşik uygulamalar — kurulum gerekmez, hepsi dahil.
        </p>
      </div>

      <div className="grid sm:grid-cols-2 gap-3">
        <AppCard icon="🧩" title="Varyant Setleri"
          desc="Model listesini tek yerden yönetin — seti düzenleyince bağlı tüm ürünler otomatik senkronlanır."
          stat={`${withSet.length} ürün sete bağlı`}
          cta="Setleri Yönet" onOpen={() => setOpenApp('sets')} />
        <AppCard icon="🎨" title="Kişiye Özel Alanlar"
          desc="Müşteriden yazı, fotoğraf veya renk seçimi isteyin. Hazır alan düzenleri oluşturup ürünlere tek tıkla uygulayın."
          stat={`${withFields.length} üründe aktif`}
          cta="Alanları Yönet" onOpen={() => setOpenApp('fields')} />
        <AppCard icon="👫" title="Couple Ürünler"
          desc="Tek üründe 2 telefon kılıfı — müşteri iki ayrı model seçer, üretim planına ikisi de düşer."
          stat={`${couples.length} couple ürün`}
          cta="Ürünleri Gör" onOpen={() => setOpenApp('couple')} />
        <div className="card !p-4 flex flex-col">
          <div className="text-2xl">🖌️</div>
          <div className="font-semibold text-sm mt-1.5">Tasarım Talepleri</div>
          <p className="text-xs text-panel-muted mt-1 flex-1">
            Müşteriler hesaplarından kendi tasarımlarını yükleyip talep açar; teklifle yanıtlayın.
          </p>
          <Link to="/tasarim-talepleri" className="btn-ghost !py-1.5 text-xs mt-3 self-start">
            Talepleri Aç →
          </Link>
        </div>
      </div>

      {openApp === 'sets' && (
        <VariantSetsModal storeId={storeId} onClose={() => { setOpenApp(null); load() }} />
      )}
      {openApp === 'fields' && (
        <FieldsApp storeId={storeId} products={withFields} onClose={() => setOpenApp(null)} />
      )}
      {openApp === 'couple' && (
        <ProductListModal title="👫 Couple Ürünler" products={couples}
          empty="Henüz couple ürün yok — ürün detayında 'Bu ürün 2 telefon kılıfı içerir' kutusunu işaretleyin."
          onClose={() => setOpenApp(null)} />
      )}
    </div>
  )
}

function AppCard({ icon, title, desc, stat, cta, onOpen }) {
  return (
    <div className="card !p-4 flex flex-col">
      <div className="text-2xl">{icon}</div>
      <div className="font-semibold text-sm mt-1.5">{title}</div>
      <p className="text-xs text-panel-muted mt-1 flex-1">{desc}</p>
      <div className="flex items-center mt-3">
        <span className="text-[11px] text-panel-muted">{stat}</span>
        <button onClick={onOpen} className="btn-ghost !py-1.5 text-xs ml-auto">{cta} →</button>
      </div>
    </div>
  )
}

// Basit modal (UrunlerPage'dekiyle aynı görünüm; bağımsız kopya).
function Modal({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 z-40 bg-black/40 flex items-start justify-center p-6 overflow-y-auto"
      onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-panel-card rounded-2xl shadow-xl w-full max-w-2xl p-5 my-6">
        <div className="flex items-center mb-3">
          <h2 className="text-base font-semibold">{title}</h2>
          <button onClick={onClose} className="ml-auto text-panel-muted hover:text-panel-ink">✕</button>
        </div>
        {children}
      </div>
    </div>
  )
}

function ProductListModal({ title, products, empty, onClose }) {
  return (
    <Modal title={title} onClose={onClose}>
      <div className="space-y-1.5">
        {products.map(p => (
          <Link key={p.id} to={`/urunler/${p.id}`}
            className="flex items-center gap-2.5 border border-panel-border rounded-xl px-3 py-2 text-sm hover:border-panel-accent transition">
            {p.cover_image
              ? <img src={p.cover_image} alt="" className="w-9 h-9 rounded-lg object-cover border border-panel-border" />
              : <span className="w-9 h-9 rounded-lg bg-panel-input flex items-center justify-center">📱</span>}
            <span className="flex-1 min-w-0 truncate font-medium">{p.title}</span>
            <span className="text-xs text-panel-muted">{p.status === 'active' ? 'yayında' : p.status}</span>
            <span className="text-xs text-panel-muted">Düzenle ›</span>
          </Link>
        ))}
        {products.length === 0 && (
          <p className="text-sm text-panel-muted text-center py-5">{empty}</p>
        )}
      </div>
    </Modal>
  )
}

// Kişiye Özel Alanlar uygulaması — hazır düzenler (preset) + kullanan ürünler.
function FieldsApp({ storeId, products, onClose }) {
  const toast = useToast()
  const [presets, setPresets] = useState([])
  const [busy, setBusy] = useState(false)
  const [editing, setEditing] = useState(null)  // {index|-1, name, fields}

  const load = useCallback(async () => {
    try {
      const r = await api.get(`/api/store-settings/${storeId}/custom-field-presets`)
      setPresets(r.presets || [])
    } catch { /* boş liste */ }
  }, [storeId])
  useEffect(() => { load() }, [load])

  const saveAll = async (next) => {
    setBusy(true)
    try {
      const r = await api.put(`/api/store-settings/${storeId}/custom-field-presets`, { presets: next })
      setPresets(r.presets || [])
      setEditing(null)
      toast.success('Hazır düzenler kaydedildi')
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Kaydedilemedi')
    } finally { setBusy(false) }
  }

  if (editing) {
    return (
      <Modal title={editing.index === -1 ? 'Yeni Hazır Düzen' : 'Düzeni Düzenle'} onClose={() => setEditing(null)}>
        <PresetEditor value={editing} busy={busy}
          onCancel={() => setEditing(null)}
          onSave={p => {
            const next = [...presets]
            if (editing.index === -1) next.push(p)
            else next[editing.index] = p
            saveAll(next)
          }} />
      </Modal>
    )
  }

  return (
    <Modal title="🎨 Kişiye Özel Alanlar" onClose={onClose}>
      <p className="text-xs text-panel-muted -mt-1 mb-3">
        Hazır düzenler; sık kullandığınız alan kombinasyonlarıdır (örn. "İsimli Kılıf" =
        yazı + renk). Ürün detayındaki Kişiye Özel Alanlar bölümünden tek tıkla uygulanır.
      </p>

      <h3 className="text-sm font-semibold mb-1.5">Hazır düzenler ({presets.length})</h3>
      <div className="space-y-1.5 mb-2">
        {presets.map((p, i) => (
          <div key={i} className="flex items-center gap-2 border border-panel-border rounded-xl px-3 py-2 text-sm">
            <span className="font-medium">{p.name}</span>
            <span className="text-xs text-panel-muted truncate">
              {p.fields.map(f => f.label).join(' · ')}
            </span>
            <span className="ml-auto flex gap-2 shrink-0">
              <button onClick={() => setEditing({ index: i, name: p.name, fields: structuredClone(p.fields) })}
                className="text-xs text-panel-muted hover:text-panel-ink">Düzenle</button>
              <button disabled={busy}
                onClick={() => window.confirm(`"${p.name}" düzeni silinsin mi? (Ürünlerdeki alanlar etkilenmez)`)
                  && saveAll(presets.filter((_, j) => j !== i))}
                className="text-xs text-red-300 hover:text-red-300">Sil</button>
            </span>
          </div>
        ))}
        {presets.length === 0 && (
          <p className="text-xs text-panel-muted py-2">Henüz hazır düzen yok.</p>
        )}
      </div>
      <button onClick={() => setEditing({ index: -1, name: '', fields: [{ label: '', type: 'text', required: false }] })}
        className="btn-ghost !py-1.5 text-xs">+ Yeni Hazır Düzen</button>

      <h3 className="text-sm font-semibold mt-5 mb-1.5">Kişiye özel alan kullanan ürünler ({products.length})</h3>
      <div className="space-y-1.5">
        {products.map(p => (
          <Link key={p.id} to={`/urunler/${p.id}`}
            className="flex items-center gap-2.5 border border-panel-border rounded-xl px-3 py-2 text-sm hover:border-panel-accent transition">
            <span className="flex-1 min-w-0 truncate font-medium">{p.title}</span>
            <span className="text-xs text-panel-muted truncate">
              {(p.custom_fields || []).map(f => f.label).join(' · ')}
            </span>
            <span className="text-xs text-panel-muted shrink-0">Düzenle ›</span>
          </Link>
        ))}
        {products.length === 0 && (
          <p className="text-xs text-panel-muted py-2">
            Henüz yok — ürün detayındaki "Kişiye Özel Alanlar" bölümünden ekleyin.
          </p>
        )}
      </div>
    </Modal>
  )
}

function PresetEditor({ value, busy, onSave, onCancel }) {
  const [name, setName] = useState(value.name)
  const [fields, setFields] = useState(value.fields)
  const patchF = (i, p) => setFields(f => f.map((x, j) => j === i ? { ...x, ...p } : x))

  return (
    <div className="space-y-2">
      <input className="input" value={name} maxLength={80} autoFocus
        onChange={e => setName(e.target.value)} placeholder="Düzen adı (örn. İsimli Kılıf)" />
      {fields.map((f, i) => (
        <div key={i} className="border border-panel-border rounded-xl p-2 space-y-1.5">
          <div className="flex gap-1.5">
            <input className="input !py-1.5 text-xs flex-1" value={f.label || ''} maxLength={80}
              onChange={e => patchF(i, { label: e.target.value })} placeholder="Alan adı" />
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
            <button onClick={() => setFields(fl => fl.filter((_, j) => j !== i))}
              className="text-red-300 hover:text-red-300 px-1">×</button>
          </div>
          {f.type === 'color' && (
            <input className="input !py-1.5 text-xs" value={(f.options || []).join(', ')}
              onChange={e => patchF(i, { options: e.target.value.split(',').map(x => x.trim()).filter(Boolean) })}
              placeholder="Seçenekler (virgülle): Beyaz, Siyah, Altın" />
          )}
        </div>
      ))}
      {fields.length < 6 && (
        <button onClick={() => setFields(f => [...f, { label: '', type: 'text', required: false }])}
          className="btn-ghost !py-1 text-xs">+ Alan Ekle</button>
      )}
      <div className="flex justify-end gap-2 pt-1">
        <button onClick={onCancel} className="btn-ghost !py-1.5 text-xs">Vazgeç</button>
        <button onClick={() => onSave({ name: name.trim(), fields })}
          disabled={busy || !name.trim() || !fields.some(f => (f.label || '').trim())}
          className="btn-primary !py-1.5 text-xs">Kaydet</button>
      </div>
    </div>
  )
}
