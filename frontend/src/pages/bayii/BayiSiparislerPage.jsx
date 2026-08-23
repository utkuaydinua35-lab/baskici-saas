/** Bayinin tum siparisleri — arama + durum suzgeci. */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../../lib/api'
import { kanalAdi, tarihYaz } from '../../lib/bayii'
import { Bos, DurumRozet, Hata, Iskelet } from '../../components/BayiParcalar'

const SUZGECLER = [
  { id: 'hepsi', ad: 'Hepsi', kural: () => true },
  { id: 'onay', ad: 'Onay bekleyen', kural: (o) => o.onay_bekliyor },
  { id: 'uretim', ad: 'Üretimde', kural: (o) => !o.onay_bekliyor && !o.iptal && o.asama < 8 },
  { id: 'kargo', ad: 'Kargoda', kural: (o) => o.asama >= 8 && !o.iptal },
]

export default function BayiSiparislerPage() {
  const [liste, setListe] = useState(null)
  const [hata, setHata] = useState('')
  const [suzgec, setSuzgec] = useState('hepsi')
  const [arama, setArama] = useState('')
  const navigate = useNavigate()

  const yukle = useCallback(async () => {
    setHata('')
    try { setListe((await api.get('/api/bayii/siparisler')).items) }
    catch (e) { setHata(e.detail || 'Siparişler yüklenemedi') }
  }, [])
  useEffect(() => { yukle() }, [yukle])

  const gorunen = useMemo(() => {
    if (!liste) return []
    const k = SUZGECLER.find((x) => x.id === suzgec)?.kural || (() => true)
    const q = arama.trim().toLocaleLowerCase('tr')
    return liste.filter((o) => {
      if (!k(o)) return false
      if (!q) return true
      const saman = [o.order_number, o.musteri, o.kanal,
                     ...(o.kalemler || []).map((x) => x.model)].join(' ').toLocaleLowerCase('tr')
      return saman.includes(q)
    })
  }, [liste, suzgec, arama])

  const sayi = useCallback((id) => {
    if (!liste) return 0
    const k = SUZGECLER.find((x) => x.id === id)?.kural || (() => true)
    return liste.filter(k).length
  }, [liste])

  return (
    <div className="space-y-5">
      <Hata mesaj={hata} tekrar={yukle} />

      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold text-white tracking-tight">Siparişlerim</h1>
          <p className="text-[13px] text-gray-500 mt-1">
            {liste ? `${liste.length} sipariş` : 'Yükleniyor…'}
          </p>
        </div>
        <Link to="/bayii/yeni" className="btn-primary">Yeni sipariş</Link>
      </div>

      <div className="flex items-center gap-2.5 flex-wrap">
        <div className="flex items-center gap-1 p-1 rounded-full border border-brand-border bg-brand-input/40">
          {SUZGECLER.map((s) => (
            <button key={s.id} onClick={() => setSuzgec(s.id)}
                    className={`px-3.5 py-1.5 rounded-full text-[12.5px] transition-all
                      ${suzgec === s.id
                        ? 'bg-accent/18 text-white shadow-[inset_0_0_0_1px_rgb(var(--accent-rgb)/0.3)]'
                        : 'text-gray-400 hover:text-gray-200'}`}>
              {s.ad}
              {liste && <span className="ml-1.5 text-[11px] opacity-60">{sayi(s.id)}</span>}
            </button>
          ))}
        </div>
        <div className="relative flex-1 min-w-[180px] max-w-xs ml-auto">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
               className="w-4 h-4 text-gray-600 absolute left-3 top-1/2 -translate-y-1/2">
            <circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" strokeLinecap="round" />
          </svg>
          <input value={arama} onChange={(e) => setArama(e.target.value)}
                 placeholder="Sipariş no, alıcı, model…" className="input w-full !pl-9" />
        </div>
      </div>

      {!liste ? <Iskelet satir={5} /> : gorunen.length === 0 ? (
        <div className="card">
          <Bos baslik={arama ? 'Eşleşen sipariş yok' : 'Bu listede sipariş yok'}
               aciklama={arama ? 'Farklı bir arama dene.' : 'Süzgeci değiştir ya da yeni sipariş oluştur.'} />
        </div>
      ) : (
        <div className="space-y-2.5">
          {gorunen.map((o, i) => (
            <button key={o.id} onClick={() => navigate(`/bayii/siparis/${o.id}`)}
                    className="card !p-4 bayi-kart bayi-sira w-full text-left flex items-center gap-4"
                    style={{ '--gecikme': `${Math.min(i, 12) * 45}ms` }}>
              <div className="w-14 h-14 rounded-xl overflow-hidden bg-white/[0.04] shrink-0
                              border border-white/6 grid place-items-center">
                {o.kalemler?.[0]?.gorsel
                  ? <img src={o.kalemler[0].gorsel} alt="" className="w-full h-full object-cover" />
                  : <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4"
                         className="w-6 h-6 text-gray-600"><rect x="6" y="2.5" width="12" height="19" rx="3" /></svg>}
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[14px] text-gray-100 font-medium">
                    {o.kalemler?.[0]?.model || '—'}
                  </span>
                  {o.adet > 1 && <span className="text-[11px] text-gray-500">×{o.adet}</span>}
                  {o.kanal && (
                    <span className="text-[10.5px] tracking-wide text-gray-500
                                     border border-white/8 rounded px-1.5 py-0.5">{kanalAdi(o.kanal)}</span>
                  )}
                </div>
                <div className="text-[12px] text-gray-500 mt-1 truncate">
                  #{o.order_number} · {o.musteri}
                </div>
                <div className="text-[11.5px] text-gray-600 mt-0.5">{tarihYaz(o.tarih)}</div>
              </div>

              <div className="flex flex-col items-end gap-2 shrink-0">
                <DurumRozet siparis={o} />
                {o.kargo_takip && (
                  <span className="text-[11px] text-gray-500 font-mono">{o.kargo_takip}</span>
                )}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
