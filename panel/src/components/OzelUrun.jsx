// Tasarım talebine ÖZEL ürün — yalnız linki bilen görür (vitrinde hiçbir
// listede, aramada, site haritasında çıkmaz). Yüklenen görseller ürünün
// görselleri olur (ilki kapak). Baskı dosyası isteğe bağlı: verilirse tasarım
// kaydı olur ve kalıp planlayıcı siparişte bulur. Kargo/kampanya sepetteki
// her ürün gibi işler.
import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'

export default function OzelUrun({ talep, storeId, onDegisti, onHata }) {
  const u = talep.urun
  const [acik, setAcik] = useState(false)
  const [sec, setSec] = useState(null)
  const [fiyat, setFiyat] = useState(u ? String(u.price) : '')
  const [baslik, setBaslik] = useState(u?.title || '')
  const [setId, setSetId] = useState('')
  const [kilifId, setKilifId] = useState('')
  const [baski, setBaski] = useState(null)
  const [gorseller, setGorseller] = useState([])
  // Seçilen görsellerin önizlemesi (yüklemeden önce görülsün)
  const onizlemeler = useMemo(() => gorseller.map(f => URL.createObjectURL(f)), [gorseller])
  useEffect(() => () => onizlemeler.forEach(u => URL.revokeObjectURL(u)), [onizlemeler])
  const gorselEkle = (liste) => {
    const yeni = [...liste].filter(f => /^image\/(png|jpe?g|webp)$/.test(f.type))
    setGorseller(g => [...g, ...yeni].slice(0, 8))
  }
  const [busy, setBusy] = useState(false)
  const [kopyalandi, setKopyalandi] = useState(false)

  useEffect(() => {
    if (!acik || sec) return
    api.get(`/api/design-requests/secenekler?store_id=${storeId}`)
      .then(d => { setSec(d); setSetId(d.varsayilan_set || d.setler[0]?.id || ''); setKilifId(d.kiliflar[0]?.id || '') })
      .catch(() => setSec({ setler: [], kiliflar: [] }))
  }, [acik, sec, storeId])

  const kaydet = async () => {
    setBusy(true); onHata('')
    try {
      const fd = new FormData()
      fd.append('fiyat', String(Number(String(fiyat).replace(',', '.'))))
      if (baslik.trim()) fd.append('baslik', baslik.trim())
      if (!u && setId) fd.append('variant_set_id', setId)
      if (kilifId) fd.append('template_id', kilifId)
      if (baski) fd.append('baski', baski)
      gorseller.forEach(f => fd.append('gorsel', f))
      await api.postForm(`/api/design-requests/${talep.id}/urun`, fd)
      setAcik(false); setBaski(null); setGorseller([])
      onDegisti()
    } catch (e) {
      onHata(typeof e?.detail === 'string' ? e.detail : 'Ürün kaydedilemedi')
    } finally { setBusy(false) }
  }

  const kaldir = async () => {
    if (!window.confirm('Ürün satıştan kaldırılsın mı? Link açılmaz olur. (Silinmez — "Düzenle › Kaydet" ile yeniden açılır.)')) return
    setBusy(true)
    try { await api.del(`/api/design-requests/${talep.id}/urun`); onDegisti() }
    catch { onHata('Kaldırılamadı') } finally { setBusy(false) }
  }

  const kopyala = async () => {
    try { await navigator.clipboard.writeText(u.url); setKopyalandi(true); setTimeout(() => setKopyalandi(false), 1500) }
    catch { window.prompt('Linki kopyalayın:', u.url) }
  }

  const fiyatGecerli = Number(String(fiyat).replace(',', '.')) > 0
  const dosyaSecici = (etiket, aciklama, deger, ayarla, accept) => (
    <label className="block text-[11px] text-panel-muted">
      {etiket}
      <input type="file" accept={accept} onChange={e => ayarla(e.target.files?.[0] || null)}
        className="block w-full text-xs mt-0.5 file:mr-2 file:rounded-lg file:border-0 file:bg-panel-input file:px-2 file:py-1 file:text-panel-ink" />
      <span className="text-[10px]">{deger ? `✓ ${deger.name}` : aciklama}</span>
    </label>
  )

  return (
    <div className="mt-3 rounded-xl border border-panel-border p-2.5">
      {u ? (
        <div className="flex items-center gap-2.5 flex-wrap">
          {u.image_url && <img src={u.image_url} alt="" className="w-12 h-12 rounded-lg object-cover border border-panel-border" />}
          <div className="flex-1 min-w-40">
            <div className="text-sm font-medium truncate">{u.title}</div>
            {!u.baski_var && (
              <div className="text-[10px] text-amber-300">Baskı dosyası yüklenmedi — siparişte üretim dosyasını Düzenle'den ekleyin</div>
            )}
            <div className="text-xs text-panel-muted">
              {Number(u.price).toLocaleString('tr-TR')} TL · {u.satista
                ? <span className="text-emerald-300">Satışta — yalnız linkle görünür</span>
                : <span className="text-amber-300">Satıştan kaldırıldı</span>}
            </div>
          </div>
          {u.satista && (
            <>
              <button onClick={kopyala} className="px-2.5 py-1.5 rounded-lg text-xs border border-panel-border">
                {kopyalandi ? 'Kopyalandı ✓' : '🔗 Linki kopyala'}
              </button>
              <a href={u.url} target="_blank" rel="noopener noreferrer"
                className="px-2.5 py-1.5 rounded-lg text-xs border border-panel-border text-panel-muted hover:text-panel-ink">Aç ↗</a>
            </>
          )}
          <button onClick={() => setAcik(a => !a)} className="px-2.5 py-1.5 rounded-lg text-xs border border-panel-border">
            {acik ? 'Kapat' : 'Düzenle'}
          </button>
          {u.satista && (
            <button onClick={kaldir} disabled={busy} className="px-2.5 py-1.5 rounded-lg text-xs text-red-300 disabled:opacity-40">
              Satıştan kaldır
            </button>
          )}
        </div>
      ) : (
        <button onClick={() => setAcik(a => !a)} className="text-xs font-medium text-emerald-300">
          {acik ? '× Vazgeç' : '🛍 Bu müşteriye özel ürün oluştur'}
        </button>
      )}

      {acik && (
        <div className="mt-2.5 grid sm:grid-cols-2 gap-2.5">
          <div className="sm:col-span-2">
            <div className="text-[11px] text-panel-muted mb-1">
              Ürün görselleri {u ? '(yüklerseniz mevcutların YERİNE geçer)' : '*'} — müşteri ürün sayfasında bunları görür, ilki kapak
            </div>
            <label
              onDragOver={e => e.preventDefault()}
              onDrop={e => { e.preventDefault(); gorselEkle(e.dataTransfer.files) }}
              className="flex flex-wrap items-center gap-2 rounded-xl border border-dashed border-panel-border p-2 cursor-pointer hover:border-panel-accent">
              <input type="file" multiple accept="image/png,image/jpeg,image/webp" className="hidden"
                onChange={e => { gorselEkle(e.target.files || []); e.target.value = '' }} />
              {onizlemeler.map((src, i) => (
                <span key={src} className="relative">
                  <img src={src} alt="" className="w-16 h-16 rounded-lg object-cover border border-panel-border" />
                  {i === 0 && <span className="absolute bottom-0.5 left-0.5 text-[9px] px-1 rounded bg-black/70 text-white">Kapak</span>}
                  <button type="button" title="Kaldır"
                    onClick={e => { e.preventDefault(); setGorseller(g => g.filter((_, k) => k !== i)) }}
                    className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-red-500 text-white text-[11px] leading-5">×</button>
                </span>
              ))}
              <span className="text-xs text-panel-muted px-2">
                {gorseller.length ? '+ görsel ekle' : '📷 Görsel seçin ya da buraya sürükleyin (JPG/PNG/WEBP, en çok 8)'}
              </span>
            </label>
            {u?.gorseller?.length > 0 && !gorseller.length && (
              <div className="flex gap-1.5 mt-1.5 items-center">
                <span className="text-[10px] text-panel-muted">Şu anki görseller:</span>
                {u.gorseller.map(g => <img key={g} src={g} alt="" className="w-9 h-9 rounded object-cover border border-panel-border" />)}
              </div>
            )}
          </div>
          {dosyaSecici(u?.baski_var ? 'Baskı dosyası (değiştirmek için)' : 'Baskı dosyası (isteğe bağlı)',
            'PNG/JPG/PDF — üretime giden dosya; şimdi ya da sonra yükleyebilirsiniz', baski, setBaski, '.png,.jpg,.jpeg,.pdf,.svg')}
          <label className="block text-[11px] text-panel-muted">
            Fiyat (TL) *
            <input value={fiyat} onChange={e => setFiyat(e.target.value)} inputMode="decimal" placeholder="örn. 449"
              className="input !py-1.5 text-xs mt-0.5" />
          </label>
          <label className="block text-[11px] text-panel-muted">
            Ürün adı
            <input value={baslik} onChange={e => setBaslik(e.target.value)} maxLength={300}
              placeholder={`Özel Tasarım Kılıf — ${(talep.customer_name || '').split(' ')[0]}`}
              className="input !py-1.5 text-xs mt-0.5" />
          </label>
          {!u && (
            <label className="block text-[11px] text-panel-muted">
              Model listesi
              <select value={setId} onChange={e => setSetId(e.target.value)} className="input !py-1.5 text-xs mt-0.5">
                {(sec?.setler || []).map(s => <option key={s.id} value={s.id}>{s.name} ({s.adet} model)</option>)}
              </select>
            </label>
          )}
          {(sec?.kiliflar || []).length > 0 && (
            <label className="block text-[11px] text-panel-muted">
              Fotoğraftaki kılıf
              <select value={kilifId} onChange={e => setKilifId(e.target.value)} className="input !py-1.5 text-xs mt-0.5">
                {sec.kiliflar.map(k => <option key={k.id} value={k.id}>{k.label}</option>)}
              </select>
            </label>
          )}
          <div className="sm:col-span-2 flex items-center gap-2 flex-wrap">
            <button onClick={kaydet} disabled={busy || !fiyatGecerli || (!u && !baski && !gorseller.length)}
              className="btn !py-1.5 text-xs disabled:opacity-40">
              {busy ? 'Kaydediliyor…' : u ? 'Ürünü güncelle' : 'Ürünü oluştur'}
            </button>
            <span className="text-[10px] text-panel-muted">
              Ürün yalnız linkle açılır; müşteri linki istediği kadar kullanabilir. Kargo ve kampanyalar
              sepetine göre uygulanır. Sonra aşağıdan “Kaydet + Bildir” ile linki gönderin.
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
