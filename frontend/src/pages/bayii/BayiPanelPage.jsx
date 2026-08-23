/** Bayi ana ekrani: cari durum + sayilar + son siparisler. */
import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../../lib/api'
import { paraYaz, tarihYaz } from '../../lib/bayii'
import { Bos, DurumRozet, Hata, Iskelet, Sayac } from '../../components/BayiParcalar'

const SAYAC_KUTULARI = [
  { anahtar: 'onay_bekleyen', ad: 'Onay bekleyen', renk: '#fbbf24',
    ipucu: 'Varyasyonu seçilip onaylanmayı bekliyor' },
  { anahtar: 'uretimde', ad: 'Üretimde', renk: '#a78bfa',
    ipucu: 'Kalıba alındı, baskıda ya da paketlemede' },
  { anahtar: 'kargoda', ad: 'Kargoda', renk: '#38bdf8',
    ipucu: 'Kargoya verildi' },
  { anahtar: 'toplam', ad: 'Toplam sipariş', renk: '#9ca3af', ipucu: 'Açık siparişlerin' },
]

export default function BayiPanelPage() {
  const [veri, setVeri] = useState(null)
  const [hata, setHata] = useState('')
  const navigate = useNavigate()

  const yukle = useCallback(async () => {
    setHata('')
    try { setVeri(await api.get('/api/bayii/ozet')) }
    catch (e) { setHata(e.detail || 'Panel yüklenemedi') }
  }, [])
  useEffect(() => { yukle() }, [yukle])

  const birim = veri?.bayi?.para_birimi || 'TRY'
  const bakiye = birim === 'USD' ? veri?.cari?.bakiye_usd : veri?.cari?.bakiye
  const ikiBakiye = Number(veri?.cari?.bakiye || 0) > 0 && Number(veri?.cari?.bakiye_usd || 0) > 0

  return (
    <div className="space-y-6">
      <Hata mesaj={hata} tekrar={yukle} />

      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold text-white tracking-tight">
            Merhaba{veri?.bayi?.ad ? `, ${veri.bayi.ad}` : ''}
          </h1>
          <p className="text-[13px] text-gray-500 mt-1">Siparişlerinin güncel durumu burada.</p>
        </div>
        <Link to="/bayii/yeni" className="btn-primary inline-flex items-center gap-2">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"
               strokeLinecap="round" className="w-4 h-4"><path d="M12 5v14M5 12h14" /></svg>
          Yeni sipariş
        </Link>
      </div>

      {/* Cari kart */}
      <div className="card relative overflow-hidden bayi-sira" style={{ '--gecikme': '0ms' }}>
        <div aria-hidden className="absolute -right-16 -top-16 w-56 h-56 rounded-full blur-3xl"
             style={{ background: 'rgb(var(--accent-rgb) / 0.16)' }} />
        <div className="relative flex flex-wrap items-end gap-x-10 gap-y-5">
          <div>
            <div className="text-[11px] uppercase tracking-[0.14em] text-gray-500 mb-2">
              Cari borcun
            </div>
            {veri ? (
              <div className="flex items-baseline gap-3">
                <Sayac deger={bakiye} className="text-[34px] font-semibold text-white leading-none bayi-sayac"
                       bicim={(n) => paraYaz(n, birim)} />
                {ikiBakiye && (
                  <span className="text-sm text-gray-400">
                    + {paraYaz(veri.cari.bakiye, 'TRY')}
                  </span>
                )}
              </div>
            ) : (
              <div className="h-9 w-40 rounded-lg bg-white/5 animate-pulse" />
            )}
            <Link to="/bayii/cari"
                  className="inline-flex items-center gap-1 text-[12.5px] text-accent hover:brightness-125 mt-3 transition">
              Hesap hareketleri
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                   strokeLinecap="round" className="w-3.5 h-3.5"><path d="M9 6l6 6-6 6" /></svg>
            </Link>
          </div>

          <div className="flex gap-8 ml-auto">
            <div>
              <div className="text-[11px] uppercase tracking-[0.14em] text-gray-500 mb-1.5">Birim fiyat</div>
              <div className="text-lg text-gray-200">{paraYaz(veri?.cari?.birim_fiyat, birim)}</div>
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-[0.14em] text-gray-500 mb-1.5">Kargo</div>
              <div className="text-lg text-gray-200">{paraYaz(veri?.cari?.kargo_ucreti, 'TRY')}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Sayaclar */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {SAYAC_KUTULARI.map((k, i) => (
          <div key={k.anahtar} title={k.ipucu}
               className="card !p-4 bayi-kart bayi-sira cursor-default"
               style={{ '--gecikme': `${60 + i * 55}ms` }}>
            <div className="flex items-center gap-2 mb-2.5">
              <span className="w-2 h-2 rounded-full" style={{ background: k.renk }} />
              <span className="text-[11.5px] text-gray-500">{k.ad}</span>
            </div>
            {veri
              ? <Sayac deger={veri.sayilar[k.anahtar]} className="text-[26px] font-semibold text-white leading-none" />
              : <div className="h-7 w-10 rounded bg-white/5 animate-pulse" />}
          </div>
        ))}
      </div>

      {/* Son siparisler */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-[15px] font-medium text-gray-200">Son siparişlerin</h2>
          <Link to="/bayii/siparisler" className="text-[12.5px] text-gray-500 hover:text-gray-300 transition">
            Tümünü gör
          </Link>
        </div>

        {!veri ? <Iskelet satir={3} /> : veri.son_siparisler.length === 0 ? (
          <div className="card">
            <Bos baslik="Henüz siparişin yok"
                 aciklama="İlk siparişini oluştur; tasarımı yükle, modeli seç, gerisini biz halledelim."
                 eylem={<Link to="/bayii/yeni" className="btn-primary">Sipariş oluştur</Link>} />
          </div>
        ) : (
          <div className="space-y-2.5">
            {veri.son_siparisler.map((o, i) => (
              <button key={o.id} onClick={() => navigate(`/bayii/siparis/${o.id}`)}
                      className="card !p-3.5 bayi-kart bayi-sira w-full text-left flex items-center gap-3.5"
                      style={{ '--gecikme': `${i * 55}ms` }}>
                <div className="w-12 h-12 rounded-xl overflow-hidden bg-white/[0.04] shrink-0
                                border border-white/6 grid place-items-center">
                  {o.kalemler?.[0]?.gorsel
                    ? <img src={o.kalemler[0].gorsel} alt="" className="w-full h-full object-cover" />
                    : <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"
                           className="w-5 h-5 text-gray-600"><rect x="6" y="2.5" width="12" height="19" rx="3" /></svg>}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[13.5px] text-gray-200 font-medium truncate">
                      {o.kalemler?.[0]?.model || o.order_number}
                    </span>
                    {o.adet > 1 && (
                      <span className="text-[11px] text-gray-500 shrink-0">×{o.adet}</span>
                    )}
                  </div>
                  <div className="text-[11.5px] text-gray-500 truncate mt-0.5">
                    {o.musteri} · {tarihYaz(o.tarih)}
                  </div>
                </div>
                <DurumRozet siparis={o} />
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
