// Tema editörünün ortak parçaları — bölüm tipleri, varsayılanlar ve ayar formları.
// TemaEditorPage kullanır; TemaPage (kütüphane) yalnızca SECTION_TYPES'a bakar.
/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useState } from 'react'
import { api } from '../lib/api'

export const FONTS = [
  { key: 'inter', label: 'Inter (modern, varsayılan)' },
  { key: 'poppins', label: 'Poppins (yuvarlak, samimi)' },
  { key: 'playfair', label: 'Playfair Display (şık, serif)' },
  { key: 'dm-sans', label: 'DM Sans (sade, geometrik)' },
  { key: 'editoryal', label: 'Editoryal (Inter + Instrument Serif başlıklar)' },
]

// İkon şeridindeki çizgi ikonlar (vitrin lib/cizgiIkon.tsx ile birebir)
export const CIZGI_IKONLAR = [
  ['kargo', '🚚'], ['konum', '📍'], ['iade', '↩️'], ['eposta', '✉️'], ['destek', '🎧'], ['guvenli', '🔒'],
  ['hediye', '🎁'], ['yildiz', '⭐'], ['kalp', '♡'], ['saat', '🕒'], ['telefon', '📱'], ['kutu', '📦'],
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
  kurdele: { label: 'Çapraz Kurdeleler (akan yazı)', icon: '🎗️' },
  stil_onerici: { label: 'Stil Önerici (tarzını seç)', icon: '🎨' },
  adimlar: { label: 'Numaralı Adımlar', icon: '🔢' },
  kilif_onizleme: { label: 'Canlı Kılıf Önizleme', icon: '📱' },
  son_bakilanlar: { label: 'Son Baktıkların', icon: '🕘' },
}

export const SECTION_DEFAULTS = {
  hero_slider: { slides: [], autoplay_sec: 5, radius_scope: 'both', radius_pct: 50, align: 'center', height: 'normal',
    stil: 'kaplama', panel_renk: '#efefef' },
  featured_collections: { eyebrow: '', title: 'Koleksiyonlar', subtitle: '', slugs: [], layout: 'grid', limit: 4 },
  products_grid: { eyebrow: '', title: 'Öne Çıkanlar', subtitle: '', collection: null, limit: 8, layout: 'grid', sekmeler: [] },
  featured_products: { eyebrow: '', title: 'Öne Çıkan Ürünler', subtitle: '', slugs: [], layout: 'grid' },
  rich_text: { title: '', body: '' },
  banner: { image: null, url: '', radius_scope: 'both', radius_pct: 50 },
  image_with_text: { image: null, eyebrow: '', title: '', body: '', cta_text: '', cta_url: '', image_side: 'left',
    stil: 'acik', gorsel_notu: '' },
  faq: { eyebrow: '', title: 'Sıkça Sorulan Sorular', subtitle: '', items: [], stil: 'tek', eposta: '' },
  newsletter: { title: 'Kampanyalardan haberdar olun', subtitle: 'İndirim ve yeni tasarımlar e-postanıza gelsin.' },
  icon_bar: { items: [{ icon: '🚚', title: 'Hızlı Kargo', text: '1-3 iş gününde kargoda', url: '' }], stil: 'kart' },
  comparison: { title: 'Neden Biz?', us_label: 'Biz', them_label: 'Diğerleri',
    rows: [{ feature: 'Kişiye özel baskı kalitesi', us: true, them: false }] },
  testimonials: { eyebrow: '', title: 'Müşterilerimiz Ne Diyor?', subtitle: '', items: [], stil: 'kart', alt_not: '' },
  gallery: { eyebrow: '', title: 'Sizden Gelenler', subtitle: '', ogeler: [], aspect: 'square', mode: 'scroll',
    baglanti: '', baglanti_metni: '' },
  contact: { title: 'İletişim', subtitle: 'Soru ve önerileriniz için bize yazın.' },
  countdown: { title: 'Kampanya bitiyor!', subtitle: '', ends_at: '',
    cta_text: 'Alışverişe Başla', cta_url: '/urunler' },
  kurdele: { palet: 'neon', sembol: '✦', items: [
    { text: 'YENİ KOLEKSİYON', buyuk: true }, { text: '{magaza}', buyuk: false },
    { text: 'Tarzını yanında taşı', buyuk: false }] },
  stil_onerici: { eyebrow: 'STİL ÖNERİCİ', title: 'Hangi tarz\nsana göre?',
    subtitle: 'Birini seç, sana uygun tasarımı gösterelim.', secenekler: [
      { etiket: 'Sakin & sanatsal', renk: '#69778c', kelime: 'SANAT.', neden: 'Sakin renkler. Güçlü bir bakış açısı.', urun: '', zemin: '#e5e8ed' },
      { etiket: 'Cesur & hızlı', renk: '#ce4444', kelime: 'HIZ.', neden: 'Enerjini her gün yanında taşı.', urun: '', zemin: '#edc4c2' },
    ] },
  adimlar: { eyebrow: '', title: 'Kendi tasarımını\n3 adımda oluştur.', subtitle: '', items: [
    { title: 'Görselini seç.', text: 'Bir fotoğraf, bir çizim ya da bir yazı.', url: '/tasarla' },
    { title: 'Baskıya hazırlıyoruz.', text: 'Tasarımın özenle basılır ve paketlenir.', url: '' },
    { title: 'Kargonu takip et.', text: 'Siparişinin nerede olduğunu tek yerden gör.', url: '/hesap' },
  ] },
  kilif_onizleme: { eyebrow: 'CANLI ÖNİZLEME', title: 'Fotoğrafını seç,\nkılıfını hemen gör.',
    subtitle: 'Fotoğrafın yalnızca bu ekranda kalır, hiçbir yere yüklenmez.', buton: 'FOTOĞRAF SEÇ',
    cta_text: 'Bu tasarımla sipariş ver', cta_url: '/tasarla', logo_yazi: '{magaza}',
    not: 'Önizlemedir; baskı renkleri ekrana göre küçük farklar gösterebilir.' },
  son_bakilanlar: { eyebrow: 'SON BAKTIKLARIN', title: 'Son baktığın tasarımlar', subtitle: '' },
}

// Bölüm vitrinde HİÇBİR ŞEY çizmeyecekse nedeni (yoksa null). Kurallar
// vitrin bileşenlerindeki "return null" koşullarıyla birebir — hazır şablonun
// görsel alanları boş gelir ve boş bölüm sessizce kaybolur; sahibi bunu
// bölüm listesinde görsün. (Koleksiyon/ürün ızgarası veriye bağlı, atlanır.)
export function bosBolumNedeni(sec) {
  const s = sec.settings || {}
  const dolu = (liste, alan) => (liste || []).some(x => (alan ? x?.[alan] : x))
  switch (sec.type) {
    case 'gallery':
      return dolu(s.ogeler, 'url') || dolu(s.images) ? null : 'görsel bekliyor'
    case 'banner': return s.image ? null : 'görsel bekliyor'
    case 'featured_products': return (s.slugs || []).length ? null : 'ürün seçilmedi'
    case 'testimonials': return dolu(s.items, 'text') ? null : 'yorum eklenmedi'
    case 'faq': return (s.items || []).some(i => i?.q && i?.a) ? null : 'soru-cevap eklenmedi'
    case 'icon_bar': return dolu(s.items, 'title') ? null : 'avantaj eklenmedi'
    case 'comparison': return dolu(s.rows, 'feature') ? null : 'satır eklenmedi'
    case 'rich_text': return s.title || s.body ? null : 'metin yok'
    case 'image_with_text': return s.image || s.title || s.body ? null : 'içerik yok'
    case 'countdown':
      if (!s.ends_at) return 'bitiş zamanı yok'
      return new Date(s.ends_at) > new Date() ? null : 'süresi doldu'
    case 'kurdele': return dolu(s.items, 'text') ? null : 'yazı eklenmedi'
    case 'stil_onerici': return (s.secenekler || []).some(o => o?.etiket && o?.urun) ? null : 'ürün seçilmedi'
    case 'adimlar': return dolu(s.items, 'title') ? null : 'adım eklenmedi'
    default: return null
  }
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
function HeadingFields({ s, patch, titlePlaceholder = 'Bölüm başlığı', cokSatir = false }) {
  return (
    <>
      <input className="input" value={s.eyebrow || ''} maxLength={60}
        onChange={e => patch({ eyebrow: e.target.value })}
        placeholder="Üst etiket (ops.) — örn. SENİN İÇİN SEÇTİK" />
      {cokSatir ? (
        <>
          <textarea className="input" rows={2} value={s.title || ''} maxLength={100}
            onChange={e => patch({ title: e.target.value })} placeholder={titlePlaceholder} />
          <p className="text-[11px] text-panel-muted -mt-1">Başlıkta alt satıra geçtiğiniz kısım italik görünür.</p>
        </>
      ) : (
        <input className="input" value={s.title || ''} maxLength={100}
          onChange={e => patch({ title: e.target.value })} placeholder={titlePlaceholder} />
      )}
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
  const medya = useContext(MedyaContext)

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
              onUrl={url => patchSlide(i, { image: url })}
              onClear={() => patchSlide(i, { image: null })} />
            <input className="input" value={slide.eyebrow || ''} maxLength={60}
              onChange={e => patchSlide(i, { eyebrow: e.target.value })}
              placeholder="Üst etiket (ops.) — örn. YENİ SEZON" />
            <textarea className="input" rows={2} value={slide.title || ''} maxLength={100}
              onChange={e => patchSlide(i, { title: e.target.value })}
              placeholder={s.stil === 'bolunmus' ? 'Başlık — alt satır italik görünür' : 'Başlık'} />
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
            {s.stil === 'bolunmus' && (
              <Choice label="Görsel" value={slide.gorsel_kip || 'sigdir'}
                options={[['sigdir', 'Kesmeden sığdır (dekupe/beyaz zeminli görsel)'], ['kapla', 'Yuvarlak kart gibi doldur']]}
                onChange={v => patchSlide(i, { gorsel_kip: v })} />
            )}
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
        <Choice label="Görünüm" value={s.stil || 'kaplama'}
          options={[['kaplama', 'Görsel tam zemin, yazı üstünde'], ['bolunmus', 'Bölünmüş pano (yazı solda, görsel sağda)']]}
          onChange={v => patch({ stil: v })} />
        {s.stil === 'bolunmus' ? (
          <ColorField label="Pano rengi" value={s.panel_renk || '#efefef'} onChange={v => patch({ panel_renk: v })} />
        ) : (<>
          <Choice label="Yazı hizası" value={s.align || 'center'}
            options={[['center', 'Ortada'], ['left', 'Solda']]} onChange={v => patch({ align: v })} />
          <Choice label="Yükseklik" value={s.height || 'normal'}
            options={[['normal', 'Normal'], ['tall', 'Yüksek vitrin']]} onChange={v => patch({ height: v })} />
        </>)}
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
          options={[['grid', "4'lü küçük kart"], ['showcase', "2'li büyük, numaralı"], ['kartlar', "4'lü görsel kart, beyaz etiket"]]}
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
    const sekmeler = s.sekmeler || []
    return (
      <>
        <HeadingFields s={s} patch={patch} />
        <Choice label="Düzen" value={s.layout || 'grid'}
          options={[['grid', 'Izgara'], ['carousel', 'Oklu şerit'], ['sekmeli', 'Sekmeli (koleksiyon hapları + sıralama)']]}
          onChange={v => patch({ layout: v })} />
        {s.layout === 'sekmeli' && (
          <div className="space-y-1.5">
            <span className="text-panel-muted text-xs">Sekmeler (en fazla 6 koleksiyon; "Tümü" her zaman var)</span>
            <div className="flex gap-1.5 flex-wrap">
              {collections.map(c => {
                const on = sekmeler.includes(c.slug)
                return (
                  <button key={c.slug} type="button"
                    onClick={() => patch({ sekmeler: on ? sekmeler.filter(x => x !== c.slug) : [...sekmeler, c.slug].slice(0, 6) })}
                    className={`px-2.5 py-1 rounded-full text-xs border transition ${on
                      ? 'border-panel-accent bg-emerald-500/10 text-emerald-300'
                      : 'border-panel-border text-panel-muted hover:text-panel-ink'}`}>{c.title}</button>
                )
              })}
            </div>
          </div>
        )}
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
    const koyu = s.stil === 'koyu'
    return (
      <>
        <Choice label="Görünüm" value={s.stil || 'acik'}
          options={[['acik', 'Açık kart'], ['koyu', 'Koyu editoryal pano']]} onChange={v => patch({ stil: v })} />
        <AssetField label="Görsel" current={s.image}
          onUrl={url => patch({ image: url })}
          onClear={() => patch({ image: null })} />
        {koyu && (<>
          <input className="input" value={s.gorsel_notu || ''} maxLength={80}
            onChange={e => patch({ gorsel_notu: e.target.value })}
            placeholder="Görselin köşesindeki küçük not (ops.) — örn. İMZA TASARIM / 2026" />
          <input className="input" value={s.eyebrow || ''} maxLength={60}
            onChange={e => patch({ eyebrow: e.target.value })} placeholder="Üst etiket (ops.)" />
        </>)}
        <textarea className="input" rows={koyu ? 2 : 1} value={s.title || ''} maxLength={100}
          onChange={e => patch({ title: e.target.value })}
          placeholder={koyu ? 'Başlık — alt satır italik görünür' : 'Başlık'} />
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
    const iki = s.stil === 'iki_sutun'
    return (
      <>
        <Choice label="Düzen" value={s.stil || 'tek'}
          options={[['tek', 'Ortada liste'], ['iki_sutun', 'İki sütun (başlık solda)']]} onChange={v => patch({ stil: v })} />
        {iki && (
          <input className="input" value={s.eyebrow || ''} maxLength={60}
            onChange={e => patch({ eyebrow: e.target.value })} placeholder="Üst etiket (ops.) — örn. YARDIM" />
        )}
        <input className="input" value={s.title || ''} maxLength={100}
          onChange={e => patch({ title: e.target.value })} placeholder="Bölüm başlığı" />
        {iki && (<>
          <input className="input" value={s.subtitle || ''} maxLength={200}
            onChange={e => patch({ subtitle: e.target.value })} placeholder="Açıklama (ops.)" />
          <input className="input" value={s.eposta || ''} maxLength={120}
            onChange={e => patch({ eposta: e.target.value })}
            placeholder="İletişim e-postası (boşsa mağaza e-postası)" />
        </>)}
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
        <Choice label="Görünüm" value={s.stil || 'kart'}
          options={[['kart', 'Ayrı kutular'], ['serit', 'Tek şerit (çizgi ikonlu, tıklanır)']]} onChange={v => patch({ stil: v })} />
        {items.map((it, i) => (
          <div key={i} className="flex gap-1.5 items-start">
            <input className="input !py-1.5 text-base !w-14 text-center" value={it.icon || ''} maxLength={8}
              onChange={e => patchItem(i, { icon: e.target.value })} placeholder="🚚" />
            <div className="flex-1 space-y-1">
              <div className="flex gap-1 flex-wrap" title="Çizgi ikon seç (emoji de yazabilirsiniz)">
                {CIZGI_IKONLAR.map(([ad, simge]) => (
                  <button key={ad} type="button" onClick={() => patchItem(i, { icon: ad })}
                    className={`w-6 h-6 rounded-md text-[11px] border ${it.icon === ad
                      ? 'border-panel-accent bg-emerald-500/10' : 'border-panel-border'}`}
                    aria-label={ad}>{simge}</button>
                ))}
              </div>
              <input className="input !py-1.5 text-xs" value={it.title || ''} maxLength={80}
                onChange={e => patchItem(i, { title: e.target.value })} placeholder="Başlık" />
              <input className="input !py-1.5 text-xs" value={it.text || ''} maxLength={200}
                onChange={e => patchItem(i, { text: e.target.value })} placeholder="Kısa açıklama (ops.)" />
              {s.stil === 'serit' && (
                <UrlPicker value={it.url || ''} collections={collections} products={products} pages={pages}
                  placeholder="Tıklanınca gidilecek yer (ops.)" onChange={url => patchItem(i, { url })} />
              )}
            </div>
            <button onClick={() => patch({ items: items.filter((_, j) => j !== i) })}
              className="text-red-300 hover:text-red-300 px-1">×</button>
          </div>
        ))}
        {items.length < 6 && (
          <button onClick={() => patch({ items: [...items, { icon: '✨', title: '', text: '', url: '' }] })}
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
    const foto = s.stil === 'fotografli'
    return (
      <>
        <Choice label="Görünüm" value={s.stil || 'kart'}
          options={[['kart', 'Yıldızlı kutular'], ['fotografli', 'Koyu bant, fotoğraflı kayan kartlar']]}
          onChange={v => patch({ stil: v })} />
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
            {foto && (
              <AssetField label="Müşteri fotoğrafı (ops.)" current={it.image}
                onUrl={url => patchItem(i, { image: url })} onClear={() => patchItem(i, { image: '' })} />
            )}
          </div>
        ))}
        {items.length < 6 && (
          <button onClick={() => patch({ items: [...items, { author: '', text: '', rating: 5 }] })}
            className="btn-ghost !py-1 text-xs">+ Yorum Ekle</button>
        )}
        {foto && (
          <input className="input !py-1.5 text-xs" value={s.alt_not || ''} maxLength={120}
            onChange={e => patch({ alt_not: e.target.value })}
            placeholder="Alt satır (ops.) — örn. Daha fazlası Instagram'da. (Instagram adresiniz yanına eklenir)" />
        )}
        <p className="text-[11px] text-panel-muted">
          Ürün sayfalarındaki gerçek yorumlardan bağımsız, anasayfa vitrini içindir. Yalnız gerçek
          müşteri yorumlarını ve izin aldığınız fotoğrafları kullanın.
        </p>
      </>
    )
  }

  if (sec.type === 'gallery') {
    // Eski biçim (images: [url]) de okunur; kayıtta ogeler yazılır
    const ogeler = s.ogeler?.length ? s.ogeler : (s.images || []).map(url => ({ url }))
    const yaz = yeni => patch({ ogeler: yeni, images: yeni.map(o => o.url) })
    const guncelle = (i, p2) => yaz(ogeler.map((o, j) => j === i ? { ...o, ...p2 } : o))
    const tasi = (i, yon) => {
      const j = i + yon
      if (j < 0 || j >= ogeler.length) return
      const n = [...ogeler]; [n[i], n[j]] = [n[j], n[i]]; yaz(n)
    }
    const videoMu = o => o.tip === 'video' || /\.(mp4|webm|mov|m4v)$/i.test(o.url || '')
    return (
      <>
        <HeadingFields s={s} patch={patch} />
        <Choice label="Kart oranı" value={s.aspect || 'square'}
          options={[['square', 'Kare'], ['story', 'Hikâye (9:16)']]} onChange={v => patch({ aspect: v })} />
        <Choice label="Akış" value={s.mode || 'scroll'}
          options={[['scroll', 'Elle kaydır'], ['carousel', 'Oklu + otomatik'], ['marquee', 'Sürekli akan'],
            ['izgara', 'Izgara (Instagram, yavaş yakınlaşan)']]}
          onChange={v => patch({ mode: v })} />
        {s.mode === 'izgara' && (
          <div className="grid grid-cols-2 gap-1.5">
            <input className="input !py-1.5 text-xs" value={s.baglanti_metni || ''} maxLength={40}
              onChange={e => patch({ baglanti_metni: e.target.value })} placeholder="Bağlantı yazısı — örn. Takip et" />
            <input className="input !py-1.5 text-xs" value={s.baglanti || ''} maxLength={300}
              onChange={e => patch({ baglanti: e.target.value })}
              placeholder="https://… (boşsa Instagram adresiniz)" />
          </div>
        )}
        <div className="space-y-1.5">
          {ogeler.map((o, i) => (
            <div key={`${o.url}-${i}`} className="flex gap-2 items-start border border-panel-border rounded-xl p-1.5">
              <div className={`shrink-0 w-12 ${s.aspect === 'story' ? 'aspect-[9/16]' : 'aspect-square'} rounded-lg overflow-hidden bg-panel-input grid place-items-center`}>
                {videoMu(o)
                  ? <video src={o.url} muted playsInline preload="metadata" className="w-full h-full object-cover" />
                  : <img src={o.url} alt="" className="w-full h-full object-cover" />}
              </div>
              <div className="flex-1 min-w-0 space-y-1">
                <input className="input !py-1 text-xs" value={o.etiket || ''} maxLength={60}
                  onChange={e => guncelle(i, { etiket: e.target.value })}
                  placeholder="Etiket (ops.) — örn. @kullaniciadi" />
                <UrlPicker value={o.link || ''} collections={collections} products={products} pages={pages}
                  placeholder="Tıklanınca gidilecek yer (ops.)" onChange={url => guncelle(i, { link: url })} />
              </div>
              <div className="flex flex-col items-center text-xs text-panel-muted">
                <button onClick={() => tasi(i, -1)} disabled={i === 0} className="px-1 disabled:opacity-30">↑</button>
                <button onClick={() => tasi(i, 1)} disabled={i === ogeler.length - 1} className="px-1 disabled:opacity-30">↓</button>
                <button onClick={() => yaz(ogeler.filter((_, j) => j !== i))} className="px-1 text-red-300">×</button>
              </div>
            </div>
          ))}
          {ogeler.length < 12 && (
            <div className="flex gap-1.5">
              <label className="flex-1 flex items-center justify-center gap-2 rounded-xl border border-dashed border-panel-border
                py-2.5 text-xs text-panel-muted cursor-pointer hover:text-panel-ink">
                + Görsel ya da video ekle
                <input type="file" accept="image/*,video/mp4,video/webm,video/quicktime" className="hidden"
                  onChange={e => e.target.files?.[0] && uploadAsset('hero', e.target.files[0],
                    url => yaz([...ogeler, { url, tip: /\.(mp4|webm|mov|m4v)$/i.test(url) ? 'video' : 'gorsel' }]))} />
              </label>
              {medya && (
                <button type="button" className="btn-ghost !py-2 text-xs"
                  onClick={async () => {
                    const url = await medya.sec('hepsi')
                    if (url) yaz([...ogeler, { url, tip: /\.(mp4|webm|mov|m4v)$/i.test(url) ? 'video' : 'gorsel' }])
                  }}>🖼️ Kütüphaneden</button>
              )}
            </div>
          )}
        </div>
        <p className="text-[11px] text-panel-muted">
          En fazla 12 öğe. Hikâye oranında 1080×1920 dikey görsel önerilir. Videolar sessiz ve döngülü,
          yalnız ekrandayken oynar (en fazla 100 MB; kısa ve sıkıştırılmış video sayfayı hızlı tutar).
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

  if (sec.type === 'kurdele') {
    const items = s.items || []
    const patchItem = (i, p2) => patch({ items: items.map((it, j) => j === i ? { ...it, ...p2 } : it) })
    return (
      <>
        <Choice label="Renkler" value={s.palet || 'neon'}
          options={[['neon', 'Neon (sarı + pembe)'], ['tema', 'Tema renkleri']]} onChange={v => patch({ palet: v })} />
        {items.map((it, i) => (
          <div key={i} className="flex gap-1.5 items-center">
            <input className="input !py-1.5 text-xs flex-1" value={it.text || ''} maxLength={60}
              onChange={e => patchItem(i, { text: e.target.value })} placeholder="Yazı" />
            <label className="text-[11px] flex items-center gap-1 text-panel-muted shrink-0">
              <input type="checkbox" checked={!!it.buyuk} onChange={e => patchItem(i, { buyuk: e.target.checked })} />
              büyük
            </label>
            <button onClick={() => patch({ items: items.filter((_, j) => j !== i) })}
              className="text-red-300 hover:text-red-300 px-1">×</button>
          </div>
        ))}
        {items.length < 10 && (
          <button onClick={() => patch({ items: [...items, { text: '', buyuk: false }] })}
            className="btn-ghost !py-1 text-xs">+ Yazı Ekle</button>
        )}
        <label className="flex items-center gap-2 text-xs text-panel-muted">
          Ayraç simgesi
          <input className="input !w-16 !py-1 text-center" value={s.sembol || '✦'} maxLength={4}
            onChange={e => patch({ sembol: e.target.value })} />
        </label>
        <p className="text-[11px] text-panel-muted">
          Üç eğik şerit zıt yönlerde akar. <b>{'{magaza}'}</b> yazdığınız yere mağaza adınız gelir.
        </p>
      </>
    )
  }

  if (sec.type === 'stil_onerici') {
    const sec_ = s.secenekler || []
    const patchOpt = (i, p2) => patch({ secenekler: sec_.map((o, j) => j === i ? { ...o, ...p2 } : o) })
    return (
      <>
        <HeadingFields s={s} patch={patch} cokSatir />
        {sec_.map((o, i) => (
          <div key={i} className="border border-panel-border rounded-xl p-2 space-y-1.5">
            <div className="flex gap-1.5 items-center">
              <input type="color" value={o.renk || '#888888'} onChange={e => patchOpt(i, { renk: e.target.value })}
                title="Nokta rengi" className="w-8 h-8 rounded-lg border border-panel-border p-0.5 bg-panel-card shrink-0" />
              <input className="input !py-1.5 text-xs" value={o.etiket || ''} maxLength={40}
                onChange={e => patchOpt(i, { etiket: e.target.value })} placeholder="Seçenek — örn. Sakin & sanatsal" />
              <button onClick={() => patch({ secenekler: sec_.filter((_, j) => j !== i) })}
                className="text-red-300 hover:text-red-300 px-1">×</button>
            </div>
            <select className="input !py-1.5 text-xs" value={o.urun || ''}
              onChange={e => patchOpt(i, { urun: e.target.value })}>
              <option value="">Gösterilecek ürünü seçin…</option>
              {products.map(pr => <option key={pr.slug} value={pr.slug}>{pr.title}</option>)}
            </select>
            <div className="grid grid-cols-[1fr_auto] gap-1.5 items-center">
              <input className="input !py-1.5 text-xs" value={o.kelime || ''} maxLength={14}
                onChange={e => patchOpt(i, { kelime: e.target.value })} placeholder="Arka plandaki büyük kelime — örn. SANAT." />
              <input type="color" value={o.zemin || '#e5e8ed'} onChange={e => patchOpt(i, { zemin: e.target.value })}
                title="Sahne zemin rengi" className="w-8 h-8 rounded-lg border border-panel-border p-0.5 bg-panel-card" />
            </div>
            <input className="input !py-1.5 text-xs" value={o.neden || ''} maxLength={120}
              onChange={e => patchOpt(i, { neden: e.target.value })} placeholder="Kısa açıklama — örn. Sakin renkler, güçlü bir bakış." />
          </div>
        ))}
        {sec_.length < 6 && (
          <button onClick={() => patch({ secenekler: [...sec_, { etiket: '', renk: '#888888', kelime: '', neden: '', urun: '', zemin: '#e5e8ed' }] })}
            className="btn-ghost !py-1 text-xs">+ Seçenek Ekle</button>
        )}
        <p className="text-[11px] text-panel-muted">
          Ziyaretçi bir tarz seçince o tarza bağlı ürün sahnede belirir. Ürünü seçilmeyen seçenek görünmez.
        </p>
      </>
    )
  }

  if (sec.type === 'adimlar') {
    const items = s.items || []
    const patchItem = (i, p2) => patch({ items: items.map((it, j) => j === i ? { ...it, ...p2 } : it) })
    return (
      <>
        <HeadingFields s={s} patch={patch} cokSatir />
        {items.map((it, i) => (
          <div key={i} className="border border-panel-border rounded-xl p-2 space-y-1.5">
            <div className="flex gap-1.5 items-center">
              <span className="text-xs text-panel-muted w-5">{String(i + 1).padStart(2, '0')}</span>
              <input className="input !py-1.5 text-xs" value={it.title || ''} maxLength={80}
                onChange={e => patchItem(i, { title: e.target.value })} placeholder="Adım başlığı" />
              <button onClick={() => patch({ items: items.filter((_, j) => j !== i) })}
                className="text-red-300 hover:text-red-300 px-1">×</button>
            </div>
            <input className="input !py-1.5 text-xs" value={it.text || ''} maxLength={200}
              onChange={e => patchItem(i, { text: e.target.value })} placeholder="Açıklama (ops.)" />
            <UrlPicker value={it.url || ''} collections={collections} products={products} pages={pages}
              placeholder="Tıklanınca gidilecek yer (ops.)" onChange={url => patchItem(i, { url })} />
          </div>
        ))}
        {items.length < 6 && (
          <button onClick={() => patch({ items: [...items, { title: '', text: '', url: '' }] })}
            className="btn-ghost !py-1 text-xs">+ Adım Ekle</button>
        )}
      </>
    )
  }

  if (sec.type === 'kilif_onizleme') {
    return (
      <>
        <HeadingFields s={s} patch={patch} cokSatir />
        <input className="input" value={s.buton || ''} maxLength={30}
          onChange={e => patch({ buton: e.target.value })} placeholder="Fotoğraf seçme düğmesi — örn. FOTOĞRAF SEÇ" />
        <div className="grid grid-cols-2 gap-2">
          <input className="input" value={s.cta_text || ''} maxLength={40}
            onChange={e => patch({ cta_text: e.target.value })} placeholder="Alt bağlantı yazısı (ops.)" />
          <UrlPicker value={s.cta_url} collections={collections} products={products} pages={pages}
            placeholder="Bağlantı hedefi" onChange={url => patch({ cta_url: url })} />
        </div>
        <input className="input" value={s.logo_yazi || ''} maxLength={24}
          onChange={e => patch({ logo_yazi: e.target.value })} placeholder="Kılıfın altındaki yazı — örn. {magaza}" />
        <input className="input" value={s.not || ''} maxLength={140}
          onChange={e => patch({ not: e.target.value })} placeholder="Önizleme altındaki küçük not (ops.)" />
        <p className="text-[11px] text-panel-muted">
          Ziyaretçi fotoğrafını seçip kılıfın üstünde sürükler, yakınlaştırır; iPhone/Samsung ve parlak/mat
          arasında geçer. Fotoğraf yalnız ziyaretçinin cihazında kalır, sunucuya yüklenmez.
          <b> {'{magaza}'}</b> yazan yere mağaza adınız gelir.
        </p>
      </>
    )
  }

  if (sec.type === 'son_bakilanlar') {
    return (
      <>
        <HeadingFields s={s} patch={patch} />
        <p className="text-[11px] text-panel-muted">
          Ziyaretçinin ürün sayfalarında son gezdiği 4 ürün, kendi tarayıcısından okunur (sunucuya bir şey
          gitmez). İlk kez gelen ziyaretçide liste boş olduğundan bölüm görünmez; ziyaretçi "Geçmişi temizle" ile silebilir.
        </p>
      </>
    )
  }

  if (sec.type === 'banner') {
    return (
      <>
        <AssetField label="Banner görseli" current={s.image}
          onUrl={url => patch({ image: url })}
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

// Tema editörü medya bağlamı: yukle(kind, file) → url, sec(tur) → url|null.
// TemaEditorPage sağlar; varsa görsel alanlarında "Kütüphaneden" düğmesi çıkar.
export const MedyaContext = createContext(null)

export function AssetField({ label, current, kind = 'hero', onUrl, onClear, tur = 'gorsel' }) {
  const medya = useContext(MedyaContext)
  const yukle = async file => {
    if (!file || !medya) return
    const url = await medya.yukle(kind, file)
    if (url) onUrl(url)
  }
  const kutuphane = async () => {
    const url = await medya?.sec(tur)
    if (url) onUrl(url)
  }
  return (
    <div className="text-sm">
      <span className="text-panel-muted text-xs">{label}</span>
      <div className="mt-1 flex items-center gap-2 flex-wrap">
        {current ? (
          <>
            <img src={current} alt={label} className="h-10 max-w-[120px] object-contain rounded-lg border border-panel-border bg-panel-card p-1" />
            <label className="text-xs text-panel-muted hover:text-panel-ink cursor-pointer">
              Değiştir
              <input type="file" accept="image/png,image/jpeg,image/webp,image/x-icon" className="hidden"
                onChange={e => yukle(e.target.files?.[0])} />
            </label>
            <button onClick={onClear} className="text-xs text-red-300 hover:text-red-300">Kaldır</button>
          </>
        ) : (
          <label className="btn-ghost !py-1.5 text-xs cursor-pointer">
            Dosya seç
            <input type="file" accept="image/png,image/jpeg,image/webp,image/x-icon" className="hidden"
              onChange={e => yukle(e.target.files?.[0])} />
          </label>
        )}
        {medya && kind !== 'favicon' && (
          <button type="button" onClick={kutuphane} className="btn-ghost !py-1.5 text-xs">🖼️ Kütüphaneden</button>
        )}
      </div>
    </div>
  )
}

// Medya kütüphanesi penceresi — daha önce yüklenen görsel/videolardan seç
// ya da yeni yükle. Silme yok (bkz. backend list_assets).
export function MedyaKutuphanesi({ storeId, tur, onSec, onKapat, yukle }) {
  const [items, setItems] = useState(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    api.get(`/api/store-settings/${storeId}/assets`)
      .then(r => setItems(r.items || [])).catch(() => setItems([]))
  }, [storeId])
  const gorunen = (items || []).filter(o => tur === 'hepsi' || o.tur === tur)
  const yeni = async file => {
    if (!file) return
    setBusy(true)
    try { const url = await yukle('hero', file); if (url) onSec(url) } finally { setBusy(false) }
  }
  return (
    <div className="fixed inset-0 z-[200] bg-black/60 flex items-center justify-center p-4"
      onMouseDown={e => e.target === e.currentTarget && onKapat()}>
      <div className="card w-full max-w-2xl max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold">🖼️ Medya kütüphanesi</h2>
          <button onClick={onKapat} className="text-panel-muted hover:text-panel-ink text-xl leading-none">×</button>
        </div>
        <div className="overflow-y-auto flex-1 min-h-40">
          {items === null ? <div className="skeleton h-5 w-40 rounded" />
            : gorunen.length === 0 ? <p className="text-sm text-panel-muted py-8 text-center">Henüz yüklenmiş dosya yok.</p>
            : (
              <div className="grid grid-cols-3 sm:grid-cols-5 gap-2">
                {gorunen.map(o => (
                  <button key={o.url} type="button" onClick={() => onSec(o.url)} title={o.alan}
                    className="aspect-square rounded-lg overflow-hidden border border-panel-border hover:border-panel-accent bg-panel-input">
                    {o.tur === 'video'
                      ? <video src={o.url} muted playsInline preload="metadata" className="w-full h-full object-cover" />
                      : <img src={o.url.replace(/(\.(jpg|png))$/i, '-400$1')} alt="" loading="lazy"
                          onError={e => { if (!e.currentTarget.dataset.yedek) { e.currentTarget.dataset.yedek = '1'; e.currentTarget.src = o.url } }}
                          className="w-full h-full object-cover" />}
                  </button>
                ))}
              </div>
            )}
        </div>
        <label className="btn-ghost !py-2 text-xs cursor-pointer mt-3 text-center">
          {busy ? 'Yükleniyor…' : '+ Yeni dosya yükle'}
          <input type="file" className="hidden" disabled={busy}
            accept={tur === 'gorsel' ? 'image/*' : 'image/*,video/mp4,video/webm,video/quicktime'}
            onChange={e => yeni(e.target.files?.[0])} />
        </label>
      </div>
    </div>
  )
}
