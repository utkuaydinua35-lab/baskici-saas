/**
 * Tek bir ürünün seçimi: tasarım + telefon modeli + adet.
 *
 * Sihirbazda "ürün ekle" ile birden çok kez kullanılır; her kopya KENDİ
 * tasarımını taşır. Ortak bir tasarım kutusu kullanmak, çoklu üründe
 * hepsini aynı görsele bağlama hatasına açık kapı bırakırdı.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

const MAX_MB = 75
const IZINLI = ['jpg', 'jpeg', 'png', 'pdf']

export default function UrunSecici({ urun, modeller, katalog, onDegis, onSil,
                                    silinebilir, sira }) {
  const [uzerinde, setUzerinde] = useState(false)
  const [katalogAcik, setKatalogAcik] = useState(false)
  const [modelArama, setModelArama] = useState('')
  const [onizleme, setOnizleme] = useState('')
  const [hata, setHata] = useState('')
  const dosyaRef = useRef(null)

  // Önizleme URL'i sızmasın — dosya değişince/çıkışta serbest bırakılır
  useEffect(() => {
    if (!urun.dosya) { setOnizleme(''); return }
    const u = URL.createObjectURL(urun.dosya)
    setOnizleme(u)
    return () => URL.revokeObjectURL(u)
  }, [urun.dosya])

  const dosyaSec = useCallback((f) => {
    setHata('')
    if (!f) return
    const ext = (f.name.split('.').pop() || '').toLowerCase()
    if (!IZINLI.includes(ext)) { setHata('Sadece JPG, PNG veya PDF.'); return }
    if (f.size > MAX_MB * 1024 * 1024) { setHata(`Dosya çok büyük (max ${MAX_MB} MB).`); return }
    // Yeni dosya secilince katalog secimi DUSER: ikisi birden gonderilirse
    // sunucu hangisini kullanacagini bilemez.
    onDegis({ ...urun, dosya: f, tasarim: null })
  }, [urun, onDegis])

  // modeller: [{deger, etiket}] — etiket gosterilir, deger siparise yazilir
  const liste = useMemo(() => {
    const q = modelArama.trim().toLocaleLowerCase('tr')
    if (!q) return modeller.slice(0, 50)
    return modeller.filter((m) => m.etiket.toLocaleLowerCase('tr').includes(q)).slice(0, 50)
  }, [modeller, modelArama])

  // Urunun bir tasarimi var mi (yuklenen dosya VEYA katalogdan secilen)
  const secili = !!(urun.dosya || urun.tasarim)
  // Onizleme: yuklenen gorselde blob URL, katalogda sunucudaki kucuk gorsel.
  // PDF'te ikisi de yok -> format rozeti gosterilir.
  const onizlemeKaynagi = urun.tasarim
    ? urun.tasarim.gorsel
    : (urun.dosya?.type.startsWith('image/') ? onizleme : null)

  const temizle = () => onDegis({ ...urun, dosya: null, tasarim: null })

  return (
    <div className="rounded-2xl border border-brand-border bg-brand-input/25 p-4 bayi-sira"
         style={{ '--gecikme': `${sira * 60}ms` }}>
      <div className="flex items-center justify-between mb-3.5">
        <span className="text-[11px] uppercase tracking-[0.14em] text-gray-500">
          {sira + 1}. ürün
        </span>
        {silinebilir && (
          <button onClick={onSil} type="button"
                  className="text-[12px] text-gray-500 hover:text-red-300 transition-colors
                             flex items-center gap-1.5">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
                 strokeLinecap="round" className="w-3.5 h-3.5">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
            Kaldır
          </button>
        )}
      </div>

      {hata && (
        <div className="mb-3 text-[12px] text-red-300 bg-red-500/10 border border-red-500/20
                        rounded-lg px-3 py-2 animate-popin">{hata}</div>
      )}

      <div className="flex gap-4 flex-wrap sm:flex-nowrap">
        {/* Tasarım */}
        <div className="shrink-0">
          <input ref={dosyaRef} type="file" accept=".jpg,.jpeg,.png,.pdf" hidden
                 onChange={(e) => { dosyaSec(e.target.files?.[0]); e.target.value = '' }} />

          {secili ? (
            <div className="relative w-28">
              <button type="button"
                      onClick={() => (urun.tasarim ? setKatalogAcik(true) : dosyaRef.current?.click())}
                      className="relative group block w-28 h-28 rounded-2xl overflow-hidden
                                 animate-popin border bg-white/[0.03]
                                 border-accent/40 grid place-items-center">
                {onizlemeKaynagi
                  ? <img src={onizlemeKaynagi} alt=""
                         className="absolute inset-0 w-full h-full object-cover" />
                  : <span className="text-[12px] text-gray-400 font-medium">
                      {(urun.tasarim?.format || 'PDF').toUpperCase()}
                    </span>}
                {/* Dokunmatikte hover yok; degistirme ipucu her zaman gorunsun */}
                <span className="absolute inset-x-0 bottom-0 py-1 text-[10.5px] text-center
                                 text-white/90 bg-black/55 transition-opacity
                                 sm:opacity-0 sm:group-hover:opacity-100">
                  Değiştir
                </span>
              </button>

              {/* Yanlis dosya secildiginde geri donebilmek icin — her zaman gorunur */}
              <button type="button" onClick={temizle} title="Tasarımı kaldır"
                      aria-label="Tasarımı kaldır"
                      className="absolute -top-2 -right-2 w-7 h-7 rounded-full grid place-items-center
                                 bg-brand-input border border-white/15 text-gray-400
                                 hover:text-white hover:border-red-400/50 hover:bg-red-500/20
                                 transition-colors shadow-lg">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"
                     strokeLinecap="round" className="w-3.5 h-3.5">
                  <path d="M6 6l12 12M18 6L6 18" />
                </svg>
              </button>
            </div>
          ) : (
            <button type="button" onClick={() => dosyaRef.current?.click()}
                    onDragOver={(e) => { e.preventDefault(); setUzerinde(true) }}
                    onDragLeave={() => setUzerinde(false)}
                    onDrop={(e) => { e.preventDefault(); setUzerinde(false)
                                     dosyaSec(e.dataTransfer.files?.[0]) }}
                    data-uzerinde={uzerinde ? '1' : '0'}
                    className="bayi-birak w-28 h-28 grid place-items-center text-center px-2">
              <span>
                <svg viewBox="0 0 24 24" fill="none" stroke="rgb(var(--accent-rgb))"
                     strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"
                     className="w-5 h-5 mx-auto mb-1.5">
                  <path d="M12 16V4M8 8l4-4 4 4M4 16v2.5A1.5 1.5 0 0 0 5.5 20h13a1.5 1.5 0 0 0 1.5-1.5V16" />
                </svg>
                <span className="text-[11px] text-gray-400 leading-tight block">Tasarım<br />yükle</span>
              </span>
            </button>
          )}

          <div className="w-28 mt-1.5 space-y-1">
            {urun.dosya && (
              <div className="text-[10.5px] text-gray-600 truncate" title={urun.dosya.name}>
                {urun.dosya.name}
              </div>
            )}
            {urun.tasarim && (
              <div className="text-[10.5px] text-gray-500 truncate" title={urun.tasarim.ad}>
                {urun.tasarim.kod}
              </div>
            )}
            {katalog?.length > 0 && (
              <button type="button" onClick={() => setKatalogAcik(true)}
                      className="text-[10.5px] text-accent hover:brightness-125 transition">
                Tasarımlarımdan seç
              </button>
            )}
          </div>
        </div>

        {/* Model + adet */}
        <div className="flex-1 min-w-[190px] space-y-3">
          {urun.model ? (
            <div className="flex items-center gap-2.5 rounded-xl border border-accent/35
                            bg-accent/8 px-3.5 py-2.5 animate-popin">
              <svg viewBox="0 0 24 24" fill="none" stroke="rgb(var(--accent-rgb))" strokeWidth="1.6"
                   className="w-4 h-4 shrink-0"><rect x="6" y="2.5" width="12" height="19" rx="3" /></svg>
              <span className="text-[13.5px] text-white flex-1 truncate">{urun.modelEtiket || urun.model}</span>
              <button type="button" onClick={() => onDegis({ ...urun, model: '' })}
                      className="text-[12px] text-gray-400 hover:text-white transition shrink-0">
                Değiştir
              </button>
            </div>
          ) : (
            <div>
              <input value={modelArama} onChange={(e) => setModelArama(e.target.value)}
                     placeholder="Telefon modeli ara…" className="input w-full" />
              <div className="mt-2 max-h-44 overflow-y-auto rounded-xl border border-brand-border
                              divide-y divide-white/5">
                {liste.length === 0 ? (
                  <div className="px-3.5 py-4 text-[12.5px] text-gray-500 text-center">
                    Eşleşen model yok
                  </div>
                ) : liste.map((m) => (
                  <button key={m.deger} type="button"
                          onClick={() => {
                            onDegis({ ...urun, model: m.deger, modelEtiket: m.etiket })
                            setModelArama('')
                          }}
                          className="w-full text-left px-3.5 py-2 text-[13px] text-gray-300
                                     hover:bg-accent/10 hover:text-white transition-colors">
                    {m.etiket}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="flex items-center gap-2.5">
            <span className="text-[12px] text-gray-500">Adet</span>
            <div className="flex items-center rounded-full border border-brand-border bg-brand-input/50">
              <button type="button" onClick={() => onDegis({ ...urun, adet: Math.max(1, urun.adet - 1) })}
                      className="w-9 h-9 grid place-items-center text-gray-400 hover:text-white
                                 transition-colors">−</button>
              <input value={urun.adet} inputMode="numeric"
                     onChange={(e) => onDegis({ ...urun,
                       adet: Math.min(99, Math.max(1, parseInt(e.target.value, 10) || 1)) })}
                     className="w-10 bg-transparent text-center text-[14px] text-white outline-none" />
              <button type="button" onClick={() => onDegis({ ...urun, adet: Math.min(99, urun.adet + 1) })}
                      className="w-9 h-9 grid place-items-center text-gray-400 hover:text-white
                                 transition-colors">+</button>
            </div>
          </div>
        </div>
      </div>

      {katalogAcik && (
        <TasarimKatalogu
          katalog={katalog}
          seciliId={urun.tasarim?.id}
          onKapat={() => setKatalogAcik(false)}
          onSec={(t) => {
            // Katalogdan secilince yuklenen dosya DUSER (bkz. dosyaSec)
            onDegis({ ...urun, tasarim: t, dosya: null })
            setKatalogAcik(false)
          }} />
      )}
    </div>
  )
}


/** Her zaman KARE kutu.
 *
 * `aspect-square` (aspect-ratio) bir <button> icinde iOS Safari'de cokuyor:
 * kutu yuksekligini alamayinca gorsel dogal en-boy oraniyla yassi ciziliyordu.
 * padding-top: 100% her tarayicida calisir.
 */
function Kare({ children }) {
  return (
    <div className="relative w-full bg-white/[0.04] overflow-hidden"
         style={{ paddingTop: '100%' }}>
      {children}
    </div>
  )
}


/** Bayinin kendi tasarimlari — gorselleriyle katalog.
 *
 * Masaustunde gorselin uzerine gelince buyur (fare varsa onizleme yeterli).
 * Dokunmatikte hover YOK: bir dokunusla secmek yanlis tasarim secmeye cok
 * musait oldugu icin once buyutup "Onayla" istiyoruz.
 */
function TasarimKatalogu({ katalog, seciliId, onSec, onKapat }) {
  const [q, setQ] = useState('')
  const [odak, setOdak] = useState(null)   // dokunmatikte buyutulen tasarim
  const dokunmatik = useMemo(
    () => typeof window !== 'undefined'
      && window.matchMedia?.('(hover: none)').matches, [])

  const liste = (katalog || []).filter((t) => {
    const s = q.trim().toLocaleLowerCase('tr')
    return !s || (t.ad || '').toLocaleLowerCase('tr').includes(s)
      || (t.kod || '').toLocaleLowerCase('tr').includes(s)
  })

  const tikla = (t) => {
    if (dokunmatik) setOdak(t)   // once buyut, secim "Onayla" ile
    else onSec(t)
  }

  // GOVDEYE portal: ust bilesenin `animation`'i (bayi-sira) yiginlama baglami
  // yaratiyor ve `fixed` modali icine hapsediyor — sayfadaki "Devam" dugmesi
  // modalin ustune cikiyordu. Portal bu baglamdan tamamen cikariyor.
  return createPortal((
    <div className="fixed inset-0 z-50 grid place-items-center p-4 animate-fadein"
         style={{ background: 'rgb(6 4 12 / 0.86)' }}
         onClick={onKapat}>
      <div className="rounded-2xl w-full max-w-6xl max-h-[86vh] flex flex-col p-5 animate-popin
                      border border-white/10"
           style={{ background: 'rgb(23 16 43)',
                    boxShadow: '0 30px 70px -30px rgb(0 0 0 / 0.95)' }}
           onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3.5">
          <h3 className="text-[15px] font-semibold text-white">Tasarımlarım</h3>
          <button onClick={onKapat} className="text-gray-500 hover:text-gray-200 text-xl leading-none">
            ×
          </button>
        </div>
        <input value={q} onChange={(e) => setQ(e.target.value)}
               autoFocus={!dokunmatik}
               placeholder="Tasarım ara…" className="input w-full mb-3.5" />
        {liste.length === 0 ? (
          <div className="py-10 text-center text-[13px] text-gray-500">
            {q ? 'Eşleşen tasarım yok' : 'Henüz kayıtlı tasarımın yok'}
          </div>
        ) : (
          <div className="gap-3 overflow-y-auto py-1
                          grid [grid-template-columns:repeat(auto-fill,minmax(min(100%,140px),1fr))]
                          sm:[grid-template-columns:repeat(auto-fill,minmax(min(100%,240px),1fr))]">
            {liste.map((t, i) => (
              <button key={t.id} type="button" onClick={() => tikla(t)}
                      className={`bayi-katalog-kart block w-full text-left rounded-xl
                        overflow-hidden border bayi-sira
                        ${t.id === seciliId
                          ? 'border-accent ring-2 ring-accent/30'
                          : 'border-white/10'}`}
                      style={{ '--gecikme': `${Math.min(i, 12) * 25}ms` }}>
                <Kare>
                  {t.gorsel
                    ? <img src={t.gorsel} alt=""
                           className="absolute inset-0 w-full h-full object-cover" />
                    : <span className="absolute inset-0 grid place-items-center
                                       text-[11px] text-gray-600">
                        {(t.format || '?').toUpperCase()}
                      </span>}
                </Kare>
                <div className="px-2 py-1.5 text-[11px] sm:text-[12.5px] text-gray-400 truncate"
                     title={t.ad}>
                  {t.ad}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Dokunmatik: buyutulmus onizleme + acik onay */}
      {odak && (
        <div className="fixed inset-0 z-[60] grid place-items-center p-5 animate-fadein"
             style={{ background: 'rgb(6 4 12)' }}
             onClick={() => setOdak(null)}>
          <div className="rounded-2xl w-full max-w-xs p-4 animate-popin border border-white/10"
               style={{ background: 'rgb(23 16 43)',
                        boxShadow: '0 30px 70px -30px rgb(0 0 0 / 0.95)' }}
               onClick={(e) => e.stopPropagation()}>
            <div className="rounded-xl overflow-hidden border border-white/12 bg-black/40">
              <Kare>
                {odak.gorsel
                  ? <img src={odak.gorsel} alt=""
                         className="absolute inset-0 w-full h-full object-contain" />
                  : <span className="absolute inset-0 grid place-items-center text-sm text-gray-500">
                      {(odak.format || '?').toUpperCase()}
                    </span>}
              </Kare>
            </div>
            <div className="text-[13px] text-gray-200 mt-3 text-center truncate"
                 title={odak.ad}>{odak.ad}</div>
            <div className="flex items-center gap-2.5 mt-4">
              <button type="button" onClick={() => setOdak(null)}
                      className="btn-secondary flex-1">Vazgeç</button>
              <button type="button" onClick={() => { onSec(odak); setOdak(null) }}
                      className="btn-primary flex-1">Onayla</button>
            </div>
          </div>
        </div>
      )}
    </div>
  ), document.body)
}
