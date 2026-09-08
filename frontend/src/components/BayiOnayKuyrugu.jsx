/**
 * Yonetim tarafi: bayi portalinden gelen siparislerin ONAY kuyrugu.
 *
 * Bayi siparis acinca 'bayii_onay_bekliyor' ile bekler; kaliba GIRMEZ ve cari
 * borc ISLENMEZ. Burada varyasyon secilip onaylandiginda borc yazilir ve
 * siparis uretime akar.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useToast } from './Toast'
import { kanalAdi } from '../lib/bayii'
import GorselBuyutec from './GorselBuyutec'

// placement_rules.normalize_variation'in urettigi degerler
export const VARYASYONLAR = ['SİYAH', 'BEYAZ', 'ŞEFFAF', 'PARLAK', 'MAGSAFE']

export default function BayiOnayKuyrugu({ onOnaylandi }) {
  const [liste, setListe] = useState([])
  const [yuklendi, setYuklendi] = useState(false)
  const [secim, setSecim] = useState({})     // {line_item_id: varyasyon}
  const [kargo, setKargo] = useState({})     // {order_id: bool}
  const [bekle, setBekle] = useState('')
  const [yukleniyor, setYukleniyor] = useState('')
  const pdfRef = useRef(null)
  const hedefRef = useRef(null)
  // Tasarim secici: bayi ayni gorseli her sipariste yeniden yukluyor ve
  // sunucuda ayni dosyanin kopyalari birikiyor. Onaylarken katalogdaki
  // tasarim secilirse yeni dosya hic olusmaz.
  const [secici, setSecici] = useState(null)   // {order, kalem}
  const [buyutec, setBuyutec] = useState(null) // tiklanan kalem — ayni sayfada buyur
  const toast = useToast()
  const navigate = useNavigate()

  const yukle = useCallback(async () => {
    try {
      const d = await api.get('/api/dealers/portal/onay-bekleyen')
      const items = Array.isArray(d) ? d : []
      setListe(items)
      // Tik bayinin ayarindan: kargo ucreti 0 ise yansitilmasin.
      setKargo((c) => {
        const y = { ...c }
        for (const o of items) if (y[o.id] === undefined) y[o.id] = Number(o.kargo_ucreti) > 0
        return y
      })
    } catch { /* yetkisiz/hata: kuyruk gizli kalir */ }
    finally { setYuklendi(true) }
  }, [])
  useEffect(() => { yukle() }, [yukle])

  // JPG olarak yuklenen tasarim baskiya uygun degil. Yonetici disarida PDF
  // uretip buradan yukler; /print-file gorseli de kabul edip CMYK PDF'e cevirir.
  const pdfSec = (kalem) => { hedefRef.current = kalem; pdfRef.current?.click() }

  const tasarimSec = async (tasarim) => {
    const { order, kalem } = secici || {}
    if (!order || !kalem) return
    try {
      const r = await api.patch(
        `/api/dealers/portal/siparis/${order.id}/kalem/${kalem.id}`,
        { design_id: tasarim.id })
      setSecici(null)
      if (r.degismedi) { toast.info('Zaten bu tasarım seçili'); return }
      toast.success(
        `Tasarım değiştirildi: ${r.tasarim_kodu}`
        + (r.eski_bosta ? ` · ${r.eski_tasarim_kodu} artık kullanılmıyor` : ''))
      await yukle()
    } catch (e) { toast.error(e.detail || 'Değiştirilemedi') }
  }

  const pdfYukle = async (dosya) => {
    const kalem = hedefRef.current
    if (!dosya || !kalem?.tasarim_id) return
    setYukleniyor(kalem.id)
    try {
      const fd = new FormData()
      fd.append('file', dosya)
      await api.postForm(`/api/designs/${kalem.tasarim_id}/print-file`, fd)
      toast.success('Baskı dosyası güncellendi')
      await yukle()
    } catch (e) { toast.error(e.detail || 'Yüklenemedi') }
    finally { setYukleniyor(''); hedefRef.current = null; if (pdfRef.current) pdfRef.current.value = '' }
  }

  const onayla = async (o) => {
    setBekle(o.id)
    try {
      const varyasyonlar = {}
      for (const k of o.kalemler) varyasyonlar[k.id] = secim[k.id] || 'SİYAH'
      const r = await api.post(`/api/dealers/portal/onay-bekleyen/${o.id}`, {
        varyasyonlar, apply_shipping: !!kargo[o.id],
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
      <input ref={pdfRef} type="file" accept=".pdf,.png,.jpg,.jpeg" hidden
             onChange={(e) => pdfYukle(e.target.files?.[0])} />
      <GorselBuyutec key={buyutec?.id || 'yok'}
                     acik={!!buyutec} kapat={() => setBuyutec(null)}
                     kaynak={buyutec?.dosya || buyutec?.gorsel}
                     tasarimId={buyutec?.tasarim_id} format={buyutec?.format}
                     baslik={buyutec ? `${buyutec.tasarim_kodu || ''} · ${buyutec.model || ''}` : ''} />
      {secici && (
        <TasarimSecici storeId={secici.order.store_id}
                       mevcutId={secici.kalem.tasarim_id}
                       onSec={tasarimSec} onKapat={() => setSecici(null)} />
      )}
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
                  <div className="flex items-center gap-1.5 shrink-0">
                    <button type="button" onClick={() => k.gorsel && setBuyutec(k)}
                            disabled={!k.gorsel} title={k.gorsel ? 'Tasarımı büyüt' : ''}
                            className="w-11 h-11 rounded-lg overflow-hidden border border-white/8
                                       bg-white/[0.03] grid place-items-center
                                       enabled:hover:border-accent/60 enabled:cursor-zoom-in
                                       transition-colors">
                      {k.gorsel
                        ? <img src={k.gorsel} alt="" className="w-full h-full object-cover" />
                        : <span className="text-[10px] text-gray-600">—</span>}
                    </button>
                    {k.onizleme && (
                      <button type="button" title="Bayinin yüklediği önizleme — BASKIYA GİRMEZ"
                              onClick={() => setBuyutec({
                                ...k, gorsel: k.onizleme, dosya: k.onizleme,
                                format: 'jpg', tasarim_id: null,
                                tasarim_kodu: `${k.tasarim_kodu || ''} · önizleme` })}
                              className="w-11 h-11 rounded-lg overflow-hidden border border-dashed
                                         border-emerald-500/40 bg-emerald-500/5 relative
                                         hover:border-emerald-400/70 cursor-zoom-in transition-colors">
                        <img src={k.onizleme} alt="" className="w-full h-full object-cover" />
                        <span className="absolute inset-x-0 bottom-0 text-[7px] leading-[10px]
                                         text-center bg-black/70 text-emerald-300">
                          ÖNİZLEME
                        </span>
                      </button>
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-[13px] text-gray-200 flex items-center gap-2 flex-wrap">
                      {k.model || '—'}
                      {k.format && k.format !== 'pdf' && (
                        <span className="text-[10.5px] px-1.5 py-0.5 rounded-full uppercase
                                         bg-amber-500/15 text-amber-300 border border-amber-500/30">
                          {k.format} · PDF gerekli
                        </span>
                      )}
                    </div>
                    <div className="text-[11.5px] text-gray-500 flex items-center gap-2 flex-wrap">
                      <span>{k.tasarim_kodu || '—'} · {k.adet} adet</span>
                      <button type="button" onClick={() => setSecici({ order: o, kalem: k })}
                              className="text-accent hover:brightness-125 transition">
                        ⇄ Tasarım değiştir
                      </button>
                    </div>
                    {k.format && k.format !== 'pdf' && (
                      <div className="flex items-center gap-2 mt-1.5">
                        {k.dosya && (
                          <a href={k.dosya} download
                             className="text-[11.5px] text-accent hover:brightness-125 transition">
                            ⬇ {k.format.toUpperCase()} indir
                          </a>
                        )}
                        <span className="text-gray-700">·</span>
                        <button type="button" onClick={() => pdfSec(k)}
                                disabled={yukleniyor === k.id}
                                className="text-[11.5px] text-accent hover:brightness-125 transition">
                          {yukleniyor === k.id ? 'Yükleniyor…' : '⬆ PDF yükle'}
                        </button>
                      </div>
                    )}
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
                <input type="checkbox" checked={!!kargo[o.id]}
                       onChange={(e) => setKargo((c) => ({ ...c, [o.id]: e.target.checked }))}
                       className="accent-[rgb(var(--accent-rgb))]" />
                Kargo ücretini yansıt
                {Number(o.kargo_ucreti) > 0 && (
                  <span className="text-gray-600">
                    ({Number(o.kargo_ucreti).toLocaleString('tr-TR',
                      { minimumFractionDigits: 2 })} ₺)
                  </span>
                )}
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


/** Katalogdan tasarim sec — kayitli tasarimi kullan, yeni dosya olusturma. */
export function TasarimSecici({ storeId, mevcutId, onSec, onKapat }) {
  const [q, setQ] = useState('')
  const [liste, setListe] = useState([])
  const [yukleniyor, setYukleniyor] = useState(!!storeId)

  useEffect(() => {
    if (!storeId) return
    let iptal = false
    const t = setTimeout(async () => {
      if (!iptal) setYukleniyor(true)
      try {
        const r = await api.get(`/api/designs?store_id=${storeId}`
          + `&per_page=60${q.trim() ? `&search=${encodeURIComponent(q.trim())}` : ''}`)
        if (!iptal) setListe(r.items || [])
      } catch { if (!iptal) setListe([]) }
      finally { if (!iptal) setYukleniyor(false) }
    }, 250)
    return () => { iptal = true; clearTimeout(t) }
  }, [storeId, q])

  // Ust bilesenin animasyonu yiginlama baglami yaratiyor; modal ICINDE kalmasin
  return createPortal((
    <div className="fixed inset-0 z-[70] grid place-items-center p-4 animate-fadein"
         style={{ background: 'rgb(6 4 12 / 0.86)' }} onClick={onKapat}>
      <div className="rounded-2xl w-full max-w-3xl max-h-[86vh] flex flex-col p-5
                      border border-white/10 animate-popin"
           style={{ background: 'rgb(23 16 43)' }}
           onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="text-[15px] font-semibold text-white">Kayıtlı tasarımlar</h3>
            <p className="text-[11px] text-gray-500">
              Var olanı seçmek yeni dosya oluşturmaz — sunucuda yer kaplamaz.
            </p>
          </div>
          <button onClick={onKapat}
                  className="text-gray-500 hover:text-gray-200 text-xl leading-none">×</button>
        </div>
        <input value={q} onChange={(e) => setQ(e.target.value)} autoFocus
               placeholder="Kod veya ad ara…" className="input w-full mb-3" />
        {yukleniyor ? (
          <div className="py-10 text-center text-[13px] text-gray-500">Yükleniyor…</div>
        ) : liste.length === 0 ? (
          <div className="py-10 text-center text-[13px] text-gray-500">
            {q ? 'Eşleşen tasarım yok' : 'Bu mağazada kayıtlı tasarım yok'}
          </div>
        ) : (
          <div className="overflow-y-auto -mx-1 px-1">
            <div className="grid gap-3 py-1 content-start
                            [grid-template-columns:repeat(auto-fill,minmax(min(100%,150px),1fr))]">
              {liste.map((t) => (
                <button key={t.id} type="button" onClick={() => onSec(t)}
                        className={`block w-full text-left rounded-xl overflow-hidden border
                                    transition-colors ${t.id === mevcutId
                                      ? 'border-accent ring-2 ring-accent/30'
                                      : 'border-white/10 hover:border-white/25'}`}>
                  <div className="relative w-full bg-white/[0.04]" style={{ paddingTop: '100%' }}>
                    {t.thumbnail_url
                      ? <img src={t.thumbnail_url} alt=""
                             className="absolute inset-0 w-full h-full object-cover" />
                      : <span className="absolute inset-0 grid place-items-center
                                         text-[11px] text-gray-600">
                          {(t.file_format || '?').toUpperCase()}
                        </span>}
                  </div>
                  <div className="px-2 py-1.5">
                    <div className="text-[11.5px] text-gray-300 truncate" title={t.code}>
                      {t.code}
                    </div>
                    <div className="text-[10px] text-gray-500 truncate">
                      {(t.file_format || '').toUpperCase()}{t.name ? ` · ${t.name}` : ''}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  ), document.body)
}
