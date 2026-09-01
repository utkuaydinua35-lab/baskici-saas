/**
 * Onaylanmış ama HENÜZ KALIBA GİRMEMİŞ bayi siparişleri — hatalı onayı düzeltme
 * penceresi.
 *
 * Neden onayı geri almak yerine bu: onay bayinin carisine borç yazıyor. Geri
 * alıp yeniden onaylamak carisinde borç–iade–borç üçlemesi bırakırdı. Hata
 * genelde onayın kendisinde değil içeriğinde (hangi tasarım / hangi varyasyon).
 *
 * Sınır ONAY değil KALIP: kalıba girmiş kalem burada listelenmez, çünkü
 * basılmış olabilir. Tamamı kalıpta olan sipariş hiç görünmez.
 */
import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useToast } from './Toast'
import { kanalAdi } from '../lib/bayii'
import GorselBuyutec from './GorselBuyutec'
import { TasarimSecici, VARYASYONLAR } from './BayiOnayKuyrugu'

export default function BayiDuzeltmeKuyrugu({ onDegisti }) {
  const [liste, setListe] = useState([])
  const [acik, setAcik] = useState(false)
  const [secici, setSecici] = useState(null)   // {order, kalem}
  const [buyutec, setBuyutec] = useState(null)
  const [iptalHedef, setIptalHedef] = useState(null)  // {order, onizleme}
  const [bekle, setBekle] = useState('')
  const toast = useToast()

  const yukle = useCallback(async () => {
    try { setListe(await api.get('/api/dealers/portal/duzeltilebilir')) }
    catch { /* yetkisiz/hata: bölüm gizli kalır */ }
  }, [])
  // Kurulumda tek veri çekimi. setState efekt gövdesinde değil, asenkron
  // cevapta çağrılıyor — kural burada yanlış pozitif veriyor.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { yukle() }, [yukle])

  const duzelt = async (order, kalem, govde, mesaj) => {
    setBekle(kalem.id)
    try {
      const r = await api.patch(
        `/api/dealers/portal/siparis/${order.id}/kalem/${kalem.id}`, govde)
      if (r.degismedi) { toast.info('Değişiklik yok'); return }
      toast.success(mesaj(r))
      await yukle()
    } catch (e) { toast.error(e.detail || 'Değiştirilemedi') }
    finally { setBekle('') }
  }

  // İptal iki adım: önce ne olacağını SOR, sonra onayla. Geri alınamayan bir
  // işlemi tek tıkla yapmak kabul edilemez.
  const iptalSor = async (order) => {
    try {
      const r = await api.post(`/api/dealers/portal/siparis/${order.id}/iptal`, {})
      setIptalHedef({ order, onizleme: r })
    } catch (e) { toast.error(e.detail || 'İptal bilgisi alınamadı') }
  }

  const iptalEt = async (sebep) => {
    const { order } = iptalHedef
    setBekle(order.id)
    try {
      const r = await api.post(`/api/dealers/portal/siparis/${order.id}/iptal`,
        { sebep, onayla: true })
      setIptalHedef(null)
      toast.success(`#${order.order_number} iptal edildi`
        + (r.iade_tutari_var ? ' · ücret iade edildi'
          : r.iade_edildi ? ' · iade edilecek borç yoktu'
          : ' · ücret iade edilmedi'))
      await yukle(); onDegisti?.()
    } catch (e) { toast.error(e.detail || 'İptal edilemedi') }
    finally { setBekle('') }
  }

  if (!liste.length) return null

  return (
    <div className="card mb-4">
      <button onClick={() => setAcik((a) => !a)}
              className="w-full flex items-center justify-between text-left">
        <div>
          <h2 className="text-[15px] font-medium text-gray-100">
            ✎ Düzeltilebilir siparişler
            <span className="ml-2 text-[12px] text-gray-500">({liste.length})</span>
          </h2>
          <p className="text-[11.5px] text-gray-500 mt-0.5">
            Onaylandı ama henüz kalıba girmedi — tasarım ve varyasyon düzeltilebilir
          </p>
        </div>
        <span className="text-gray-500 text-sm">{acik ? '▲' : '▼'}</span>
      </button>

      {acik && (
        <div className="mt-4 space-y-4">
          {liste.map((o) => (
            <div key={o.id} className="rounded-xl border border-brand-border bg-brand-input/20 p-3.5">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <div className="text-[13px] text-gray-200">
                  #{o.order_number}
                  <span className="text-gray-500"> · {o.bayi}</span>
                  {o.kanal && <span className="text-gray-600"> · {kanalAdi(o.kanal)}</span>}
                </div>
                <button onClick={() => iptalSor(o)} disabled={bekle === o.id}
                        className="text-[11.5px] px-2.5 py-1 rounded-lg border
                                   border-red-500/30 text-red-300 hover:bg-red-500/10
                                   disabled:opacity-40">
                  Siparişi iptal et
                </button>
              </div>
              {o.kismen_kalipta && (
                <p className="text-[11px] text-amber-400/90 mt-1">
                  Bu siparişin bir kısmı kalıba girdi — yalnız aşağıdakiler düzeltilebilir.
                </p>
              )}

              <div className="mt-3 space-y-2.5">
                {o.kalemler.map((k) => (
                  <div key={k.id} className="flex items-center gap-3 flex-wrap">
                    <button type="button" onClick={() => k.gorsel && setBuyutec(k)}
                            disabled={!k.gorsel} title={k.gorsel ? 'Büyüt' : ''}
                            className="w-11 h-11 rounded-lg overflow-hidden border border-white/8
                                       bg-white/[0.03] grid place-items-center shrink-0
                                       enabled:hover:border-accent/60 enabled:cursor-zoom-in
                                       transition-colors">
                      {k.gorsel
                        ? <img src={k.gorsel} alt="" className="w-full h-full object-cover" />
                        : <span className="text-[10px] text-gray-600">—</span>}
                    </button>
                    <div className="min-w-0 flex-1">
                      <div className="text-[13px] text-gray-200">{k.model || '—'}</div>
                      <div className="text-[11.5px] text-gray-500 flex items-center gap-2 flex-wrap">
                        <span>{k.tasarim_kodu || '—'} · {k.adet} adet</span>
                        <button type="button" onClick={() => setSecici({ order: o, kalem: k })}
                                className="text-accent hover:brightness-125 transition">
                          ⇄ Tasarım değiştir
                        </button>
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5 flex-wrap">
                      {VARYASYONLAR.map((v) => {
                        const aktif = (k.varyasyon || '') === v
                        return (
                          <button key={v} disabled={bekle === k.id}
                                  onClick={() => duzelt(o, k, { varyasyon: v },
                                    () => `${k.model || 'Ürün'} → ${v}`)}
                                  className={`text-[11.5px] px-2.5 py-1 rounded-full border
                                              transition-all disabled:opacity-40 ${aktif
                                    ? 'border-accent/50 bg-accent/15 text-white'
                                    : 'border-brand-border text-gray-500 hover:text-gray-300'}`}>
                            {v}
                          </button>
                        )
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      <GorselBuyutec key={buyutec?.id || 'yok'} acik={!!buyutec}
                     kapat={() => setBuyutec(null)}
                     kaynak={buyutec?.dosya || buyutec?.gorsel}
                     tasarimId={buyutec?.tasarim_id} format={buyutec?.format}
                     baslik={buyutec ? `${buyutec.tasarim_kodu || ''} · ${buyutec.model || ''}` : ''} />

      {secici && (
        <TasarimSecici storeId={secici.order.store_id} mevcutId={secici.kalem.tasarim_id}
                       onKapat={() => setSecici(null)}
                       onSec={(t) => {
                         const { order, kalem } = secici
                         setSecici(null)
                         duzelt(order, kalem, { design_id: t.id },
                           (r) => `Tasarım: ${r.tasarim_kodu}`
                             + (r.eski_bosta ? ` · ${r.eski_tasarim_kodu} artık kullanılmıyor` : ''))
                       }} />
      )}

      {iptalHedef && (
        <IptalOnayi hedef={iptalHedef} bekle={bekle === iptalHedef.order.id}
                    kapat={() => setIptalHedef(null)} onay={iptalEt} />
      )}
    </div>
  )
}

/** İptal onayı — ne olacağını (özellikle iade durumunu) ÖNCE söyler. */
function IptalOnayi({ hedef, bekle, kapat, onay }) {
  const [sebep, setSebep] = useState('')
  const { order, onizleme } = hedef
  return (
    <div className="fixed inset-0 z-[120] grid place-items-center p-4"
         style={{ background: 'rgb(6 4 12 / 0.86)' }}
         onMouseDown={(e) => e.target === e.currentTarget && kapat()}>
      <div className="rounded-2xl w-full max-w-sm p-5 border border-white/10"
           style={{ background: 'rgb(23 16 43)' }}>
        <h3 className="text-[15px] font-semibold text-white mb-1">
          #{order.order_number} iptal edilsin mi?
        </h3>
        <p className={`text-[12.5px] mb-3 ${onizleme.iade_edilecek
          ? 'text-gray-300' : 'text-amber-300'}`}>
          {onizleme.mesaj}
        </p>
        {onizleme.etkilenecek_kalip > 0 && (
          <p className="text-[11.5px] text-amber-300/90 mb-3">
            {onizleme.etkilenecek_kalip} kalıp etkilenecek.
          </p>
        )}
        <input value={sebep} onChange={(e) => setSebep(e.target.value)} maxLength={120}
               placeholder="Sebep (bayiye gösterilir)"
               className="input w-full mb-3 !text-[13px]" />
        <div className="flex gap-2">
          <button onClick={kapat}
                  className="flex-1 px-3 py-2 rounded-lg border border-white/15
                             text-[13px] text-gray-300 hover:bg-white/10">
            Vazgeç
          </button>
          <button onClick={() => onay(sebep)} disabled={bekle}
                  className="flex-1 px-3 py-2 rounded-lg bg-red-500/15 border border-red-500/40
                             text-[13px] text-red-200 hover:bg-red-500/25 disabled:opacity-40">
            {bekle ? 'İptal ediliyor…' : 'Evet, iptal et'}
          </button>
        </div>
      </div>
    </div>
  )
}
