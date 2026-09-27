// Tema editörünün ortak parçaları — bölüm tipleri, varsayılanlar ve ayar formları.
// TemaEditorPage kullanır; TemaPage (kütüphane) yalnızca SECTION_TYPES'a bakar.
/* eslint-disable react-refresh/only-export-components */
import { useState } from 'react'

export const FONTS = [
  { key: 'inter', label: 'Inter (modern, varsayılan)' },
  { key: 'poppins', label: 'Poppins (yuvarlak, samimi)' },
  { key: 'playfair', label: 'Playfair Display (şık, serif)' },
  { key: 'dm-sans', label: 'DM Sans (sade, geometrik)' },
]

export const SECTION_TYPES = {
  hero_slider: { label: 'Hero / Slayt Gösterisi', icon: '🌅' },
  featured_collections: { label: 'Koleksiyon Kartları', icon: '🗂️' },
  products_grid: { label: 'Ürün Izgarası', icon: '🛍️' },
  featured_products: { label: 'Öne Çıkan Ürünler (elle seç)', icon: '🌟' },
  rich_text: { label: 'Metin Bölümü', icon: '📝' },
  banner: { label: 'Banner Görseli', icon: '🖼️' },
  image_with_text: { label: 'Görsel + Metin', icon: '🏞️' },
  faq: { label: 'SSS (Akordeon)', icon: '❓' },
  newsletter: { label: 'Bülten Kaydı', icon: '📮' },
  icon_bar: { label: 'İkon Şeridi (Avantajlar)', icon: '✨' },
  comparison: { label: 'Karşılaştırma (Biz vs Diğerleri)', icon: '⚖️' },
  testimonials: { label: 'Müşteri Yorumları Vitrini', icon: '💬' },
  gallery: { label: 'Görsel Galerisi', icon: '🖼️' },
  contact: { label: 'İletişim Formu', icon: '✉️' },
  countdown: { label: 'Kampanya Geri Sayımı', icon: '⏳' },
}

export const SECTION_DEFAULTS = {
  hero_slider: { slides: [], autoplay_sec: 5, radius_scope: 'both', radius_pct: 50, align: 'center', height: 'normal' },
  featured_collections: { eyebrow: '', title: 'Koleksiyonlar', subtitle: '', slugs: [], layout: 'grid', limit: 4 },
  products_grid: { eyebrow: '', title: 'Öne Çıkanlar', subtitle: '', collection: null, limit: 8, layout: 'grid' },
  featured_products: { eyebrow: '', title: 'Öne Çıkan Ürünler', subtitle: '', slugs: [], layout: 'grid' },
  rich_text: { title: '', body: '' },
  banner: { image: null, url: '', radius_scope: 'both', radius_pct: 50 },
  image_with_text: { image: null, title: '', body: '', cta_text: '', cta_url: '', image_side: 'left' },
  faq: { title: 'Sıkça Sorulan Sorular', items: [] },
  newsletter: { title: 'Kampanyalardan haberdar olun', subtitle: 'İndirim ve yeni tasarımlar e-postanıza gelsin.' },
  icon_bar: { items: [{ icon: '🚚', title: 'Hızlı Kargo', text: '1-3 iş gününde kargoda' }] },
  comparison: { title: 'Neden Biz?', us_label: 'Biz', them_label: 'Diğerleri',
    rows: [{ feature: 'Kişiye özel baskı kalitesi', us: true, them: false }] },
  testimonials: { eyebrow: '', title: 'Müşterilerimiz Ne Diyor?', subtitle: '', items: [] },
  gallery: { eyebrow: '', title: 'Sizden Gelenler', subtitle: '', images: [], aspect: 'square', mode: 'scroll' },
  contact: { title: 'İletişim', subtitle: 'Soru ve önerileriniz için bize yazın.' },
  countdown: { title: 'Kampanya bitiyor!', subtitle: '', ends_at: '',
    cta_text: 'Alışverişe Başla', cta_url: '/urunler' },
}

// CTA/link hedef seçici — koleksiyon, ürün, sayfa hazır listeden seçilir;
// "Özel URL" ile serbest adres de girilebilir (Shopify link picker).
export function UrlPicker({ value, onChange, collections = [], products = [], pages = [], placeholder = 'Hedef seçin' }) {
  const presets = [
    { url: '/urunler', label: '🛍️ Tüm Ürünler' },
    ...collections.map(c => ({ url: `/koleksiyon/${c.slug}`, label: `🗂️ ${c.title}` })),
    ...products.map(p => ({ url: `/urun/${p.slug}`, label: `📱 ${p.title}` })),
    ...pages.map(p => ({ url: `/sayfa/${p.slug}`, label: `📄 ${p.title}` })),
  ]
  const isPreset = presets.some(p => p.url === value)
  const [forceCustom, setForceCustom] = useState(false)
  const custom = forceCustom || (!!value && !isPreset)
  return (
    <div className="space-y-1.5">
      <select className="input" value={custom ? '__ozel' : (value || '')}
        onChange={e => {
          if (e.target.value === '__ozel') { setForceCustom(true); if (isPreset) onChange('') }
          else { setForceCustom(false); onChange(e.target.value) }
        }}>
        <option value="">{placeholder}</option>
        {presets.map(p => <option key={p.url} value={p.url}>{p.label}</option>)}
        <option value="__ozel">✏️ Özel URL…</option>
      </select>
      {custom && (
        <input className="input" value={value || ''}
          onChange={e => onChange(e.target.value)} placeholder="/sayfa/hakkimizda veya https://…" />
      )}
    </div>
  )
}

// Bölüm başlığı üçlüsü — üst etiket / başlık / alt başlık.
// Tema "Büyük ortalı başlık" stilindeyken üst etiket ve alt başlık öne çıkar.
function HeadingFields({ s, patch, titlePlaceholder = 'Bölüm başlığı' }) {
  return (
    <>
      <input className="input" value={s.eyebrow || ''} maxLength={60}
        onChange={e => patch({ eyebrow: e.target.value })}
        placeholder="Üst etiket (ops.) — örn. SENİN İÇİN SEÇTİK" />
      <input className="input" value={s.title || ''} maxLength={100}
        onChange={e => patch({ title: e.target.value })} placeholder={titlePlaceholder} />
      <input className="input" value={s.subtitle || ''} maxLength={200}
        onChange={e => patch({ subtitle: e.target.value })}
        placeholder="Alt başlık (ops.) — örn. En sevilen tasarımları keşfet." />
    </>
  )
}

// Hap şeklinde tek seçim — [[değer, etiket], …]
export function Choice({ label, value, options, onChange }) {
  return (
    <div className="flex gap-1.5 text-xs items-center flex-wrap">
      <span className="text-panel-muted">{label}:</span>
      {options.map(([v, l]) => (
        <button key={v} type="button" onClick={() => onChange(v)}
          className={`px-2.5 py-1 rounded-full border transition ${value === v
            ? 'border-panel-accent bg-emerald-500/10 text-emerald-300'
            : 'border-panel-border text-panel-muted hover:text-panel-ink'}`}>{l}</button>
      ))}
    </div>
  )
}

// Köşe ovalleştirme paneli — hero ve banner çerçeveleri için ortak.
function RadiusControl({ s, patch }) {
  return (
    <div className="space-y-1.5">
      <span className="text-panel-muted text-xs">Köşe ovalleştirme</span>
      <div className="flex gap-2 items-center">
        <select className="input !w-auto" value={s.radius_scope || 'both'}
          onChange={e => patch({ radius_scope: e.target.value })}>
          <option value="both">Açık (her yerde)</option>
          <option value="mobile">Yalnız mobil</option>
          <option value="desktop">Yalnız masaüstü</option>
          <option value="none">Kapalı (köşeli)</option>
        </select>
        {(s.radius_scope || 'both') !== 'none' && (
          <label className="flex items-center gap-1.5 text-xs text-panel-muted">
            <input className="input !w-20" type="number" min="0" max="100"
              value={s.radius_pct ?? 50}
              onChange={e => patch({ radius_pct: Math.max(0, Math.min(100, Number(e.target.value) || 0)) })} />
            % ovallik
          </label>
        )}
      </div>
    </div>
  )
}

// Bölüm tipine özel ayar formu.
export function SectionSettings({ sec, collections, products = [], pages = [], patch, uploadAsset }) {
  const s = sec.settings

  if (sec.type === 'hero_slider') {
    const slides = s.slides || []
    const patchSlide = (i, p) => patch({ slides: slides.map((sl, j) => j === i ? { ...sl, ...p } : sl) })
    return (
      <>
        {slides.map((slide, i) => (
          <div key={i} className="border border-panel-border rounded-xl p-2.5 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium">Slayt {i + 1}</span>
              <button onClick={() => patch({ slides: slides.filter((_, j) => j !== i) })}
                className="text-xs text-red-300 hover:text-red-300">Sil</button>
            </div>
            <AssetField label="Görsel" current={slide.image}
              onUpload={f => uploadAsset('hero', f, url => patchSlide(i, { image: url }))}
              onClear={() => patchSlide(i, { image: null })} />
            <input className="input" value={slide.eyebrow || ''} maxLength={60}
              onChange={e => patchSlide(i, { eyebrow: e.target.value })}
              placeholder="Üst etiket (ops.) — örn. YENİ SEZON" />
            <input className="input" value={slide.title || ''} maxLength={100}
              onChange={e => patchSlide(i, { title: e.target.value })} placeholder="Başlık" />
            <input className="input" value={slide.subtitle || ''} maxLength={200}
              onChange={e => patchSlide(i, { subtitle: e.target.value })} placeholder="Alt başlık" />
            <div className="grid grid-cols-2 gap-2">
              <input className="input" value={slide.cta_text || ''} maxLength={40}
                onChange={e => patchSlide(i, { cta_text: e.target.value })} placeholder="Buton yazısı" />
              <UrlPicker value={slide.cta_url} collections={collections} products={products} pages={pages}
                placeholder="Buton hedefi" onChange={url => patchSlide(i, { cta_url: url })} />
              <input className="input" value={slide.cta2_text || ''} maxLength={40}
                onChange={e => patchSlide(i, { cta2_text: e.target.value })}
                placeholder="2. buton yazısı (ops. — çerçeveli görünür)" />
              <UrlPicker value={slide.cta2_url} collections={collections} products={products} pages={pages}
                placeholder="2. buton hedefi" onChange={url => patchSlide(i, { cta2_url: url })} />
            </div>
          </div>
        ))}
        {slides.length < 6 && (
          <button onClick={() => patch({ slides: [...slides, { image: null, eyebrow: '', title: '', subtitle: '', cta_text: '', cta_url: '/urunler' }] })}
            className="btn-ghost !py-1.5 text-xs w-full">+ Slayt Ekle</button>
        )}
        {slides.length > 1 && (
          <label className="block text-sm">
            <span className="text-panel-muted text-xs">Otomatik geçiş (saniye; 0 = kapalı)</span>
            <input className="input mt-1 !w-24" type="number" min="0" max="30"
              value={s.autoplay_sec ?? 5}
              onChange={e => patch({ autoplay_sec: Number(e.target.value) })} />
          </label>
        )}
        {slides.length === 0 && (
          <p className="text-[11px] text-panel-muted">
            Slayt eklemezseniz sade bir karşılama metni gösterilir.
          </p>
        )}
        <Choice label="Yazı hizası" value={s.align || 'center'}
          options={[['center', 'Ortada'], ['left', 'Solda']]} onChange={v => patch({ align: v })} />
        <Choice label="Yükseklik" value={s.height || 'normal'}
          options={[['normal', 'Normal'], ['tall', 'Yüksek vitrin']]} onChange={v => patch({ height: v })} />
        <RadiusControl s={s} patch={patch} />
      </>
    )
  }

  if (sec.type === 'featured_collections') {
    const slugs = s.slugs || []
    return (
      <>
        <HeadingFields s={s} patch={patch} />
        <Choice label="Düzen" value={s.layout || 'grid'}
          options={[['grid', "4'lü küçük kart"], ['showcase', "2'li büyük, numaralı"]]}
          onChange={v => patch({ layout: v })} />
        {collections.length === 0 ? (
          <p className="text-xs text-panel-muted">Önce Koleksiyonlar sayfasından koleksiyon oluşturun.</p>
        ) : (
          <div className="flex gap-2 flex-wrap">
            {collections.map(c => {
              const active = slugs.includes(c.slug)
              return (
                <button key={c.slug}
                  onClick={() => patch({ slugs: active ? slugs.filter(x => x !== c.slug) : [...slugs, c.slug] })}
                  className={`px-3 py-1 rounded-full text-xs border transition ${active
                    ? 'border-panel-accent bg-emerald-500/10 text-emerald-300'
                    : 'border-panel-border text-panel-muted hover:text-panel-ink'}`}>
                  {c.title}
                </button>
              )
            })}
          </div>
        )}
        {slugs.length === 0 && (
          <label className="flex items-center gap-2 text-xs text-panel-muted">
            Hiçbiri seçilmezse ilk
            <input className="input !w-16 !py-1" type="number" min="1" max="12" value={s.limit ?? 4}
              onChange={e => patch({ limit: Math.max(1, Math.min(12, Number(e.target.value) || 4)) })} />
            koleksiyon gösterilir.
          </label>
        )}
        <p className="text-[11px] text-panel-muted">
          Büyük kartlarda koleksiyonun görseli ve açıklaması görünür — Koleksiyonlar sayfasından ekleyin.
        </p>
      </>
    )
  }

  if (sec.type === 'featured_products') {
    const slugs = s.slugs || []
    const available = products.filter(pr => !slugs.includes(pr.slug))
    const bySlug = Object.fromEntries(products.map(pr => [pr.slug, pr]))
    const move = (i, dir) => {
      const j = i + dir
      if (j < 0 || j >= slugs.length) return
      const next = [...slugs]
      ;[next[i], next[j]] = [next[j], next[i]]
      patch({ slugs: next })
    }
    return (
      <>
        <HeadingFields s={s} patch={patch} />
        <Choice label="Düzen" value={s.layout || 'grid'}
          options={[['grid', 'Izgara'], ['carousel', 'Oklu şerit']]} onChange={v => patch({ layout: v })} />
        {slugs.length > 0 && (
          <div className="space-y-1">
            {slugs.map((slug, i) => (
              <div key={slug} className="flex items-center gap-1.5 text-xs bg-panel-input rounded-lg px-2 py-1.5">
                <span className="flex-1 min-w-0 truncate">
                  {bySlug[slug]?.title || <span className="text-red-300">{slug} (silinmiş ürün)</span>}
                </span>
                <button onClick={() => move(i, -1)} disabled={i === 0}
                  className="text-panel-muted hover:text-panel-ink disabled:opacity-30 px-0.5">↑</button>
                <button onClick={() => move(i, 1)} disabled={i === slugs.length - 1}
                  className="text-panel-muted hover:text-panel-ink disabled:opacity-30 px-0.5">↓</button>
                <button onClick={() => patch({ slugs: slugs.filter(x => x !== slug) })}
                  className="text-red-300 hover:text-red-300 px-0.5">×</button>
              </div>
            ))}
          </div>
        )}
        {slugs.length < 12 && available.length > 0 && (
          <select className="input" value=""
            onChange={e => e.target.value && patch({ slugs: [...slugs, e.target.value] })}>
            <option value="">+ Ürün ekle…</option>
            {available.map(pr => <option key={pr.slug} value={pr.slug}>{pr.title}</option>)}
          </select>
        )}
        {products.length === 0 && (
          <p className="text-xs text-panel-muted">Önce Ürünler sayfasından aktif ürün ekleyin.</p>
        )}
        <p className="text-[11px] text-panel-muted">
          Seçtiğiniz sırayla gösterilir (en fazla 12). Boşsa bölüm vitrinde görünmez.
        </p>
      </>
    )
  }

  if (sec.type === 'products_grid') {
    return (
      <>
        <HeadingFields s={s} patch={patch} />
        <Choice label="Düzen" value={s.layout || 'grid'}
          options={[['grid', 'Izgara'], ['carousel', 'Oklu şerit']]} onChange={v => patch({ layout: v })} />
        <div className="grid grid-cols-2 gap-2">
          <label className="block text-sm">
            <span className="text-panel-muted text-xs">Koleksiyon (ops.)</span>
            <select className="input mt-1" value={s.collection || ''}
              onChange={e => patch({ collection: e.target.value || null })}>
              <option value="">Tüm ürünler</option>
              {collections.map(c => <option key={c.slug} value={c.slug}>{c.title}</option>)}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-panel-muted text-xs">Ürün sayısı</span>
            <input className="input mt-1" type="number" min="1" max="24" value={s.limit ?? 8}
              onChange={e => patch({ limit: Number(e.target.value) })} />
          </label>
        </div>
      </>
    )
  }

  if (sec.type === 'rich_text') {
    return (
      <>
        <input className="input" value={s.title || ''} maxLength={100}
          onChange={e => patch({ title: e.target.value })} placeholder="Başlık" />
        <textarea className="input" rows={4} maxLength={2000} value={s.body || ''}
          onChange={e => patch({ body: e.target.value })} placeholder="Metin (satır sonları korunur)" />
      </>
    )
  }

  if (sec.type === 'image_with_text') {
    return (
      <>
        <AssetField label="Görsel" current={s.image}
          onUpload={f => uploadAsset('hero', f, url => patch({ image: url }))}
          onClear={() => patch({ image: null })} />
        <input className="input" value={s.title || ''} maxLength={100}
          onChange={e => patch({ title: e.target.value })} placeholder="Başlık" />
        <textarea className="input" rows={3} maxLength={2000} value={s.body || ''}
          onChange={e => patch({ body: e.target.value })} placeholder="Metin" />
        <div className="grid grid-cols-2 gap-2">
          <input className="input" value={s.cta_text || ''} maxLength={40}
            onChange={e => patch({ cta_text: e.target.value })} placeholder="Buton yazısı (ops.)" />
          <UrlPicker value={s.cta_url} collections={collections} products={products} pages={pages}
            placeholder="Buton hedefi" onChange={url => patch({ cta_url: url })} />
        </div>
        <div className="flex gap-2 text-xs items-center">
          <span className="text-panel-muted">Görsel tarafı:</span>
          {[['left', 'Sol'], ['right', 'Sağ']].map(([v, l]) => (
            <button key={v} onClick={() => patch({ image_side: v })}
              className={`px-2.5 py-1 rounded-full border ${(s.image_side || 'left') === v
                ? 'border-panel-accent bg-emerald-500/10 text-emerald-300'
                : 'border-panel-border text-panel-muted'}`}>{l}</button>
          ))}
        </div>
      </>
    )
  }

  if (sec.type === 'faq') {
    const items = s.items || []
    const patchItem = (i, p2) =>
      patch({ items: items.map((it, j) => j === i ? { ...it, ...p2 } : it) })
    return (
      <>
        <input className="input" value={s.title || ''} maxLength={100}
          onChange={e => patch({ title: e.target.value })} placeholder="Bölüm başlığı" />
        <div className="space-y-2">
          {items.map((it, i) => (
            <div key={i} className="border border-panel-border rounded-xl p-2 space-y-1.5">
              <div className="flex gap-1.5">
                <input className="input !py-1.5 text-xs" value={it.q || ''} maxLength={300}
                  onChange={e => patchItem(i, { q: e.target.value })} placeholder="Soru" />
                <button onClick={() => patch({ items: items.filter((_, j) => j !== i) })}
                  className="text-red-300 hover:text-red-300 px-1">×</button>
              </div>
              <textarea className="input !py-1.5 text-xs" rows={2} maxLength={2000} value={it.a || ''}
                onChange={e => patchItem(i, { a: e.target.value })} placeholder="Cevap" />
            </div>
          ))}
        </div>
        {items.length < 12 && (
          <button onClick={() => patch({ items: [...items, { q: '', a: '' }] })}
            className="btn-ghost !py-1 text-xs">+ Soru Ekle</button>
        )}
        <p className="text-[11px] text-panel-muted">
          SSS, Google'da zengin sonuç (FAQ şeması) olarak da işaretlenir.
        </p>
      </>
    )
  }

  if (sec.type === 'newsletter') {
    return (
      <>
        <input className="input" value={s.title || ''} maxLength={100}
          onChange={e => patch({ title: e.target.value })} placeholder="Başlık" />
        <input className="input" value={s.subtitle || ''} maxLength={200}
          onChange={e => patch({ subtitle: e.target.value })} placeholder="Alt başlık (ops.)" />
      </>
    )
  }

  if (sec.type === 'icon_bar') {
    const items = s.items || []
    const patchItem = (i, p2) => patch({ items: items.map((it, j) => j === i ? { ...it, ...p2 } : it) })
    return (
      <>
        {items.map((it, i) => (
          <div key={i} className="flex gap-1.5 items-start">
            <input className="input !py-1.5 text-base !w-14 text-center" value={it.icon || ''} maxLength={8}
              onChange={e => patchItem(i, { icon: e.target.value })} placeholder="🚚" />
            <div className="flex-1 space-y-1">
              <input className="input !py-1.5 text-xs" value={it.title || ''} maxLength={80}
                onChange={e => patchItem(i, { title: e.target.value })} placeholder="Başlık" />
              <input className="input !py-1.5 text-xs" value={it.text || ''} maxLength={200}
                onChange={e => patchItem(i, { text: e.target.value })} placeholder="Kısa açıklama (ops.)" />
            </div>
            <button onClick={() => patch({ items: items.filter((_, j) => j !== i) })}
              className="text-red-300 hover:text-red-300 px-1">×</button>
          </div>
        ))}
        {items.length < 6 && (
          <button onClick={() => patch({ items: [...items, { icon: '✨', title: '', text: '' }] })}
            className="btn-ghost !py-1 text-xs">+ Avantaj Ekle</button>
        )}
      </>
    )
  }

  if (sec.type === 'comparison') {
    const rows = s.rows || []
    const patchRow = (i, p2) => patch({ rows: rows.map((r, j) => j === i ? { ...r, ...p2 } : r) })
    return (
      <>
        <input className="input" value={s.title || ''} maxLength={100}
          onChange={e => patch({ title: e.target.value })} placeholder="Bölüm başlığı" />
        <div className="grid grid-cols-2 gap-2">
          <input className="input !py-1.5 text-xs" value={s.us_label || ''} maxLength={30}
            onChange={e => patch({ us_label: e.target.value })} placeholder="Sol kolon (Biz)" />
          <input className="input !py-1.5 text-xs" value={s.them_label || ''} maxLength={30}
            onChange={e => patch({ them_label: e.target.value })} placeholder="Sağ kolon (Diğerleri)" />
        </div>
        {rows.map((r, i) => (
          <div key={i} className="flex gap-1.5 items-center">
            <input className="input !py-1.5 text-xs flex-1" value={r.feature || ''} maxLength={120}
              onChange={e => patchRow(i, { feature: e.target.value })} placeholder="Özellik" />
            <label className="text-[11px] flex items-center gap-1" title={s.us_label || 'Biz'}>
              <input type="checkbox" checked={!!r.us} onChange={e => patchRow(i, { us: e.target.checked })} />✓
            </label>
            <label className="text-[11px] flex items-center gap-1 text-panel-muted" title={s.them_label || 'Diğerleri'}>
              <input type="checkbox" checked={!!r.them} onChange={e => patchRow(i, { them: e.target.checked })} />✓
            </label>
            <button onClick={() => patch({ rows: rows.filter((_, j) => j !== i) })}
              className="text-red-300 hover:text-red-300 px-1">×</button>
          </div>
        ))}
        {rows.length < 8 && (
          <button onClick={() => patch({ rows: [...rows, { feature: '', us: true, them: false }] })}
            className="btn-ghost !py-1 text-xs">+ Satır Ekle</button>
        )}
      </>
    )
  }

  if (sec.type === 'testimonials') {
    const items = s.items || []
    const patchItem = (i, p2) => patch({ items: items.map((it, j) => j === i ? { ...it, ...p2 } : it) })
    return (
      <>
        <HeadingFields s={s} patch={patch} />
        {items.map((it, i) => (
          <div key={i} className="border border-panel-border rounded-xl p-2 space-y-1.5">
            <div className="flex gap-1.5">
              <input className="input !py-1.5 text-xs" value={it.author || ''} maxLength={80}
                onChange={e => patchItem(i, { author: e.target.value })} placeholder="Müşteri adı" />
              <select className="input !py-1.5 text-xs !w-24" value={it.rating ?? 5}
                onChange={e => patchItem(i, { rating: Number(e.target.value) })}>
                {[5, 4, 3, 2, 1].map(n => <option key={n} value={n}>{'★'.repeat(n)}</option>)}
              </select>
              <button onClick={() => patch({ items: items.filter((_, j) => j !== i) })}
                className="text-red-300 hover:text-red-300 px-1">×</button>
            </div>
            <textarea className="input !py-1.5 text-xs" rows={2} maxLength={600} value={it.text || ''}
              onChange={e => patchItem(i, { text: e.target.value })} placeholder="Yorum metni" />
          </div>
        ))}
        {items.length < 6 && (
          <button onClick={() => patch({ items: [...items, { author: '', text: '', rating: 5 }] })}
            className="btn-ghost !py-1 text-xs">+ Yorum Ekle</button>
        )}
        <p className="text-[11px] text-panel-muted">
          Ürün sayfalarındaki gerçek yorumlardan bağımsız, anasayfa vitrini içindir.
        </p>
      </>
    )
  }

  if (sec.type === 'gallery') {
    const images = s.images || []
    return (
      <>
        <HeadingFields s={s} patch={patch} />
        <Choice label="Kart oranı" value={s.aspect || 'square'}
          options={[['square', 'Kare'], ['story', 'Hikâye (9:16)']]} onChange={v => patch({ aspect: v })} />
        <Choice label="Akış" value={s.mode || 'scroll'}
          options={[['scroll', 'Elle kaydır'], ['carousel', 'Oklu + otomatik'], ['marquee', 'Sürekli akan']]}
          onChange={v => patch({ mode: v })} />
        <div className="grid grid-cols-4 gap-1.5">
          {images.map((u, i) => (
            <div key={i} className="relative group">
              <img src={u} alt="" className={`w-full ${s.aspect === 'story' ? 'aspect-[9/16]' : 'aspect-square'} object-cover rounded-lg border border-panel-border`} />
              <button onClick={() => patch({ images: images.filter((_, j) => j !== i) })}
                className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-red-500 text-white text-xs
                  opacity-0 group-hover:opacity-100 transition">×</button>
            </div>
          ))}
          {images.length < 12 && (
            <label className="aspect-square rounded-lg border border-dashed border-panel-border
              flex items-center justify-center text-panel-muted cursor-pointer text-lg">
              +
              <input type="file" accept="image/*" className="hidden"
                onChange={e => e.target.files?.[0] && uploadAsset('hero', e.target.files[0],
                  url => patch({ images: [...images, url] }))} />
            </label>
          )}
        </div>
        <p className="text-[11px] text-panel-muted">
          Müşteri fotoğrafları, hikâye ekran görüntüleri… (en fazla 12 görsel).
          Hikâye oranında 1080×1920 dikey görsel önerilir.
        </p>
      </>
    )
  }

  if (sec.type === 'contact') {
    return (
      <>
        <input className="input" value={s.title || ''} maxLength={100}
          onChange={e => patch({ title: e.target.value })} placeholder="Başlık" />
        <input className="input" value={s.subtitle || ''} maxLength={200}
          onChange={e => patch({ subtitle: e.target.value })} placeholder="Alt başlık (ops.)" />
        <p className="text-[11px] text-panel-muted">
          Mesajlar, Ayarlar'daki <b>iletişim e-postanıza</b> gönderilir — orayı doldurmayı unutmayın.
        </p>
      </>
    )
  }

  if (sec.type === 'countdown') {
    return (
      <>
        <input className="input" value={s.title || ''} maxLength={100}
          onChange={e => patch({ title: e.target.value })} placeholder="Başlık" />
        <input className="input" value={s.subtitle || ''} maxLength={200}
          onChange={e => patch({ subtitle: e.target.value })} placeholder="Alt başlık (ops.)" />
        <label className="block text-sm">
          <span className="text-panel-muted text-xs">Bitiş zamanı</span>
          <input className="input mt-1" type="datetime-local"
            value={s.ends_at ? s.ends_at.slice(0, 16) : ''}
            onChange={e => patch({ ends_at: e.target.value ? new Date(e.target.value).toISOString() : '' })} />
        </label>
        <div className="grid grid-cols-2 gap-2">
          <input className="input" value={s.cta_text || ''} maxLength={40}
            onChange={e => patch({ cta_text: e.target.value })} placeholder="Buton yazısı" />
          <UrlPicker value={s.cta_url} collections={collections} products={products} pages={pages}
            placeholder="Buton hedefi" onChange={url => patch({ cta_url: url })} />
        </div>
        <p className="text-[11px] text-panel-muted">
          Süre dolunca bölüm vitrinde kendiliğinden kaybolur.
        </p>
      </>
    )
  }

  if (sec.type === 'banner') {
    return (
      <>
        <AssetField label="Banner görseli" current={s.image}
          onUpload={f => uploadAsset('hero', f, url => patch({ image: url }))}
          onClear={() => patch({ image: null })} />
        <UrlPicker value={s.url} collections={collections} products={products} pages={pages}
          placeholder="Tıklanınca gidilecek hedef (ops.)" onChange={url => patch({ url })} />
        <RadiusControl s={s} patch={patch} />
      </>
    )
  }
  return null
}

export function Section({ title, icon, children }) {
  return (
    <section className="card space-y-2.5">
      <h2 className="text-sm font-semibold flex items-center gap-2"><span>{icon}</span> {title}</h2>
      {children}
    </section>
  )
}

export function ColorField({ label, value, onChange }) {
  return (
    <label className="block text-sm">
      <span className="text-panel-muted text-xs">{label}</span>
      <div className="mt-1 flex items-center gap-1.5">
        <input type="color" value={value} onChange={e => onChange(e.target.value)}
          className="w-9 h-9 rounded-lg border border-panel-border cursor-pointer p-0.5 bg-panel-card" />
        <input className="input !px-2 font-mono text-xs" value={value}
          onChange={e => onChange(e.target.value)} maxLength={7} />
      </div>
    </label>
  )
}

export function Toggle({ checked, onChange, label }) {
  return (
    <label className="flex items-center gap-2 text-sm cursor-pointer">
      <input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} />
      {label}
    </label>
  )
}

export function AssetField({ label, current, onUpload, onClear }) {
  return (
    <div className="text-sm">
      <span className="text-panel-muted text-xs">{label}</span>
      <div className="mt-1 flex items-center gap-2">
        {current ? (
          <>
            <img src={current} alt={label} className="h-10 max-w-[120px] object-contain rounded-lg border border-panel-border bg-panel-card p-1" />
            <button onClick={onClear} className="text-xs text-red-300 hover:text-red-300">Kaldır</button>
          </>
        ) : (
          <label className="btn-ghost !py-1.5 text-xs cursor-pointer">
            Dosya seç
            <input type="file" accept="image/png,image/jpeg,image/webp,image/x-icon" className="hidden"
              onChange={e => onUpload(e.target.files?.[0])} />
          </label>
        )}
      </div>
    </div>
  )
}
