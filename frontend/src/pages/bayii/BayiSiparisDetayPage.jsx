/**
 * Siparis detayi + izin verilen duzenlemeler.
 *
 * Neyin duzenlenebilecegine SUNUCU karar verir (yetkiler nesnesi); burada
 * sadece o karara gore alan aciyoruz. Kurali istemcide yeniden yazmak iki
 * kaynak demek olurdu ve zamanla ayrisirdi.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../../lib/api'
import { ADRES_ZORUNLU, kanalAdi, paraYaz, tarihYaz } from '../../lib/bayii'
import { Bildirim, DurumRozet, Hata, Iskelet } from '../../components/BayiParcalar'
import IlIlceSecici from '../../components/IlIlceSecici'

const EYLEM_ADI = {
  bayii_siparis: 'Sipariş oluşturuldu',
  bayii_guncelleme: 'Güncelleme',
  bayii_onay: 'Onaylandı',
  silindi: 'İptal edildi',
}

/** Kilitli alanin nedenini anlatan satir. */
function Kilit({ metin }) {
  return (
    <div className="flex items-start gap-2 text-[12px] text-gray-500 mt-2">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"
           className="w-3.5 h-3.5 shrink-0 mt-0.5">
        <rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" />
      </svg>
      {metin}
    </div>
  )
}

/**
 * Tek bir ürün kalemi: görsel + model + adet, kendi düzenleme durumuyla.
 *
 * Düzenleme uçları KALEM hedefli (.../kalem/{id}); çoklu üründe "ilk kalem"
 * varsaymak, bayinin 2. ürününe yaptığı değişikliği 1.'ye uygulardı.
 */
function KalemKarti({ kalem, sira, siparisId, cokluMu, duzenlenebilir, modeller,
                      onGuncellendi, onHata, onBildirim }) {
  const [modelDuzenle, setModelDuzenle] = useState(false)
  const [arama, setArama] = useState('')
  const [bekle, setBekle] = useState('')
  const dosyaRef = useRef(null)

  const liste = (() => {
    const q = arama.trim().toLocaleLowerCase('tr')
    return (q ? modeller.filter((m) => m.toLocaleLowerCase('tr').includes(q)) : modeller).slice(0, 40)
  })()

  const modelSec = async (m) => {
    setBekle('model'); onHata('')
    try {
      await api.patch(`/api/bayii/siparis/${siparisId}/kalem/${kalem.id}`, { model: m })
      setModelDuzenle(false); setArama('')
      onBildirim('Telefon modeli güncellendi')
      await onGuncellendi()
    } catch (e) { onHata(e.detail || 'Güncellenemedi') }
    finally { setBekle('') }
  }

  const adetDegis = async (yeni) => {
    if (yeni < 1 || yeni > 99 || yeni === kalem.adet) return
    setBekle('adet'); onHata('')
    try {
      await api.patch(`/api/bayii/siparis/${siparisId}/kalem/${kalem.id}`, { adet: yeni })
      onBildirim('Adet güncellendi')
      await onGuncellendi()
    } catch (e) { onHata(e.detail || 'Güncellenemedi') }
    finally { setBekle('') }
  }

  const tasarimYukle = async (f) => {
    if (!f) return
    if (f.size > 75 * 1024 * 1024) { onHata('Dosya çok büyük (max 75 MB).'); return }
    setBekle('tasarim'); onHata('')
    try {
      const fd = new FormData()
      fd.append('tasarim', f)
      await api.postForm(`/api/bayii/siparis/${siparisId}/kalem/${kalem.id}/tasarim`, fd)
      onBildirim('Tasarım güncellendi')
      await onGuncellendi()
    } catch (e) { onHata(e.detail || 'Tasarım yüklenemedi') }
    finally { setBekle(''); if (dosyaRef.current) dosyaRef.current.value = '' }
  }

  return (
    <div className={`bayi-sira ${cokluMu
      ? 'rounded-xl border border-brand-border bg-brand-input/25 p-3.5' : ''}`}
         style={{ '--gecikme': `${sira * 55}ms` }}>
      {cokluMu && (
        <div className="text-[11px] uppercase tracking-[0.14em] text-gray-600 mb-3">
          {sira + 1}. ürün
        </div>
      )}
      <div className="flex items-start gap-4 flex-wrap">
        <div className="relative group shrink-0">
          <div className={`${cokluMu ? 'w-20 h-20' : 'w-28 h-28'} rounded-2xl overflow-hidden
                           border border-white/8 bg-white/[0.03] grid place-items-center`}>
            {kalem.gorsel
              ? <img src={kalem.gorsel} alt="" className="w-full h-full object-cover" />
              : <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4"
                     className="w-8 h-8 text-gray-600">
                  <rect x="6" y="2.5" width="12" height="19" rx="3" /></svg>}
          </div>
          {duzenlenebilir && (
            <>
              <input ref={dosyaRef} type="file" accept=".jpg,.jpeg,.png,.pdf" hidden
                     onChange={(e) => tasarimYukle(e.target.files?.[0])} />
              <button onClick={() => dosyaRef.current?.click()} disabled={bekle === 'tasarim'}
                      className="absolute inset-0 rounded-2xl grid place-items-center bg-black/65
                                 opacity-0 group-hover:opacity-100 focus:opacity-100
                                 transition-opacity text-[11.5px] text-white px-1 text-center">
                {bekle === 'tasarim'
                  ? <span className="w-5 h-5 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                  : 'Tasarımı değiştir'}
              </button>
            </>
          )}
        </div>

        <div className="flex-1 min-w-[190px]">
          <div className="text-[11px] uppercase tracking-wider text-gray-500 mb-1.5">
            Telefon modeli
          </div>
          {modelDuzenle ? (
            <div className="animate-popin">
              <input value={arama} onChange={(e) => setArama(e.target.value)}
                     placeholder="Model ara…" className="input w-full" autoFocus />
              <div className="mt-2 max-h-52 overflow-y-auto rounded-xl border border-brand-border
                              divide-y divide-white/5">
                {liste.map((m) => (
                  <button key={m} onClick={() => modelSec(m)} disabled={bekle === 'model'}
                          className="w-full text-left px-3.5 py-2 text-[13px] text-gray-300
                                     hover:bg-accent/10 hover:text-white transition-colors">
                    {m}
                  </button>
                ))}
                {liste.length === 0 && (
                  <div className="px-3.5 py-4 text-[12.5px] text-gray-500 text-center">
                    Eşleşen model yok
                  </div>
                )}
              </div>
              <button onClick={() => setModelDuzenle(false)}
                      className="text-[12.5px] text-gray-500 hover:text-gray-300 mt-2 transition">
                Vazgeç
              </button>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-3 flex-wrap">
                <span className={`${cokluMu ? 'text-[14.5px]' : 'text-[16px]'} text-white`}>
                  {kalem.model || '—'}
                </span>
                {duzenlenebilir && (
                  <button onClick={() => setModelDuzenle(true)}
                          className="text-[12.5px] text-accent hover:brightness-125 transition">
                    Değiştir
                  </button>
                )}
              </div>

              <div className="flex items-center gap-2.5 mt-2.5">
                <span className="text-[12px] text-gray-500">Adet</span>
                {duzenlenebilir ? (
                  <div className="flex items-center rounded-full border border-brand-border
                                  bg-brand-input/50">
                    <button onClick={() => adetDegis((kalem.adet || 1) - 1)}
                            disabled={bekle === 'adet' || (kalem.adet || 1) <= 1}
                            className="w-8 h-8 grid place-items-center text-gray-400
                                       hover:text-white transition-colors disabled:opacity-30">−</button>
                    <span className="w-8 text-center text-[13.5px] text-white">{kalem.adet || 1}</span>
                    <button onClick={() => adetDegis((kalem.adet || 1) + 1)}
                            disabled={bekle === 'adet'}
                            className="w-8 h-8 grid place-items-center text-gray-400
                                       hover:text-white transition-colors disabled:opacity-30">+</button>
                  </div>
                ) : (
                  <span className="text-[13.5px] text-gray-300">{kalem.adet || 1}</span>
                )}
              </div>
            </>
          )}
          {kalem.varyasyon && (
            <div className="text-[12px] text-gray-500 mt-2.5">
              Varyasyon: <span className="text-gray-300">{kalem.varyasyon}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}


export default function BayiSiparisDetayPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [o, setO] = useState(null)
  const [hata, setHata] = useState('')
  const [bildirim, setBildirim] = useState('')
  const [bekle, setBekle] = useState('')

  const [modeller, setModeller] = useState([])
  const [adresDuzenle, setAdresDuzenle] = useState(false)
  const [adresForm, setAdresForm] = useState(null)

  const yukle = useCallback(async () => {
    setHata('')
    try { setO(await api.get(`/api/bayii/siparis/${id}`)) }
    catch (e) { setHata(e.detail || 'Sipariş yüklenemedi') }
  }, [id])
  useEffect(() => { yukle() }, [yukle])

  // Model listesi duzenlenebilir siparislerde onden yuklenir; kalem kartlari
  // paylasir (her kart ayri ayri cekseydi ayni istek N kez giderdi).
  const duzenlenebilir = !!o?.yetkiler?.urun_degistir
  useEffect(() => {
    if (duzenlenebilir && modeller.length === 0) {
      api.get('/api/bayii/modeller').then((d) => setModeller(d.items || [])).catch(() => {})
    }
  }, [duzenlenebilir, modeller.length])

  const y = o?.yetkiler || {}

  const adresKaydet = async () => {
    setBekle('adres'); setHata('')
    try {
      await api.patch(`/api/bayii/siparis/${id}/adres`, {
        ad_soyad: adresForm.ad || '', telefon: adresForm.telefon || '',
        adres: adresForm.adres || '', il: adresForm.il || '', ilce: adresForm.ilce || '',
      })
      setAdresDuzenle(false)
      setBildirim('Adres güncellendi')
      await yukle()
    } catch (e) { setHata(e.detail || 'Adres güncellenemedi') }
    finally { setBekle('') }
  }

  const geriCek = async () => {
    if (!window.confirm('Bu siparişi geri çekmek istediğine emin misin?')) return
    setBekle('sil'); setHata('')
    try {
      await api.del(`/api/bayii/siparis/${id}`)
      navigate('/bayii/siparisler', { replace: true })
    } catch (e) { setHata(e.detail || 'İptal edilemedi'); setBekle('') }
  }

  if (!o) {
    return (
      <div className="space-y-5">
        <Hata mesaj={hata} tekrar={yukle} />
        {!hata && <Iskelet satir={3} yukseklik={110} />}
      </div>
    )
  }

  const adresGerek = ADRES_ZORUNLU.includes(o.kanal)

  return (
    <div className="max-w-3xl mx-auto space-y-5">
      <Bildirim mesaj={bildirim} onKapat={() => setBildirim('')} />
      <Hata mesaj={hata} />

      <Link to="/bayii/siparisler"
            className="inline-flex items-center gap-1.5 text-[12.5px] text-gray-500 hover:text-gray-300 transition">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
             strokeLinecap="round" className="w-3.5 h-3.5"><path d="M15 6l-6 6 6 6" /></svg>
        Siparişlerim
      </Link>

      {/* Baslik */}
      <div className="card">
        <div className="flex items-start gap-4 flex-wrap">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-xl font-semibold text-white tracking-tight">
                #{o.order_number}
              </h1>
              <DurumRozet siparis={o} buyuk />
            </div>
            <p className="text-[12.5px] text-gray-500 mt-1.5">
              {tarihYaz(o.tarih)}
              {o.kanal && <> · {kanalAdi(o.kanal)}</>}
            </p>
          </div>
          <div className="text-right">
            <div className="text-[11px] uppercase tracking-wider text-gray-500 mb-1">Tutar</div>
            <div className="text-lg text-gray-100">{paraYaz(o.tutar, o.para_birimi)}</div>
            {Number(o.kargo_ucreti) > 0 && (
              <div className="text-[11.5px] text-gray-500 mt-0.5">
                + {paraYaz(o.kargo_ucreti, 'TRY')} kargo
              </div>
            )}
          </div>
        </div>

        {o.onay_bekliyor && (
          <div className="mt-4 rounded-xl border border-amber-500/20 bg-amber-500/8 px-4 py-3
                          flex items-start gap-3 animate-fadein">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
                 className="w-[18px] h-[18px] text-amber-400 shrink-0 mt-0.5" strokeLinecap="round">
              <circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" />
            </svg>
            <div className="text-[12.5px] text-amber-100/85 leading-relaxed">
              Siparişin onay bekliyor. Onaylandığında üretime alınır ve tutar cari hesabına işlenir.
              O ana kadar tasarımı, modeli ve adresi değiştirebilirsin.
            </div>
          </div>
        )}
        {o.kargo_takip && (
          <div className="mt-4 flex items-center gap-2.5 text-[13px]">
            <span className="text-gray-500">Kargo takip:</span>
            <span className="font-mono text-gray-200">{o.kargo_takip}</span>
          </div>
        )}
      </div>

      {/* Urunler — her kalem KENDI tasarimi ve modeliyle ayri duzenlenir */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-[13px] uppercase tracking-[0.12em] text-gray-500">
            {o.kalemler.length > 1 ? `Ürünler (${o.kalemler.length})` : 'Ürün'}
          </h2>
          {o.kalemler.length > 1 && (
            <span className="text-[12px] text-gray-500">toplam {o.adet} adet</span>
          )}
        </div>

        <div className="space-y-3">
          {o.kalemler.map((k, i) => (
            <KalemKarti key={k.id} kalem={k} sira={i} siparisId={id}
                        cokluMu={o.kalemler.length > 1}
                        duzenlenebilir={!!y.urun_degistir} modeller={modeller}
                        onGuncellendi={yukle} onHata={setHata} onBildirim={setBildirim} />
          ))}
        </div>

        {!y.urun_degistir && (
          <Kilit metin="Sipariş üretime alındı — model ve tasarım artık değiştirilemez." />
        )}
      </div>

      {/* Alici */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-[13px] uppercase tracking-[0.12em] text-gray-500">Alıcı</h2>
          {y.adres_degistir && !adresDuzenle && (
            <button onClick={() => { setAdresForm({ ...o.adres }); setAdresDuzenle(true) }}
                    className="text-[12.5px] text-accent hover:brightness-125 transition">
              Düzenle
            </button>
          )}
        </div>

        {adresDuzenle ? (
          <div className="space-y-3.5 animate-popin">
            <input value={adresForm.ad || ''} placeholder="Ad Soyad" className="input w-full"
                   onChange={(e) => setAdresForm((f) => ({ ...f, ad: e.target.value }))} />
            {adresGerek && (
              <>
                <input value={adresForm.telefon || ''} placeholder="Telefon" className="input w-full"
                       onChange={(e) => setAdresForm((f) => ({ ...f, telefon: e.target.value }))} />
                <IlIlceSecici il={adresForm.il} ilce={adresForm.ilce}
                              onDegis={(i, c) => setAdresForm((f) => ({ ...f, il: i, ilce: c }))} />
                <textarea value={adresForm.adres || ''} rows={3} placeholder="Adres"
                          className="input w-full resize-none"
                          onChange={(e) => setAdresForm((f) => ({ ...f, adres: e.target.value }))} />
              </>
            )}
            <div className="flex items-center gap-2.5">
              <button onClick={adresKaydet} disabled={bekle === 'adres'} className="btn-primary !py-1.5 !px-4">
                {bekle === 'adres' ? 'Kaydediliyor…' : 'Kaydet'}
              </button>
              <button onClick={() => setAdresDuzenle(false)} className="btn-secondary !py-1.5 !px-4">
                Vazgeç
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-2 text-[13.5px]">
            <div className="text-gray-100">{o.adres?.ad || '—'}</div>
            {o.adres?.telefon && <div className="text-gray-400">{o.adres.telefon}</div>}
            {o.adres?.adres && <div className="text-gray-400 leading-relaxed">{o.adres.adres}</div>}
            {(o.adres?.ilce || o.adres?.il) && (
              <div className="text-gray-400">
                {[o.adres.ilce, o.adres.il].filter(Boolean).join(' / ')}
              </div>
            )}
            {!adresGerek && (
              <div className="text-[12px] text-gray-600 pt-1">
                Trendyol siparişi — adres Trendyol tarafından iletilir.
              </div>
            )}
            {!y.adres_degistir && (
              <Kilit metin={y.uretimde
                ? 'Sipariş üretime alındı — adres değiştirilemez.'
                : 'Kargo barkodu oluşturuldu — adres artık değiştirilemez.'} />
            )}
          </div>
        )}
      </div>

      {o.not && (
        <div className="card">
          <h2 className="text-[13px] uppercase tracking-[0.12em] text-gray-500 mb-2.5">Notun</h2>
          <p className="text-[13.5px] text-gray-300 leading-relaxed">{o.not}</p>
        </div>
      )}

      {/* Gecmis */}
      <div className="card">
        <h2 className="text-[13px] uppercase tracking-[0.12em] text-gray-500 mb-4">Durum geçmişi</h2>
        {o.gecmis?.length ? (
          <div className="bayi-zaman space-y-4">
            {o.gecmis.map((h, i) => (
              <div key={i} className="relative bayi-sira" style={{ '--gecikme': `${i * 45}ms` }}>
                <span className="bayi-zaman-nokta" />
                <div className="text-[13px] text-gray-200">{EYLEM_ADI[h.eylem] || h.eylem}</div>
                {h.not && <div className="text-[12.5px] text-gray-500 mt-1 leading-relaxed">{h.not}</div>}
                <div className="text-[11.5px] text-gray-600 mt-1">
                  {tarihYaz(h.tarih)}{h.kim ? ` · ${h.kim}` : ''}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-[13px] text-gray-500">Henüz hareket yok.</p>
        )}
      </div>

      {y.silinebilir && (
        <div className="flex justify-end">
          <button onClick={geriCek} disabled={bekle === 'sil'}
                  className="text-[12.5px] text-red-400/80 hover:text-red-300 transition
                             border border-red-500/20 hover:border-red-500/40 rounded-full px-4 py-2">
            {bekle === 'sil' ? 'İptal ediliyor…' : 'Siparişi geri çek'}
          </button>
        </div>
      )}
    </div>
  )
}
