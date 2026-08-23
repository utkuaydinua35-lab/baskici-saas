/**
 * Yeni siparis sihirbazi — 3 adim: Tasarim → Ürün → Alıcı.
 *
 * Adres kurali kanaldan turer: Trendyol adresi kendi tarafinda tuttugu icin
 * yalnizca alici adi istenir; Shopier/Instagram'da kargo icin tam adres sart.
 * Ayni kural backend'de de var (bayii_portal._adres_dogrula) — burasi sadece
 * kullaniciya erken geri bildirim, tek dogruluk kaynagi sunucu.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../lib/api'
import { ADRES_ZORUNLU, KANALLAR, paraYaz } from '../../lib/bayii'
import { Bildirim, Hata } from '../../components/BayiParcalar'
import IlIlceSecici from '../../components/IlIlceSecici'

const ADIMLAR = ['Tasarım', 'Ürün', 'Alıcı']
const MAX_MB = 75

export default function BayiYeniSiparisPage() {
  const navigate = useNavigate()
  const [adim, setAdim] = useState(0)
  const [hata, setHata] = useState('')
  const [bildirim, setBildirim] = useState('')
  const [gonderiliyor, setGonderiliyor] = useState(false)
  const [basarili, setBasarili] = useState(null)

  // Adim 1
  const [dosya, setDosya] = useState(null)
  const [onizleme, setOnizleme] = useState('')
  const [uzerinde, setUzerinde] = useState(false)
  const dosyaRef = useRef(null)

  // Adim 2
  const [modeller, setModeller] = useState([])
  const [model, setModel] = useState('')
  const [modelArama, setModelArama] = useState('')
  const [adet, setAdet] = useState(1)
  const [fiyat, setFiyat] = useState(null)

  // Adim 3
  const [kanal, setKanal] = useState('trendyol')
  const [ad, setAd] = useState('')
  const [telefon, setTelefon] = useState('')
  const [adres, setAdres] = useState('')
  const [il, setIl] = useState('')
  const [ilce, setIlce] = useState('')
  const [aciklama, setAciklama] = useState('')

  useEffect(() => {
    api.get('/api/bayii/modeller').then((d) => setModeller(d.items || [])).catch(() => {})
    api.get('/api/bayii/ozet').then((d) => setFiyat(d.cari)).catch(() => {})
  }, [])

  // Onizleme URL'i sizmasin — dosya degisince/cikista serbest birak
  useEffect(() => {
    if (!dosya) { setOnizleme(''); return }
    const u = URL.createObjectURL(dosya)
    setOnizleme(u)
    return () => URL.revokeObjectURL(u)
  }, [dosya])

  const dosyaSec = useCallback((f) => {
    setHata('')
    if (!f) return
    const uzanti = (f.name.split('.').pop() || '').toLowerCase()
    if (!['jpg', 'jpeg', 'png', 'pdf'].includes(uzanti)) {
      setHata('Sadece JPG, PNG veya PDF yükleyebilirsin.'); return
    }
    if (f.size > MAX_MB * 1024 * 1024) {
      setHata(`Dosya çok büyük (max ${MAX_MB} MB).`); return
    }
    setDosya(f)
  }, [])

  const modelListesi = useMemo(() => {
    const q = modelArama.trim().toLocaleLowerCase('tr')
    if (!q) return modeller.slice(0, 60)
    return modeller.filter((m) => m.toLocaleLowerCase('tr').includes(q)).slice(0, 60)
  }, [modeller, modelArama])

  const adresGerek = ADRES_ZORUNLU.includes(kanal)
  const adimTamam = [
    !!dosya,
    !!model && adet >= 1,
    !!ad.trim() && (!adresGerek || (telefon.trim() && adres.trim() && il.trim() && ilce.trim())),
  ]

  const gonder = async () => {
    setHata(''); setGonderiliyor(true)
    try {
      const fd = new FormData()
      fd.append('tasarim', dosya)
      fd.append('model', model)
      fd.append('adet', String(adet))
      fd.append('kanal', kanal)
      fd.append('ad_soyad', ad.trim())
      fd.append('telefon', telefon.trim())
      fd.append('adres', adres.trim())
      fd.append('il', il.trim())
      fd.append('ilce', ilce.trim())
      fd.append('aciklama', aciklama.trim())
      setBasarili(await api.postForm('/api/bayii/siparis', fd))
    } catch (e) {
      setHata(e.detail || 'Sipariş oluşturulamadı')
      setGonderiliyor(false)
    }
  }

  if (basarili) {
    return (
      <div className="max-w-md mx-auto text-center py-14">
        <svg viewBox="0 0 64 64" className="w-20 h-20 mx-auto mb-6">
          <circle cx="32" cy="32" r="28" fill="rgb(52 211 153 / 0.1)"
                  stroke="rgb(52 211 153 / 0.45)" strokeWidth="2" className="bayi-basari-halka" />
          <path d="M20 33.5 L28.5 42 L44 25" fill="none" stroke="#34d399" strokeWidth="4"
                strokeLinecap="round" strokeLinejoin="round" className="bayi-basari-tik" />
        </svg>
        <h2 className="text-xl font-semibold text-white">Siparişin alındı</h2>
        <p className="text-[13.5px] text-gray-400 mt-2 leading-relaxed">
          <span className="text-gray-200 font-medium">#{basarili.order_number}</span> numaralı sipariş
          onay bekliyor. Onaylandığında üretime alınır ve cari hesabına işlenir.
        </p>
        <div className="flex items-center justify-center gap-2.5 mt-7">
          <button onClick={() => navigate(`/bayii/siparis/${basarili.id}`)} className="btn-primary">
            Siparişi gör
          </button>
          <button onClick={() => window.location.reload()} className="btn-secondary">
            Yeni sipariş
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <Bildirim mesaj={bildirim} onKapat={() => setBildirim('')} />

      <div>
        <h1 className="text-2xl font-semibold text-white tracking-tight">Yeni sipariş</h1>
        <p className="text-[13px] text-gray-500 mt-1">
          Tasarımını yükle, modeli seç, alıcıyı gir. Varyasyon seçimi ve onay bizde.
        </p>
      </div>

      {/* Adim gostergesi */}
      <div className="flex items-center gap-3">
        {ADIMLAR.map((a, i) => (
          <div key={a} className="flex items-center gap-3 shrink-0 [&:not(:last-child)]:flex-1">
            <button onClick={() => i < adim && setAdim(i)}
                    disabled={i > adim}
                    className="flex items-center gap-2.5 shrink-0 disabled:cursor-default">
              <span className="bayi-adim-nokta"
                    data-durum={i < adim ? 'tamam' : i === adim ? 'aktif' : 'bos'}>
                {i < adim
                  ? <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"
                         strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5">
                      <path d="M4 12.5l5 5L20 7" /></svg>
                  : i + 1}
              </span>
              <span className={`text-[13px] hidden sm:block transition-colors ${
                i === adim ? 'text-white' : i < adim ? 'text-gray-400' : 'text-gray-600'}`}>{a}</span>
            </button>
            {i < ADIMLAR.length - 1 && (
              <div className="bayi-adim-cizgi flex-1 min-w-[16px]">
                <div className="bayi-adim-dolu" style={{ width: i < adim ? '100%' : '0%' }} />
              </div>
            )}
          </div>
        ))}
      </div>

      <Hata mesaj={hata} />

      <div className="card">
        {/* ── Adim 1: Tasarim ── */}
        {adim === 0 && (
          <div className="animate-fadeinup">
            <input ref={dosyaRef} type="file" accept=".jpg,.jpeg,.png,.pdf" hidden
                   onChange={(e) => dosyaSec(e.target.files?.[0])} />
            {!dosya ? (
              <div className="bayi-birak p-10 text-center cursor-pointer"
                   data-uzerinde={uzerinde ? '1' : '0'}
                   onClick={() => dosyaRef.current?.click()}
                   onDragOver={(e) => { e.preventDefault(); setUzerinde(true) }}
                   onDragLeave={() => setUzerinde(false)}
                   onDrop={(e) => {
                     e.preventDefault(); setUzerinde(false)
                     dosyaSec(e.dataTransfer.files?.[0])
                   }}>
                <div className="inline-grid place-items-center w-14 h-14 rounded-2xl mb-4"
                     style={{ background: 'rgb(var(--accent-rgb) / 0.12)' }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="rgb(var(--accent-rgb))" strokeWidth="1.8"
                       strokeLinecap="round" strokeLinejoin="round" className="w-6 h-6">
                    <path d="M12 16V4M8 8l4-4 4 4M4 16v2.5A1.5 1.5 0 0 0 5.5 20h13a1.5 1.5 0 0 0 1.5-1.5V16" />
                  </svg>
                </div>
                <div className="text-[15px] text-gray-200 font-medium">Tasarımını sürükle ya da seç</div>
                <div className="text-[12.5px] text-gray-500 mt-1.5">
                  JPG, PNG veya PDF · en fazla {MAX_MB} MB
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-4 animate-popin">
                <div className="w-24 h-24 rounded-2xl overflow-hidden border border-white/8
                                bg-white/[0.03] grid place-items-center shrink-0">
                  {dosya.type.startsWith('image/') && onizleme
                    ? <img src={onizleme} alt="" className="w-full h-full object-cover" />
                    : <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"
                           className="w-8 h-8 text-gray-500">
                        <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
                        <path d="M14 3v5h5" /></svg>}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-[14px] text-gray-100 truncate">{dosya.name}</div>
                  <div className="text-[12px] text-gray-500 mt-1">
                    {dosya.size < 1024 * 1024
                      ? `${Math.max(1, Math.round(dosya.size / 1024))} KB`
                      : `${(dosya.size / 1024 / 1024).toFixed(2)} MB`}
                  </div>
                  <button onClick={() => dosyaRef.current?.click()}
                          className="text-[12.5px] text-accent hover:brightness-125 mt-2.5 transition">
                    Başka dosya seç
                  </button>
                </div>
                <span className="w-8 h-8 rounded-full grid place-items-center shrink-0
                                 bg-emerald-500/15 text-emerald-300">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6"
                       strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
                    <path d="M4 12.5l5 5L20 7" /></svg>
                </span>
              </div>
            )}
          </div>
        )}

        {/* ── Adim 2: Urun ── */}
        {adim === 1 && (
          <div className="space-y-5 animate-fadeinup">
            <div>
              <label className="block text-[11px] uppercase tracking-wider text-gray-500 mb-2">
                Telefon modeli
              </label>
              {model ? (
                <div className="flex items-center gap-3 rounded-xl border border-accent/35
                                bg-accent/8 px-4 py-3 animate-popin">
                  <svg viewBox="0 0 24 24" fill="none" stroke="rgb(var(--accent-rgb))" strokeWidth="1.6"
                       className="w-5 h-5 shrink-0"><rect x="6" y="2.5" width="12" height="19" rx="3" /></svg>
                  <span className="text-[14px] text-white flex-1">{model}</span>
                  <button onClick={() => { setModel(''); setModelArama('') }}
                          className="text-[12.5px] text-gray-400 hover:text-white transition">
                    Değiştir
                  </button>
                </div>
              ) : (
                <>
                  <input value={modelArama} onChange={(e) => setModelArama(e.target.value)}
                         placeholder="Model ara — örn. iPhone 15" className="input w-full" autoFocus />
                  <div className="mt-2.5 max-h-64 overflow-y-auto rounded-xl border border-brand-border
                                  divide-y divide-white/5">
                    {modelListesi.length === 0 ? (
                      <div className="px-4 py-6 text-center text-[13px] text-gray-500">
                        Eşleşen model yok
                      </div>
                    ) : modelListesi.map((m, i) => (
                      <button key={m} onClick={() => setModel(m)}
                              className="w-full text-left px-4 py-2.5 text-[13.5px] text-gray-300
                                         hover:bg-accent/10 hover:text-white transition-colors bayi-sira"
                              style={{ '--gecikme': `${Math.min(i, 10) * 18}ms` }}>
                        {m}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>

            <div>
              <label className="block text-[11px] uppercase tracking-wider text-gray-500 mb-2">
                Adet
              </label>
              <div className="flex items-center gap-3">
                <div className="flex items-center rounded-xl border border-brand-border bg-brand-input/50">
                  <button onClick={() => setAdet((n) => Math.max(1, n - 1))}
                          className="w-10 h-10 grid place-items-center text-gray-400
                                     hover:text-white transition-colors">−</button>
                  <input value={adet} inputMode="numeric"
                         onChange={(e) => setAdet(Math.min(99, Math.max(1, parseInt(e.target.value, 10) || 1)))}
                         className="w-12 bg-transparent text-center text-[15px] text-white outline-none" />
                  <button onClick={() => setAdet((n) => Math.min(99, n + 1))}
                          className="w-10 h-10 grid place-items-center text-gray-400
                                     hover:text-white transition-colors">+</button>
                </div>
                {fiyat && Number(fiyat.birim_fiyat) > 0 && (
                  <div className="text-[13px] text-gray-500">
                    ≈ <span className="text-gray-200">
                        {paraYaz(Number(fiyat.birim_fiyat) * adet, fiyat.para_birimi || 'TRY')}
                      </span>
                    <span className="text-gray-600"> (onayda kesinleşir)</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ── Adim 3: Alici ── */}
        {adim === 2 && (
          <div className="space-y-5 animate-fadeinup">
            <div>
              <label className="block text-[11px] uppercase tracking-wider text-gray-500 mb-2">
                Sipariş nereden geldi?
              </label>
              <div className="grid grid-cols-3 gap-2.5">
                {KANALLAR.map((k) => (
                  <button key={k.id} onClick={() => setKanal(k.id)}
                          className={`rounded-xl border px-3 py-3 text-[13px] transition-all ${
                            kanal === k.id
                              ? 'border-accent/50 bg-accent/10 text-white scale-[1.02]'
                              : 'border-brand-border text-gray-400 hover:text-gray-200 hover:border-white/15'}`}>
                    <span className="block w-2 h-2 rounded-full mx-auto mb-2"
                          style={{ background: k.renk }} />
                    {k.ad}
                  </button>
                ))}
              </div>
              <p className="text-[12px] text-gray-500 mt-2.5">
                {KANALLAR.find((k) => k.id === kanal)?.ipucu}
              </p>
            </div>

            <div>
              <label className="block text-[11px] uppercase tracking-wider text-gray-500 mb-1.5">
                Alıcı adı soyadı
              </label>
              <input value={ad} onChange={(e) => setAd(e.target.value)}
                     placeholder="Ad Soyad" className="input w-full" />
            </div>

            {/* Adres alanlari yalnizca gerektiginde acilir — akordeon */}
            <div className="grid transition-[grid-template-rows,opacity] duration-300 ease-out"
                 style={{ gridTemplateRows: adresGerek ? '1fr' : '0fr',
                          opacity: adresGerek ? 1 : 0 }}>
              <div className="overflow-hidden">
                <div className="space-y-4 pt-1">
                  <div>
                    <label className="block text-[11px] uppercase tracking-wider text-gray-500 mb-1.5">
                      Telefon
                    </label>
                    <input value={telefon} onChange={(e) => setTelefon(e.target.value)}
                           inputMode="tel" placeholder="05XX XXX XX XX" className="input w-full" />
                  </div>
                  <IlIlceSecici il={il} ilce={ilce}
                                onDegis={(i, c) => { setIl(i); setIlce(c) }} />
                  <div>
                    <label className="block text-[11px] uppercase tracking-wider text-gray-500 mb-1.5">
                      Adres (cadde, sokak, bina, daire)
                    </label>
                    <textarea value={adres} onChange={(e) => setAdres(e.target.value)} rows={3}
                              placeholder="Mahalle, cadde/sokak, bina no, daire no"
                              className="input w-full resize-none" />
                  </div>
                </div>
              </div>
            </div>

            <div>
              <label className="block text-[11px] uppercase tracking-wider text-gray-500 mb-1.5">
                Not <span className="text-gray-600 normal-case tracking-normal">(isteğe bağlı)</span>
              </label>
              <input value={aciklama} onChange={(e) => setAciklama(e.target.value)}
                     placeholder="Bize iletmek istediğin bir şey" className="input w-full" />
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between gap-3">
        <button onClick={() => (adim === 0 ? navigate('/bayii') : setAdim((a) => a - 1))}
                className="btn-secondary" disabled={gonderiliyor}>
          {adim === 0 ? 'Vazgeç' : 'Geri'}
        </button>
        {adim < 2 ? (
          <button onClick={() => setAdim((a) => a + 1)} disabled={!adimTamam[adim]}
                  className="btn-primary inline-flex items-center gap-2">
            Devam
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"
                 strokeLinecap="round" className="w-4 h-4"><path d="M9 6l6 6-6 6" /></svg>
          </button>
        ) : (
          <button onClick={gonder} disabled={!adimTamam[2] || gonderiliyor}
                  className="btn-primary inline-flex items-center gap-2">
            {gonderiliyor && (
              <span className="w-3.5 h-3.5 rounded-full border-2 border-white/30
                               border-t-white animate-spin" />
            )}
            {gonderiliyor ? 'Gönderiliyor…' : 'Siparişi oluştur'}
          </button>
        )}
      </div>
    </div>
  )
}
