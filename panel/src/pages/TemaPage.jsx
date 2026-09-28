import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useStore } from '../lib/store'
import { useToast } from '../components/Toast'

// Tema Kütüphanesi (Shopify tarzı) — yayındaki tema + taslak temalar.
// Özelleştir → /tema/duzenle tam ekran editörü açar (taslaklar ?taslak=key ile).
// Taslaklar yayını etkilemeden düzenlenir; Yayınla ile takas edilir
// (eski yayın "Önceki yayın" taslağı olarak saklanır — geri dönülebilir).
export default function TemaPage() {
  const { storeId } = useStore()
  const navigate = useNavigate()
  const toast = useToast()
  const [live, setLive] = useState(null)
  const [drafts, setDrafts] = useState([])
  const [presets, setPresets] = useState([])
  const [busy, setBusy] = useState(false)
  const [renaming, setRenaming] = useState(null)  // {key, name}

  const load = useCallback(async () => {
    if (!storeId) return
    try {
      const [t, d] = await Promise.all([
        api.get(`/api/store-settings/${storeId}/theme`),
        api.get(`/api/store-settings/${storeId}/theme/drafts`),
      ])
      setLive(t)
      setDrafts(d.drafts.sort((a, b) => (b.updated_at || '').localeCompare(a.updated_at || '')))
      api.get(`/api/store-settings/${storeId}/theme/presets`)
        .then(setPresets).catch(() => {})
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Temalar yüklenemedi')
    }
  }, [storeId])
  useEffect(() => { load() }, [load])

  // Temalar adıyla tutulur: aynı adda taslak varsa yenisi açılmaz — üzerine
  // yazmak ya da mevcut olanı açmak sorulur (kopya yığılmasın)
  const newDraft = async (name, theme) => {
    const mevcut = drafts.find(d => (d.name || '').trim() === name.trim())
    if (mevcut && !window.confirm(`"${name}" adında bir tema zaten var.\n\n`
        + `Tamam: şablonla ÜZERİNE yaz (o temadaki değişiklikler gider)\n`
        + `İptal: mevcut "${name}" temasını aç`)) {
      navigate(`/tema/duzenle?taslak=${mevcut.key}`)
      return
    }
    setBusy(true)
    try {
      const key = mevcut?.key || `taslak-${Date.now().toString(36)}`
      await api.put(`/api/store-settings/${storeId}/theme/drafts/${key}`, { name, theme })
      toast.success(mevcut ? `"${name}" teması şablonla yenilendi` : `"${name}" taslağı oluşturuldu`)
      navigate(`/tema/duzenle?taslak=${key}`)
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Taslak oluşturulamadı')
    } finally { setBusy(false) }
  }

  const publish = async (d) => {
    if (!window.confirm(`"${d.name}" yayına alınacak — vitrindeki tema değişir. `
        + `Şu anki "${live.name || 'Mağaza Teması'}" teması taslaklara döner (aynı adda taslak varsa onun üzerine yazılır). Devam?`)) return
    setBusy(true)
    try {
      await api.post(`/api/store-settings/${storeId}/theme/drafts/${d.key}/publish`)
      toast.success('Tema yayında ✓')
      await load()
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Yayınlanamadı')
    } finally { setBusy(false) }
  }

  // Eski sürümün her yayında açtığı "Önceki yayın — tarih" kopyaları
  const yedekler = drafts.filter(d => d.key.startsWith('eski-') || (d.name || '').startsWith('Önceki yayın'))
  const yedekleriTemizle = async () => {
    if (!window.confirm(`${yedekler.length} otomatik yedek ("Önceki yayın — tarih") kalıcı olarak silinecek. `
        + `Adıyla kaydettiğiniz taslaklar ve yayındaki tema etkilenmez. Devam?`)) return
    setBusy(true)
    try {
      for (const d of yedekler) await api.del(`/api/store-settings/${storeId}/theme/drafts/${d.key}`)
      toast.success('Otomatik yedekler temizlendi')
      await load()
    } catch { toast.error('Bazı yedekler silinemedi'); await load() }
    finally { setBusy(false) }
  }

  const remove = async (d) => {
    if (!window.confirm(`"${d.name}" taslağı kalıcı olarak silinecek. Emin misiniz?`)) return
    setBusy(true)
    try {
      await api.del(`/api/store-settings/${storeId}/theme/drafts/${d.key}`)
      await load()
    } catch { toast.error('Silinemedi') }
    finally { setBusy(false) }
  }

  const rename = async () => {
    if (!renaming) return
    setBusy(true)
    try {
      await api.put(`/api/store-settings/${storeId}/theme/drafts/${renaming.key}`,
        { name: renaming.name, theme: drafts.find(x => x.key === renaming.key)?.theme })
      setRenaming(null)
      await load()
    } catch (e) { toast.error(typeof e?.detail === 'string' ? e.detail : 'Ad değiştirilemedi') }
    finally { setBusy(false) }
  }

  if (!live) return <p className="text-sm text-panel-muted">Yükleniyor…</p>

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Tema</h1>
        <p className="text-xs text-panel-muted mt-1">
          Yayındaki temayı özelleştirin veya taslak temalar üzerinde çalışın —
          taslaklar siz yayınlayana kadar vitrini etkilemez.
        </p>
      </div>

      {/* Yayındaki tema */}
      <section>
        <h2 className="text-sm font-semibold mb-2">Yayındaki tema</h2>
        <div className="card !p-4 flex items-center gap-4 border-emerald-500/30">
          <ThemeSwatch theme={live} size="lg" />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-medium text-sm">{live.name || 'Mağaza Teması'}</span>
              <span className="text-[10px] text-emerald-300 bg-emerald-500/10 px-2 py-0.5 rounded-full font-medium">
                ● Yayında
              </span>
            </div>
            <p className="text-xs text-panel-muted mt-0.5">
              {live.sections?.length ?? 0} anasayfa bölümü · {live.font}
            </p>
          </div>
          <button onClick={() => navigate('/tema/duzenle')}
            className="px-4 py-2 rounded-xl text-xs font-medium bg-panel-accent text-white">
            Özelleştir
          </button>
        </div>
      </section>

      {/* Taslaklar */}
      <section>
        <div className="flex items-center mb-2 gap-3">
          <h2 className="text-sm font-semibold">Taslak temalar ({drafts.length})</h2>
          {yedekler.length > 0 && (
            <button onClick={yedekleriTemizle} disabled={busy}
              className="ml-auto text-xs text-red-300 hover:text-red-200 disabled:opacity-40">
              Otomatik yedekleri temizle ({yedekler.length})
            </button>
          )}
        </div>
        <div className="space-y-2">
          {drafts.map(d => (
            <div key={d.key} className="card !p-4 flex items-center gap-4">
              <ThemeSwatch theme={d.theme} />
              <div className="flex-1 min-w-0">
                {renaming?.key === d.key ? (
                  <div className="flex gap-1.5">
                    <input className="input !py-1 text-xs" value={renaming.name} maxLength={80} autoFocus
                      onChange={e => setRenaming(r => ({ ...r, name: e.target.value }))}
                      onKeyDown={e => e.key === 'Enter' && rename()} />
                    <button onClick={rename} disabled={busy} className="btn-ghost !py-1 text-xs">✓</button>
                    <button onClick={() => setRenaming(null)} className="btn-ghost !py-1 text-xs">×</button>
                  </div>
                ) : (
                  <button onClick={() => setRenaming({ key: d.key, name: d.name })}
                    className="font-medium text-sm truncate hover:underline text-left py-1.5"
                    title="Adı değiştirmek için tıklayın">
                    {d.name} ✏️
                  </button>
                )}
                <p className="text-xs text-panel-muted mt-0.5">
                  {d.theme.sections?.length ?? 0} bölüm
                  {d.updated_at && ` · ${new Date(d.updated_at).toLocaleString('tr-TR')}`}
                </p>
              </div>
              <button onClick={() => navigate(`/tema/duzenle?taslak=${d.key}`)}
                className="btn-ghost !py-1.5 text-xs">Düzenle</button>
              <button onClick={() => publish(d)} disabled={busy}
                className="px-3 py-1.5 rounded-xl text-xs font-medium bg-emerald-600 text-white disabled:opacity-40">
                🚀 Yayınla
              </button>
              <button onClick={() => remove(d)} disabled={busy}
                className="text-red-300 hover:text-red-300 text-xs px-2 py-1.5">Sil</button>
            </div>
          ))}
          {drafts.length === 0 && (
            <div className="card text-center !p-6 text-xs text-panel-muted">
              Taslak yok — aşağıdan yayındaki temanın kopyasıyla veya bir şablonla başlayın.
            </div>
          )}
        </div>
      </section>

      {/* Yeni taslak */}
      <section>
        <h2 className="text-sm font-semibold mb-2">Yeni taslak oluştur</h2>
        <div className="flex gap-2 flex-wrap">
          <button disabled={busy}
            onClick={() => newDraft(`${live.name || 'Mağaza Teması'} (kopya)`, live)}
            className="card !p-3 text-left hover:border-panel-accent transition disabled:opacity-50">
            <div className="text-sm font-medium">📋 Yayındaki temanın kopyası</div>
            <p className="text-[11px] text-panel-muted mt-0.5">
              Mevcut temayı bozmadan üzerinde deneme yapın.
            </p>
          </button>
          {presets.map(pr => (
            <button key={pr.key} disabled={busy}
              onClick={() => newDraft(pr.label, sablonuUygula(pr.theme, live))}
              className="card !p-3 text-left hover:border-panel-accent transition disabled:opacity-50">
              <SablonKrokisi tema={pr.theme} />
              <div className="flex items-center gap-2 text-sm font-medium mt-2">
                <span className="flex gap-1">
                  {[pr.colors.primary, pr.colors.accent, pr.colors.bg].map((c2, i) => (
                    <span key={i} className="w-3.5 h-3.5 rounded-full border border-panel-border"
                      style={{ background: c2 }} />
                  ))}
                </span>
                {pr.label} şablonu
              </div>
              <p className="text-[11px] text-panel-muted mt-0.5 max-w-56">{pr.description}</p>
            </button>
          ))}
        </div>
        <p className="text-[11px] text-panel-muted mt-2">
          Şablon yalnız görünümü değiştirir: logo, menü, footer, WhatsApp, çark/çıkış kampanyası ve
          sepet mesajlarınız taslakta korunur.
        </p>
      </section>
    </div>
  )
}

// Şablon yalnız GÖRÜNÜMÜ değiştirir; mağazanın kendi içeriği yayındaki
// temadan taşınır. Eskiden yalnız logo/WhatsApp/footer korunuyordu: şablondan
// açılan taslak yayınlanınca üst menü, çark/çıkış kampanyası, sepet mesajları
// ve metin sözlüğü sessizce siliniyordu.
const KORUNAN_ALANLAR = ['logo_url', 'favicon_url', 'logo_width', 'logo_width_mobile', 'whatsapp', 'footer',
  'nav_links', 'cark', 'cikis', 'cart_messages', 'texts', 'thankyou', 'trust_badges', 'collection_pages']
function sablonuUygula(sablon, yayin) {
  const tema = structuredClone(sablon)
  for (const alan of KORUNAN_ALANLAR) {
    if (yayin[alan] !== undefined && yayin[alan] !== null) tema[alan] = structuredClone(yayin[alan])
  }
  // Açılış pop-up'ı: mağaza kendi kampanyasını yazmışsa o kalır
  if (yayin.popup?.baslik || yayin.popup?.metin) tema.popup = structuredClone(yayin.popup)
  return tema
}

// Tema renklerinden mini kart önizlemesi.
function ThemeSwatch({ theme, size = 'md' }) {
  const c = theme.colors || {}
  return (
    <div className={`${size === 'lg' ? 'w-20 h-14' : 'w-16 h-12'} rounded-xl border border-panel-border overflow-hidden shrink-0 flex flex-col`}
      style={{ background: c.bg || '#fff' }}>
      <div className="h-2.5" style={{ background: c.primary || '#111' }} />
      <div className="flex-1 flex items-center justify-center gap-1 px-1.5">
        <span className="w-3 h-3 rounded-full" style={{ background: c.accent || '#999' }} />
        <span className="flex-1 h-1.5 rounded-full opacity-30" style={{ background: c.primary || '#111' }} />
      </div>
    </div>
  )
}

// Şablonun şematik krokisi — kendi verisinden çizilir (renkler, header
// düzeni, buton şekli, bölüm sırası). Ekran görüntüsü yerine: hazır
// şablonların görsel alanları boş gelir, fotoğraf boş sayfa gösterirdi;
// kroki yapıyı anlatır ve yeni şablonlarda kendiliğinden çalışır.
function SablonKrokisi({ tema }) {
  const c = tema.colors || {}
  const st = tema.style || {}
  const hap = st.button_shape === 'pill'
  const ortali = st.heading_style === 'showcase'
  const minimal = st.card_style === 'minimal'
  const cizgi = (en, renk = c.primary, op = 0.35) => (
    <div className="h-1 rounded-full" style={{ width: en, background: renk, opacity: op }} />
  )
  const baslik = () => (
    <div className={`flex flex-col gap-0.5 mb-1 ${ortali ? 'items-center' : ''}`}>
      {ortali && cizgi(14, '#111', 0.5)}
      {cizgi(ortali ? 34 : 24, '#111', 0.7)}
    </div>
  )
  const bolum = (sec, i) => {
    const s = sec.settings || {}
    switch (sec.type) {
      case 'hero_slider': {
        const sol = s.align === 'left'
        if (s.stil === 'bolunmus') {
          return (
            <div key={i} className="h-12 rounded-md grid grid-cols-[40%_60%] items-center px-1.5 gap-1"
              style={{ background: s.panel_renk || '#efefef' }}>
              <div className="flex flex-col gap-0.5">
                {cizgi(20, '#111', 0.75)}{cizgi(14, '#111', 0.4)}
                <div className="mt-0.5 h-1.5 w-7 rounded-full" style={{ background: c.primary }} />
              </div>
              <div className="h-9 rounded-sm bg-black/10" />
            </div>
          )
        }
        return (
          <div key={i} className={`rounded-md flex flex-col justify-center gap-1 px-2 ${s.height === 'tall' ? 'h-14' : 'h-10'} ${sol ? 'items-start' : 'items-center'}`}
            style={{ background: `linear-gradient(120deg, ${c.primary}, ${c.accent})` }}>
            {cizgi(sol ? 38 : 44, '#fff', 0.9)}
            {cizgi(26, '#fff', 0.6)}
            <div className="flex gap-1 mt-0.5">
              <div className={`h-1.5 w-6 bg-white ${hap ? 'rounded-full' : 'rounded-sm'}`} />
              <div className={`h-1.5 w-6 border border-white/80 ${hap ? 'rounded-full' : 'rounded-sm'}`} />
            </div>
          </div>
        )
      }
      case 'gallery': {
        const hikaye = s.aspect === 'story'
        return (
          <div key={i}>{baslik()}
            <div className="flex gap-1 overflow-hidden">
              {[0, 1, 2, 3, 4].map(k => (
                <div key={k} className={`shrink-0 rounded-sm bg-black/15 ${hikaye ? 'w-5 h-9' : 'w-6 h-6'}`} />
              ))}
            </div>
          </div>
        )
      }
      case 'featured_collections':
        return (
          <div key={i}>{baslik()}
            <div className={`grid gap-1 ${s.layout === 'showcase' ? 'grid-cols-2' : 'grid-cols-4'}`}>
              {(s.layout === 'showcase' ? [0, 1] : [0, 1, 2, 3]).map(k => (
                <div key={k} className={`rounded-sm ${s.layout === 'showcase' ? 'h-9' : 'h-5'} flex items-end p-0.5`}
                  style={{ background: c.accent, opacity: 0.55 }}>{cizgi(10, '#fff', 0.9)}</div>
              ))}
            </div>
          </div>
        )
      case 'products_grid': case 'featured_products':
        return (
          <div key={i}>{baslik()}
            <div className="grid grid-cols-4 gap-1">
              {[0, 1, 2, 3].map(k => (
                <div key={k} className={`rounded-sm p-0.5 ${minimal ? '' : 'border border-black/10'}`}
                  style={minimal ? undefined : { background: '#fff' }}>
                  <div className="h-5 rounded-sm bg-black/10" />
                  <div className={`mt-0.5 flex ${minimal ? 'justify-center' : ''}`}>{cizgi(12, '#111', 0.5)}</div>
                </div>
              ))}
            </div>
          </div>
        )
      case 'banner':
        return <div key={i} className="h-6 rounded-md bg-black/10" />
      case 'kurdele':
        return (
          <div key={i} className="relative h-7 overflow-hidden">
            <div className="absolute -inset-x-2 top-1.5 h-2 -rotate-3" style={{ background: '#edff34' }} />
            <div className="absolute -inset-x-2 top-4 h-2 rotate-3" style={{ background: '#e7d4f3' }} />
          </div>
        )
      case 'icon_bar':
        return (
          <div key={i} className={`grid grid-cols-4 ${s.stil === 'serit' ? 'border border-black/10 rounded-sm divide-x divide-black/10' : 'gap-1'}`}>
            {[0, 1, 2, 3].map(k => (
              <div key={k} className={`h-3 flex items-center justify-center ${s.stil === 'serit' ? '' : 'rounded-sm border border-black/10'}`}>
                {cizgi(8, '#111', 0.35)}
              </div>
            ))}
          </div>
        )
      case 'stil_onerici': case 'kilif_onizleme': {
        const koyu = sec.type === 'kilif_onizleme'
        return (
          <div key={i} className="h-10 rounded-md grid grid-cols-2 overflow-hidden border border-black/10"
            style={{ background: koyu ? '#171717' : '#fcfcfa' }}>
            <div className="flex flex-col justify-center gap-0.5 px-1">
              {cizgi(18, koyu ? '#fff' : '#111', 0.7)}{cizgi(12, koyu ? '#fff' : '#111', 0.35)}
            </div>
            <div className="grid place-items-center" style={{ background: koyu ? '#2a2a28' : '#e5e8ed' }}>
              <div className={`${koyu ? 'w-2.5 h-5 rounded-[3px]' : 'w-4 h-4 rounded-sm -rotate-6'} bg-white/70`} />
            </div>
          </div>
        )
      }
      case 'image_with_text':
        return (
          <div key={i} className="h-8 rounded-md grid grid-cols-2 overflow-hidden"
            style={{ background: s.stil === 'koyu' ? '#171717' : '#fff' }}>
            <div className="bg-black/15" />
            <div className="flex items-center px-1">{cizgi(16, s.stil === 'koyu' ? '#fff' : '#111', 0.7)}</div>
          </div>
        )
      case 'testimonials':
        if (s.stil !== 'fotografli') return <div key={i}>{baslik()}<div className="h-3 rounded-sm bg-black/5" /></div>
        return (
          <div key={i} className="-mx-1.5 px-1.5 py-1.5 bg-black flex gap-1 overflow-hidden">
            {[0, 1].map(k => <div key={k} className="shrink-0 w-16 h-6 rounded-sm border border-white/15 grid grid-cols-2"><div className="bg-white/15" /></div>)}
          </div>
        )
      default:
        return <div key={i}>{baslik()}<div className="h-3 rounded-sm bg-black/5" /></div>
    }
  }
  return (
    <div className="w-44 h-48 rounded-lg border border-panel-border overflow-hidden flex flex-col"
      style={{ background: c.bg || '#fff' }} aria-hidden="true">
      {/* Header */}
      <div className="shrink-0 px-2 py-1 border-b border-black/10 bg-white/70">
        {st.header_layout === 'vitrin' ? (
          <div className="flex flex-col gap-1">
            <div className="w-full flex items-center justify-between">
              {cizgi(10, '#111', 0.3)}
              {cizgi(22, '#111', 0.8)}
              <div className="w-3 h-1.5 rounded-sm bg-black/30" />
            </div>
            <div className="flex gap-1">
              <div className="h-2 w-8 rounded-sm bg-black/80" />
              <div className="h-2 flex-1 rounded-sm bg-black/10" />
            </div>
          </div>
        ) : st.header_layout === 'center' ? (
          <div className="flex flex-col items-center gap-0.5">
            <div className="w-full flex items-center justify-between">
              <div className="w-1.5 h-1.5 rounded-full bg-black/30" />
              {cizgi(22, '#111', 0.8)}
              <div className="w-3 h-1.5 rounded-sm bg-black/30" />
            </div>
            <div className="flex gap-1">
              <div className="h-1.5 w-4 rounded-full bg-black/70" />
              {cizgi(8, '#111', 0.3)}{cizgi(8, '#111', 0.3)}
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-1.5">
            {cizgi(16, '#111', 0.8)}
            <div className="flex-1 flex justify-center gap-1">{cizgi(8, '#111', 0.3)}{cizgi(8, '#111', 0.3)}</div>
            <div className="w-3 h-1.5 rounded-sm bg-black/30" />
          </div>
        )}
      </div>
      <div className="flex-1 overflow-hidden p-1.5 space-y-2">
        {(tema.sections || []).slice(0, 6).map(bolum)}
      </div>
    </div>
  )
}
