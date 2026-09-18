import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, fetchYetkili } from '../lib/api'
import { useToast } from '../components/Toast'
import { mutlak } from '../lib/taban'

// Kargo etiketi şablonu — soldan ayarla, sağda ANINDA gör.
//
// Önizleme sunucuda çiziliyor: panelde etiketi ikinci kez (HTML'le) çizmek
// olurdu ama o zaman ekranda gördüğün şey basılanla aynı OLMAZDI. Aynı
// render_label_pdf çağrılıp PNG'ye çevriliyor, yani ekrandaki tam olarak
// yazıcıya gidecek olan.

const SAYISAL = [
  ['magaza_punto', 'Mağaza adı', 'Üst satırdaki firma adı'],
  ['alici_punto', 'Alıcı adı', 'En büyük olması gereken bilgi'],
  ['adres_punto', 'Adres', 'Yer darsa otomatik küçülür'],
  ['ilce_punto', 'İlçe / il', 'Kargo ayrımını yapan bilgi'],
  ['telefon_punto', 'Telefon', ''],
  ['takip_punto', 'Takip no', 'Barkodun altındaki numara'],
]
const BARKOD = [
  ['barkod_min_cm', 'Barkod en az (cm)', 'Uzun adreste bu kadar kalır'],
  ['barkod_max_cm', 'Barkod en çok (cm)', 'Kısa adreste buraya kadar büyür'],
]
const ANAHTARLAR = [
  ['siparis_no_goster', 'Sipariş numarası'],
  ['ilce_il_goster', 'İlçe / il satırı'],
  ['adres_goster', 'Açık adres (sokak)'],
  ['telefon_goster', 'Telefon'],
  ['kargo_firma_goster', 'Kargo firması adı'],
  ['site_goster', 'Site adresi (en altta)'],
]

export default function EtiketSablonPage({ embedded = false }) {
  const toast = useToast()
  const [ayar, setAyar] = useState(null)
  const [varsayilan, setVarsayilan] = useState(null)
  const [sinir, setSinir] = useState({})
  const [png, setPng] = useState(null)
  const [ciziliyor, setCiziliyor] = useState(false)
  const [kaydediyor, setKaydediyor] = useState(false)
  const [magazalar, setMagazalar] = useState([])
  const [magazaId, setMagazaId] = useState('')
  const [site, setSite] = useState('')
  const [siteBusy, setSiteBusy] = useState(false)
  const sonUrl = useRef(null)

  // Etiketteki ad ve site adresi MAĞAZAYA ait (tenant'a değil) — hangi atölye
  // basıyorsa onun bilgisi çıkmalı. Bu yüzden önizleme mağaza seçimine bağlı.
  useEffect(() => {
    api.get('/api/stores').then((r) => {
      const l = (r.items || r || []).filter((x) => x.is_active !== false)
      setMagazalar(l)
      if (l.length && !magazaId) setMagazaId(l[0].id)
    }).catch(() => {})
  }, [])   // eslint-disable-line

  const secili = useMemo(() => magazalar.find((m) => m.id === magazaId), [magazalar, magazaId])
  useEffect(() => {
    const c = secili?.config || {}
    setSite(c.etiket_site || c.custom_domain || c.shop_domain || '')
  }, [secili])

  useEffect(() => {
    api.get('/api/tenant/etiket-ayarlari').then((r) => {
      setAyar(r.ayarlar); setVarsayilan(r.varsayilan); setSinir(r.sinirlar || {})
    }).catch((e) => toast.error(e?.detail || 'Ayarlar okunamadı'))
  }, [])

  const ciz = useCallback(async (a) => {
    setCiziliyor(true)
    try {
      const res = await fetchYetkili(mutlak('/api/packaging/etiket-onizleme'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ayarlar: a, store_id: magazaId || null }),
      })
      if (!res.ok) throw new Error('önizleme alınamadı')
      const url = URL.createObjectURL(await res.blob())
      // Önceki blob'u serbest bırak — her tuşta yeni URL üretiliyor
      if (sonUrl.current) URL.revokeObjectURL(sonUrl.current)
      sonUrl.current = url
      setPng(url)
    } catch {
      /* önizleme başarısızsa eski görsel kalsın; yazı ile bağırmaya gerek yok */
    } finally { setCiziliyor(false) }
  }, [magazaId])

  // Yazarken her tuşta sunucuya gitmesin
  useEffect(() => {
    if (!ayar) return
    const t = setTimeout(() => ciz(ayar), 250)
    return () => clearTimeout(t)
  }, [ayar, ciz])

  useEffect(() => () => { if (sonUrl.current) URL.revokeObjectURL(sonUrl.current) }, [])

  const degis = (k, v) => setAyar((o) => ({ ...o, [k]: v }))

  const kaydet = async () => {
    setKaydediyor(true)
    try {
      const r = await api.put('/api/tenant/etiket-ayarlari', ayar)
      setAyar(r.ayarlar)
      toast.success('Şablon kaydedildi — bundan sonraki etiketler böyle basılacak')
    } catch (e) { toast.error(e?.detail || 'Kaydedilemedi') }
    finally { setKaydediyor(false) }
  }

  const siteKaydet = async () => {
    if (!magazaId) return
    setSiteBusy(true)
    try {
      await api.patch(`/api/stores/${magazaId}`, { config: { etiket_site: site.trim() } })
      setMagazalar((l) => l.map((m) => m.id === magazaId
        ? { ...m, config: { ...(m.config || {}), etiket_site: site.trim() } } : m))
      toast.success('Site adresi kaydedildi')
      ciz(ayar)
    } catch (e) { toast.error(e?.detail || 'Kaydedilemedi') }
    finally { setSiteBusy(false) }
  }

  const degisti = useMemo(
    () => ayar && varsayilan && JSON.stringify(ayar) !== JSON.stringify(varsayilan),
    [ayar, varsayilan])

  if (!ayar) return <div className="p-6 text-sm text-gray-400">Yükleniyor…</div>

  const Sayi = ({ k, ad, ipucu }) => {
    const [alt, ust] = sinir[k] || [0, 100]
    const adim = k.endsWith('_cm') ? 0.1 : 0.5
    return (
      <label className="block">
        <div className="flex items-baseline justify-between">
          <span className="text-[13px] text-gray-200">{ad}</span>
          <span className="text-[11px] tabular-nums text-gray-500">{ayar[k]}</span>
        </div>
        <input type="range" min={alt} max={ust} step={adim} value={ayar[k]}
               onChange={(e) => degis(k, Number(e.target.value))}
               className="w-full accent-accent" />
        {ipucu && <p className="text-[10px] text-gray-500 -mt-1">{ipucu}</p>}
      </label>
    )
  }

  return (
    <div className={embedded ? 'animate-fadein' : 'p-4 sm:p-6 max-w-6xl mx-auto'}>
      <div className="flex items-baseline justify-between mb-1 flex-wrap gap-2">
        {!embedded && <h1 className="text-lg font-semibold text-white">Etiket Şablonu</h1>}
        {embedded && <span />}
        <div className="flex items-center gap-2">
          <button onClick={() => setAyar(varsayilan)} disabled={!degisti}
                  className="text-[12px] px-3 py-1.5 rounded-lg border border-white/15
                             text-gray-300 hover:bg-white/10 disabled:opacity-40">
            Varsayılana dön
          </button>
          <button onClick={kaydet} disabled={kaydediyor}
                  className="btn-primary !text-sm disabled:opacity-50">
            {kaydediyor ? '⏳ Kaydediliyor…' : 'Kaydet'}
          </button>
        </div>
      </div>
      <p className="text-[12px] text-gray-500 mb-5">
        Sağdaki önizleme sunucuda, gerçek etiket koduyla çiziliyor — ekranda
        gördüğün, yazıcıya gidenin aynısı. Kaydedene kadar hiçbir şey değişmez.
      </p>

      <div className="grid lg:grid-cols-[1fr_auto] gap-6 items-start">
        <div className="space-y-5">
          <section className="card !p-4">
            <h2 className="text-[13px] font-medium text-gray-200 mb-3">Yazı boyutları</h2>
            <div className="grid sm:grid-cols-2 gap-x-5 gap-y-3">
              {SAYISAL.map(([k, ad, ip]) => <Sayi key={k} k={k} ad={ad} ipucu={ip} />)}
            </div>
          </section>

          <section className="card !p-4">
            <h2 className="text-[13px] font-medium text-gray-200 mb-3">Barkod</h2>
            <div className="grid sm:grid-cols-2 gap-x-5 gap-y-3">
              {BARKOD.map(([k, ad, ip]) => <Sayi key={k} k={k} ad={ad} ipucu={ip} />)}
            </div>
            <p className="text-[10px] text-gray-500 mt-2">
              Barkod alta sabittir ve kalan boşluğu doldurur; adres uzadıkça küçülür.
              Böylece okutan kişi her etikette aynı yere bakar.
            </p>
          </section>

          <section className="card !p-4">
            <h2 className="text-[13px] font-medium text-gray-200 mb-3">Görünecek alanlar</h2>
            <div className="grid sm:grid-cols-2 gap-2">
              {ANAHTARLAR.map(([k, ad]) => (
                <label key={k} className="flex items-center gap-2 text-[13px] text-gray-300">
                  <input type="checkbox" checked={!!ayar[k]}
                         onChange={(e) => degis(k, e.target.checked)}
                         className="accent-accent w-4 h-4" />
                  {ad}
                </label>
              ))}
            </div>
          </section>

          <section className="card !p-4 space-y-3">
            <h2 className="text-[13px] font-medium text-gray-200">Mağaza</h2>
            <p className="text-[10px] text-gray-500 -mt-1">
              Etiketin üstündeki ad ve altındaki site adresi mağazadan gelir —
              hangi atölye basıyorsa onun bilgisi çıkar.
            </p>
            <label className="block">
              <span className="text-[12px] text-gray-400">Önizlenen mağaza</span>
              <select value={magazaId} onChange={(e) => setMagazaId(e.target.value)}
                      className="input w-full mt-1 !text-[13px]">
                {magazalar.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="text-[12px] text-gray-400">Bu mağazanın site adresi</span>
              <div className="flex gap-2 mt-1">
                <input value={site} maxLength={80} onChange={(e) => setSite(e.target.value)}
                       placeholder="www.bernzcompany.com"
                       className="input flex-1 !text-[13px]" />
                <button onClick={siteKaydet} disabled={siteBusy || !magazaId}
                        className="px-3 rounded-lg border border-white/15 text-[12px]
                                   text-gray-300 hover:bg-white/10 disabled:opacity-40">
                  {siteBusy ? '…' : 'Kaydet'}
                </button>
              </div>
              <p className="text-[10px] text-gray-500 mt-1">
                Mağaza bazında saklanır; şablonun diğer ayarları tüm mağazalar için ortaktır.
              </p>
            </label>
          </section>

          <section className="card !p-4 space-y-3">
            <h2 className="text-[13px] font-medium text-gray-200">Ek satırlar</h2>
            <label className="block">
              <span className="text-[12px] text-gray-400">Gönderici / iade adresi</span>
              <input value={ayar.gonderici_metni} maxLength={120}
                     onChange={(e) => degis('gonderici_metni', e.target.value)}
                     placeholder="boş bırakılabilir"
                     className="input w-full mt-1 !text-[13px]" />
            </label>
            <label className="block">
              <span className="text-[12px] text-gray-400">Etiket notu</span>
              <input value={ayar.not_metni} maxLength={120}
                     onChange={(e) => degis('not_metni', e.target.value)}
                     placeholder="örn. Kırılacak eşya"
                     className="input w-full mt-1 !text-[13px]" />
            </label>
          </section>
        </div>

        <div className="lg:sticky lg:top-4">
          <div className="card !p-3 w-[min(100%,340px)] mx-auto">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[12px] text-gray-400">Önizleme · 10×15 cm</span>
              {ciziliyor && <span className="text-[10px] text-gray-500">çiziliyor…</span>}
            </div>
            <div className="rounded-lg overflow-hidden bg-white">
              {png
                ? <img src={png} alt="Etiket önizleme" className="w-full block" />
                : <div className="aspect-[2/3] grid place-items-center text-gray-400 text-xs">
                    hazırlanıyor…
                  </div>}
            </div>
            <p className="text-[10px] text-gray-500 mt-2 leading-snug">
              Örnek adres bilerek UZUN — tasarımın sınandığı yer orası. Kısa adres
              her şablonda iyi görünür.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
