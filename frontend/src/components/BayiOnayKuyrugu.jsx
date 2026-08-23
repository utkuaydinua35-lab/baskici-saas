/**
 * Yonetim tarafi: bayi portalinden gelen siparislerin ONAY kuyrugu.
 *
 * Bayi siparis acinca 'bayii_onay_bekliyor' ile bekler; kaliba GIRMEZ ve cari
 * borc ISLENMEZ. Burada varyasyon secilip onaylandiginda borc yazilir ve
 * siparis uretime akar.
 */
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useToast } from './Toast'
import { kanalAdi } from '../lib/bayii'

// placement_rules.normalize_variation'in urettigi degerler
const VARYASYONLAR = ['SİYAH', 'BEYAZ', 'ŞEFFAF', 'PARLAK', 'MAGSAFE']

export default function BayiOnayKuyrugu({ onOnaylandi }) {
  const [liste, setListe] = useState([])
  const [yuklendi, setYuklendi] = useState(false)
  const [secim, setSecim] = useState({})     // {line_item_id: varyasyon}
  const [kargo, setKargo] = useState({})     // {order_id: bool}
  const [bekle, setBekle] = useState('')
  const toast = useToast()
  const navigate = useNavigate()

  const yukle = useCallback(async () => {
    try {
      const d = await api.get('/api/dealers/portal/onay-bekleyen')
      setListe(Array.isArray(d) ? d : [])
    } catch { /* yetkisiz/hata: kuyruk gizli kalir */ }
    finally { setYuklendi(true) }
  }, [])
  useEffect(() => { yukle() }, [yukle])

  const onayla = async (o) => {
    setBekle(o.id)
    try {
      const varyasyonlar = {}
      for (const k of o.kalemler) varyasyonlar[k.id] = secim[k.id] || 'SİYAH'
      const r = await api.post(`/api/dealers/portal/onay-bekleyen/${o.id}`, {
        varyasyonlar, apply_shipping: kargo[o.id] !== false,
      })
      toast.success(`#${o.order_number} onaylandı · borç ${r.urun} ${r.currency}` +
                    (r.kargo ? ` + ${r.kargo} ₺ kargo` : ''))
      setListe((l) => l.filter((x) => x.id !== o.id))
      onOnaylandi?.()
    } catch (e) {
      toast.error(e.detail || 'Onaylanamadı')
    } finally { setBekle('') }
  }

  if (!yuklendi || liste.length === 0) return null

  return (
    <div className="card mb-5 animate-fadeinup !border-amber-500/25">
      <div className="flex items-center gap-2.5 mb-4">
        <span className="w-2 h-2 rounded-full bg-amber-400"
              style={{ animation: 'glow-pulse 2s ease-in-out infinite' }} />
        <h2 className="text-[15px] font-semibold text-gray-100">
          Bayi siparişleri — onay bekliyor
        </h2>
        <span className="text-[11px] px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-300
                         border border-amber-500/25">{liste.length}</span>
      </div>

      <div className="space-y-3">
        {liste.map((o, i) => (
          <div key={o.id} className="rounded-xl border border-brand-border bg-brand-input/30 p-3.5
                                     bayi-sira" style={{ '--gecikme': `${i * 60}ms` }}>
            <div className="flex items-start gap-3 flex-wrap">
              <div className="flex-1 min-w-[220px]">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[13.5px] font-semibold text-gray-100">{o.bayi}</span>
                  <span className="text-[11.5px] text-gray-500">#{o.order_number}</span>
                  {o.kanal && (
                    <span className="text-[10px] tracking-wide text-gray-500
                                     border border-white/10 rounded px-1.5 py-0.5">{kanalAdi(o.kanal)}</span>
                  )}
                </div>
                <div className="text-[12px] text-gray-500 mt-1">
                  {o.musteri}
                  {o.adres?.city && ` · ${o.adres.province || ''} ${o.adres.city}`}
                  {o.adres?.phone && ` · ${o.adres.phone}`}
                </div>
                {o.not && <div className="text-[12px] text-gray-400 mt-1.5 italic">“{o.not}”</div>}
              </div>
              <button onClick={() => navigate(`/orders/${o.id}`)}
                      className="btn-secondary !text-xs !py-1.5 !px-3">Sipariş detayı</button>
            </div>

            <div className="mt-3 space-y-2.5">
              {o.kalemler.map((k) => (
                <div key={k.id} className="flex items-center gap-3 flex-wrap">
                  <div className="w-11 h-11 rounded-lg overflow-hidden border border-white/8
                                  bg-white/[0.03] grid place-items-center shrink-0">
                    {k.gorsel
                      ? <img src={k.gorsel} alt="" className="w-full h-full object-cover" />
                      : <span className="text-[10px] text-gray-600">—</span>}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-[13px] text-gray-200">{k.model || '—'}</div>
                    <div className="text-[11.5px] text-gray-500">
                      {k.tasarim_kodu || '—'} · {k.adet} adet
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {VARYASYONLAR.map((v) => {
                      const aktif = (secim[k.id] || k.varyasyon || 'SİYAH') === v
                      return (
                        <button key={v}
                                onClick={() => setSecim((s) => ({ ...s, [k.id]: v }))}
                                className={`text-[11.5px] px-2.5 py-1 rounded-full border transition-all ${
                                  aktif ? 'border-accent/50 bg-accent/15 text-white'
                                        : 'border-brand-border text-gray-500 hover:text-gray-300'}`}>
                          {v}
                        </button>
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-3.5 pt-3 border-t border-white/6 flex items-center gap-3 flex-wrap">
              <label className="flex items-center gap-2 text-[12.5px] text-gray-400 cursor-pointer">
                <input type="checkbox" checked={kargo[o.id] !== false}
                       onChange={(e) => setKargo((c) => ({ ...c, [o.id]: e.target.checked }))}
                       className="accent-[rgb(var(--accent-rgb))]" />
                Kargo ücretini yansıt
              </label>
              <button onClick={() => onayla(o)} disabled={bekle === o.id}
                      className="btn-primary !text-xs !py-1.5 !px-4 ml-auto">
                {bekle === o.id ? 'Onaylanıyor…' : 'Onayla ve üretime al'}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
