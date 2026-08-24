/**
 * Yonetim: bayi IPTAL taleplerinin kuyrugu.
 *
 * Onaylamak geri alinmasi zor iki sey yapar — kalibi siler ve borcu iade eder.
 * O yuzden her talebin yaninda "onaylarsan ne olacak" ONIZLEMESI gosteriliyor;
 * karar sunucudan (app.services.bayii_iptal) geliyor, burada tekrar
 * hesaplanmiyor.
 */
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useToast } from './Toast'

const KALIP_ASAMA = { 1: 'Taslak', 2: 'Hazır', 3: 'Baskıya gönderildi', 4: 'Baskıda', 5: 'Tamamlandı' }

export default function BayiIptalKuyrugu({ onDegisti }) {
  const [liste, setListe] = useState([])
  const [yuklendi, setYuklendi] = useState(false)
  const [bekle, setBekle] = useState('')
  const toast = useToast()
  const navigate = useNavigate()

  const yukle = useCallback(async () => {
    try {
      const d = await api.get('/api/dealers/portal/iptal-talepleri')
      setListe(Array.isArray(d) ? d : [])
    } catch { /* yetkisiz: kuyruk gizli kalir */ }
    finally { setYuklendi(true) }
  }, [])
  useEffect(() => { yukle() }, [yukle])

  const onayla = async (o) => {
    const s = o.sonuc
    const satirlar = [
      `#${o.order_number} — ${o.bayi}`,
      s.iade_edilir ? '• Ücret cari hesaptan DÜŞÜLECEK' : '• Kalıp basıldı — ücret İADE EDİLMEYECEK',
      s.kaliplar_silinir && s.kaliplar.length
        ? `• Şu kalıp(lar) SİLİNECEK: ${s.kaliplar.map((k) => k.kod).join(', ')}`
        : '• Kalıp silinmeyecek',
      '• Sipariş "iptal edildi" olacak, paketlemede çıkmayacak',
    ]
    if (!window.confirm(satirlar.join('\n') + '\n\nOnaylıyor musun?')) return
    setBekle(o.id)
    try {
      const r = await api.post(`/api/dealers/portal/iptal-talepleri/${o.id}`)
      toast.success(`#${o.order_number} iptal edildi` +
        (r.iade_edildi ? ' · ücret iade edildi' : ' · iade yok (basılmış)'))
      setListe((l) => l.filter((x) => x.id !== o.id))
      onDegisti?.()
    } catch (e) { toast.error(e.detail || 'Onaylanamadı') }
    finally { setBekle('') }
  }

  const reddet = async (o) => {
    if (!window.confirm(`#${o.order_number} iptal talebi reddedilsin mi? Sipariş üretimde kalır.`)) return
    setBekle(o.id)
    try {
      await api.del(`/api/dealers/portal/iptal-talepleri/${o.id}`)
      toast.success('Talep reddedildi')
      setListe((l) => l.filter((x) => x.id !== o.id))
      onDegisti?.()
    } catch (e) { toast.error(e.detail || 'Reddedilemedi') }
    finally { setBekle('') }
  }

  if (!yuklendi || liste.length === 0) return null

  return (
    <div className="card mb-5 animate-fadeinup !border-red-500/25">
      <div className="flex items-center gap-2.5 mb-4">
        <span className="w-2 h-2 rounded-full bg-red-400"
              style={{ animation: 'glow-pulse 2s ease-in-out infinite' }} />
        <h2 className="text-[15px] font-semibold text-gray-100">Bayi iptal talepleri</h2>
        <span className="text-[11px] px-2 py-0.5 rounded-full bg-red-500/15 text-red-300
                         border border-red-500/25">{liste.length}</span>
      </div>

      <div className="space-y-3">
        {liste.map((o, i) => (
          <div key={o.id} className="rounded-xl border border-brand-border bg-brand-input/30 p-3.5
                                     bayi-sira" style={{ '--gecikme': `${i * 60}ms` }}>
            <div className="flex items-start gap-3 flex-wrap">
              <div className="flex-1 min-w-[200px]">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[13.5px] font-semibold text-gray-100">{o.bayi}</span>
                  <span className="text-[11.5px] text-gray-500">#{o.order_number}</span>
                </div>
                <div className="text-[12px] text-gray-500 mt-1">{o.musteri}</div>
                {o.sebep && (
                  <div className="text-[12.5px] text-gray-400 mt-1.5 italic">“{o.sebep}”</div>
                )}
              </div>
              <button onClick={() => navigate(`/orders/${o.id}`)}
                      className="btn-secondary !text-xs !py-1.5 !px-3">Sipariş detayı</button>
            </div>

            <div className="mt-3 flex items-center gap-2 flex-wrap">
              {o.kalemler.map((k, n) => (
                <div key={n} className="flex items-center gap-2 rounded-lg border border-white/8
                                        bg-white/[0.03] pr-2.5">
                  <div className="w-8 h-8 rounded-l-lg overflow-hidden grid place-items-center">
                    {k.gorsel
                      ? <img src={k.gorsel} alt="" className="w-full h-full object-cover" />
                      : <span className="text-[10px] text-gray-600">—</span>}
                  </div>
                  <span className="text-[12px] text-gray-300">{k.model} ×{k.adet}</span>
                </div>
              ))}
            </div>

            {/* Onaylarsan ne olacak — karar sunucudan */}
            <div className="mt-3 rounded-lg bg-black/25 border border-white/6 px-3 py-2.5
                            text-[12px] space-y-1">
              <div className={o.sonuc.iade_edilir ? 'text-emerald-300' : 'text-amber-300'}>
                {o.sonuc.iade_edilir
                  ? '↩ Ücret cari hesaptan düşülecek'
                  : '⚠ Kalıp basılmış — ücret iade EDİLMEYECEK'}
              </div>
              {o.sonuc.kaliplar.length > 0 && (
                <div className="text-gray-400">
                  {o.sonuc.kaliplar_silinir ? '🗑 Silinecek kalıp: ' : '📦 Kalıp: '}
                  {o.sonuc.kaliplar.map((k) =>
                    `${k.kod} (${KALIP_ASAMA[k.asama] || k.asama})`).join(', ')}
                  {!o.sonuc.kaliplar_silinir && ' — silinmeyecek'}
                </div>
              )}
            </div>

            <div className="mt-3 flex items-center gap-2 justify-end">
              <button onClick={() => reddet(o)} disabled={bekle === o.id}
                      className="btn-secondary !text-xs !py-1.5 !px-4">Reddet</button>
              <button onClick={() => onayla(o)} disabled={bekle === o.id}
                      className="!text-xs !py-1.5 !px-4 rounded-full font-semibold
                                 bg-red-500/85 hover:bg-red-500 text-white transition-colors
                                 disabled:opacity-50">
                {bekle === o.id ? 'İşleniyor…' : 'İptali onayla'}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
