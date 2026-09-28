import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'
import { SNIPPETS, kampanyaKoduVarMi, kampanyaKodunuAyristir, kampanyaKodunuKaldir } from '../lib/snippets'
import { useStore } from '../lib/store'
import { useToast } from '../components/Toast'
import {
  FONTS, SECTION_TYPES, SECTION_DEFAULTS,
  SectionSettings, Section, ColorField, Toggle, AssetField, UrlPicker, Choice,
  MedyaContext, MedyaKutuphanesi, bosBolumNedeni,
} from '../components/ThemeEditorParts'

// Tam ekran tema editörü (Shopify tarzı) — sol ayar paneli + sağ canlı önizleme.
// ?taslak=<key> ile taslak tema, parametresiz yayındaki tema düzenlenir.
// Önizlemede bir bölüme tıklanınca sol panel o bölümün ayarlarına geçer.
export default function TemaEditorPage() {
  const { storeId, store } = useStore()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const draftKey = searchParams.get('taslak')
  const toast = useToast()

  const [theme, setTheme] = useState(null)
  // Medya kütüphanesi isteği: { tur, resolve } — açık pencere, seçilince çözülür
  const [medyaIstek, setMedyaIstek] = useState(null)
  const [draftName, setDraftName] = useState('')
  const [collections, setCollections] = useState([])
  const [products, setProducts] = useState([])
  const [busy, setBusy] = useState(false)
  const [saveCount, setSaveCount] = useState(0)   // iframe reload anahtarı
  // TELEFON: editör masaüstü için tasarlandı — 400px sol panel + canlı
  // önizleme YAN YANA. 375px'te ikisi birlikte sığmıyor ve sayfa yatay
  // kayıyordu (ölçüldü: 608px). Dar ekranda ikisinden BİRİ gösterilir.
  const [mobilGorunum, setMobilGorunum] = useState('ayarlar')
  const [device, setDevice] = useState('desktop')
  const [openSection, setOpenSection] = useState(null) // dolu ise tek-bölüm modu
  const [customCode, setCustomCode] = useState(null)
  // Aktif kupon kodları — çark/çıkış pop-up'ına yazılan kod gerçekten var mı?
  // (Eski ham kod parçacığında kuponu önce oluşturmak unutuluyordu: müşteri
  // "kazandığı" kodu sepete girince "geçersiz" alıyordu.)
  const [kuponlar, setKuponlar] = useState(null)
  const [pages, setPages] = useState([])         // özel sayfalar (önizleme seçici)
  const [previewPath, setPreviewPath] = useState('/')  // önizlenen vitrin sayfası
  const [dragIdx, setDragIdx] = useState(null)   // sürüklenen bölüm indeksi
  const [overIdx, setOverIdx] = useState(null)   // üzerine gelinen indeks
  const initialRef = useRef('')

  const storefrontUrl = store?.config?.storefront_url
    || (store?.config?.shop_domain ? `https://${store.config.shop_domain}` : 'http://localhost:3001')
  const iframeRef = useRef(null)
  const previewTimer = useRef(null)
  const skipFirst = useRef(true)

  // CANLI ÖNİZLEME: değişiklikten 800ms sonra taslağı gönder, iframe'i tazele.
  // DİKKAT: contentWindow.location.reload() CROSS-ORIGIN'de (panel ile vitrin
  // farklı domain) SecurityError fırlatır ve önizleme HİÇ yenilenmez — bu
  // yüzden iframe React key'i üzerinden remount edilir (origin bağımsız).
  useEffect(() => {
    if (!theme || !storeId) return
    if (skipFirst.current) { skipFirst.current = false; return }
    clearTimeout(previewTimer.current)
    previewTimer.current = setTimeout(async () => {
      try {
        await api.put(`/api/store-settings/${storeId}/theme/preview`, theme)
        setSaveCount(n => n + 1)   // iframe key değişir → önizleme tazelenir
      } catch { /* önizleme başarısız — kaydetmeyi engellemez */ }
    }, 800)
    return () => clearTimeout(previewTimer.current)
  }, [theme, storeId])

  // Önizlemede bölüme tıklanınca sol panel o bölümün ayarına geçer
  useEffect(() => {
    const onMsg = (e) => {
      if (e.data?.type === 'vitrin-sec-click' && e.data.id) setOpenSection(e.data.id)
    }
    window.addEventListener('message', onMsg)
    return () => window.removeEventListener('message', onMsg)
  }, [])

  const load = useCallback(async () => {
    if (!storeId) return
    try {
      const [c, cc, pr] = await Promise.all([
        api.get(`/api/catalog/collections?store_id=${storeId}`),
        api.get(`/api/store-settings/${storeId}/custom-code`),
        api.get(`/api/catalog/products?store_id=${storeId}&status=active&slim=1`),
      ])
      setCollections(c.filter(x => x.is_active))
      setProducts(pr)
      setCustomCode(cc)
      api.get(`/api/store-settings/${storeId}/pages`)
        .then(r => setPages(r.pages || [])).catch(() => {})

      let t
      if (draftKey) {
        const { drafts } = await api.get(`/api/store-settings/${storeId}/theme/drafts`)
        const d = drafts.find(x => x.key === draftKey)
        if (!d) { toast.error('Taslak bulunamadı'); navigate('/tema'); return }
        t = d.theme
        setDraftName(d.name)
        // Önizleme taslağı göstersin (yayındaki temayı değil)
        skipFirst.current = true
        api.put(`/api/store-settings/${storeId}/theme/preview`, t)
          .then(() => setSaveCount(n => n + 1)).catch(() => {})
      } else {
        t = await api.get(`/api/store-settings/${storeId}/theme`)
      }
      setTheme(t)
      initialRef.current = JSON.stringify([t, cc])
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Tema yüklenemedi')
    }
  }, [storeId, draftKey])
  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (!storeId) return
    api.get(`/api/discounts?store_id=${storeId}`)
      .then(r => setKuponlar(new Set((r.items || r || []).filter(k => k.is_active !== false)
        .map(k => String(k.code || '').toUpperCase()))))
      .catch(() => setKuponlar(null))
  }, [storeId])

  const save = async () => {
    setBusy(true)
    // KRİTİK: bekleyen önizleme PUT'u iptal — yoksa Kaydet ile yarışıp
    // eski temayı config'e geri yazabiliyor (kaydettim-ama-eski-haline-döndü bug'ı)
    clearTimeout(previewTimer.current)
    try {
      if (draftKey) {
        await Promise.all([
          api.put(`/api/store-settings/${storeId}/theme/drafts/${draftKey}`,
            { name: draftName, theme }),
          customCode ? api.put(`/api/store-settings/${storeId}/custom-code`, customCode) : Promise.resolve(),
        ])
        initialRef.current = JSON.stringify([theme, customCode])
        toast.success('Taslak kaydedildi (yayında değişiklik yok)')
      } else {
        const [t] = await Promise.all([
          api.put(`/api/store-settings/${storeId}/theme`, theme),
          customCode ? api.put(`/api/store-settings/${storeId}/custom-code`, customCode) : Promise.resolve(),
        ])
        skipFirst.current = true   // setTheme(t) yeni önizleme PUT'u tetiklemesin
        setTheme(t)
        initialRef.current = JSON.stringify([t, customCode])
        api.del(`/api/store-settings/${storeId}/theme/preview`).catch(() => {})
        setSaveCount(n => n + 1)
        toast.success('Tema kaydedildi ve yayında ✓')
      }
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Kaydedilemedi')
    } finally { setBusy(false) }
  }

  const publish = async () => {
    if (!window.confirm(`"${draftName}" yayına alınacak — vitrindeki tema değişir. `
        + `Şu anki yayın, taslak olarak saklanır. Devam?`)) return
    setBusy(true)
    try {
      if (dirty) await api.put(`/api/store-settings/${storeId}/theme/drafts/${draftKey}`, { theme })
      await api.post(`/api/store-settings/${storeId}/theme/drafts/${draftKey}/publish`)
      toast.success('Tema yayında ✓')
      navigate('/tema')
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Yayınlanamadı')
    } finally { setBusy(false) }
  }

  const discard = () => {
    try {
      const [t, cc] = JSON.parse(initialRef.current)
      skipFirst.current = true   // setTheme yeni önizleme PUT'u tetiklemesin
      setTheme(t); setCustomCode(cc)
      const after = draftKey
        ? api.put(`/api/store-settings/${storeId}/theme/preview`, t)
        : api.del(`/api/store-settings/${storeId}/theme/preview`)
      // cross-origin reload çalışmaz — iframe remount ile tazele
      after.then(() => setSaveCount(n => n + 1)).catch(() => {})
    } catch { /* ilk yükleme yoksa */ }
  }
  const dirty = !!theme && initialRef.current !== '' &&
    JSON.stringify([theme, customCode]) !== initialRef.current

  const goBack = () => {
    if (dirty && !window.confirm('Kaydedilmemiş değişiklikler var — çıkılsın mı?')) return
    if (draftKey) api.del(`/api/store-settings/${storeId}/theme/preview`).catch(() => {})
    navigate('/tema')
  }

  const uploadAsset = async (kind, file, target) => {
    if (!file) return
    setBusy(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('kind', kind)
      const r = await api.postForm(`/api/store-settings/${storeId}/assets`, fd)
      target(r.url)
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Yükleme başarısız')
    } finally { setBusy(false) }
  }

  const set = (path, value) => {
    setTheme(t => {
      const next = structuredClone(t)
      const keys = path.split('.')
      let obj = next
      for (const k of keys.slice(0, -1)) {
        if (obj[k] == null || typeof obj[k] !== 'object') obj[k] = {}
        obj = obj[k]
      }
      obj[keys[keys.length - 1]] = value
      return next
    })
  }

  // ── Bölüm işlemleri ──
  const patchSectionMeta = (id, meta) => {
    setTheme(t => ({
      ...t,
      sections: t.sections.map(s => s.id === id ? { ...s, ...meta } : s),
    }))
  }
  const patchSection = (id, patch) => {
    setTheme(t => ({
      ...t,
      sections: t.sections.map(s => s.id === id
        ? { ...s, settings: { ...s.settings, ...patch } } : s),
    }))
  }
  const moveSec = (idx, dir) => {
    setTheme(t => {
      const arr = [...t.sections]
      const j = idx + dir
      if (j < 0 || j >= arr.length) return t
      ;[arr[idx], arr[j]] = [arr[j], arr[idx]]
      return { ...t, sections: arr }
    })
  }
  const dropSec = (from, to) => {
    setDragIdx(null); setOverIdx(null)
    if (from === null || to === null || from === to) return
    setTheme(t => {
      const arr = [...t.sections]
      const [moved] = arr.splice(from, 1)
      arr.splice(to, 0, moved)
      return { ...t, sections: arr }
    })
  }
  const removeSec = (id) => {
    if (!window.confirm('Bu bölüm anasayfadan kaldırılacak. Emin misiniz?')) return
    setTheme(t => ({ ...t, sections: t.sections.filter(s => s.id !== id) }))
    setOpenSection(o => (o === id ? null : o))
  }
  const addSec = (type) => {
    const id = `${type}-${Date.now().toString(36)}`
    setTheme(t => ({
      ...t,
      sections: [...t.sections, { id, type, settings: structuredClone(SECTION_DEFAULTS[type]) }],
    }))
    setOpenSection(id)
  }

  if (!theme) {
    return (
      <div className="h-screen flex items-center justify-center text-sm text-panel-muted">
        Tema yükleniyor…
      </div>
    )
  }

  const activeSec = openSection ? theme.sections.find(s => s.id === openSection) : null
  const activeIdx = activeSec ? theme.sections.findIndex(s => s.id === openSection) : -1

  // BAĞLAMSAL PANEL: seçili önizleme sayfasına göre ilgili ayarlar gösterilir
  // (Shopify: sepette sepet ayarları, onay ekranında onay metinleri...)
  const pageScope = previewPath === '/' ? 'home'
    : previewPath.startsWith('/sepet') ? 'sepet'
    : previewPath.startsWith('/odeme/sonuc') ? 'tesekkur'
    : previewPath.startsWith('/koleksiyon/') ? 'koleksiyon'
    : 'genel'
  const showHome = pageScope === 'home'          // anasayfa bölüm listesi
  const showGeneral = pageScope !== 'tesekkur' && pageScope !== 'sepet'  // marka/menü/footer…
  const showCart = pageScope === 'home' || pageScope === 'sepet'
  // Önizlenen koleksiyonun slug'ı — sayfa bazlı içerik bloğu bu anahtarla saklanır
  const collectionSlug = pageScope === 'koleksiyon'
    ? previewPath.replace('/koleksiyon/', '').split('?')[0] : null
  const collectionBlock = collectionSlug ? (theme.collection_pages?.[collectionSlug] || {}) : {}

  // Görsel alanlarının ortak yükle/seç yolu (AssetField, galeri)
  const medya = {
    yukle: (kind, file) => new Promise(res => uploadAsset(kind, file, res)),
    sec: tur => new Promise(res => setMedyaIstek({ tur, resolve: res })),
  }
  const medyaKapat = url => { medyaIstek?.resolve(url || null); setMedyaIstek(null) }

  return (
    <MedyaContext.Provider value={medya}>
    {medyaIstek && (
      <MedyaKutuphanesi storeId={storeId} tur={medyaIstek.tur} yukle={medya.yukle}
        onSec={url => medyaKapat(url)} onKapat={() => medyaKapat(null)} />
    )}
    <div className="h-screen flex flex-col bg-panel-input/40">
      {/* Üst çubuk */}
      {/* Telefonda sekiz kontrol tek satıra sığmıyordu — sarıyor, yükseklik
          serbest; sm'den itibaren eski sabit 56px tek satır. */}
      <header className="shrink-0 bg-panel-card border-b border-panel-border
                         flex items-center gap-2 sm:gap-3 px-3 sm:px-4
                         flex-wrap py-2 sm:py-0 sm:h-14 sm:flex-nowrap">
        <button onClick={goBack} className="btn-ghost !py-1.5 text-xs">← Temalar</button>
        <div className="min-w-0">
          {/* Tema adı — yayındayken de düzenlenebilir (Kaydet ile kalıcılaşır) */}
          <input
            className="text-sm font-semibold bg-transparent border-b border-transparent
              hover:border-panel-border focus:border-panel-accent focus:outline-none
              w-44 truncate transition-colors"
            title="Tema adını düzenlemek için tıklayın"
            maxLength={80}
            value={draftKey ? draftName : (theme.name || 'Mağaza Teması')}
            onChange={e => draftKey
              ? setDraftName(e.target.value)
              : set('name', e.target.value)} />
          <div className="text-[10px] leading-none">
            {draftKey ? (
              <span className="text-panel-muted bg-white/5 px-1.5 py-0.5 rounded-full">Taslak — yayını etkilemez</span>
            ) : (
              <span className="text-emerald-300 bg-emerald-500/10 px-1.5 py-0.5 rounded-full">● Yayında</span>
            )}
          </div>
        </div>

        {/* Önizlenecek sayfa — kategorili seçim (Shopify üst menüsü) */}
        <select value={previewPath}
          onChange={e => setPreviewPath(e.target.value)}
          className="input !w-auto !py-1.5 text-xs max-w-52">
          <optgroup label="Genel">
            <option value="/">🏠 Ana sayfa</option>
            <option value="/urunler">🛍 Tüm ürünler</option>
            <option value="/sepet">🛒 Sepet</option>
            <option value="/odeme/sonuc?demo=1">🧾 Sipariş Onayı (örnek)</option>
            <option value="/favoriler">❤️ Favoriler</option>
            <option value="/hesap">👤 Hesap</option>
            <option value="/blog">✍️ Blog</option>
          </optgroup>
          {collections.length > 0 && (
            <optgroup label="Koleksiyonlar">
              {collections.map(c => (
                <option key={c.slug} value={`/koleksiyon/${c.slug}`}>{c.title}</option>
              ))}
            </optgroup>
          )}
          {products.length > 0 && (
            <optgroup label="Ürünler">
              {products.slice(0, 30).map(p => (
                <option key={p.slug} value={`/urun/${p.slug}`}>{p.title}</option>
              ))}
            </optgroup>
          )}
          {pages.length > 0 && (
            <optgroup label="Sayfalar">
              {pages.map(p => (
                <option key={p.slug} value={`/sayfa/${p.slug}`}>{p.title}</option>
              ))}
            </optgroup>
          )}
        </select>

        <div className="hidden sm:flex gap-1 bg-panel-input rounded-lg p-0.5 ml-auto">
          {[['desktop', '🖥 Masaüstü'], ['mobile', '📱 Mobil']].map(([k, l]) => (
            <button key={k} onClick={() => setDevice(k)}
              className={`px-2.5 py-1 rounded-md text-xs transition ${device === k
                ? 'bg-panel-card shadow-sm font-medium' : 'text-panel-muted hover:text-panel-ink'}`}>
              {l}
            </button>
          ))}
        </div>
        {/* Telefonda hangi bölümün görüneceğini seçer (masaüstünde ikisi yan yana). */}
        <div className="sm:hidden flex gap-1 bg-panel-input rounded-lg p-0.5 order-last w-full">
          {[['ayarlar', '⚙️ Ayarlar'], ['onizleme', '👁 Önizleme']].map(([k, l]) => (
            <button key={k} onClick={() => setMobilGorunum(k)}
              className={`flex-1 px-2.5 py-2 rounded-md text-xs transition ${mobilGorunum === k
                ? 'bg-panel-card shadow-sm font-medium' : 'text-panel-muted'}`}>
              {l}
            </button>
          ))}
        </div>
        <button onClick={() => setSaveCount(n => n + 1)} className="btn-ghost !py-1.5 text-xs">↻</button>
        {dirty && (
          <button onClick={discard} disabled={busy} className="btn-ghost !py-1.5 text-xs">
            Vazgeç
          </button>
        )}
        <button onClick={save} disabled={busy || !dirty}
          className="px-4 py-1.5 rounded-xl text-xs font-medium bg-panel-accent text-white disabled:opacity-40">
          {busy ? '…' : draftKey ? 'Taslağı Kaydet' : 'Kaydet ve Yayınla'}
        </button>
        {draftKey && (
          <button onClick={publish} disabled={busy}
            className="px-4 py-1.5 rounded-xl text-xs font-medium bg-emerald-600 text-white disabled:opacity-40">
            🚀 Yayınla
          </button>
        )}
      </header>

      <div className="flex-1 flex min-h-0">
        {/* Sol panel */}
        <div className={`w-full sm:w-[400px] sm:shrink-0 bg-panel-card border-r
                         border-panel-border overflow-y-auto p-4 space-y-4
                         ${mobilGorunum === 'ayarlar' ? '' : 'hidden sm:block'}`}>
          {activeSec ? (
            /* ── Tek bölüm modu — önizlemede tıklanan/lısteden seçilen bölüm ── */
            <>
              <div className="flex items-center gap-2 sticky -top-4 -mx-4 px-4 py-2.5 bg-panel-card border-b border-panel-border z-10">
                <button onClick={() => setOpenSection(null)} className="btn-ghost !py-1 text-xs">← Geri</button>
                <span className="text-sm font-semibold truncate">
                  {(SECTION_TYPES[activeSec.type] || { icon: '▫️', label: activeSec.type }).icon}{' '}
                  {(SECTION_TYPES[activeSec.type] || { label: activeSec.type }).label}
                </span>
                {activeSec.hidden && (
                  <span className="text-[10px] bg-slate-500/20 text-panel-muted px-1.5 py-0.5 rounded-full">gizli</span>
                )}
              </div>
              <div className="flex items-center gap-1.5 text-xs">
                <button onClick={() => patchSectionMeta(activeSec.id, { hidden: !activeSec.hidden })}
                  className="btn-ghost !py-1 text-xs">
                  {activeSec.hidden ? '🙈 Gizli — göster' : '👁 Görünür — gizle'}
                </button>
                <button onClick={() => moveSec(activeIdx, -1)} disabled={activeIdx === 0}
                  className="w-7 h-7 rounded-lg border border-panel-border disabled:opacity-30">↑</button>
                <button onClick={() => moveSec(activeIdx, 1)} disabled={activeIdx === theme.sections.length - 1}
                  className="w-7 h-7 rounded-lg border border-panel-border disabled:opacity-30">↓</button>
                <button onClick={() => removeSec(activeSec.id)}
                  className="ml-auto text-red-300 hover:text-red-300">Bölümü Sil</button>
              </div>
              <div className="flex items-center gap-2 text-xs text-panel-muted">
                Zemin:
                {[['none', 'Sayfa rengi'], ['band', 'Beyaz bant']].map(([v, l]) => (
                  <button key={v} onClick={() => patchSectionMeta(activeSec.id, { scheme: v })}
                    className={`px-2 py-0.5 rounded-full border ${(activeSec.scheme || 'none') === v
                      ? 'border-panel-accent bg-emerald-500/10 text-emerald-300'
                      : 'border-panel-border'}`}>{l}</button>
                ))}
              </div>
              {theme.style?.akis_cizgisi && (
                <Toggle checked={!!activeSec.akis}
                  onChange={v => patchSectionMeta(activeSec.id, { akis: v })}
                  label="〰️ Akış çizgisi bu bölümün üstünden geçsin" />
              )}
              <div className="space-y-2">
                <SectionSettings sec={activeSec} collections={collections} products={products}
                  pages={pages} patch={p => patchSection(activeSec.id, p)} uploadAsset={uploadAsset} />
              </div>
            </>
          ) : (
            /* ── Liste modu — genel ayarlar + bölüm listesi ── */
            <>
              {/* Hazır şablonlar bilinçli olarak editörde YOK — şablondan
                  başlamak Tema kütüphanesindeki "Yeni taslak oluştur"dan yapılır */}
              {pageScope !== 'home' && (
                <p className="text-[11px] text-sky-300 bg-sky-500/10 border border-sky-500/30 rounded-xl px-3 py-2">
                  {pageScope === 'sepet' ? '🛒 Sepet sayfası ayarları gösteriliyor.'
                    : pageScope === 'tesekkur' ? '🧾 Sipariş onayı ekranı ayarları gösteriliyor.'
                    : 'ℹ️ Bu sayfa genel tema ayarlarını (renk, menü, footer…) kullanır.'}
                  {' '}Anasayfa bölümleri için üstten <b>Ana sayfa</b>yı seçin.
                </p>
              )}

              {/* Sipariş onayı (teşekkür) metinleri — yalnız onay ekranında */}
              {pageScope === 'tesekkur' && (
                <Section title="Sipariş Onayı Ekranı" icon="🧾">
                  <label className="block text-sm">
                    <span className="text-panel-muted text-xs">Başlık</span>
                    <input className="input mt-1" maxLength={120}
                      value={theme.thankyou?.title || ''}
                      onChange={e => set('thankyou.title', e.target.value)}
                      placeholder="Siparişiniz alındı!" />
                  </label>
                  <label className="block text-sm">
                    <span className="text-panel-muted text-xs">Mesaj</span>
                    <textarea className="input mt-1" rows={3} maxLength={1000}
                      value={theme.thankyou?.message || ''}
                      onChange={e => set('thankyou.message', e.target.value)}
                      placeholder="Onay e-postası gönderildi. Siparişinizin durumunu istediğiniz an kontrol edebilirsiniz." />
                  </label>
                  <p className="text-[11px] text-panel-muted">
                    Onay e-postasının metinleri Ayarlar → E-posta sekmesinden düzenlenir.
                  </p>
                </Section>
              )}

              {pageScope === 'koleksiyon' && collectionSlug && (
                <Section title="Bu Koleksiyon Sayfası" icon="📄">
                  <p className="text-[11px] text-panel-muted -mt-1">
                    Yalnızca <b>{collectionSlug}</b> sayfasında görünen içerik bloğu —
                    örn. kılıf takma rehberi görseli. Kapak görseli ve açıklama
                    Koleksiyonlar sayfasından düzenlenir.
                  </p>
                  <AssetField label="Blok görseli (ops.)" current={collectionBlock.image}
                    onUrl={url => set(`collection_pages.${collectionSlug}.image`, url)}
                    onClear={() => set(`collection_pages.${collectionSlug}.image`, null)} />
                  <label className="block text-sm">
                    <span className="text-panel-muted text-xs">Blok metni (ops.)</span>
                    <textarea className="input mt-1" rows={4} maxLength={4000}
                      value={collectionBlock.body || ''}
                      onChange={e => set(`collection_pages.${collectionSlug}.body`, e.target.value)}
                      placeholder="Bu koleksiyona özel tanıtım / kullanım rehberi metni…" />
                  </label>
                  <div className="flex gap-2 text-xs items-center">
                    <span className="text-panel-muted">Konum:</span>
                    {[['ust', 'Ürünlerin üstünde'], ['alt', 'Ürünlerin altında']].map(([v, l]) => (
                      <button key={v}
                        onClick={() => set(`collection_pages.${collectionSlug}.position`, v)}
                        className={`px-2.5 py-1 rounded-full border ${(collectionBlock.position || 'ust') === v
                          ? 'border-panel-accent bg-emerald-500/10 text-emerald-300'
                          : 'border-panel-border text-panel-muted'}`}>{l}</button>
                    ))}
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <label className="block text-sm">
                      <span className="text-panel-muted text-xs">Buton yazısı (ops.)</span>
                      <input className="input mt-1" maxLength={60}
                        value={collectionBlock.cta_text || ''}
                        onChange={e => set(`collection_pages.${collectionSlug}.cta_text`, e.target.value)}
                        placeholder="Tüm Ürünler" />
                    </label>
                    <label className="block text-sm">
                      <span className="text-panel-muted text-xs">Buton hedefi</span>
                      <div className="mt-1">
                        <UrlPicker value={collectionBlock.cta_url}
                          collections={collections} products={products} pages={pages}
                          placeholder="Hedef seçin"
                          onChange={url => set(`collection_pages.${collectionSlug}.cta_url`, url)} />
                      </div>
                    </label>
                  </div>
                </Section>
              )}

              {showGeneral && (<>
              <Section title="Renkler" icon="🎨">
                <div className="grid grid-cols-3 gap-3">
                  <ColorField label="Ana renk" value={theme.colors.primary} onChange={v => set('colors.primary', v)} />
                  <ColorField label="Vurgu" value={theme.colors.accent} onChange={v => set('colors.accent', v)} />
                  <ColorField label="Zemin" value={theme.colors.bg} onChange={v => set('colors.bg', v)} />
                </div>
              </Section>

              <Section title="Yazı Tipi" icon="🔤">
                <select className="input" value={theme.font} onChange={e => set('font', e.target.value)}>
                  {FONTS.map(f => <option key={f.key} value={f.key}>{f.label}</option>)}
                </select>
              </Section>

              <Section title="Görünüm" icon="🧩">
                <Choice label="Üst menü" value={theme.style?.header_layout || 'left'}
                  options={[['left', 'Logo solda'], ['center', 'Logo ortada, menü altta'],
                    ['vitrin', 'Logo ortada + Koleksiyonlar düğmesi ve arama çubuğu']]}
                  onChange={v => set('style.header_layout', v)} />
                {theme.style?.header_layout === 'vitrin' && (
                  <div className="space-y-1.5 border border-panel-border rounded-xl p-2.5">
                    <input className="input !py-1.5 text-xs" value={theme.style?.ust_not || ''} maxLength={40}
                      onChange={e => set('style.ust_not', e.target.value)}
                      placeholder="Logonun solundaki küçük yazı (ops.) — örn. SIRA DIŞI TASARIMLAR" />
                    <div className="grid grid-cols-2 gap-1.5">
                      <input className="input !py-1.5 text-xs" value={theme.style?.ust_link_metin || ''} maxLength={30}
                        onChange={e => set('style.ust_link_metin', e.target.value)}
                        placeholder="Sağdaki bağlantı — örn. Sipariş takibi" />
                      <UrlPicker value={theme.style?.ust_link_url || ''} collections={collections} products={products}
                        pages={pages} placeholder="Bağlantı hedefi" onChange={url => set('style.ust_link_url', url)} />
                    </div>
                  </div>
                )}
                <Choice label="Butonlar" value={theme.style?.button_shape || 'rounded'}
                  options={[['rounded', 'Yuvarlatılmış köşe'], ['pill', 'Tam yuvarlak']]}
                  onChange={v => set('style.button_shape', v)} />
                <Choice label="Ürün kartı" value={theme.style?.card_style || 'boxed'}
                  options={[['boxed', 'Çerçeveli'], ['minimal', 'Çerçevesiz, ortalı'], ['yumusak', 'Yumuşak (gri zemin, fiyat sağda)']]}
                  onChange={v => set('style.card_style', v)} />
                <Choice label="Bölüm başlıkları" value={theme.style?.heading_style || 'compact'}
                  options={[['compact', 'Küçük, solda'], ['showcase', 'Büyük, ortalı'], ['editoryal', 'Editoryal (büyük, solda, açıklama sağda)']]}
                  onChange={v => set('style.heading_style', v)} />
                <Choice label="Kaydırınca üst menü" value={theme.style?.header_sabit || 'hep'}
                  options={[['hep', 'Hep görünür'], ['mobil', 'Yalnız mobilde görünür'],
                    ['masaustu', 'Yalnız masaüstünde görünür'], ['yok', 'Sayfayla kayar']]}
                  onChange={v => set('style.header_sabit', v)} />
                <Choice label="Footer" value={theme.style?.footer_stil || 'sade'}
                  options={[['sade', 'Sade (tek blok)'], ['genis', 'Geniş (logolu, sütunlu)']]}
                  onChange={v => set('style.footer_stil', v)} />
                <Toggle checked={!!theme.style?.scroll_top}
                  onChange={v => set('style.scroll_top', v)}
                  label='Sol altta "yukarı çık" düğmesi' />
                <Toggle checked={!!theme.style?.mobil_dock}
                  onChange={v => set('style.mobil_dock', v)}
                  label="📱 Telefonda altta sabit çubuk (Keşfet · Tasarla · Favoriler · Sepet)" />
                <Toggle checked={!!theme.style?.ilerleme}
                  onChange={v => set('style.ilerleme', v)}
                  label="En üstte kaydırma ilerleme çizgisi" />
                <Toggle checked={!!theme.style?.akis_cizgisi}
                  onChange={v => set('style.akis_cizgisi', v)}
                  label="〰️ Anasayfada kaydırdıkça çizilen akış çizgisi" />
                {theme.style?.akis_cizgisi && (
                  <p className="text-[11px] text-panel-muted">
                    Çizgi, bölüm ayarlarında <b>“Akış çizgisi bu bölümün üstünden geçsin”</b> işaretli
                    bölümlerde karşı kenara geçer; ilk işaretli bölümde soldan girer, footer'da biter.
                    {!theme.sections.some(x => x.akis) && ' Henüz işaretli bölüm yok — çizgi görünmez.'}
                  </p>
                )}
              </Section>

              <Section title="Logo ve Favicon" icon="🖼️">
                <AssetField label="Logo" current={theme.logo_url} kind="logo"
                  onUrl={url => set('logo_url', url)}
                  onClear={() => set('logo_url', null)} />
                {theme.logo_url && (<>
                  <label className="block text-sm">
                    <span className="text-panel-muted text-xs">
                      🖥️ Masaüstü logo genişliği: <b>{theme.logo_width || 120}px</b>
                    </span>
                    <input type="range" min="60" max="320" step="10"
                      value={theme.logo_width || 120}
                      onChange={e => set('logo_width', Number(e.target.value))}
                      className="w-full mt-1 accent-emerald-600" />
                  </label>
                  <label className="block text-sm">
                    <span className="text-panel-muted text-xs flex items-center justify-between">
                      <span>📱 Mobil logo genişliği: <b>{theme.logo_width_mobile ? `${theme.logo_width_mobile}px` : 'masaüstüyle aynı'}</b></span>
                      {theme.logo_width_mobile && (
                        <button type="button" onClick={() => set('logo_width_mobile', null)}
                          className="text-[11px] underline">masaüstüyle aynı yap</button>
                      )}
                    </span>
                    <input type="range" min="40" max="240" step="5"
                      value={theme.logo_width_mobile || Math.min(theme.logo_width || 120, 240)}
                      onChange={e => set('logo_width_mobile', Number(e.target.value))}
                      className="w-full mt-1 accent-emerald-600" />
                  </label>
                  <p className="text-[11px] text-panel-muted -mt-1">
                    Önizlemenin üstündeki cihaz düğmesiyle mobil görünümü kontrol edebilirsiniz.
                  </p>
                </>)}
                <AssetField label="Favicon" current={theme.favicon_url} kind="favicon"
                  onUrl={url => set('favicon_url', url)}
                  onClear={() => set('favicon_url', null)} />
              </Section>

              <Section title="Üst Menü" icon="🧭">
                <p className="text-[11px] text-panel-muted -mt-1">
                  Boş bırakılırsa varsayılan menü (Ürünler + Koleksiyonlar) kullanılır.
                  Hedefi listeden seçin; dış site için "Özel bağlantı"yı kullanın.
                </p>
                {(theme.nav_links || []).map((l, i) => (
                  <NavLinkRow key={i} link={l} index={i} count={theme.nav_links.length}
                    collections={collections} products={products} pages={pages}
                    onChange={patch => set('nav_links', theme.nav_links.map((x, j) =>
                      j === i ? { ...x, ...patch } : x))}
                    onMove={dir => {
                      const arr = [...theme.nav_links]
                      const j = i + dir
                      if (j < 0 || j >= arr.length) return
                      ;[arr[i], arr[j]] = [arr[j], arr[i]]
                      set('nav_links', arr)
                    }}
                    onRemove={() => set('nav_links', theme.nav_links.filter((_, j) => j !== i))} />
                ))}
                {(theme.nav_links || []).length < 8 && (
                  <button onClick={() => set('nav_links', [...(theme.nav_links || []), { label: '', url: '' }])}
                    className="btn-ghost !py-1 text-xs">+ Link Ekle</button>
                )}
              </Section>

              <Section title="Duyuru Şeridi" icon="📢">
                <Toggle checked={theme.announcement.enabled}
                  onChange={v => set('announcement.enabled', v)} label="Duyuru şeridini göster" />
                {theme.announcement.enabled && (() => {
                  // Eski tek-duyuru biçimi de okunur; kayıtta items yazılır
                  const items = theme.announcement.items?.length ? theme.announcement.items
                    : (theme.announcement.text ? [{ text: theme.announcement.text, url: theme.announcement.url || '' }] : [])
                  const yaz = yeni => set('announcement.items', yeni)
                  return (
                    <>
                      {items.map((d, i) => (
                        <div key={i} className="border border-panel-border rounded-xl p-2 space-y-1.5">
                          <div className="flex gap-1.5">
                            <input className="input !py-1.5 text-xs flex-1" value={d.text} maxLength={140}
                              onChange={e => yaz(items.map((x, j) => j === i ? { ...x, text: e.target.value } : x))}
                              placeholder="örn. 3 AL 2 ÖDE!" />
                            <button onClick={() => { if (i > 0) { const n = [...items]; [n[i - 1], n[i]] = [n[i], n[i - 1]]; yaz(n) } }}
                              disabled={i === 0} className="px-1 text-panel-muted disabled:opacity-30">↑</button>
                            <button onClick={() => yaz(items.filter((_, j) => j !== i))}
                              className="px-1 text-red-300">×</button>
                          </div>
                          <UrlPicker value={d.url || ''} collections={collections} products={products} pages={pages}
                            placeholder="Tıklanınca gidilecek yer (ops.)"
                            onChange={url => yaz(items.map((x, j) => j === i ? { ...x, url } : x))} />
                        </div>
                      ))}
                      {items.length < 8 && (
                        <button onClick={() => yaz([...items, { text: '', url: '' }])}
                          className="btn-ghost !py-1 text-xs w-full">+ Duyuru ekle</button>
                      )}
                      <Toggle checked={theme.announcement.kayan !== false}
                        onChange={v => set('announcement.kayan', v)}
                        label="Kayan şerit (kapalıysa duyurular sırayla değişir)" />
                      <div className="flex items-end gap-2">
                        <ColorField label="Şerit rengi" value={theme.announcement.bg || theme.colors.primary}
                          onChange={v => set('announcement.bg', v)} />
                        {theme.announcement.bg && (
                          <button onClick={() => set('announcement.bg', '')}
                            className="text-xs text-panel-muted hover:text-panel-ink pb-2">
                            Ana renge dön
                          </button>
                        )}
                      </div>
                    </>
                  )
                })()}
              </Section>

              <Section title="Açılış Pop-up'ı" icon="🎁">
                <Toggle checked={!!theme.popup?.enabled}
                  onChange={v => set('popup.enabled', v)}
                  label="Sayfa açılınca kampanya pop-up'ı göster" />
                {theme.popup?.enabled && (
                  <>
                    <p className="text-[11px] text-panel-muted -mt-1">
                      Ziyaretçi siteyi açınca bir kez belirir; kapatınca o oturumda
                      tekrar çıkmaz. <b>Başlık boşsa hiç gösterilmez.</b>
                    </p>
                    <button type="button" className="btn-ghost !py-1.5 text-xs w-full"
                      disabled={!theme.popup.baslik && !theme.popup.metin}
                      title={!theme.popup.baslik && !theme.popup.metin ? 'Önce başlık yazın' : ''}
                      onClick={() => iframeRef.current?.contentWindow?.postMessage({ type: 'vitrin-popup-onizle' }, '*')}>
                      👁 Önizlemede göster
                    </button>
                    <input className="input" value={theme.popup.ust_baslik || ''} maxLength={40}
                      onChange={e => set('popup.ust_baslik', e.target.value)}
                      placeholder="Üst etiket (ops.) — örn. ✨ KAMPANYA ✨" />
                    <textarea className="input" rows={2} value={theme.popup.baslik || ''} maxLength={80}
                      onChange={e => set('popup.baslik', e.target.value)}
                      placeholder={'Başlık — örn. 3 AL 2 ÖDE\n(ikinci satır için Enter)'} />
                    <input className="input" value={theme.popup.metin || ''} maxLength={140}
                      onChange={e => set('popup.metin', e.target.value)}
                      placeholder="Açıklama — örn. 700 TL üzeri ücretsiz kargo" />
                    <input className="input font-mono" value={theme.popup.kupon || ''} maxLength={40}
                      onChange={e => set('popup.kupon', e.target.value.toUpperCase())}
                      placeholder="Kupon kodu (ops.) — tıklayınca kopyalanır" />
                    <input className="input" value={theme.popup.buton || ''} maxLength={40}
                      onChange={e => set('popup.buton', e.target.value)}
                      placeholder="Buton yazısı — örn. Alışverişe Başla" />
                    <AssetField label="Görsel (ops.) — masaüstünde sağda, mobilde üstte"
                      current={theme.popup.gorsel_url || null}
                      onUrl={url => set('popup.gorsel_url', url)}
                      onClear={() => set('popup.gorsel_url', '')} />
                    {theme.popup.gorsel_url && (
                      <label className="block text-sm">
                        <span className="text-panel-muted text-xs">
                          Görsel boyutu: <b>%{theme.popup.gorsel_boyut || 100}</b>
                        </span>
                        <input type="range" min="30" max="100" step="5"
                          value={theme.popup.gorsel_boyut || 100}
                          onChange={e => set('popup.gorsel_boyut', Number(e.target.value))}
                          className="w-full mt-1 accent-emerald-600" />
                      </label>
                    )}
                  </>
                )}
              </Section>

              <Section title="Kampanya Araçları" icon="🎡">
                <KampanyaAraclari theme={theme} set={set} kuponlar={kuponlar}
                  onizle={tip => iframeRef.current?.contentWindow?.postMessage({ type: `vitrin-${tip}-onizle` }, '*')} />
              </Section>

              <Section title="WhatsApp Butonu" icon="💬">
                <Toggle checked={!!theme.whatsapp?.enabled}
                  onChange={v => set('whatsapp.enabled', v)} label="Vitrinde yüzen WhatsApp butonu göster" />
                {theme.whatsapp?.enabled && (
                  <>
                    <input className="input" value={theme.whatsapp.number || ''} maxLength={15}
                      onChange={e => set('whatsapp.number', e.target.value.replace(/[^0-9]/g, ''))}
                      placeholder="905xxxxxxxxx (ülke koduyla, + olmadan)" />
                    <input className="input" value={theme.whatsapp.message || ''} maxLength={200}
                      onChange={e => set('whatsapp.message', e.target.value)}
                      placeholder="Hazır mesaj (müşteri tıklayınca dolu gelir)" />
                  </>
                )}
              </Section>
              </>)}

              {showCart && (
              <Section title="Sepet Kampanya Mesajları" icon="🛒">
                <p className="text-[11px] text-panel-muted -mt-1">
                  X Al Y Öde kampanyası aktifken sepette görünen yazılar.
                  Yer tutucular: <code>{'{x}'}</code> <code>{'{y}'}</code> <code>{'{kalan}'}</code>
                </p>
                <label className="block text-sm">
                  <span className="text-panel-muted text-xs">Hedefe yaklaşırken</span>
                  <input className="input mt-1" maxLength={200}
                    value={theme.cart_messages?.bxgy_progress || ''}
                    onChange={e => set('cart_messages.bxgy_progress', e.target.value)} />
                </label>
                <label className="block text-sm">
                  <span className="text-panel-muted text-xs">Hedefe ulaşınca</span>
                  <input className="input mt-1" maxLength={200}
                    value={theme.cart_messages?.bxgy_reached || ''}
                    onChange={e => set('cart_messages.bxgy_reached', e.target.value)} />
                </label>
              </Section>
              )}

              {(showGeneral || pageScope === 'sepet') && (
              <Section title="Güven Şeridi" icon="🛡️">
                <Toggle checked={theme.trust_badges?.enabled !== false}
                  onChange={v => set('trust_badges.enabled', v)}
                  label="Ürün ve ödeme sayfasında güven rozetleri (SSL, iade, kargo) göster" />
              </Section>
              )}

              {showGeneral && (
              <Section title="Vitrin Metinleri" icon="📝">
                <p className="text-[11px] text-panel-muted -mt-1">
                  Sabit arayüz yazılarını marka dilinize göre düzenleyin — boş
                  bırakılan alanda varsayılan metin kullanılır.
                </p>
                {[
                  ['add_to_cart', 'Sepete Ekle butonu', 'Sepete Ekle'],
                  ['checkout_cta', 'Ödemeye Geç butonu', 'Ödemeye Geç'],
                  ['cart_empty', 'Boş sepet yazısı', 'Sepetiniz boş.'],
                  ['newsletter_title', 'Bülten başlığı (footer)', '📮 Kampanyalardan haberdar olun'],
                  ['trust_ssl', 'Güven rozeti: SSL', '256-bit SSL güvenli ödeme'],
                  ['trust_shipping', 'Güven rozeti: kargo', '1-3 iş gününde kargo'],
                  ['trust_return', 'Güven rozeti: iade', 'Kolay iade ve değişim'],
                  ['fav_empty_title', 'Favoriler boş — başlık', 'Favori listeniz boş'],
                  ['fav_empty_sub', 'Favoriler boş — açıklama', 'Beğendiğiniz ürünlerin kalbine dokunun, burada biriksin.'],
                ].map(([key, label, ph]) => (
                  <label key={key} className="block text-sm">
                    <span className="text-panel-muted text-xs">{label}</span>
                    <input className="input mt-1" maxLength={200}
                      value={theme.texts?.[key] ?? ''}
                      onChange={e => set(`texts.${key}`, e.target.value)}
                      placeholder={ph} />
                  </label>
                ))}
              </Section>
              )}

              {/* ── Bölüm listesi — tıklanan bölüm tek-bölüm modunda açılır ── */}
              {showHome && (
              <Section title={`Anasayfa Bölümleri (${theme.sections.length})`} icon="🧱">
                <div className="space-y-1.5">
                  {theme.sections.map((sec, i) => {
                    const meta = SECTION_TYPES[sec.type] || { label: sec.type, icon: '▫️' }
                    return (
                      <div key={sec.id} draggable
                        onDragStart={e => { setDragIdx(i); e.dataTransfer.effectAllowed = 'move' }}
                        onDragOver={e => { e.preventDefault(); if (overIdx !== i) setOverIdx(i) }}
                        onDrop={() => dropSec(dragIdx, i)}
                        onDragEnd={() => { setDragIdx(null); setOverIdx(null) }}
                        className={`flex items-center gap-2 px-3 py-2 rounded-xl border transition
                          bg-panel-input/60 hover:border-panel-accent ${sec.hidden ? 'opacity-55' : ''} ${
                          dragIdx === i ? 'opacity-40 border-dashed border-panel-accent'
                            : overIdx === i && dragIdx !== null ? 'border-panel-accent ring-1 ring-emerald-500/30'
                              : 'border-panel-border'}`}>
                        <span className="cursor-grab active:cursor-grabbing text-panel-muted select-none"
                          title="Sürükleyerek sırala">⠿</span>
                        <button onClick={() => setOpenSection(sec.id)}
                          className="flex items-center gap-2 text-sm font-medium flex-1 text-left min-w-0">
                          <span>{meta.icon}</span>
                          <span className="truncate">{meta.label}</span>
                          {sec.hidden && (
                            <span className="text-[10px] bg-slate-500/20 text-panel-muted px-1.5 py-0.5 rounded-full shrink-0">gizli</span>
                          )}
                          {!sec.hidden && bosBolumNedeni(sec) && (
                            <span className="text-[10px] bg-amber-500/15 text-amber-300 px-1.5 py-0.5 rounded-full shrink-0 truncate"
                              title="Bu bölüm vitrinde görünmüyor — doldurun ya da gizleyin">
                              görünmüyor: {bosBolumNedeni(sec)}
                            </span>
                          )}
                          <span className="text-panel-muted text-xs ml-auto shrink-0">Düzenle ›</span>
                        </button>
                        <button onClick={() => moveSec(i, -1)} disabled={i === 0}
                          className="w-8 h-8 sm:w-6 sm:h-6 rounded-lg border border-panel-border text-xs disabled:opacity-30">↑</button>
                        <button onClick={() => moveSec(i, 1)} disabled={i === theme.sections.length - 1}
                          className="w-8 h-8 sm:w-6 sm:h-6 rounded-lg border border-panel-border text-xs disabled:opacity-30">↓</button>
                      </div>
                    )
                  })}
                </div>
                {theme.sections.length < 16 && (
                  <div className="flex gap-1.5 flex-wrap pt-1">
                    {Object.entries(SECTION_TYPES).map(([type, meta]) => (
                      <button key={type} onClick={() => addSec(type)}
                        className="px-2.5 py-1 rounded-lg text-xs border border-dashed border-panel-border text-panel-muted hover:text-panel-ink hover:border-panel-border">
                        + {meta.icon} {meta.label}
                      </button>
                    ))}
                  </div>
                )}
              </Section>
              )}

              {showGeneral && (<>
              <Section title="Animasyonlar" icon="✨">
                <Toggle checked={theme.animations.reveal}
                  onChange={v => set('animations.reveal', v)} label="Kaydırmada belirme + sayfa geçişleri" />
                <Toggle checked={theme.animations.hover_zoom}
                  onChange={v => set('animations.hover_zoom', v)} label="Ürün görseline yakınlaşma (hover)" />
                <Toggle checked={theme.animations.cart_drawer}
                  onChange={v => set('animations.cart_drawer', v)} label="Sepet çekmecesi (yandan kayan)" />
              </Section>

              <Section title="Alt Bilgi (Footer)" icon="⬇️">
                <label className="block text-sm">
                  <span className="text-panel-muted text-xs">Hakkında metni (footer'da görünür)</span>
                  <textarea className="input mt-1" rows={3} maxLength={500}
                    value={theme.footer?.about || ''}
                    onChange={e => set('footer.about', e.target.value)} />
                </label>
                <label className="block text-sm">
                  <span className="text-panel-muted text-xs">Instagram kullanıcı adı</span>
                  <input className="input mt-1" value={theme.footer?.instagram || ''} maxLength={60}
                    onChange={e => set('footer.instagram', e.target.value)} placeholder="@magazam" />
                </label>
              </Section>

              <Section title="Özel Kod (Gelişmiş)" icon="⚡">
                <p className="text-[11px] text-amber-300 bg-amber-500/10 border border-amber-500/30 rounded-lg px-2.5 py-1.5">
                  ⚠️ Buraya eklenen kod vitrininizde aynen çalışır — yalnızca güvendiğiniz
                  kodu ekleyin. Özel kod temadan bağımsızdır (taslakta da kaydedilse yayına yansır).
                </p>
                {customCode && (
                  <>
                    {/* Çark ve çıkış pop-up'ı artık "Kampanya Araçları"nda formla ayarlanıyor;
                        burada yalnız CSS örnekleri kaldı. Eski ham kodu aktarma aşağıda. */}
                    {(() => {
                      const var_ = kampanyaKoduVarMi(customCode.body_html)
                      if (!var_.cark && !var_.cikis) return null
                      const adlar = [var_.cark && 'İndirim çarkı', var_.cikis && 'Çıkışta yakala'].filter(Boolean).join(' ve ')
                      return (
                        <div className="rounded-lg border border-sky-500/40 bg-sky-500/10 px-2.5 py-2 text-[11px] text-sky-200 space-y-1.5">
                          <p><b>{adlar}</b> alt kodda ham kod olarak duruyor. Artık yukarıdaki
                            <b> Kampanya Araçları</b> bölümünden formla ayarlanabiliyor.</p>
                          <div className="flex gap-1.5 flex-wrap">
                            <button type="button" className="btn-ghost !py-1 text-xs"
                              onClick={() => {
                                const a = kampanyaKodunuAyristir(customCode.body_html)
                                if (a.cark) set('cark', { ...theme.cark, ...a.cark })
                                if (a.cikis) set('cikis', { ...theme.cikis, ...a.cikis })
                                toast.info('Ayarlar aktarıldı — Kampanya Araçları\'nda kontrol edin')
                              }}>1 · Ayarlara aktar</button>
                            <button type="button" className="btn-ghost !py-1 text-xs disabled:opacity-40"
                              disabled={!!draftKey}
                              title={draftKey ? 'Taslakta kullanılamaz' : ''}
                              onClick={() => {
                                if (!window.confirm('Eski ham kod alt koddan kaldırılacak (aynı kod birden fazla kez eklenmişse hepsi). Kaydettiğinizde vitrinde yalnız yeni ayarlı sürüm çalışır. Devam?')) return
                                setCustomCode(c => ({ ...c, body_html: kampanyaKodunuKaldir(c.body_html) }))
                                toast.info('Eski kod kaldırıldı — Kaydet\'e basın')
                              }}>2 · Eski kodu kaldır</button>
                          </div>
                          {draftKey && (
                            <p className="text-amber-300">Taslakta çalışıyorsunuz: özel kod her zaman YAYINA kaydedilir.
                              Eski kodu kaldırmayı yayındaki temada yapın, yoksa yeni ayarlar yayınlanana kadar
                              vitrinde ikisi de olmaz.</p>
                          )}
                          {(theme.cark?.enabled && var_.cark) || (theme.cikis?.enabled && var_.cikis) ? (
                            <p className="text-amber-300">⚠ Hem ayar hem eski kod açık — vitrinde iki kez çıkar. Eski kodu kaldırın.</p>
                          ) : null}
                        </div>
                      )
                    })()}
                    <div className="space-y-1.5">
                      <span className="text-panel-muted text-xs">Hazır ekle</span>
                      <div className="flex gap-1.5 flex-wrap">
                        {SNIPPETS.filter(sn => sn.key === 'css_examples').map(sn => (
                          <button key={sn.key} type="button" title={sn.hint}
                            onClick={() => {
                              if (!window.confirm(`${sn.label} kodu eklenecek.\n\n${sn.hint}\n\nDevam?`)) return
                              setCustomCode(c => ({
                                ...c,
                                [sn.target]: ((c[sn.target] || '').trim()
                                  ? (c[sn.target] + '\n\n') : '') + sn.code,
                              }))
                              toast.info(`${sn.label} eklendi — kodu düzenleyip Kaydet'e basın`)
                            }}
                            className="px-2.5 py-1 rounded-lg text-xs border border-panel-border
                              hover:border-panel-accent hover:text-panel-ink text-panel-muted transition">
                            {sn.label}
                          </button>
                        ))}
                      </div>
                    </div>
                    <CodeArea label="Özel CSS" value={customCode.css} rows={8}
                      placeholder=".urun-karti { border-radius: 0; }"
                      onChange={v => setCustomCode(c => ({ ...c, css: v }))} />
                    <CodeArea label="Üst kod (sayfa başı — script/HTML)" rows={5}
                      value={customCode.head_html}
                      onChange={v => setCustomCode(c => ({ ...c, head_html: v }))} />
                    <CodeArea label="Alt kod (sayfa sonu — script/HTML)" rows={10}
                      value={customCode.body_html}
                      onChange={v => setCustomCode(c => ({ ...c, body_html: v }))} />
                  </>
                )}
              </Section>
              </>)}
            </>
          )}
        </div>

        {/* Sağ: canlı önizleme */}
        <div className={`flex-1 min-w-0 flex-col p-3
                         ${mobilGorunum === 'onizleme' ? 'flex' : 'hidden sm:flex'}`}>
          <div className={`flex-1 min-h-0 ${device === 'mobile'
            ? 'flex justify-center bg-panel-input/50 rounded-2xl py-4' : ''}`}>
            <iframe key={`${saveCount}-${device}-${previewPath}`} ref={iframeRef}
              src={`${storefrontUrl}${previewPath}${previewPath.includes('?') ? '&' : '?'}onizleme=1`}
              title="Vitrin önizleme"
              className={device === 'mobile'
                ? 'w-[390px] h-full rounded-[2rem] border-8 border-panel-border bg-panel-card shadow-xl'
                : 'w-full h-full rounded-2xl border border-panel-border bg-panel-card'} />
          </div>
          <p className="text-[11px] text-panel-muted mt-1.5 px-1">
            ⚡ Canlı önizleme: değişiklikler ~1 sn içinde yansır (kaydetmeden yayınlanmaz).
            Önizlemede bir bölüme tıklayın — ayarları solda açılır.
          </p>
        </div>
      </div>
    </div>
    </MedyaContext.Provider>
  )
}

// Menü linki satırı — hedef, hazır listeden seçilir (Shopify Navigation);
// dış site için "Özel bağlantı", açılır liste için "Koleksiyon menüsü".
// ↑↓ ile menüdeki buton sırası değiştirilir.
const CUSTOM = '__ozel'
const COLMENU = '__koleksiyon_menu'
const GENEL_LINKS = [
  ['/', '🏠 Ana Sayfa'], ['/urunler', '🛍 Tüm Ürünler'], ['/sepet', '🛒 Sepet'],
  ['/favoriler', '❤️ Favoriler'], ['/hesap', '👤 Hesabım'], ['/blog', '✍️ Blog'],
]

function NavLinkRow({ link, index, count, collections, products, pages, onChange, onMove, onRemove }) {
  const options = [
    { group: 'Genel', items: GENEL_LINKS },
    { group: 'Koleksiyonlar', items: collections.map(c => [`/koleksiyon/${c.slug}`, c.title]) },
    { group: 'Sayfalar', items: pages.map(p => [`/sayfa/${p.slug}`, p.title]) },
    { group: 'Ürünler', items: products.slice(0, 30).map(p => [`/urun/${p.slug}`, p.title]) },
  ].filter(g => g.items.length > 0)

  const known = new Set(options.flatMap(g => g.items.map(([u]) => u)))
  const isColMenu = link.type === 'collections'
  // Boş url yeni satırdır → seçim yapılmamış görünsün; bilinmeyen dolu url = özel bağlantı
  const isCustom = !isColMenu && !!link.url && !known.has(link.url)
  const selectValue = isColMenu ? COLMENU : isCustom ? CUSTOM : (link.url || '')

  const pick = (value) => {
    if (value === COLMENU) {
      onChange({ type: 'collections', slugs: link.slugs || [], url: undefined,
        ...(link.label ? {} : { label: 'Koleksiyonlar' }) })
      return
    }
    if (value === CUSTOM) { onChange({ type: undefined, slugs: undefined, url: 'https://' }); return }
    const found = options.flatMap(g => g.items).find(([u]) => u === value)
    // Etiket boşsa seçilen sayfanın adını yaz
    const cleanTitle = found ? found[1].replace(/^[^\wÇĞİÖŞÜçğıöşü]+\s*/u, '') : ''
    onChange({ type: undefined, slugs: undefined, url: value,
      ...(link.label ? {} : { label: cleanTitle.slice(0, 40) }) })
  }

  const toggleSlug = (slug) => {
    const cur = link.slugs || []
    onChange({ slugs: cur.includes(slug) ? cur.filter(s => s !== slug) : [...cur, slug] })
  }

  return (
    <div className="space-y-1 border border-panel-border rounded-xl p-2">
      <div className="flex gap-1.5 items-center">
        <input className="input !py-1.5 text-xs !w-28" value={link.label} maxLength={40}
          placeholder="Etiket"
          onChange={e => onChange({ label: e.target.value })} />
        <select className="input !py-1.5 text-xs flex-1" value={selectValue}
          onChange={e => pick(e.target.value)}>
          {!link.url && !isColMenu && <option value="">Hedef seçin…</option>}
          {options.map(g => (
            <optgroup key={g.group} label={g.group}>
              {g.items.map(([u, t]) => <option key={u} value={u}>{t}</option>)}
            </optgroup>
          ))}
          <optgroup label="Diğer">
            <option value={COLMENU}>📂 Koleksiyon menüsü (açılır liste)</option>
            <option value={CUSTOM}>🔗 Özel bağlantı / dış site…</option>
          </optgroup>
        </select>
        <button onClick={() => onMove(-1)} disabled={index === 0}
          title="Yukarı taşı (menüde sola)"
          className="w-8 h-8 sm:w-6 sm:h-6 rounded-lg border border-panel-border text-xs disabled:opacity-30">↑</button>
        <button onClick={() => onMove(1)} disabled={index === count - 1}
          title="Aşağı taşı (menüde sağa)"
          className="w-8 h-8 sm:w-6 sm:h-6 rounded-lg border border-panel-border text-xs disabled:opacity-30">↓</button>
        <button onClick={onRemove}
          className="text-red-300 hover:text-red-300 px-1">×</button>
      </div>
      {isCustom && (
        <input className="input !py-1.5 text-xs font-mono" value={link.url} maxLength={300}
          placeholder="https://siparis.magazaniz.com"
          onChange={e => onChange({ url: e.target.value })} />
      )}
      {isColMenu && (
        <div className="pt-1">
          <p className="text-[10px] text-panel-muted mb-1">
            Menüde görünecek koleksiyonları seçin (seçim sırasıyla listelenir):
          </p>
          <div className="flex gap-1 flex-wrap">
            {collections.map(c => {
              const on = (link.slugs || []).includes(c.slug)
              return (
                <button key={c.slug} onClick={() => toggleSlug(c.slug)}
                  className={`px-2 py-0.5 rounded-full text-[11px] border transition ${on
                    ? 'border-panel-accent bg-emerald-500/10 text-emerald-300 font-medium'
                    : 'border-panel-border text-panel-muted hover:text-panel-ink'}`}>
                  {c.title}
                </button>
              )
            })}
            {collections.length === 0 && (
              <span className="text-[11px] text-panel-muted">Önce koleksiyon oluşturun.</span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}


// Kod alanı — satır numarası, karakter sayacı ve Tab girintisi.
// (Tam sözdizimi vurgusu için harici kütüphane gerekirdi; panel hafif kalsın.)
function CodeArea({ label, value, onChange, rows = 6, placeholder = '' }) {
  const v = value || ''
  const lines = v ? v.split('\n').length : 1
  const LIMIT = 20000
  return (
    <label className="block text-sm">
      <span className="text-panel-muted text-xs flex items-center gap-2">
        {label}
        <span className="ml-auto tabular-nums">
          {lines} satır · {v.length.toLocaleString('tr-TR')}/{LIMIT.toLocaleString('tr-TR')}
        </span>
      </span>
      <textarea
        className={`input mt-1 font-mono text-xs leading-relaxed ${
          v.length > LIMIT ? 'border-red-500' : ''}`}
        rows={rows} maxLength={LIMIT} spellCheck={false} value={v}
        placeholder={placeholder}
        onKeyDown={e => {
          if (e.key !== 'Tab') return
          e.preventDefault()   // Tab odak değiştirmesin, girinti eklesin
          const el = e.target
          const s0 = el.selectionStart, s1 = el.selectionEnd
          const next = v.slice(0, s0) + '  ' + v.slice(s1)
          onChange(next)
          requestAnimationFrame(() => { el.selectionStart = el.selectionEnd = s0 + 2 })
        }}
        onChange={e => onChange(e.target.value)} />
    </label>
  )
}

// Kupon alanı + "İndirimler'de var mı" uyarısı
function KuponAlani({ value, onChange, kuponlar, placeholder = 'KUPON KODU' }) {
  const kod = (value || '').replace(/\s+/g, '').toUpperCase()
  const yok = kod && kuponlar && !kuponlar.has(kod)
  return (
    <div>
      <input className={`input font-mono !py-1.5 text-xs ${yok ? '!border-amber-500/60' : ''}`}
        value={value || ''} maxLength={40} placeholder={placeholder}
        onChange={e => onChange(e.target.value.toUpperCase())} />
      {yok && (
        <p className="text-[10px] text-amber-300 mt-0.5">
          ⚠ Bu kod İndirimler'de yok ya da pasif — müşteri sepette "geçersiz" alır. Önce kuponu oluşturun.
        </p>
      )}
    </div>
  )
}

// Tema → Kampanya Araçları: indirim çarkı + çıkışta yakala (eskiden ham kod)
function KampanyaAraclari({ theme, set, kuponlar, onizle }) {
  const c = theme.cark || {}
  const x = theme.cikis || {}
  const dilimler = c.dilimler || []
  const yazDilim = yeni => set('cark.dilimler', yeni)
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Toggle checked={!!c.enabled} onChange={v => set('cark.enabled', v)} label="🎡 İndirim çarkı" />
        {c.enabled && (
          <div className="space-y-2 pl-1">
            <input className="input !py-1.5 text-xs" value={c.baslik || ''} maxLength={60}
              onChange={e => set('cark.baslik', e.target.value)} placeholder="Başlık" />
            <input className="input !py-1.5 text-xs" value={c.metin || ''} maxLength={140}
              onChange={e => set('cark.metin', e.target.value)} placeholder="Alt metin (ops.)" />
            <div className="grid grid-cols-3 gap-1.5">
              <label className="text-[11px] text-panel-muted">Buton
                <input className="input !py-1 text-xs mt-0.5" value={c.buton || ''} maxLength={24}
                  onChange={e => set('cark.buton', e.target.value)} /></label>
              <label className="text-[11px] text-panel-muted">Kaç sn sonra
                <input className="input !py-1 text-xs mt-0.5" type="number" min="0" max="120" value={c.gecikme_sn ?? 8}
                  onChange={e => set('cark.gecikme_sn', Number(e.target.value))} /></label>
              <label className="text-[11px] text-panel-muted">Tekrar (gün)
                <input className="input !py-1 text-xs mt-0.5" type="number" min="1" max="60" value={c.tekrar_gun ?? 7}
                  onChange={e => set('cark.tekrar_gun', Number(e.target.value))} /></label>
            </div>
            <div className="text-[11px] text-panel-muted">Dilimler — kupon boşsa "Tekrar dene" dilimi olur</div>
            {dilimler.map((d, i) => (
              <div key={i} className="flex gap-1.5 items-start">
                <input className="input !py-1.5 text-xs flex-1" value={d.yazi || ''} maxLength={24}
                  onChange={e => yazDilim(dilimler.map((y, j) => j === i ? { ...y, yazi: e.target.value } : y))}
                  placeholder="Dilim yazısı — örn. %10 İNDİRİM" />
                <div className="w-36">
                  <KuponAlani value={d.kod} kuponlar={kuponlar} placeholder="KUPON (ops.)"
                    onChange={v => yazDilim(dilimler.map((y, j) => j === i ? { ...y, kod: v } : y))} />
                </div>
                <button type="button" disabled={dilimler.length <= 2}
                  onClick={() => yazDilim(dilimler.filter((_, j) => j !== i))}
                  className="px-1 pt-1 text-red-300 disabled:opacity-30">×</button>
              </div>
            ))}
            {dilimler.length < 8 && (
              <button type="button" className="btn-ghost !py-1 text-xs w-full"
                onClick={() => yazDilim([...dilimler, { yazi: '', kod: '' }])}>+ Dilim ekle</button>
            )}
            {!dilimler.some(d => d.kod) && (
              <p className="text-[11px] text-amber-300">Hiçbir dilimde kupon yok — çark vitrinde gösterilmez.</p>
            )}
            <button type="button" className="btn-ghost !py-1.5 text-xs w-full" onClick={() => onizle('cark')}>
              👁 Önizlemede göster
            </button>
          </div>
        )}
      </div>

      <div className="space-y-2 border-t border-panel-border pt-3">
        <Toggle checked={!!x.enabled} onChange={v => set('cikis.enabled', v)} label="🚪 Çıkışta yakala (exit-intent)" />
        {x.enabled && (
          <div className="space-y-2 pl-1">
            <p className="text-[11px] text-panel-muted">
              Masaüstünde ziyaretçi sekmeyi kapatmak için imleci yukarı götürünce, mobilde belirlediğiniz
              süre sonra indirim teklifi çıkar.
            </p>
            <input className="input !py-1.5 text-xs" value={x.baslik || ''} maxLength={60}
              onChange={e => set('cikis.baslik', e.target.value)} placeholder="Başlık" />
            <input className="input !py-1.5 text-xs" value={x.metin || ''} maxLength={200}
              onChange={e => set('cikis.metin', e.target.value)} placeholder="Metin — örn. Bu siparişe özel %10 indirim" />
            <KuponAlani value={x.kupon} kuponlar={kuponlar} onChange={v => set('cikis.kupon', v)} />
            <div className="grid grid-cols-2 gap-1.5">
              <input className="input !py-1.5 text-xs" value={x.buton || ''} maxLength={30}
                onChange={e => set('cikis.buton', e.target.value)} placeholder="Buton" />
              <input className="input !py-1.5 text-xs" value={x.vazgec || ''} maxLength={40}
                onChange={e => set('cikis.vazgec', e.target.value)} placeholder="Vazgeç yazısı" />
              <label className="text-[11px] text-panel-muted">Tekrar (gün)
                <input className="input !py-1 text-xs mt-0.5" type="number" min="1" max="60" value={x.tekrar_gun ?? 3}
                  onChange={e => set('cikis.tekrar_gun', Number(e.target.value))} /></label>
              <label className="text-[11px] text-panel-muted">Mobilde kaç sn sonra
                <input className="input !py-1 text-xs mt-0.5" type="number" min="5" max="600" value={x.mobil_gecikme_sn ?? 45}
                  onChange={e => set('cikis.mobil_gecikme_sn', Number(e.target.value))} /></label>
            </div>
            {!x.kupon && <p className="text-[11px] text-amber-300">Kupon boş — vitrinde gösterilmez.</p>}
            <button type="button" className="btn-ghost !py-1.5 text-xs w-full" onClick={() => onizle('cikis')}>
              👁 Önizlemede göster
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
