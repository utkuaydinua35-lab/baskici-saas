/**
 * Bayi ↔ atölye sohbeti (bayi tarafı).
 *
 * Yazarken üç ek var: GÖRSEL (fotoğrafla anlatmak kelimeden hızlı),
 * SİPARİŞ EKİ ("şu siparişten bahsediyorum" — atölye tek tıkla açar) ve
 * ACİLİYET (acil mesaj yöneticinin telefonuna anında düşer).
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { api, fetchYetkili } from '../../lib/api'
import { mutlak } from '../../lib/taban'
import { Hata, Iskelet } from '../../components/BayiParcalar'
import { Balon, GunAyraci, SiparisSecici, gunlereBol } from '../../components/SohbetParcalari'

const ACILIYETLER = [
  { deger: 'normal', ad: 'Normal', sinif: 'bg-brand-input text-gray-300 border-brand-border' },
  { deger: 'acil', ad: 'Acil', sinif: 'bg-amber-500/15 text-amber-300 border-amber-500/30' },
  { deger: 'cok_acil', ad: 'Çok acil', sinif: 'bg-red-500/15 text-red-300 border-red-500/30' },
]
const YENILE_MS = 20000      // açık ekranda yeni mesajlar kendiliğinden gelsin

export default function BayiSohbetPage() {
  const [mesajlar, setMesajlar] = useState(null)
  const [hata, setHata] = useState('')
  const [metin, setMetin] = useState('')
  const [aciliyet, setAciliyet] = useState('normal')
  const [gorsel, setGorsel] = useState(null)      // {url, yukleniyor}
  const [siparisler, setSiparisler] = useState([])
  const [siparisId, setSiparisId] = useState('')
  const [gonderiliyor, setGonderiliyor] = useState(false)
  const altRef = useRef(null)
  const dosyaRef = useRef(null)

  const yukle = useCallback(async (sessiz = false) => {
    if (!sessiz) setHata('')
    try {
      const d = await api.get('/api/bayii/sohbet')
      setMesajlar(d.mesajlar || [])
      if ((d.sohbet?.okunmamis_bayi || 0) > 0) api.post('/api/bayii/sohbet/okundu', {}).catch(() => {})
    } catch (e) { if (!sessiz) setHata(e.detail || 'Sohbet yüklenemedi') }
  }, [])

  useEffect(() => { yukle() }, [yukle])
  useEffect(() => {
    const t = setInterval(() => yukle(true), YENILE_MS)
    return () => clearInterval(t)
  }, [yukle])
  useEffect(() => {
    api.get('/api/bayii/siparisler').then(d => setSiparisler(d.items || [])).catch(() => {})
  }, [])
  useEffect(() => { altRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [mesajlar?.length])

  const gorselSec = async (dosya) => {
    if (!dosya) return
    setGorsel({ yukleniyor: true })
    try {
      const fd = new FormData()
      fd.append('file', dosya)
      const r = await fetchYetkili(mutlak('/api/bayii/sohbet/gorsel'), { method: 'POST', body: fd })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail || 'Görsel yüklenemedi')
      setGorsel({ url: d.url })
    } catch (e) {
      setGorsel(null)
      setHata(e.message || 'Görsel yüklenemedi')
    }
  }

  const gonder = async () => {
    if (gonderiliyor) return
    if (!metin.trim() && !gorsel?.url) return
    setGonderiliyor(true)
    try {
      await api.post('/api/bayii/sohbet', {
        body: metin.trim() || null,
        image_url: gorsel?.url || null,
        order_id: siparisId || null,
        aciliyet,
      })
      setMetin(''); setGorsel(null); setSiparisId(''); setAciliyet('normal')
      if (dosyaRef.current) dosyaRef.current.value = ''
      await yukle(true)
    } catch (e) { setHata(e.detail || 'Mesaj gönderilemedi') }
    finally { setGonderiliyor(false) }
  }

  const tusla = (e) => {
    // Enter gönderir, Shift+Enter alt satır — sohbet alışkanlığı
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); gonder() }
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold text-white tracking-tight">Atölyeyle sohbet</h1>
        <p className="text-[13px] text-gray-500 mt-1">
          Soru, sorun ya da acil bir durum — buradan yaz. Görsel ve sipariş ekleyebilirsin.
        </p>
      </div>

      <Hata mesaj={hata} tekrar={() => yukle()} />

      <div className="card !p-0 overflow-hidden flex flex-col" style={{ minHeight: '55vh' }}>
        <div className="flex-1 overflow-y-auto p-4 space-y-3" style={{ maxHeight: '60vh' }}>
          {mesajlar === null ? <Iskelet satir={4} /> : mesajlar.length === 0 ? (
            <div className="text-center text-sm text-gray-500 py-10">
              Henüz mesaj yok — ilk mesajı sen yaz.
            </div>
          ) : gunlereBol(mesajlar).map((grup) => (
            <div key={grup.gun} className="space-y-3">
              <GunAyraci gun={grup.gun} />
              {grup.mesajlar.map((m) => (
                <Balon key={m.id} m={m} benimMi={m.gonderen === 'bayi'}
                       ad={m.gonderen === 'bayi' ? 'Sen' : 'Atölye'} />
              ))}
            </div>
          ))}
          <div ref={altRef} />
        </div>

        {/* Yazma alanı */}
        <div className="border-t border-brand-border p-3 space-y-2 bg-brand-input/20">
          {(gorsel || siparisId) && (
            <div className="flex items-center gap-2 flex-wrap text-[11px]">
              {gorsel && (
                <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg bg-brand-input border border-brand-border">
                  {gorsel.yukleniyor ? 'Görsel yükleniyor…' : '📎 Görsel eklendi'}
                  {!gorsel.yukleniyor && (
                    <button onClick={() => { setGorsel(null); if (dosyaRef.current) dosyaRef.current.value = '' }}
                            className="text-gray-500 hover:text-red-300">✕</button>
                  )}
                </span>
              )}
              {siparisId && (
                <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg bg-accent/10 border border-accent/25 text-accent">
                  🧾 {siparisler.find(s => s.id === siparisId)?.order_number || 'Sipariş'} ekli
                  <button onClick={() => setSiparisId('')} className="text-accent/70 hover:text-red-300">✕</button>
                </span>
              )}
            </div>
          )}

          <textarea
            value={metin} onChange={e => setMetin(e.target.value)} onKeyDown={tusla}
            rows={2} placeholder="Mesajını yaz… (Enter gönderir, Shift+Enter alt satır)"
            className="input w-full !text-sm resize-none" />

          <div className="flex items-center gap-2 flex-wrap">
            <input ref={dosyaRef} type="file" accept="image/jpeg,image/png,image/webp"
                   onChange={e => gorselSec(e.target.files?.[0])} className="hidden" id="sohbet-gorsel" />
            <label htmlFor="sohbet-gorsel"
                   className="btn-secondary !text-xs !py-1.5 cursor-pointer whitespace-nowrap">📎 Görsel</label>

            <SiparisSecici siparisler={siparisler} secili={siparisId} onSec={setSiparisId} />

            <div className="flex gap-1">
              {ACILIYETLER.map(a => (
                <button key={a.deger} type="button" onClick={() => setAciliyet(a.deger)}
                  className={`text-[11px] px-2 py-1 rounded-lg border transition-colors ${
                    aciliyet === a.deger ? a.sinif : 'bg-transparent text-gray-500 border-brand-border hover:text-gray-300'}`}>
                  {a.ad}
                </button>
              ))}
            </div>

            <button onClick={gonder} disabled={gonderiliyor || (!metin.trim() && !gorsel?.url)}
                    className="btn-primary !text-sm ml-auto disabled:opacity-40">
              {gonderiliyor ? 'Gönderiliyor…' : 'Gönder'}
            </button>
          </div>
          {aciliyet !== 'normal' && (
            <p className="text-[10px] text-amber-300/80">
              Acil işaretlenen mesaj atölyeye anında bildirim olarak düşer — gerçekten acil durumlar için kullan.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
