/**
 * Yeni sipariş sihirbazı — 2 adım: Ürünler → Alıcı.
 *
 * Bir siparişte birden çok ürün olabilir; her ürünün KENDİ tasarımı, modeli ve
 * adedi vardır (UrunSecici). Sunucuya üç liste konum konum eşleşerek gider —
 * tasarim[i] ↔ model[i] ↔ adet[i].
 *
 * Adres kuralı kanaldan türer: Trendyol adresi kendi tarafında tuttuğu için
 * yalnızca alıcı adı istenir; Shopier/Instagram'da kargo için tam adres şart.
 * Aynı kural sunucuda da var (bayii_portal._adres_dogrula) — burası yalnız
 * erken geri bildirim, tek doğruluk kaynağı sunucu.
 */
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../lib/api'
import { ADRES_ZORUNLU, KANALLAR, paraYaz } from '../../lib/bayii'
import { Hata } from '../../components/BayiParcalar'
import IlIlceSecici from '../../components/IlIlceSecici'
import UrunSecici from '../../components/UrunSecici'

const ADIMLAR = ['Ürünler', 'Alıcı']
const MAX_URUN = 20      // sunucudaki MAX_KALEM ile aynı
let _sonrakiId = 1
const bosUrun = () => ({ yerelId: _sonrakiId++, dosya: null, tasarim: null,
                         model: '', modelEtiket: '', adet: 1 })

export default function BayiYeniSiparisPage() {
  const navigate = useNavigate()
  const [adim, setAdim] = useState(0)
  const [hata, setHata] = useState('')
  const [gonderiliyor, setGonderiliyor] = useState(false)
  const [basarili, setBasarili] = useState(null)

  const [urunler, setUrunler] = useState(() => [bosUrun()])
  const [modeller, setModeller] = useState([])
  const [katalog, setKatalog] = useState([])
  const [fiyat, setFiyat] = useState(null)

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
    api.get('/api/bayii/tasarimlar').then((d) => setKatalog(d.items || [])).catch(() => {})
  }, [])

  const urunDegis = (yerelId, yeni) =>
    setUrunler((l) => l.map((u) => (u.yerelId === yerelId ? yeni : u)))
  const urunSil = (yerelId) =>
    setUrunler((l) => l.filter((u) => u.yerelId !== yerelId))
  const urunEkle = () => {
    setHata('')
    if (urunler.length >= MAX_URUN) {
      setHata(`Bir siparişte en fazla ${MAX_URUN} ürün olabilir.`); return
    }
    setUrunler((l) => [...l, bosUrun()])
  }

  const toplamAdet = useMemo(
    () => urunler.reduce((t, u) => t + (u.adet || 0), 0), [urunler])
  const urunlerTamam = urunler.length > 0 && urunler.every((u) => (u.dosya || u.tasarim) && u.model)
  const adresGerek = ADRES_ZORUNLU.includes(kanal)
  const aliciTamam = ad.trim() &&
    (!adresGerek || (telefon.trim() && adres.trim() && il.trim() && ilce.trim()))
  const adimTamam = [urunlerTamam, aliciTamam]

  const gonder = async () => {
    setHata(''); setGonderiliyor(true)
    try {
      const fd = new FormData()
      // Konum eşleşmesi: her ürün için üç alan da AYNI sırada eklenir.
      for (const u of urunler) {
        // Katalogdan secildiyse dosya YOK, tasarim_id var. Sunucu konum konum
        // esler: tasarim_id[i] bossa sıradaki yuklenen dosya kullanilir.
        if (u.tasarim) fd.append('tasarim_id', u.tasarim.id)
        else { fd.append('tasarim_id', ''); fd.append('tasarim', u.dosya) }
        fd.append('model', u.model)
        fd.append('adet', String(u.adet))
      }
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
          {basarili.kalem_sayisi > 1 && (
            <> — {basarili.kalem_sayisi} ürün, toplam {basarili.toplam_adet} adet</>
          )}
          {' '}onay bekliyor. Onaylandığında üretime alınır ve cari hesabına işlenir.
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
      <div>
        <h1 className="text-2xl font-semibold text-white tracking-tight">Yeni sipariş</h1>
        <p className="text-[13px] text-gray-500 mt-1">
          Ürünlerini ekle, alıcıyı gir. Varyasyon seçimi ve onay bizde.
        </p>
      </div>

      {/* Adım göstergesi */}
      <div className="flex items-center gap-3">
        {ADIMLAR.map((a, i) => (
          <div key={a} className="flex items-center gap-3 shrink-0 [&:not(:last-child)]:flex-1">
            <button onClick={() => i < adim && setAdim(i)} disabled={i > adim}
                    className="flex items-center gap-2.5 shrink-0 disabled:cursor-default">
              <span className="bayi-adim-nokta"
                    data-durum={i < adim ? 'tamam' : i === adim ? 'aktif' : 'bos'}>
                {i < adim
                  ? <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"
                         strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5">
                      <path d="M4 12.5l5 5L20 7" /></svg>
                  : i + 1}
              </span>
              <span className={`text-[13px] transition-colors ${
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

      {/* ── Adım 1: Ürünler ── */}
      {adim === 0 && (
        <div className="space-y-3 animate-fadeinup">
          {urunler.map((u, i) => (
            <UrunSecici key={u.yerelId} urun={u} sira={i} modeller={modeller}
                        katalog={katalog}
                        silinebilir={urunler.length > 1}
                        onDegis={(yeni) => urunDegis(u.yerelId, yeni)}
                        onSil={() => urunSil(u.yerelId)} />
          ))}

          <button type="button" onClick={urunEkle} disabled={urunler.length >= MAX_URUN}
                  className="w-full rounded-2xl border border-dashed border-white/12 py-3.5
                             text-[13.5px] text-gray-400 hover:text-white hover:border-accent/40
                             hover:bg-accent/5 transition-all disabled:opacity-40
                             disabled:cursor-not-allowed flex items-center justify-center gap-2">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                 strokeLinecap="round" className="w-4 h-4"><path d="M12 5v14M5 12h14" /></svg>
            Ürün ekle
          </button>

          {urunler.length > 1 && (
            <div className="flex items-center justify-between px-1 pt-1 text-[13px]">
              <span className="text-gray-500">
                {urunler.length} ürün · toplam {toplamAdet} adet
              </span>
              {fiyat && Number(fiyat.birim_fiyat) > 0 && (
                <span className="text-gray-400">
                  ≈ {paraYaz(Number(fiyat.birim_fiyat) * toplamAdet, fiyat.para_birimi || 'TRY')}
                  <span className="text-gray-600"> (onayda kesinleşir)</span>
                </span>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Adım 2: Alıcı ── */}
      {adim === 1 && (
        <div className="card space-y-5 animate-fadeinup">
          <div>
            <label className="block text-[11px] uppercase tracking-wider text-gray-500 mb-2">
              Sipariş nereden geldi?
            </label>
            <div className="grid grid-cols-3 gap-2.5">
              {KANALLAR.map((k) => (
                <button key={k.id} type="button" onClick={() => setKanal(k.id)}
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

          {/* Adres alanları yalnızca gerektiğinde açılır — akordeon */}
          <div className="grid transition-[grid-template-rows,opacity] duration-300 ease-out"
               style={{ gridTemplateRows: adresGerek ? '1fr' : '0fr', opacity: adresGerek ? 1 : 0 }}>
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

          {/* Özet — gönderim öncesi son kontrol */}
          <div className="rounded-xl border border-brand-border bg-brand-input/25 p-3.5">
            <div className="text-[11px] uppercase tracking-wider text-gray-500 mb-2.5">
              Sipariş özeti
            </div>
            <div className="space-y-1.5">
              {urunler.map((u, i) => (
                <div key={u.yerelId} className="flex items-center gap-2 text-[13px]">
                  <span className="text-gray-600 w-4 shrink-0">{i + 1}.</span>
                  <span className="text-gray-200 flex-1 truncate">{u.modelEtiket || u.model}</span>
                  <span className="text-gray-500 shrink-0">× {u.adet}</span>
                </div>
              ))}
            </div>
            {fiyat && Number(fiyat.birim_fiyat) > 0 && (
              <div className="mt-3 pt-3 border-t border-white/6 flex items-center justify-between text-[13px]">
                <span className="text-gray-500">Tahmini tutar</span>
                <span className="text-gray-200">
                  {paraYaz(Number(fiyat.birim_fiyat) * toplamAdet, fiyat.para_birimi || 'TRY')}
                  {adresGerek && Number(fiyat.kargo_ucreti) > 0 && (
                    <span className="text-gray-500"> + {paraYaz(fiyat.kargo_ucreti, 'TRY')} kargo</span>
                  )}
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="flex items-center justify-between gap-3">
        <button onClick={() => (adim === 0 ? navigate('/bayii') : setAdim((a) => a - 1))}
                className="btn-secondary" disabled={gonderiliyor}>
          {adim === 0 ? 'Vazgeç' : 'Geri'}
        </button>
        {adim === 0 ? (
          <button onClick={() => setAdim(1)} disabled={!adimTamam[0]}
                  className="btn-primary inline-flex items-center gap-2">
            Devam
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"
                 strokeLinecap="round" className="w-4 h-4"><path d="M9 6l6 6-6 6" /></svg>
          </button>
        ) : (
          <button onClick={gonder} disabled={!adimTamam[1] || gonderiliyor}
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
