/**
 * Bayi sohbeti — YÖNETİM tarafı.
 *
 * Sol: bayi listesi (acil olan ve okunmamışı olan üstte). Sağ: konuşma.
 * Bayi tarafı pages/bayii/BayiSohbetPage.jsx; ikisi de aynı uçları kullanır.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, fetchYetkili } from '../lib/api'
import { mutlak } from '../lib/taban'
import { useToast } from '../components/Toast'
import EmptyState from '../components/EmptyState'
import { Avatar, Balon, GunAyraci, SiparisSecici, gunlereBol } from '../components/SohbetParcalari'

const YENILE_MS = 20000

function zaman(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('tr-TR', {
    day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
  })
}

export default function BayiSohbetPage() {
  const [liste, setListe] = useState(null)
  const [secili, setSecili] = useState(null)      // dealer_id
  const [veri, setVeri] = useState(null)          // {mesajlar, bayi}
  const [metin, setMetin] = useState('')
  const [gorsel, setGorsel] = useState(null)
  const [gonderiliyor, setGonderiliyor] = useState(false)
  const [siparisler, setSiparisler] = useState([])
  const [siparisId, setSiparisId] = useState('')
  const [params, setParams] = useSearchParams()
  const toast = useToast()
  const navigate = useNavigate()
  const altRef = useRef(null)
  const dosyaRef = useRef(null)

  const listeyiYukle = useCallback(async () => {
    try { setListe((await api.get('/api/bayi-sohbet')).items || []) }
    catch { setListe([]) }
  }, [])
  useEffect(() => { listeyiYukle() }, [listeyiYukle])
  useEffect(() => {
    const t = setInterval(listeyiYukle, YENILE_MS)
    return () => clearInterval(t)
  }, [listeyiYukle])

  // Bildirimden gelindiyse (?bayi=...) o sohbeti aç
  useEffect(() => {
    const b = params.get('bayi')
    if (b) setSecili(b)
  }, [params])

  const sohbetiYukle = useCallback(async (id, sessiz = false) => {
    if (!id) return
    try {
      const d = await api.get(`/api/bayi-sohbet/${id}`)
      setVeri(d)
      if ((d.sohbet?.okunmamis_atolye || 0) > 0) {
        await api.post(`/api/bayi-sohbet/${id}/okundu`, {})
        listeyiYukle()
      }
    } catch (e) { if (!sessiz) toast.error(e?.detail || 'Sohbet açılamadı') }
  }, [listeyiYukle, toast])

  useEffect(() => { if (secili) sohbetiYukle(secili) }, [secili, sohbetiYukle])
  // Yanıtta sipariş eki: bu bayinin siparişleri (numara bilmeye gerek yok)
  useEffect(() => {
    if (!secili) { setSiparisler([]); return }
    setSiparisId('')
    api.get(`/api/bayi-sohbet/${secili}/siparisler`)
      .then(d => setSiparisler(d.items || []))
      .catch(() => setSiparisler([]))
  }, [secili])
  useEffect(() => {
    if (!secili) return
    const t = setInterval(() => sohbetiYukle(secili, true), YENILE_MS)
    return () => clearInterval(t)
  }, [secili, sohbetiYukle])
  useEffect(() => { altRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [veri?.mesajlar?.length])

  const gorselSec = async (dosya) => {
    if (!dosya) return
    setGorsel({ yukleniyor: true })
    try {
      const fd = new FormData()
      fd.append('file', dosya)
      const r = await fetchYetkili(mutlak('/api/bayi-sohbet/gorsel/yukle'), { method: 'POST', body: fd })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail || 'Görsel yüklenemedi')
      setGorsel({ url: d.url })
    } catch (e) { setGorsel(null); toast.error(e.message || 'Görsel yüklenemedi') }
  }

  const gonder = async () => {
    if (!secili || gonderiliyor) return
    if (!metin.trim() && !gorsel?.url) return
    setGonderiliyor(true)
    try {
      await api.post(`/api/bayi-sohbet/${secili}`, {
        body: metin.trim() || null, image_url: gorsel?.url || null,
        order_id: siparisId || null,
      })
      setMetin(''); setGorsel(null); setSiparisId('')
      if (dosyaRef.current) dosyaRef.current.value = ''
      await sohbetiYukle(secili, true)
      listeyiYukle()
    } catch (e) { toast.error(e?.detail || 'Gönderilemedi') }
    finally { setGonderiliyor(false) }
  }

  const sec = (id) => { setSecili(id); setParams(id ? { bayi: id } : {}, { replace: true }) }

  return (
    <div className="animate-fadein">
      <div className="mb-4">
        <h1 className="text-2xl font-semibold text-gray-100">💬 Bayi Sohbeti</h1>
        <p className="text-sm text-gray-500 mt-1">
          Bayilerle yazışma — görsel, sipariş eki ve aciliyet. Acil mesajlar en üstte.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Bayi listesi */}
        <div className="card !p-0 overflow-hidden lg:max-h-[72vh] overflow-y-auto">
          {liste === null ? (
            <div className="p-6 text-sm text-gray-500">Yükleniyor…</div>
          ) : liste.length === 0 ? (
            <EmptyState dar ikon="🤝" baslik="Bayi yok" aciklama="Önce bayi ekle." />
          ) : liste.map(b => (
            <button key={b.dealer_id} onClick={() => sec(b.dealer_id)}
              className={`w-full text-left px-3 py-2.5 border-b border-brand-border/60 transition-colors ${
                secili === b.dealer_id ? 'bg-accent/10' : 'hover:bg-brand-input/50'}`}>
              <div className="flex items-center gap-2">
                <Avatar url={b.logo_url} ad={b.dealer_ad} boyut={22} />
                <span className="text-sm text-gray-100 truncate flex-1">{b.dealer_ad}</span>
                {b.acil_bekliyor && (
                  <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded bg-red-500/20 text-red-300">ACİL</span>
                )}
                {b.okunmamis_atolye > 0 && (
                  <span className="min-w-[18px] h-[18px] px-1 rounded-full bg-accent text-[10px] font-semibold
                                   leading-[18px] text-center text-white">{b.okunmamis_atolye}</span>
                )}
              </div>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-[11px] text-gray-500 truncate flex-1">
                  {b.son_gonderen === 'atolye' ? 'Sen: ' : ''}{b.son_mesaj_ozet || 'Henüz mesaj yok'}
                </span>
                <span className="text-[10px] text-gray-600 shrink-0">{zaman(b.son_mesaj_at)}</span>
              </div>
            </button>
          ))}
        </div>

        {/* Konuşma */}
        <div className="lg:col-span-2 card !p-0 overflow-hidden flex flex-col" style={{ minHeight: '55vh' }}>
          {!secili ? (
            <div className="flex-1 grid place-items-center text-sm text-gray-500 p-10">
              Soldan bir bayi seç.
            </div>
          ) : (
            <>
              <div className="px-4 py-2.5 border-b border-brand-border flex items-center gap-2">
                <Avatar url={veri?.sohbet?.logo_url} ad={veri?.bayi?.ad} boyut={26} />
                <span className="text-sm font-medium text-gray-100">{veri?.bayi?.ad || '—'}</span>
                {veri?.bayi?.telefon && (
                  <a href={`https://wa.me/9${String(veri.bayi.telefon).replace(/\D/g, '')}`}
                     target="_blank" rel="noreferrer"
                     className="text-[11px] text-emerald-300/90 hover:underline">WhatsApp</a>
                )}
                <button onClick={() => navigate(`/bayiler?bayi=${secili}`)}
                        className="ml-auto text-[11px] text-gray-400 hover:text-gray-200">Bayi kartı →</button>
              </div>

              <div className="flex-1 overflow-y-auto p-4 space-y-3" style={{ maxHeight: '55vh' }}>
                {gunlereBol(veri?.mesajlar || []).map(grup => (
                  <div key={grup.gun} className="space-y-3">
                    <GunAyraci gun={grup.gun} />
                    {grup.mesajlar.map(m => (
                      <Balon key={m.id} m={m} benimMi={m.gonderen === 'atolye'}
                             ad={m.gonderen === 'atolye' ? 'Atölye' : (veri?.bayi?.ad || 'Bayi')}
                             onSiparis={(id) => navigate(`/orders/${id}`)} />
                    ))}
                  </div>
                ))}
                {veri && veri.mesajlar.length === 0 && (
                  <div className="text-center text-sm text-gray-500 py-10">Henüz mesaj yok.</div>
                )}
                <div ref={altRef} />
              </div>

              <div className="border-t border-brand-border p-3 space-y-2 bg-brand-input/20">
                {gorsel && (
                  <div className="text-[11px] inline-flex items-center gap-1.5 px-2 py-1 rounded-lg bg-brand-input border border-brand-border">
                    {gorsel.yukleniyor ? 'Görsel yükleniyor…' : '📎 Görsel eklendi'}
                    {!gorsel.yukleniyor && (
                      <button onClick={() => { setGorsel(null); if (dosyaRef.current) dosyaRef.current.value = '' }}
                              className="text-gray-500 hover:text-red-300">✕</button>
                    )}
                  </div>
                )}
                <textarea value={metin} onChange={e => setMetin(e.target.value)} rows={2}
                  onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); gonder() } }}
                  placeholder="Yanıt yaz… (Enter gönderir)"
                  className="input w-full !text-sm resize-none" />
                <div className="flex items-center gap-2">
                  <input ref={dosyaRef} type="file" accept="image/jpeg,image/png,image/webp"
                         onChange={e => gorselSec(e.target.files?.[0])} className="hidden" id="yonetim-sohbet-gorsel" />
                  <label htmlFor="yonetim-sohbet-gorsel"
                         className="btn-secondary !text-xs !py-1.5 cursor-pointer">📎 Görsel</label>
                  <SiparisSecici siparisler={siparisler} secili={siparisId} onSec={setSiparisId} />
                  <button onClick={gonder} disabled={gonderiliyor || (!metin.trim() && !gorsel?.url)}
                          className="btn-primary !text-sm ml-auto disabled:opacity-40">
                    {gonderiliyor ? 'Gönderiliyor…' : 'Gönder'}
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
