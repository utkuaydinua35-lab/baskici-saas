import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useStore } from '../lib/store'
import { useToast } from '../components/Toast'
import RichTextEditor from '../components/RichTextEditor'

// TAM SAYFA ürün oluşturma (Shopify "Add product") — başlık, zengin açıklama,
// medya, fiyatlar, koleksiyonlar, SEO ve yayınlama tek ekranda.
// Varsayılan: Kaydet'e basınca HEMEN YAYINLANIR; istenirse taslak/planlı.
export default function UrunYeniPage() {
  const { storeId } = useStore()
  const navigate = useNavigate()
  const toast = useToast()

  const [form, setForm] = useState({
    title: '', description: '', base_price: '', compare_at_price: '',
    tags: '', seo_title: '', seo_description: '',
  })
  const [files, setFiles] = useState([])           // {file, url(önizleme)}
  const [collections, setCollections] = useState([])
  const [selectedCols, setSelectedCols] = useState([])
  const [publishMode, setPublishMode] = useState('active')  // active | draft | scheduled
  const [publishAt, setPublishAt] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!storeId) return
    api.get(`/api/catalog/collections?store_id=${storeId}`)
      .then(c => setCollections(c.filter(x => x.is_active))).catch(() => {})
  }, [storeId])

  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }))

  const addFiles = (list) => {
    const next = [...files]
    for (const f of Array.from(list || []).slice(0, 10 - next.length)) {
      next.push({ file: f, url: URL.createObjectURL(f) })
    }
    setFiles(next)
  }

  const save = async () => {
    if (!form.title.trim()) { toast.error('Ürün adı zorunlu'); return }
    if (!form.base_price || Number(form.base_price) <= 0) { toast.error('Geçerli bir fiyat girin'); return }
    if (publishMode === 'scheduled' && !publishAt) { toast.error('Yayın zamanı seçin'); return }
    setBusy(true)
    try {
      // 1) Ürünü oluştur
      const prod = await api.post('/api/catalog/products', {
        store_id: storeId,
        title: form.title.trim(),
        description: form.description || null,
        base_price: Number(form.base_price),
        compare_at_price: form.compare_at_price ? Number(form.compare_at_price) : null,
        tags: form.tags || null,
        seo_title: form.seo_title || null,
        seo_description: form.seo_description || null,
        status: publishMode === 'active' ? 'active' : 'draft',
      })
      // 2) Planlı yayın
      if (publishMode === 'scheduled') {
        await api.patch(`/api/catalog/products/${prod.id}`,
          { publish_at: new Date(publishAt).toISOString() })
      }
      // 3) Koleksiyonlar
      if (selectedCols.length > 0) {
        await api.put(`/api/catalog/products/${prod.id}/collections`,
          { collection_ids: selectedCols })
      }
      // 4) Görseller (tek istekte max 10)
      if (files.length > 0) {
        const fd = new FormData()
        for (const f of files) fd.append('files', f.file)
        try {
          await api.postForm(`/api/catalog/products/${prod.id}/images`, fd)
        } catch (e) {
          toast.error(typeof e?.detail === 'string'
            ? `Ürün oluştu ama görseller yüklenemedi: ${e.detail}`
            : 'Ürün oluştu ama görseller yüklenemedi — detaydan tekrar deneyin')
        }
      }
      toast.success(publishMode === 'active'
        ? 'Ürün oluşturuldu ve yayında ✓'
        : publishMode === 'scheduled' ? 'Ürün oluşturuldu — planlanan saatte yayınlanacak ⏰'
        : 'Ürün taslak olarak oluşturuldu')
      navigate(`/urunler/${prod.id}`)
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Ürün oluşturulamadı')
    } finally { setBusy(false) }
  }

  return (
    <div className="max-w-5xl space-y-4 pb-10">
      <div className="flex items-center gap-3 sticky top-0 bg-panel-bg py-2 z-10">
        <Link to="/urunler" className="text-panel-muted hover:text-panel-ink">←</Link>
        <h1 className="text-xl font-semibold">Yeni Ürün</h1>
        <button disabled={busy} onClick={save} className="btn-primary !py-1.5 ml-auto">
          {busy ? 'Oluşturuluyor…' : publishMode === 'active' ? 'Kaydet ve Yayınla' : 'Kaydet'}
        </button>
      </div>

      <div className="grid lg:grid-cols-[1fr_300px] gap-4 items-start">
        {/* ── Sol: içerik ── */}
        <div className="space-y-4 min-w-0">
          <section className="card space-y-3">
            <label className="block text-sm">
              <span className="text-panel-muted text-xs">Ürün adı *</span>
              <input className="input mt-1" value={form.title} onChange={set('title')}
                maxLength={300} placeholder='BERNZ "Sparkling Ocean" Tasarım Telefon Kılıfı' autoFocus />
            </label>
            <div>
              <span className="text-panel-muted text-xs">Açıklama</span>
              <RichTextEditor value={form.description}
                onChange={v => setForm(f => ({ ...f, description: v }))}
                placeholder="Ürün açıklaması — kalın, başlık, liste ve bağlantı kullanabilirsiniz…" />
            </div>
          </section>

          {/* Medya */}
          <section className="card space-y-3">
            <h2 className="text-sm font-semibold">Medya</h2>
            <label className="block border-2 border-dashed border-panel-border rounded-xl p-6 text-center cursor-pointer hover:border-panel-accent transition-colors">
              <input type="file" accept="image/*" multiple className="hidden"
                onChange={e => addFiles(e.target.files)} />
              <span className="text-sm text-panel-muted">
                📷 Görselleri seçin veya sürükleyin (25MB'a kadar, en fazla 10)
              </span>
            </label>
            {files.length > 0 && (
              <div className="grid grid-cols-5 gap-2">
                {files.map((f, i) => (
                  <div key={i} className="relative group">
                    <img src={f.url} alt="" className="w-full aspect-square object-cover rounded-xl border border-panel-border" />
                    {i === 0 && (
                      <span className="absolute bottom-1 left-1 text-[9px] bg-panel-accent text-[#04130d] px-1.5 py-0.5 rounded-full font-semibold">
                        Kapak
                      </span>
                    )}
                    <button onClick={() => setFiles(x => x.filter((_, j) => j !== i))}
                      className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-red-500 text-white text-xs opacity-0 group-hover:opacity-100 transition">×</button>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Fiyatlandırma */}
          <section className="card space-y-3">
            <h2 className="text-sm font-semibold">Fiyatlandırma</h2>
            <div className="grid grid-cols-2 gap-3">
              <label className="block text-sm">
                <span className="text-panel-muted text-xs">Fiyat (₺) *</span>
                <input className="input mt-1" type="number" step="0.01" min="0"
                  value={form.base_price} onChange={set('base_price')} placeholder="399.90" />
              </label>
              <label className="block text-sm">
                <span className="text-panel-muted text-xs">İndirim öncesi fiyat (₺)</span>
                <input className="input mt-1" type="number" step="0.01" min="0"
                  value={form.compare_at_price} onChange={set('compare_at_price')}
                  placeholder="üstü çizili görünür + %İNDİRİM rozeti" />
              </label>
            </div>
          </section>

          {/* SEO */}
          <section className="card space-y-3">
            <h2 className="text-sm font-semibold">Arama Motoru Liste Kaydı</h2>
            <label className="block text-sm">
              <span className="text-panel-muted text-xs">SEO başlığı</span>
              <input className="input mt-1" value={form.seo_title} onChange={set('seo_title')}
                maxLength={200} placeholder={form.title || 'Boşsa ürün adı kullanılır'} />
            </label>
            <label className="block text-sm">
              <span className="text-panel-muted text-xs">SEO açıklaması</span>
              <textarea className="input mt-1" rows={2} maxLength={400}
                value={form.seo_description} onChange={set('seo_description')}
                placeholder="Google sonuçlarında görünen kısa açıklama (boşsa açıklamadan üretilir)" />
            </label>
            {/* Google önizlemesi */}
            <div className="bg-panel-input rounded-xl p-3">
              <div className="text-[13px] text-sky-700 truncate">
                {form.seo_title || form.title || 'Ürün adı'}
              </div>
              <div className="text-[11px] text-emerald-700/80">magaza.bernzcompany.com › urun</div>
              <div className="text-[11px] text-panel-muted line-clamp-2">
                {form.seo_description || 'SEO açıklaması burada görünecek…'}
              </div>
            </div>
          </section>
        </div>

        {/* ── Sağ: durum + organizasyon ── */}
        <div className="space-y-4">
          <section className="card space-y-2.5">
            <h2 className="text-sm font-semibold">Yayınlama</h2>
            {[
              ['active', '🟢 Kaydedince yayınla', 'Ürün anında vitrinde görünür (varsayılan)'],
              ['draft', '📝 Taslak olarak kaydet', 'Siz yayınlayana kadar vitrinde görünmez'],
              ['scheduled', '⏰ İleri tarihte yayınla', 'Seçtiğiniz saatte kendiliğinden yayına girer'],
            ].map(([v, label, desc]) => (
              <label key={v} className={`block rounded-xl border px-3 py-2 cursor-pointer transition ${
                publishMode === v ? 'border-panel-accent bg-panel-accent/10' : 'border-panel-border'}`}>
                <span className="flex items-center gap-2 text-sm">
                  <input type="radio" name="pub" checked={publishMode === v}
                    onChange={() => setPublishMode(v)} />
                  {label}
                </span>
                <span className="block text-[11px] text-panel-muted mt-0.5 ml-5">{desc}</span>
              </label>
            ))}
            {publishMode === 'scheduled' && (
              <input type="datetime-local" className="input !py-1.5"
                min={new Date().toISOString().slice(0, 16)}
                value={publishAt} onChange={e => setPublishAt(e.target.value)} />
            )}
          </section>

          <section className="card space-y-2">
            <h2 className="text-sm font-semibold">Koleksiyonlar</h2>
            {collections.length === 0 ? (
              <p className="text-xs text-panel-muted">
                Henüz koleksiyon yok — <Link to="/koleksiyonlar" className="underline">oluşturun</Link>.
              </p>
            ) : (
              <div className="flex gap-1.5 flex-wrap">
                {collections.map(c => {
                  const on = selectedCols.includes(c.id)
                  return (
                    <button key={c.id} type="button"
                      onClick={() => setSelectedCols(x => on ? x.filter(i => i !== c.id) : [...x, c.id])}
                      className={`px-2.5 py-1 rounded-full text-xs border transition ${on
                        ? 'border-panel-accent bg-emerald-50 text-emerald-700 font-medium'
                        : 'border-panel-border text-panel-muted hover:text-panel-ink'}`}>
                      {c.title}
                    </button>
                  )
                })}
              </div>
            )}
          </section>

          <section className="card space-y-2">
            <h2 className="text-sm font-semibold">Etiketler</h2>
            <input className="input" value={form.tags} onChange={set('tags')} maxLength={500}
              placeholder="deniz, yaz-koleksiyonu (virgülle)" />
            <p className="text-[10px] text-panel-muted">
              Vitrinde filtre ve arama; ürün sayfasında rozet olarak görünür.
            </p>
          </section>

          <p className="text-[11px] text-panel-muted px-1">
            💡 Varyantlar (telefon modelleri), video ve kişiye özel alanlar ürün
            oluşturulduktan sonra açılan detay sayfasından eklenir — Varyant
            Setleri ile tek tıkla yüzlerce model bağlayabilirsiniz.
          </p>
        </div>
      </div>
    </div>
  )
}
