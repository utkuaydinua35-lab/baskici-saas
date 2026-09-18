import { useEffect, useRef, useState } from 'react'
import { api, fetchYetkili } from '../lib/api'
import MoldTabs from '../components/MoldTabs'
import { mutlak } from '../lib/taban'

export default function MoldTemplatePage() {
  const [tpl, setTpl] = useState(null)
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const fileRef = useRef(null)

  const load = async () => {
    try {
      const r = await api.get('/api/templates')
      setTpl(r)
    } catch (e) {
      setError(typeof e?.detail === 'string' ? e.detail : 'Şablon yüklenemedi')
    } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const handleFile = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError('Sadece PDF şablon yükleyebilirsiniz'); return
    }
    setUploading(true); setError(''); setMsg('')
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await fetchYetkili(mutlak(`/api/templates/upload?name=${encodeURIComponent(file.name.replace(/\.pdf$/i, ''))}`), {
        method: 'POST',
        body: fd,
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Yükleme başarısız')
      setTpl(data)
      setMsg(`✓ Şablon yüklendi: ${data.box_count} kutu okundu (${data.cols}×${data.rows})`)
    } catch (e) {
      setError(e.message || 'Yükleme hatası')
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  return (
    <div className="mx-auto max-w-5xl">
      <MoldTabs active="sablon" />
      <div className="mb-5">
        <h1 className="text-2xl font-semibold text-gray-100">🧩 Kalıp Şablonu</h1>
        <p className="text-sm text-gray-500 mt-1">
          Baskı kalıbınızın boş şablon PDF'ini yükleyin. Sistem içindeki kutu konumlarını otomatik okur ve
          tüm kalıp PDF'leri bu düzene basılır.
        </p>
      </div>

      {error && <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 mb-3">{error}</div>}
      {msg && <div className="text-sm text-emerald-300 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2 mb-3">{msg}</div>}

      {/* Yükleme alanı */}
      <div className="card mb-4">
        <h2 className="text-sm font-medium text-gray-200 mb-3">Şablon Yükle</h2>
        <input ref={fileRef} type="file" accept="application/pdf" onChange={handleFile} className="hidden" id="tpl-file" />
        <label htmlFor="tpl-file"
          className="block border-2 border-dashed border-brand-border rounded-xl p-8 text-center cursor-pointer hover:border-accent/50 transition-colors">
          {uploading ? (
            <div className="text-accent">⏳ Yükleniyor ve kutular okunuyor...</div>
          ) : (
            <>
              <div className="text-3xl mb-2">📄</div>
              <div className="text-sm text-gray-300">PDF şablonu seçmek için tıklayın</div>
              <div className="text-[11px] text-gray-500 mt-1">İçinde 27 boş kutu çizili Illustrator çıktısı (90×60 cm önerilir)</div>
            </>
          )}
        </label>
      </div>

      {/* Mevcut şablon durumu */}
      {loading ? (
        <div className="text-gray-500 text-sm text-center py-8">Yükleniyor...</div>
      ) : tpl ? (
        <div className="card">
          <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
            <h2 className="text-sm font-medium text-gray-200">Aktif Şablon</h2>
            <span className="text-[11px] px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300">✓ Aktif</span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <Info label="İsim" value={tpl.name} />
            <Info label="Sayfa" value={`${tpl.page_w_cm} × ${tpl.page_h_cm} cm`} />
            <Info label="Izgara" value={`${tpl.cols} × ${tpl.rows}`} />
            <Info label="Kutu sayısı" value={tpl.box_count} accent />
            <BeyazKAyari tpl={tpl} onKaydedildi={load} />
          </div>
          {/* Kutu önizleme — şablon oranında */}
          <TemplatePreview tpl={tpl} />
        </div>
      ) : (
        <div className="card text-center py-10 text-gray-500">
          <div className="text-3xl mb-2">🧩</div>
          Henüz şablon yüklenmemiş. PDF indirebilmek için bir kalıp şablonu yükleyin.
        </div>
      )}
    </div>
  )
}

function TemplatePreview({ tpl }) {
  if (!tpl.boxes?.length) return null
  const W = tpl.page_w_pt || 1
  const H = tpl.page_h_pt || 1
  // ölçekli SVG — genişlik 100%, oran korunur
  return (
    <div>
      <div className="text-[11px] text-gray-500 mb-2">Kutu yerleşimi önizlemesi (şablondan okunan):</div>
      <div className="bg-brand-bg border border-brand-border rounded-lg overflow-hidden">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: 360 }}>
          <rect x="0" y="0" width={W} height={H} fill="#0a0613" />
          {tpl.boxes.map((b, i) => (
            <g key={i}>
              <rect x={b.x0} y={b.y0} width={b.w} height={b.h}
                fill="none" stroke="#16c784" strokeWidth="3" rx="14" />
              <text x={b.x0 + b.w / 2} y={b.y0 + b.h / 2} fill="#16c784"
                fontSize="60" textAnchor="middle" dominantBaseline="middle">{i + 1}</text>
            </g>
          ))}
        </svg>
      </div>
      <p className="text-[11px] text-gray-600 mt-2">
        Numaralar şablondaki kutu sırasını gösterir (panel ile aynı: üst-sol → alt-sağ).
      </p>
    </div>
  )
}

/** Beyaz altlığın CMYK K kanalı — baskı kurulumu, şablonda saklanır.
 *  Saf 0,0,0,0 baskıda HİÇ mürekkep demek; makinenin beyaz kafayı sürmesi
 *  için küçük bir K gerekiyor. Makine/RIP değişirse buradan ayarlanır. */
function BeyazKAyari({ tpl, onKaydedildi }) {
  const [deger, setDeger] = useState(Math.round((tpl.beyaz_k ?? 0.05) * 100))
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const kaydet = async () => {
    setBusy(true); setMsg('')
    try {
      await api.patch('/api/templates/beyaz-k', { beyaz_k: deger / 100 })
      setMsg('✓ kaydedildi')
      onKaydedildi && onKaydedildi()
    } catch (e) { setMsg(e?.detail || 'kaydedilemedi') }
    finally { setBusy(false); setTimeout(() => setMsg(''), 2500) }
  }
  return (
    <div className="rounded-lg border border-brand-border bg-brand-input/40 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-gray-500 mb-1">
        Beyaz altlık K
      </div>
      <div className="flex items-center gap-1.5">
        <input type="number" min="0" max="100" value={deger}
               onChange={(e) => setDeger(Math.min(100, Math.max(0, Number(e.target.value) || 0)))}
               className="input !py-1 !px-2 w-16 text-sm" />
        <span className="text-sm text-gray-400">%</span>
        <button onClick={kaydet} disabled={busy}
                className="btn-secondary !text-xs !py-1 !px-2 disabled:opacity-50">
          {busy ? '…' : 'Kaydet'}
        </button>
      </div>
      <div className="text-[10px] text-gray-500 mt-1">
        CMYK 0,0,0,{deger} {msg && <span className="text-emerald-400 ml-1">{msg}</span>}
      </div>
    </div>
  )
}

function Info({ label, value, accent }) {
  return (
    <div className="bg-brand-input/40 border border-brand-border/60 rounded-lg p-3">
      <div className="text-[10px] uppercase text-gray-500">{label}</div>
      <div className={`text-base font-semibold ${accent ? 'text-accent' : 'text-gray-100'}`}>{value}</div>
    </div>
  )
}
