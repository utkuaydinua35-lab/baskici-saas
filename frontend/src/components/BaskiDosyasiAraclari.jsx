/**
 * Bayi siparişi kaleminin BASKI DOSYASI araçları — onay ve düzeltme kuyruğu ortak.
 *
 *  • İndir: bayinin/yöneticinin güncel dosyası
 *  • Yükle / Değiştir: PDF ya da görsel (görsel CMYK PDF'e çevrilir). Hatalı
 *    yüklenen dosya istenildiği kadar değiştirilebilir.
 *  • Geri al: yöneticinin dosyasını kaldırıp bayinin orijinaline döner.
 *
 * Yönetici dosyası AYRI bir tasarım olarak yalnız bu kaleme bağlanır — bayinin
 * aynı tasarımı kullanan diğer siparişleri etkilenmez (bkz. dealers.py).
 */
import { useRef, useState } from 'react'
import { api } from '../lib/api'
import { useToast } from './Toast'

export default function BaskiDosyasiAraclari({ order, kalem, onDegisti }) {
  const input = useRef(null)
  const [bekle, setBekle] = useState('')
  const toast = useToast()
  const yol = `/api/dealers/portal/siparis/${order.id}/kalem/${kalem.id}/baski-dosyasi`
  const pdfDegil = kalem.format && kalem.format !== 'pdf'

  const sec = () => {
    if (kalem.yonetici_dosyasi && !window.confirm(
      `${kalem.tasarim_kodu} baskı dosyası yenisiyle DEĞİŞTİRİLECEK. Devam edilsin mi?`)) return
    input.current?.click()
  }

  const yukle = async (dosya) => {
    if (!dosya) return
    setBekle('yukle')
    try {
      const fd = new FormData()
      fd.append('file', dosya)
      const r = await api.postForm(yol, fd)
      toast.success(r.degistirildi ? 'Baskı dosyası değiştirildi' : `Baskı dosyası yüklendi: ${r.kalem.tasarim_kodu}`)
      onDegisti?.(r.kalem)
    } catch (e) { toast.error(e.detail || 'Yüklenemedi') }
    finally { setBekle(''); if (input.current) input.current.value = '' }
  }

  const geriAl = async () => {
    if (!window.confirm(`Yüklediğin dosya kaldırılacak, bayinin orijinal tasarımına (${kalem.orijinal_kodu}) dönülecek. Emin misin?`)) return
    setBekle('geri')
    try {
      const r = await api.del(yol)
      toast.success(`Bayinin tasarımına dönüldü${r.silindi ? ' · yüklenen dosya silindi' : ''}`)
      onDegisti?.(r.kalem)
    } catch (e) { toast.error(e.detail || 'Geri alınamadı') }
    finally { setBekle('') }
  }

  return (
    <div className="flex items-center gap-2 mt-1.5 flex-wrap text-[11.5px]">
      <input ref={input} type="file" accept=".pdf,image/*" className="hidden"
             onChange={(e) => yukle(e.target.files?.[0])} />
      {kalem.yonetici_dosyasi && (
        <span className="px-1.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
              title={`Bayinin orijinali: ${kalem.orijinal_kodu}`}>
          yönetici dosyası
        </span>
      )}
      {kalem.dosya && (
        <a href={kalem.dosya} download className="text-accent hover:brightness-125 transition">
          ⬇ {(kalem.format || 'dosya').toUpperCase()} indir
        </a>
      )}
      <span className="text-gray-700">·</span>
      <button type="button" onClick={sec} disabled={!!bekle}
              className="text-accent hover:brightness-125 transition disabled:opacity-50">
        {bekle === 'yukle' ? 'Yükleniyor…'
          : kalem.yonetici_dosyasi ? '⬆ Dosyayı değiştir'
          : pdfDegil ? '⬆ PDF yükle' : '⬆ Baskı dosyası yükle'}
      </button>
      {kalem.yonetici_dosyasi && (
        <>
          <span className="text-gray-700">·</span>
          <button type="button" onClick={geriAl} disabled={!!bekle}
                  className="text-gray-400 hover:text-red-300 transition disabled:opacity-50">
            {bekle === 'geri' ? 'Kaldırılıyor…' : '✕ Kaldır (bayinin dosyasına dön)'}
          </button>
        </>
      )}
    </div>
  )
}
