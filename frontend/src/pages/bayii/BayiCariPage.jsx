/** Cari hesap hareketleri. */
import { useCallback, useEffect, useState } from 'react'
import { api } from '../../lib/api'
import { paraYaz, tarihYaz } from '../../lib/bayii'
import { Bos, Hata, Iskelet, Sayac } from '../../components/BayiParcalar'

const TUR_ADI = {
  siparis: 'Sipariş', kargo: 'Kargo', odeme: 'Ödeme',
  duzeltme: 'Düzeltme', manuel: 'Manuel kayıt', iade: 'İade',
}
// Bakiyeyi ARTIRAN hareket borç, azaltan alacaktır.
const borcMu = (t) => Number(t.tutar) > 0

export default function BayiCariPage() {
  const [veri, setVeri] = useState(null)
  const [hata, setHata] = useState('')

  const yukle = useCallback(async () => {
    setHata('')
    try { setVeri(await api.get('/api/bayii/cari')) }
    catch (e) { setHata(e.detail || 'Cari yüklenemedi') }
  }, [])
  useEffect(() => { yukle() }, [yukle])

  const birim = veri?.para_birimi || 'TRY'
  const ikili = Number(veri?.bakiye || 0) !== 0 && Number(veri?.bakiye_usd || 0) !== 0

  return (
    <div className="space-y-5">
      <Hata mesaj={hata} tekrar={yukle} />

      <div>
        <h1 className="text-2xl font-semibold text-white tracking-tight">Cari Hesap</h1>
        <p className="text-[13px] text-gray-500 mt-1">Borç ve ödeme hareketlerin.</p>
      </div>

      <div className="card relative overflow-hidden">
        <div aria-hidden className="absolute -right-14 -top-14 w-52 h-52 rounded-full blur-3xl"
             style={{ background: 'rgb(var(--accent-rgb) / 0.15)' }} />
        <div className="relative">
          <div className="text-[11px] uppercase tracking-[0.14em] text-gray-500 mb-2">
            Güncel bakiye
          </div>
          {veri ? (
            <div className="flex items-baseline gap-4 flex-wrap">
              <Sayac deger={birim === 'USD' ? veri.bakiye_usd : veri.bakiye}
                     className="text-[32px] font-semibold text-white leading-none"
                     bicim={(n) => paraYaz(n, birim)} />
              {ikili && (
                <span className="text-base text-gray-400">
                  + {paraYaz(birim === 'USD' ? veri.bakiye : veri.bakiye_usd,
                             birim === 'USD' ? 'TRY' : 'USD')}
                </span>
              )}
            </div>
          ) : <div className="h-8 w-36 rounded-lg bg-white/5 animate-pulse" />}
        </div>
      </div>

      {!veri ? <Iskelet satir={4} yukseklik={56} /> : veri.items.length === 0 ? (
        <div className="card">
          <Bos baslik="Hareket yok" aciklama="Sipariş verdikçe hareketler burada listelenir." />
        </div>
      ) : (
        <div className="card !p-0 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="tbl">
              <thead>
                <tr><th>Tarih</th><th>Tür</th><th>Açıklama</th>
                    <th className="text-right">Tutar</th><th className="text-right">Bakiye</th></tr>
              </thead>
              <tbody>
                {veri.items.map((t, i) => (
                  <tr key={i} className="bayi-sira" style={{ '--gecikme': `${Math.min(i, 14) * 35}ms` }}>
                    <td className="whitespace-nowrap text-gray-400">{tarihYaz(t.tarih)}</td>
                    <td>
                      <span className={`text-[11px] px-2 py-0.5 rounded-full border ${
                        borcMu(t) ? 'bg-amber-500/10 text-amber-300 border-amber-500/20'
                                  : 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20'}`}>
                        {TUR_ADI[t.tur] || t.tur}
                      </span>
                    </td>
                    <td className="text-gray-300 max-w-[280px] truncate" title={t.aciklama}>
                      {t.aciklama || '—'}
                    </td>
                    <td className={`text-right font-medium whitespace-nowrap ${
                      borcMu(t) ? 'text-amber-300' : 'text-emerald-300'}`}>
                      {borcMu(t) ? '+' : ''}{paraYaz(t.tutar, t.para_birimi)}
                    </td>
                    <td className="text-right text-gray-400 whitespace-nowrap">
                      {paraYaz(t.bakiye_sonra, t.para_birimi)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
