/**
 * Dosya Aktarımı — cihazlar arası geçici dosya taşıma (yalnız yönetim paneli).
 *
 * Mac'ten Windows'a, telefondan panele bir dosyayı hızlıca taşımak için.
 * KALICI DEPO DEĞİL: her dosya 24 saat sonra kendiliğinden silinir; ekran
 * bunu kalan süreyle sürekli söyler ki kimse buraya arşiv yapmasın.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { api, fetchYetkili, yetkiBasligi } from '../lib/api'
import { mutlak } from '../lib/taban'
import { useToast } from '../components/Toast'
import EmptyState from '../components/EmptyState'

function kalanSure(iso) {
  if (!iso) return '—'
  const fark = new Date(iso) - Date.now()
  if (fark <= 0) return 'süresi doldu'
  const saat = Math.floor(fark / 3600000)
  const dakika = Math.floor((fark % 3600000) / 60000)
  return saat > 0 ? `${saat} sa ${dakika} dk` : `${dakika} dk`
}

function zaman(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('tr-TR', {
    day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
  })
}

export default function AktarimPage() {
  const [veri, setVeri] = useState(null)
  const [yukleniyor, setYukleniyor] = useState(null)   // {ad, yuzde}
  const [suruklu, setSuruklu] = useState(false)
  const [, tazele] = useState(0)                        // kalan süre sayacı
  const dosyaRef = useRef(null)
  const toast = useToast()

  const yukle = useCallback(async () => {
    try { setVeri(await api.get('/api/aktarim')) }
    catch (e) { toast.error(e?.detail || 'Liste alınamadı'); setVeri({ items: [] }) }
  }, [toast])

  useEffect(() => { yukle() }, [yukle])
  // Kalan süre dakikada bir yeniden çizilsin
  useEffect(() => {
    const t = setInterval(() => tazele(n => n + 1), 60000)
    return () => clearInterval(t)
  }, [])

  const gonder = (dosya) => {
    if (!dosya) return
    if (veri?.max_boyut && dosya.size > veri.max_boyut) {
      toast.error(`Dosya çok büyük — en fazla ${veri.max_boyut_yazi}`)
      return
    }
    setYukleniyor({ ad: dosya.name, yuzde: 0 })
    // XHR: fetch yükleme ilerlemesi vermiyor, 250 MB'lık dosyada şart
    const xhr = new XMLHttpRequest()
    xhr.open('POST', mutlak('/api/aktarim'))
    Object.entries(yetkiBasligi()).forEach(([k, v]) => xhr.setRequestHeader(k, v))
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        setYukleniyor({ ad: dosya.name, yuzde: Math.round((e.loaded / e.total) * 100) })
      }
    }
    xhr.onload = () => {
      setYukleniyor(null)
      if (dosyaRef.current) dosyaRef.current.value = ''
      if (xhr.status >= 200 && xhr.status < 300) { toast.success('Yüklendi'); yukle() }
      else {
        let d = `HTTP ${xhr.status}`
        try { d = JSON.parse(xhr.responseText).detail || d } catch { /* json değil */ }
        toast.error(d)
      }
    }
    xhr.onerror = () => { setYukleniyor(null); toast.error('Bağlantı koptu — yükleme yarıda kaldı') }
    const fd = new FormData()
    fd.append('file', dosya)
    xhr.send(fd)
  }

  // İndirme: uç kimlik doğrulaması istiyor, bağlantıyı doğrudan açamayız
  const indir = async (k) => {
    try {
      const r = await fetchYetkili(mutlak(k.indir))
      if (!r.ok) throw new Error(r.status === 410 ? 'Dosyanın süresi dolmuş' : 'İndirilemedi')
      const url = URL.createObjectURL(await r.blob())
      const a = document.createElement('a')
      a.href = url; a.download = k.dosya_adi
      document.body.appendChild(a); a.click(); a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 30000)
    } catch (e) { toast.error(e.message || 'İndirilemedi') }
  }

  const sil = async (k) => {
    if (!confirm(`"${k.dosya_adi}" silinsin mi?`)) return
    try { await api.del(`/api/aktarim/${k.id}`); yukle() }
    catch (e) { toast.error(e?.detail || 'Silinemedi') }
  }

  const birak = (e) => {
    e.preventDefault(); setSuruklu(false)
    gonder(e.dataTransfer?.files?.[0])
  }

  return (
    <div className="animate-fadein mx-auto max-w-3xl">
      <div className="mb-4">
        <h1 className="text-2xl font-semibold text-gray-100">📤 Dosya Aktarımı</h1>
        <p className="text-sm text-gray-500 mt-1">
          Cihazlar arası geçici taşıma. Yüklenen dosya <b>{veri?.saklama_saat || 24} saat</b> sonra
          kendiliğinden silinir — burası arşiv değil.
        </p>
      </div>

      <div
        onDragOver={(e) => { e.preventDefault(); setSuruklu(true) }}
        onDragLeave={() => setSuruklu(false)}
        onDrop={birak}
        className={`card border-2 border-dashed text-center py-10 transition-colors ${
          suruklu ? 'border-accent bg-accent/10' : 'border-brand-border'}`}>
        <div className="text-3xl mb-2">⬆️</div>
        <div className="text-sm text-gray-200">Dosyayı buraya sürükle</div>
        <div className="text-xs text-gray-500 mt-1">
          ya da <label htmlFor="aktarim-dosya" className="text-accent cursor-pointer hover:underline">bilgisayardan seç</label>
          {veri?.max_boyut_yazi ? ` · en fazla ${veri.max_boyut_yazi}` : ''}
        </div>
        <input id="aktarim-dosya" ref={dosyaRef} type="file" className="hidden"
               onChange={(e) => gonder(e.target.files?.[0])} />

        {yukleniyor && (
          <div className="mt-4 mx-auto max-w-sm">
            <div className="text-xs text-gray-400 mb-1 truncate">{yukleniyor.ad}</div>
            <div className="h-2 rounded-full bg-brand-input overflow-hidden">
              <div className="h-full bg-accent transition-all" style={{ width: `${yukleniyor.yuzde}%` }} />
            </div>
            <div className="text-[11px] text-gray-500 mt-1">%{yukleniyor.yuzde}</div>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between mt-5 mb-2">
        <h2 className="text-sm font-medium text-gray-300">Yüklenen dosyalar</h2>
        {veri?.items?.length > 0 && (
          <span className="text-[11px] text-gray-500">toplam {veri.toplam_boyut_yazi}</span>
        )}
      </div>

      {veri === null ? (
        <div className="card text-sm text-gray-500 py-6 text-center">Yükleniyor…</div>
      ) : veri.items.length === 0 ? (
        <EmptyState dar ikon="📭" baslik="Dosya yok"
          aciklama="Yüklediğin dosyalar burada listelenir ve 24 saat sonra silinir." />
      ) : (
        <div className="card !p-0 overflow-hidden">
          {veri.items.map((k) => (
            <div key={k.id} className="flex items-center gap-3 px-3 py-2.5 border-b border-brand-border/60 last:border-0">
              <div className="min-w-0 flex-1">
                <div className="text-sm text-gray-100 truncate">{k.dosya_adi}</div>
                <div className="text-[11px] text-gray-500">
                  {k.boyut_yazi} · {zaman(k.created_at)}
                  {k.yukleyen ? ` · ${k.yukleyen}` : ''}
                  <span className="text-amber-400/80"> · {kalanSure(k.expires_at)} sonra silinir</span>
                </div>
              </div>
              <button onClick={() => indir(k)} className="btn-secondary !text-xs !py-1.5 shrink-0">⬇️ İndir</button>
              <button onClick={() => sil(k)}
                className="text-xs px-2 py-1.5 rounded-lg text-red-300/90 hover:bg-red-500/10 shrink-0">Sil</button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
