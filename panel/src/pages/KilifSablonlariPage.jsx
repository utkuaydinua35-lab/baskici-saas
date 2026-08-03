import { useCallback, useEffect, useRef, useState } from 'react'
import { api, getToken } from '../lib/api'
import { useStore } from '../lib/store'

// Kılıf Şablonları — müşterinin tasarım stüdyosunda gördüğü boş kılıflar.
// Her şablonda: mockup görseli + BASKI ALANI (müşterinin düzenleyebildiği
// bölge) + BASILAMAYAN BÖLGELER (kamera adası, MagSafe halkası). Alanlar
// fareyle çizilir/taşınır, köşe yuvarlaklığı ayrı ayarlanır. Koordinatlar
// görsele ORANSAL (0-1) saklanır — çözünürlükten bağımsız.
export default function KilifSablonlariPage() {
  const { storeId } = useStore()
  const [data, setData] = useState({ templates: [], suggested: [] })
  const [editing, setEditing] = useState(null)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    if (!storeId) return
    try { setData(await api.get(`/api/case-templates?store_id=${storeId}`)) }
    catch { setErr('Şablonlar yüklenemedi') }
  }, [storeId])
  useEffect(() => { load() }, [load])

  const ekle = async (key, label) => {
    setBusy(true); setErr('')
    try {
      const t = await api.post('/api/case-templates', { store_id: storeId, key, label })
      await load()
      setEditing(t)          // ekler eklemez görsel yüklemeye geç
    } catch (e) {
      setErr(typeof e?.detail === 'string' ? e.detail : 'Eklenemedi')
    } finally { setBusy(false) }
  }

  const sil = async (t) => {
    if (!window.confirm(`"${t.label}" şablonu silinecek. Emin misiniz?`)) return
    try { await api.del(`/api/case-templates/${t.id}`); load() }
    catch { setErr('Silinemedi') }
  }

  const durum = async (t) => {
    try { await api.patch(`/api/case-templates/${t.id}`, { is_active: !t.is_active }); load() }
    catch { setErr('Güncellenemedi') }
  }

  return (
    <div className="space-y-4 max-w-4xl">
      <div>
        <h1 className="text-xl font-semibold">Kılıf Şablonları</h1>
        <p className="text-xs text-panel-muted mt-0.5">
          Müşteri tasarım stüdyosunda bu kılıflardan birini seçip üzerine kendi
          tasarımını yapar. Her şablona boş kılıf görselini yükleyin, sonra
          <b> baskı alanını</b> ve <b>kamera gibi basılamayan bölgeleri</b> işaretleyin.
        </p>
      </div>

      {err && <p className="text-sm text-red-600">{err}</p>}

      {data.suggested?.length > 0 && (
        <div className="card !py-3">
          <div className="text-xs text-panel-muted mb-2">Hazır kılıf tipleri — tek tıkla ekleyin:</div>
          <div className="flex gap-2 flex-wrap">
            {data.suggested.map(s => (
              <button key={s.key} disabled={busy} onClick={() => ekle(s.key, s.label)}
                className="px-3 py-1.5 rounded-xl text-xs border border-panel-border
                  hover:border-panel-accent hover:text-panel-accent transition disabled:opacity-40">
                + {s.label}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {data.templates.map(t => (
          <div key={t.id} className="card !p-0 overflow-hidden">
            <div className="h-64 bg-panel-input relative flex items-center justify-center p-2">
              {t.image_url ? (
                <KartOnizleme t={t} />
              ) : (
                <div className="text-center text-xs text-panel-muted p-4">
                  <div className="text-2xl">📱</div>
                  Görsel yüklenmedi
                </div>
              )}
            </div>
            <div className="p-3 space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="font-medium text-sm truncate">{t.label}</span>
                <button onClick={() => durum(t)}
                  className={`ml-auto text-[10px] px-2 py-0.5 rounded-full ${t.is_active
                    ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
                  {t.is_active ? 'Yayında' : 'Kapalı'}
                </button>
              </div>
              <div className="text-[11px] text-panel-muted">
                {t.print.width_mm}×{t.print.height_mm} mm · {t.print.dpi} DPI
                <span className="block">baskı dosyası: {t.print.px_w}×{t.print.px_h} px</span>
              </div>
              {!t.image_url && (
                <div className="text-[11px] text-amber-700">Görsel yüklenmeden müşteriye görünmez.</div>
              )}
              <div className="flex gap-2 pt-1">
                <button onClick={() => setEditing(t)} className="btn-ghost !py-1 text-xs flex-1">
                  🎯 Alanları Düzenle
                </button>
                <button onClick={() => sil(t)} className="text-xs text-red-600 px-2">Sil</button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {data.templates.length === 0 && (
        <div className="card text-center !p-10">
          <div className="text-3xl">📱</div>
          <p className="mt-2 text-sm text-panel-muted">
            Henüz kılıf şablonu yok. Yukarıdaki hazır tiplerden ekleyerek başlayın.
          </p>
        </div>
      )}

      {editing && (
        <AlanEditoru template={editing} storeId={storeId}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); load() }} />
      )}
    </div>
  )
}

// Kart önizlemesi — kutular EDİTÖRDEKİYLE aynı hesapla çizilir: konumlar
// görselin kendi kutusuna oranlı, köşe yuvarlaklığı piksel (yüzde elips yapar).
function KartOnizleme({ t }) {
  const [imgOran, setImgOran] = useState(0)
  const kutu = (k, cls) => (
    <div className={`absolute border-2 ${cls}`}
      style={{
        left: `${k.x * 100}%`, top: `${k.y * 100}%`,
        width: `${k.w * 100}%`, height: `${k.h * 100}%`,
        borderRadius: kose(k, imgOran),
      }} />
  )
  return (
    <div className="relative h-full">
      <img src={t.image_url} alt={t.label} className="h-full w-auto block"
        onLoad={(e) => setImgOran(e.currentTarget.naturalWidth / e.currentTarget.naturalHeight)} />
      <div className="absolute inset-0 pointer-events-none">
        {kutu(t.area, 'border-emerald-500/70 bg-emerald-500/10')}
        {(t.cutouts || []).map((c, i) => (
          <span key={i}>{kutu(c, 'border-amber-400/80 bg-amber-400/20')}</span>
        ))}
      </div>
    </div>
  )
}


// Köşe yarıçapı — ÖLÇÜMSÜZ. borderRadius'un "yatay% / dikey%" biçimi
// kullanılır: kutunun eni ve boyu farklı olsa da köşe DAİRE kalır. Oran
// yalnızca görselin doğal en/boy oranına bağlı olduğundan yakınlaştırma
// köşeyi değiştirmez (eskiden piksel ölçümü zoom sonrası geç gelip
// yüzdeye düşüyordu; ovallik o yüzden oynuyordu).
function kose(k, imgOran) {
  const r = (k.radius || 0) * 100
  if (!r || !imgOran) return 0
  const kutuOran = ((k.w || 1) * imgOran) / (k.h || 1)   // genişlik / yükseklik
  return kutuOran >= 1
    ? `${r / kutuOran}% / ${r}%`
    : `${r}% / ${r * kutuOran}%`
}

// ─── Alan editörü ─────────────────────────────────────────────
// Yeşil kutu = müşterinin tasarım yapabildiği baskı alanı.
// Sarı kutular = basılamayan bölgeler (kamera, MagSafe halkası).
const TUTAMAKLAR = [
  ['nw', 0, 0, 'nwse-resize'], ['n', 50, 0, 'ns-resize'], ['ne', 100, 0, 'nesw-resize'],
  ['e', 100, 50, 'ew-resize'], ['se', 100, 100, 'nwse-resize'], ['s', 50, 100, 'ns-resize'],
  ['sw', 0, 100, 'nesw-resize'], ['w', 0, 50, 'ew-resize'],
]

function AlanEditoru({ template, storeId, onClose, onSaved }) {
  const [t, setT] = useState(template)
  const [sel, setSel] = useState('baski')       // 'baski' | kesik index
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [err, setErr] = useState('')
  const boxRef = useRef(null)
  const drag = useRef(null)
  // Kutu ölçüleri — köşe yuvarlaklığını piksele çevirmek için. Yüzde
  // verilirse tarayıcı ELİPS çizer (kenarlar ortaya doğru şişer); doğrusu
  // kısa kenara oranlı sabit yarıçap.
  const [imgOran, setImgOran] = useState(0)   // görselin doğal en/boy oranı
  const [zoom, setZoom] = useState(1)
  // Yakinlastirma seçimi ve devam eden sürüklemeyi etkilemesin
  const zoomla = (v) => { drag.current = null; setZoom(v) }

  const kesikler = t.cutouts || []
  const aktif = sel === 'baski' ? t.area : kesikler[sel]
  const setAktif = (kutu) => setT(p => sel === 'baski'
    ? { ...p, area: { ...p.area, ...kutu } }
    : { ...p, cutouts: p.cutouts.map((c, i) => i === sel ? { ...c, ...kutu } : c) })

  // Fare konumunu görsele oransal (0-1) çevir
  const oran = (e) => {
    const b = boxRef.current?.getBoundingClientRect()
    if (!b || !b.width || !b.height) return null   // ölçüm yoksa hareket yok
    return {
      x: Math.max(0, Math.min(1, (e.clientX - b.left) / b.width)),
      y: Math.max(0, Math.min(1, (e.clientY - b.top) / b.height)),
    }
  }
  const ESIK = 3   // px — altındaki hareket "tıklama" sayılır
  const basla = (e, tip) => {
    e.preventDefault(); e.stopPropagation()
    const p0 = oran(e)
    if (aktif && p0) drag.current = { tip, bas: p0, kutu: { ...aktif },
                                basX: e.clientX, basY: e.clientY, basladi: false }
  }
  const hareket = (e) => {
    if (!drag.current) return
    // Eşiği aşana kadar hiçbir şey değiştirme — tıklama kutuyu bozmasın
    if (!drag.current.basladi) {
      if (Math.abs(e.clientX - drag.current.basX) < ESIK &&
          Math.abs(e.clientY - drag.current.basY) < ESIK) return
      drag.current.basladi = true
    }
    const p = oran(e)
    if (!p) return
    const { tip, bas, kutu } = drag.current
    if (tip === 'yeni') {
      setAktif({ x: Math.min(bas.x, p.x), y: Math.min(bas.y, p.y),
                 w: Math.abs(p.x - bas.x), h: Math.abs(p.y - bas.y) })
      return
    }
    const dx = p.x - bas.x, dy = p.y - bas.y
    let { x, y, w, h } = kutu
    if (tip === 'tasi') {
      x = Math.max(0, Math.min(1 - w, x + dx))
      y = Math.max(0, Math.min(1 - h, y + dy))
    } else {
      if (tip.includes('w')) { x = kutu.x + dx; w = kutu.w - dx }
      if (tip.includes('e')) { w = kutu.w + dx }
      if (tip.includes('n')) { y = kutu.y + dy; h = kutu.h - dy }
      if (tip.includes('s')) { h = kutu.h + dy }
      if (w < 0) { x += w; w = -w }
      if (h < 0) { y += h; h = -h }
      x = Math.max(0, x); y = Math.max(0, y)
      w = Math.max(0.01, Math.min(1 - x, w)); h = Math.max(0.01, Math.min(1 - y, h))
    }
    setAktif({ x, y, w, h })
  }
  const bitir = () => { drag.current = null }

  const kesikEkle = () => {
    const yeni = { x: 0.34, y: 0.05, w: 0.32, h: 0.16, radius: 0.25, label: 'Kamera' }
    setT(p => ({ ...p, cutouts: [...(p.cutouts || []), yeni] }))
    setSel(kesikler.length)
  }
  const kesikSil = () => {
    setT(p => ({ ...p, cutouts: (p.cutouts || []).filter((_, i) => i !== sel) }))
    setSel('baski')
  }
  const yuvarlaklik = sel === 'baski' ? (t.area.radius ?? 0) : (kesikler[sel]?.radius ?? 0.2)
  const setYuvarlaklik = (v) => sel === 'baski'
    ? setT(p => ({ ...p, area: { ...p.area, radius: v } }))
    : setT(p => ({ ...p, cutouts: p.cutouts.map((c, i) => i === sel ? { ...c, radius: v } : c) }))

  const gorselYukle = async (file) => {
    if (!file) return
    setUploading(true); setErr('')
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await fetch(`/api/case-templates/${t.id}/image`, {
        method: 'POST', headers: { Authorization: `Bearer ${getToken()}` }, body: fd,
      })
      if (!res.ok) throw new Error()
      const r = await res.json()
      setT(p => ({ ...p, image_url: r.image_url }))
    } catch { setErr('Görsel yüklenemedi') }
    finally { setUploading(false) }
  }

  const kaydet = async () => {
    setSaving(true); setErr('')
    try {
      await api.patch(`/api/case-templates/${t.id}`, {
        label: t.label,
        area_x: t.area.x, area_y: t.area.y, area_w: t.area.w, area_h: t.area.h,
        area_radius: t.area.radius ?? 0,
        cutouts: (t.cutouts || []).map(c => ({
          x: c.x, y: c.y, w: c.w, h: c.h, radius: c.radius ?? 0.2, label: c.label || null })),
        print_width_mm: Number(t.print.width_mm),
        print_height_mm: Number(t.print.height_mm),
        print_dpi: Number(t.print.dpi),
      })
      onSaved()
    } catch (e) {
      setErr(typeof e?.detail === 'string' ? e.detail : 'Kaydedilemedi')
    } finally { setSaving(false) }
  }

  const kutuCiz = (kutu, renk, secili, i) => (
    <div key={i ?? 'baski'}
      onMouseDown={secili ? (e => basla(e, 'tasi')) : undefined}
      className={`absolute border-2 ${renk === 'yesil'
        ? 'border-emerald-500 bg-emerald-500/15' : 'border-amber-400 bg-amber-400/25'}`}
      style={{
        left: `${kutu.x * 100}%`, top: `${kutu.y * 100}%`,
        width: `${kutu.w * 100}%`, height: `${kutu.h * 100}%`,
        borderRadius: kose(kutu, imgOran),
        cursor: secili ? 'move' : 'default',
        opacity: secili ? 1 : 0.45,
        // Seçili olmayan kutu tıklamayı YUTMAZ: çakışan alanlarda seçili
        // kutunun kenarına/tutamağına erişim her zaman açık kalır
        pointerEvents: secili ? 'auto' : 'none',
        // Secili olmayan kutu ustte: tiklayinca altindaki secili kutunun
        // govdesi degil kendisi yakalanir (yanlislikla tasima olmaz)
        zIndex: secili ? 2 : 1,
      }} />
  )

  // Tutamaklar KUTULARIN DISINDA, en ust katmanda: iki alan ust uste
  // bindiginde ustteki kutu alttakinin tutamagini ORTMEZ — yoksa yesil ve
  // sari cakistiginda dikey boyutlandirma yapilamiyordu.
  const tutamakCiz = () => {
    if (!aktif) return null
    return TUTAMAKLAR.map(([h, lx, ly, cur]) => (
      <div key={h} onMouseDown={e => basla(e, h)}
        className="absolute w-3.5 h-3.5 bg-white border border-slate-600 rounded-sm shadow"
        style={{
          left: `${(aktif.x + (lx / 100) * aktif.w) * 100}%`,
          top: `${(aktif.y + (ly / 100) * aktif.h) * 100}%`,
          transform: 'translate(-50%,-50%)', cursor: cur, zIndex: 3,
        }} />
    ))
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="absolute inset-0 bg-black/40" />
      <div className="relative bg-panel-card rounded-2xl shadow-xl w-full max-w-4xl max-h-[92vh] overflow-y-auto p-4">
        <div className="flex items-center gap-2 mb-3">
          <h3 className="text-sm font-semibold">Alanları Düzenle — {t.label}</h3>
          <button onClick={onClose} className="ml-auto text-panel-muted hover:text-panel-ink">×</button>
        </div>

        {!t.image_url ? (
          <label className="block border-2 border-dashed border-panel-border rounded-2xl p-10 text-center cursor-pointer hover:border-panel-accent">
            <div className="text-3xl">📤</div>
            <div className="text-sm mt-2">{uploading ? 'Yükleniyor…' : 'Boş kılıf görselini yükleyin'}</div>
            <div className="text-[11px] text-panel-muted mt-1">
              Şeffaf kılıf için arka planı saydam PNG kullanın · orijinal çözünürlük korunur
            </div>
            <input type="file" accept="image/*" className="hidden"
              onChange={e => gorselYukle(e.target.files?.[0])} />
          </label>
        ) : (
          <div className="space-y-3">
            {/* Tuval */}
            <div className="bg-panel-input rounded-xl p-2 overflow-auto max-h-[62vh] flex justify-center">
            <div ref={boxRef} className="relative select-none inline-block"
              onMouseMove={hareket} onMouseUp={bitir} onMouseLeave={bitir}>
              <img src={t.image_url} alt="" draggable={false}
                onLoad={(e) => setImgOran(e.currentTarget.naturalWidth / e.currentTarget.naturalHeight)}
                style={{ height: `${58 * zoom}vh`, width: 'auto' }}
                className="block pointer-events-none max-w-none" />
              {kutuCiz(t.area, 'yesil', sel === 'baski')}
              {kesikler.map((c, i) => kutuCiz(c, 'sari', sel === i, i))}
              {tutamakCiz()}
            </div>
            </div>

            {/* Ayarlar */}
            <div className="space-y-3 text-sm">
              <div>
                <div className="flex items-center gap-1.5 mb-2">
                  <span className="text-xs text-panel-muted">Yakınlaştır</span>
                  <button onClick={() => zoomla(Math.max(0.6, +(zoom - 0.25).toFixed(2)))}
                    className="w-7 h-7 rounded-lg border border-panel-border text-sm">−</button>
                  <span className="text-xs tabular-nums w-10 text-center">%{Math.round(zoom * 100)}</span>
                  <button onClick={() => zoomla(Math.min(3, +(zoom + 0.25).toFixed(2)))}
                    className="w-7 h-7 rounded-lg border border-panel-border text-sm">+</button>
                  <button onClick={() => zoomla(1)}
                    className="text-[11px] text-panel-muted underline ml-1">sıfırla</button>
                </div>
                <div className="text-xs text-panel-muted mb-1">Düzenlenen alan</div>
                <div className="flex flex-col gap-1">
                  <button onClick={() => setSel('baski')}
                    className={`text-left px-2.5 py-1.5 rounded-lg text-xs border ${sel === 'baski'
                      ? 'border-emerald-400 bg-emerald-50 text-emerald-700 font-medium'
                      : 'border-panel-border text-panel-muted'}`}>
                    🟩 Baskı alanı (müşteri buraya tasarım yapar)
                  </button>
                  {kesikler.map((c, i) => (
                    <button key={i} onClick={() => setSel(i)}
                      className={`text-left px-2.5 py-1.5 rounded-lg text-xs border ${sel === i
                        ? 'border-amber-400 bg-amber-50 text-amber-700 font-medium'
                        : 'border-panel-border text-panel-muted'}`}>
                      🟨 {c.label || `Basılamaz bölge ${i + 1}`}
                    </button>
                  ))}
                  <button onClick={kesikEkle} className="btn-ghost !py-1 text-xs mt-0.5">
                    + Basılamayan bölge ekle (kamera/MagSafe)
                  </button>
                </div>
              </div>

              {sel !== 'baski' && kesikler[sel] && (
                <label className="block">
                  <span className="text-xs text-panel-muted">Bölge adı</span>
                  <input className="input mt-1 !py-1.5 text-sm" value={kesikler[sel].label || ''}
                    maxLength={40} placeholder="Kamera"
                    onChange={e => setT(p => ({ ...p, cutouts: p.cutouts.map((c, i) =>
                      i === sel ? { ...c, label: e.target.value } : c) }))} />
                </label>
              )}

              <label className="block">
                <span className="text-xs text-panel-muted">
                  Köşe yuvarlaklığı — %{Math.round(yuvarlaklik * 100)}
                </span>
                <input type="range" min="0" max="0.5" step="0.005" value={yuvarlaklik}
                  onChange={e => setYuvarlaklik(Number(e.target.value))}
                  className="w-full mt-1 accent-emerald-600" />
              </label>

              {aktif && (
                <div className="text-[11px] text-panel-muted tabular-nums bg-panel-input rounded-lg px-2.5 py-2">
                  konum %{(aktif.x * 100).toFixed(1)} / %{(aktif.y * 100).toFixed(1)}<br />
                  boyut %{(aktif.w * 100).toFixed(1)} × %{(aktif.h * 100).toFixed(1)}
                </div>
              )}

              {sel !== 'baski' && (
                <button onClick={kesikSil} className="text-xs text-red-600">Bu bölgeyi sil</button>
              )}

              <div className="pt-2 border-t border-panel-border space-y-2">
                <div className="text-xs text-panel-muted">Gerçek baskı ölçüsü</div>
                <div className="grid grid-cols-2 gap-2">
                  <label className="block">
                    <span className="text-[11px] text-panel-muted">Genişlik (mm)</span>
                    <input className="input mt-1 !py-1.5 text-sm" type="number" min="10" max="500"
                      value={t.print.width_mm}
                      onChange={e => setT(p => ({ ...p, print: { ...p.print, width_mm: e.target.value } }))} />
                  </label>
                  <label className="block">
                    <span className="text-[11px] text-panel-muted">Yükseklik (mm)</span>
                    <input className="input mt-1 !py-1.5 text-sm" type="number" min="10" max="500"
                      value={t.print.height_mm}
                      onChange={e => setT(p => ({ ...p, print: { ...p.print, height_mm: e.target.value } }))} />
                  </label>
                </div>
                <label className="block">
                  <span className="text-[11px] text-panel-muted">Baskı çözünürlüğü (DPI)</span>
                  <input className="input mt-1 !py-1.5 text-sm !w-24" type="number" min="72" max="1200"
                    value={t.print.dpi}
                    onChange={e => setT(p => ({ ...p, print: { ...p.print, dpi: e.target.value } }))} />
                </label>
                <div className="text-[11px] text-panel-muted">
                  Baskı dosyası:{' '}
                  <b className="text-panel-ink tabular-nums">
                    {Math.round(Number(t.print.width_mm) / 25.4 * Number(t.print.dpi))}×
                    {Math.round(Number(t.print.height_mm) / 25.4 * Number(t.print.dpi))} px
                  </b>
                </div>
              </div>

              <label className="block">
                <span className="text-xs text-panel-muted">Görseli değiştir</span>
                <input type="file" accept="image/*" className="block mt-1 text-xs"
                  onChange={e => gorselYukle(e.target.files?.[0])} />
              </label>
            </div>
          </div>
        )}

        <p className="text-[11px] text-panel-muted mt-3">
Kutuyu sürükleyerek taşıyın, kenarındaki tutamaklarla boyutlandırın.
          Üstteki listeden hangi alanı düzenlediğinizi seçersiniz.
        </p>

        {err && <p className="text-sm text-red-600 mt-2">{err}</p>}
        <div className="flex justify-end gap-2 mt-3">
          <button onClick={onClose} className="btn-ghost">Vazgeç</button>
          <button onClick={kaydet} disabled={saving || !t.image_url} className="btn-primary">
            {saving ? 'Kaydediliyor…' : 'Kaydet'}
          </button>
        </div>
      </div>
    </div>
  )
}
