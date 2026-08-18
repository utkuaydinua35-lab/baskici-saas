import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
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

      {err && <p className="text-sm text-red-300">{err}</p>}

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
                    ? 'bg-emerald-500/10 text-emerald-300' : 'bg-white/5 text-panel-muted'}`}>
                  {t.is_active ? 'Yayında' : 'Kapalı'}
                </button>
              </div>
              <div className="text-[11px] text-panel-muted">
                {t.print.width_mm}×{t.print.height_mm} mm · {t.print.dpi} DPI
                <span className="block">baskı dosyası: {t.print.px_w}×{t.print.px_h} px</span>
              </div>
              {!t.image_url && (
                <div className="text-[11px] text-amber-300">Görsel yüklenmeden müşteriye görünmez.</div>
              )}
              <div className="flex gap-2 pt-1">
                <button onClick={() => setEditing(t)} className="btn-ghost !py-1 text-xs flex-1">
                  🎯 Alanları Düzenle
                </button>
                <button onClick={() => sil(t)} className="text-xs text-red-300 px-2">Sil</button>
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

      <HazirSablonlar storeId={storeId} templates={data.templates} />

      {editing && (
        <AlanEditoru template={editing} storeId={storeId}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); load() }} />
      )}
    </div>
  )
}

// Hazır tasarım şablonları (overlay) — müşterinin tasarımının ÜSTÜNE binen
// şeffaf PNG'ler. Örnek: fotoğraf çerçevesi. Müşterinin yüklediği görsel
// ALTTA kalır, çerçeve üstüne oturur, yazılar çerçevenin de üstündedir.
function HazirSablonlar({ storeId, templates }) {
  const [items, setItems] = useState([])
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [ad, setAd] = useState('')
  const [kilif, setKilif] = useState('')       // '' → tüm kılıflar
  const dosyaRef = useRef(null)

  const load = useCallback(async () => {
    if (!storeId) return
    try { setItems((await api.get(`/api/case-templates/overlays/list?store_id=${storeId}`)).items || []) }
    catch { setErr('Hazır şablonlar yüklenemedi') }
  }, [storeId])
  useEffect(() => { load() }, [load])

  const yukle = async (file) => {
    if (!file) return
    if (!ad.trim()) { setErr('Önce şablona bir ad verin'); return }
    setBusy(true); setErr('')
    try {
      const fd = new FormData()
      fd.append('file', file)
      const qs = new URLSearchParams({ store_id: storeId, label: ad.trim() })
      if (kilif) qs.set('case_template_id', kilif)
      const res = await fetch(`/api/case-templates/overlays?${qs}`, {
        method: 'POST', body: fd,
        headers: { Authorization: `Bearer ${getToken()}` },
      })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Yüklenemedi')
      setAd('')
      await load()
    } catch (e) {
      setErr(e.message || 'Yüklenemedi')
    } finally { setBusy(false); if (dosyaRef.current) dosyaRef.current.value = '' }
  }

  const sil = async (o) => {
    if (!window.confirm(`"${o.label}" hazır şablonu silinecek. Emin misiniz?`)) return
    try { await api.del(`/api/case-templates/overlays/${o.id}`); load() }
    catch { setErr('Silinemedi') }
  }

  const durum = async (o) => {
    try { await api.patch(`/api/case-templates/overlays/${o.id}`, { is_active: !o.is_active }); load() }
    catch { setErr('Güncellenemedi') }
  }

  const [alanDuzenle, setAlanDuzenle] = useState(null)

  return (
    <div className="card space-y-3">
      <div>
        <h2 className="font-semibold text-sm">🖼️ Hazır Tasarım Şablonları</h2>
        <p className="text-xs text-panel-muted mt-0.5">
          Müşterinin editörde seçebileceği hazır çerçeve/desenler. Şablon varsayılan
          olarak <b>en üstte</b> durur (görsellerin ve yazıların önünde); müşteri isterse
          tek tıkla <b>en alta</b> (zemin) alabilir. <b>Şeffaf PNG</b> yükleyin — saydam
          kısımda alttaki tasarım görünür. Görsel baskı alanını tam kaplar, o oranda
          hazırlayın.
        </p>
      </div>

      {err && <p className="text-sm text-red-300">{err}</p>}

      <div className="flex flex-wrap gap-2 items-end">
        <label className="text-xs text-panel-muted">
          Şablon adı
          <input value={ad} onChange={e => setAd(e.target.value)} maxLength={120}
            placeholder="Polaroid çerçeve"
            className="input !py-1.5 !text-sm block mt-0.5 w-48" />
        </label>
        <label className="text-xs text-panel-muted">
          Hangi kılıfta
          <select value={kilif} onChange={e => setKilif(e.target.value)}
            className="input !py-1.5 !text-sm block mt-0.5 w-44">
            <option value="">Tüm kılıflarda</option>
            {templates.map(t => <option key={t.id} value={t.id}>{t.label}</option>)}
          </select>
        </label>
        <button onClick={() => dosyaRef.current?.click()} disabled={busy}
          className="btn !py-1.5 !text-sm disabled:opacity-40">
          {busy ? 'Yükleniyor…' : '+ Şablon Yükle'}
        </button>
        <input ref={dosyaRef} type="file" accept="image/png,image/webp" className="hidden"
          onChange={e => yukle(e.target.files?.[0])} />
      </div>

      {alanDuzenle && (
        <SablonAlanEditoru overlay={alanDuzenle} templates={templates}
          onClose={() => setAlanDuzenle(null)}
          onSaved={() => { setAlanDuzenle(null); load() }} />
      )}

      {items.length > 0 ? (
        <div className="grid grid-cols-3 sm:grid-cols-5 lg:grid-cols-6 gap-2">
          {items.map(o => (
            <div key={o.id} className="border border-panel-border rounded-xl overflow-hidden">
              <div className="aspect-[9/16] bg-[repeating-conic-gradient(#e5e7eb_0_25%,#fff_0_50%)]
                bg-[length:14px_14px] flex items-center justify-center">
                <img src={o.thumb_url} alt={o.label} className="w-full h-full object-contain" />
              </div>
              <div className="p-1.5 space-y-1">
                <div className="text-[11px] truncate" title={o.label}>{o.label}</div>
                {o.kategori && (
                  <div className="text-[10px] text-panel-muted truncate">📁 {o.kategori}</div>
                )}
                {o.sadece_urunde && (
                  <div className="text-[10px] text-panel-accent">🧩 ürüne özel modül</div>
                )}
                {o.mod === 'kisitli' && (
                  <div className="text-[10px] text-panel-accent">
                    🔒 Kısıtlı · {o.alanlar?.length || 0} alan
                  </div>
                )}
                <button onClick={() => setAlanDuzenle(o)}
                  className="w-full text-[10px] py-1 rounded-lg border border-panel-border
                    hover:border-panel-accent transition">
                  ✏️ Alanları düzenle
                </button>
                <div className="flex items-center gap-1">
                  <button onClick={() => durum(o)}
                    className={`text-[10px] px-1.5 py-0.5 rounded-full ${o.is_active
                      ? 'bg-emerald-500/10 text-emerald-300' : 'bg-white/5 text-panel-muted'}`}>
                    {o.is_active ? 'Yayında' : 'Kapalı'}
                  </button>
                  <button onClick={() => sil(o)} className="ml-auto text-[10px] text-red-300">Sil</button>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-panel-muted">
          Henüz hazır şablon yok. Ad verip şeffaf PNG yükleyerek başlayın.
        </p>
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
          <span key={i}>{kutu(c, 'border-amber-500/30 bg-amber-400/20')}</span>
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
        ? 'border-emerald-500 bg-emerald-500/15' : 'border-amber-500/30 bg-amber-400/25'}`}
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
        className="absolute w-3.5 h-3.5 bg-white border border-panel-border rounded-sm shadow"
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
            {/* Yakınlaştırma TUVALİN TAMAMINI ölçekler (transform: scale).
                Görseli tek başına büyütmek kutuları/tutamakları kaydırıyordu;
                böyle hepsi tek parça büyür, hiçbiri bozulmaz. */}
            <div className="bg-panel-input rounded-xl p-2 overflow-auto max-h-[64vh] flex justify-center">
              <div style={{ transform: `scale(${zoom})`, transformOrigin: 'top center' }}>
                <div ref={boxRef} className="relative select-none inline-block"
                  onMouseMove={hareket} onMouseUp={bitir} onMouseLeave={bitir}>
                  <img src={t.image_url} alt="" draggable={false}
                    onLoad={(e) => setImgOran(e.currentTarget.naturalWidth / e.currentTarget.naturalHeight)}
                    style={{ height: '54vh', width: 'auto' }}
                    className="block pointer-events-none max-w-none" />
                  {kutuCiz(t.area, 'yesil', sel === 'baski')}
                  {kesikler.map((c, i) => kutuCiz(c, 'sari', sel === i, i))}
                  {tutamakCiz()}
                </div>
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
                      ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300 font-medium'
                      : 'border-panel-border text-panel-muted'}`}>
                    🟩 Baskı alanı (müşteri buraya tasarım yapar)
                  </button>
                  {kesikler.map((c, i) => (
                    <button key={i} onClick={() => setSel(i)}
                      className={`text-left px-2.5 py-1.5 rounded-lg text-xs border ${sel === i
                        ? 'border-amber-500/30 bg-amber-500/10 text-amber-300 font-medium'
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
                <button onClick={kesikSil} className="text-xs text-red-300">Bu bölgeyi sil</button>
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

        {err && <p className="text-sm text-red-300 mt-2">{err}</p>}
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

// Kısıtlı şablon alan editörü — müşterinin neyi değiştirebileceğini burada
// tanımlarsınız. Örnek: forma şablonunda "numara" ve "isim" yazı alanları,
// "Türk bayrağı" ve "logo" açılabilir görsel alanları. Müşteri bunların
// DIŞINDA hiçbir şey ekleyemez, taşıyamaz.
//
// Koordinatlar şablon görseline ORANSAL (0-1) saklanır; alan kutuları fareyle
// taşınır ve sağ alt köşeden boyutlandırılır.
// "Çerçeveyi doldur" tavanı — vitrindeki ve sunucudaki değerle aynı olmalı
// (storefront/components/studio/types.ts, backend design_render.TAVAN_PUNTO)
const TAVAN_PUNTO = 0.8

// Metni kutu genişliğine oturtan önizleme — vitrindeki SigdirilanYazi'nin eşi
function DolduranYazi({ metin, punto, doldur, cerceveYuk, tavan }) {
  // Ölçüm hep TANIMLI puntodaki gizli kopyadan yapılır (bkz. Canvas.tsx):
  // görünen metni ölçmek geri besleme yaratıp ölçeği şaşırtıyor.
  const olcRef = useRef(null)
  const [olcek, setOlcek] = useState(1)
  useLayoutEffect(() => {
    const el = olcRef.current
    const kap = el?.parentElement
    if (!doldur || !el || !kap) { setOlcek(1); return }
    const olc = () => {
      const kutu = kap.clientWidth
      const k = el.getBoundingClientRect()
      if (!kutu || !k.width || !k.height) return
      // Vitrindeki kuralın aynısı: genişlik VE yükseklik birlikte sınırlar;
      // çerçeve yüksekliği yoksa metin büyümez
      const enBuyukH = cerceveYuk > 0 ? cerceveYuk / k.height : 1
      const tavanOlcek = punto > 0 ? Math.max(1, tavan / punto) : 1
      const yeni = Math.max(0.15, Math.min(kutu / k.width, enBuyukH, tavanOlcek))
      setOlcek(eski => (Math.abs(yeni - eski) > 0.005 ? yeni : eski))
    }
    olc()
    // Font sonradan yüklenince ölçüm kopyasının genişliği değişir → kısa bir
    // pencere boyunca yeniden ölç (bkz. Canvas.tsx'teki aynı gerekçe)
    let ro = null
    try {
      ro = new ResizeObserver(olc)
      ro.observe(el)
      ro.observe(kap)
    } catch { /* eski tarayıcı */ }
    const zamanlar = [120, 350, 800, 1600].map(ms => setTimeout(olc, ms))
    return () => { ro?.disconnect(); zamanlar.forEach(clearTimeout) }
  }, [metin, punto, doldur, cerceveYuk, tavan])
  return (
    <>
      {doldur && (
        <span ref={olcRef} aria-hidden="true" style={{
          position: 'absolute', visibility: 'hidden', pointerEvents: 'none',
          left: 0, top: 0, whiteSpace: 'nowrap', fontSize: `${punto}px`,
          lineHeight: 'normal',
        }}>{metin}</span>
      )}
      <span style={{
        display: 'inline-block',
        whiteSpace: doldur ? 'nowrap' : 'normal',
        fontSize: `${punto * olcek}px`,
        lineHeight: doldur ? 'normal' : undefined,
        width: doldur ? 'auto' : '100%',
      }}>{metin}</span>
    </>
  )
}

// Alan editörünün önizlemesi VİTRİNDEKİ TUVALLE aynı geometriyi kullanır:
// şablon görseli baskı alanına GERİLİR (objectFit: fill), alanlar ve punto
// baskı alanına oranlanır. Şablon görselini burada kendi doğal oranında
// göstermek, kare bir tasarımın uzun kılıfta bambaşka görünmesine ve
// "yazıyı koyduğum yerde değil" şikâyetine yol açıyordu.
// Vitrindeki eşi: storefront/components/studio/Canvas.tsx
function SablonAlanEditoru({ overlay, templates = [], onClose, onSaved }) {
  const [mod, setMod] = useState(overlay.mod || 'serbest')
  const [kategori, setKategori] = useState(overlay.kategori || '')
  const [sadeceUrunde, setSadeceUrunde] = useState(!!overlay.sadece_urunde)
  const [alanlar, setAlanlar] = useState(() =>
    (overlay.alanlar || []).map(a => ({ ...a })))
  const [sel, setSel] = useState(0)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const tuvalRef = useRef(null)
  const gorselRef = useRef(null)
  const surukle = useRef(null)
  // Tuvalin ölçüsü — puntoyu piksele çevirmek için (vitrindeki areaPx'in eşi)
  const [tuvalPx, setTuvalPx] = useState({ w: 0, h: 0 })

  // Baskı alanının EN/BOY oranı: kılıf görselinin doğal ölçüsü × alan oranı.
  // Şablon bir kılıfa bağlı değilse görselin kendi oranı kullanılır.
  const kilif = templates.find(t => t.id === overlay.case_template_id) || null
  const [alanOran, setAlanOran] = useState(null)
  useEffect(() => {
    let iptal = false
    const im = new Image()
    im.onload = () => {
      if (iptal) return
      const a = kilif?.area
      setAlanOran(a
        ? (a.w * im.naturalWidth) / (a.h * im.naturalHeight)
        : im.naturalWidth / im.naturalHeight)
    }
    im.src = kilif?.image_url || overlay.image_url
    return () => { iptal = true }
  }, [kilif, overlay.image_url])

  useEffect(() => {
    const el = tuvalRef.current
    if (!el) return
    const olc = () => setTuvalPx({ w: el.clientWidth, h: el.clientHeight })
    olc()
    const ro = new ResizeObserver(olc)
    ro.observe(el)
    return () => ro.disconnect()
  }, [alanOran])

  const secili = alanlar[sel] || null
  const yamala = (yama) => setAlanlar(ls =>
    ls.map((a, i) => (i === sel ? { ...a, ...yama } : a)))

  const ekle = (tip) => {
    const n = alanlar.length + 1
    const yeniler = {
      yazi: { key: `yazi${n}`, tip: 'yazi', etiket: `Yazı ${n}`, varsayilan: 'METİN',
              max: 12, x: 0.2, y: 0.4, w: 0.6, h: 0.12 * 1.3, size: 0.12,
              font: 'anton', renk: '#ffffff', hiza: 'center', otomatik_kucult: true },
      gorsel: { key: `gorsel${n}`, tip: 'gorsel', etiket: `Öğe ${n}`, x: 0.2, y: 0.2,
                w: 0.2, h: 0.1, varsayilan: true, image_path: null },
      // Müşterinin YÜKLEYECEĞİ görsel — çerçeveye otomatik oturur, şablon
      // delikliyse arkada durması gerekir (arkada: true)
      foto: { key: `foto${n}`, tip: 'foto', etiket: `Fotoğraf ${n}`, x: 0.15, y: 0.15,
              w: 0.7, h: 0.4, sigdir: 'kapla', arkada: true },
      // Spotify tarzı ilerleme çubuğu — iki süre alanından oran hesaplanır
      ilerleme: { key: `ilerleme${n}`, tip: 'ilerleme', etiket: 'Şarkı konumu',
                  x: 0.1, y: 0.75, w: 0.8, kalinlik: 0.004, boyut: 0.012,
                  renk: '#ffffff', renk_pasif: '#5a5a5a',
                  kaynak_gecen: '', kaynak_toplam: '' },
    }
    setAlanlar(ls => [...ls, yeniler[tip]])
    setSel(alanlar.length)
    setMod('kisitli')
  }

  // Fareyle taşıma / boyutlandırma — konumlar şablona oransal
  const basla = (e, i, tip) => {
    e.preventDefault(); e.stopPropagation()
    setSel(i)
    const r = tuvalRef.current.getBoundingClientRect()
    surukle.current = { i, tip, sx: e.clientX, sy: e.clientY, r, ilk: { ...alanlar[i] } }
  }
  useEffect(() => {
    const hareket = (e) => {
      const d = surukle.current
      if (!d) return
      const dx = (e.clientX - d.sx) / d.r.width
      const dy = (e.clientY - d.sy) / d.r.height
      setAlanlar(ls => ls.map((a, i) => {
        if (i !== d.i) return a
        if (d.tip === 'tasi') {
          return { ...a, x: Math.min(1, Math.max(0, d.ilk.x + dx)),
                   y: Math.min(1, Math.max(0, d.ilk.y + dy)) }
        }
        const w = Math.min(1, Math.max(0.03, d.ilk.w + dx))
        // Yazıda da ÇERÇEVE kutusu ölçeklenir: metin bu kutuya oturtulur,
        // punto kutudan hesaplanır (eskiden dikey sürükleme puntoyu
        // değiştiriyordu; o zaman "çerçeve" diye bir şey yoktu ve tek
        // haneli metin kutunun dışına taşıyordu)
        const yeniH = Math.min(1, Math.max(0.02, (d.ilk.h ?? (d.ilk.size || 0.1) * 1.3) + dy))
        if (a.tip === 'yazi') return { ...a, w, h: yeniH, size: yeniH / 1.3 }
        return { ...a, w, h: yeniH }
      }))
    }
    const birak = () => { surukle.current = null }
    window.addEventListener('pointermove', hareket)
    window.addEventListener('pointerup', birak)
    return () => {
      window.removeEventListener('pointermove', hareket)
      window.removeEventListener('pointerup', birak)
    }
  }, [])

  // Seçili alanı şablona göre yasla (0-1 oransal koordinatlar)
  const yasla = (yon) => {
    if (!secili) return
    const w = Number(secili.w) || 0.3
    // Yazıda gerçek yükseklik puntodan doğar; görsel/ilerlemede h alanı var
    const h = secili.tip === 'yazi'
      ? (Number(secili.h) || (Number(secili.size) || 0.1) * 1.3)
      : secili.tip === 'ilerleme'
        ? (Number(secili.boyut) || 0.012) * 2
        : (Number(secili.h) || 0.1)
    const yama = {}
    if (['sol', 'yatay', 'sag', 'orta'].includes(yon)) {
      yama.x = yon === 'sol' ? 0 : yon === 'sag' ? 1 - w : (1 - w) / 2
    }
    if (['ust', 'dikey', 'alt', 'orta'].includes(yon)) {
      yama.y = yon === 'ust' ? 0 : yon === 'alt' ? 1 - h : (1 - h) / 2
    }
    yamala(yama)
  }

  const alanGorseliYukle = async (file) => {
    if (!file || !secili) return
    setBusy(true); setErr('')
    try {
      const fd = new FormData(); fd.append('file', file)
      const res = await fetch(`/api/case-templates/overlays/${overlay.id}/alan-gorseli`, {
        method: 'POST', body: fd, headers: { Authorization: `Bearer ${getToken()}` },
      })
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Yüklenemedi')
      const d = await res.json()
      yamala({ image_path: d.image_path, image_url: d.image_url })
    } catch (e) { setErr(e.message || 'Yüklenemedi') }
    finally { setBusy(false); if (gorselRef.current) gorselRef.current.value = '' }
  }

  const kaydet = async () => {
    setBusy(true); setErr('')
    try {
      // image_url sunucuya gönderilmez (türetilmiş alan)
      const temiz = alanlar.map(({ image_url, ...a }) => a)
      await api.patch(`/api/case-templates/overlays/${overlay.id}`,
        { mod, kategori: kategori.trim() || null, sadece_urunde: sadeceUrunde,
          alanlar: temiz })
      onSaved()
    } catch (e) {
      setErr(typeof e?.detail === 'string' ? e.detail : 'Kaydedilemedi')
    } finally { setBusy(false) }
  }

  const yuzde = (v) => `${(v || 0) * 100}%`

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4"
      onClick={onClose}>
      <div className="bg-panel-card rounded-2xl w-full max-w-4xl max-h-[92vh] overflow-y-auto p-4"
        onClick={e => e.stopPropagation()}>
        <div className="flex items-center gap-2 mb-3">
          <h2 className="font-semibold text-sm">“{overlay.label}” alanları</h2>
          <button onClick={onClose} className="ml-auto text-panel-muted text-lg leading-none">×</button>
        </div>

        {err && <p className="text-sm text-red-300 mb-2">{err}</p>}

        <label className="block text-xs text-panel-muted mb-3">
          Modül / tema adı — vitrinde şablonlar bu başlık altında gruplanır
          <input value={kategori} onChange={e => setKategori(e.target.value)} maxLength={60}
            placeholder="Forma · Spotify · Fotoğraf çerçevesi"
            className="input !py-1.5 !text-sm mt-0.5 w-full sm:w-72" />
        </label>

        <label className="flex items-start gap-2 text-xs mb-2 p-2.5 rounded-xl bg-panel-input">
          <input type="checkbox" checked={sadeceUrunde} className="mt-0.5"
            onChange={e => setSadeceUrunde(e.target.checked)} />
          <span>
            <b>Yalnız atandığı ürünlerde görünsün</b> — bu tasarımı bir MODÜL yapar.
            Ürün detayındaki “Hazır Tasarım Modülleri”nden seçtiğiniz ürünlerde
            çıkar, diğer ürünlerin stüdyosunu kalabalıklaştırmaz. Kapalıyken her
            üründe genel şablon olarak görünür.
          </span>
        </label>

        <label className="flex items-start gap-2 text-xs mb-3 p-2.5 rounded-xl bg-panel-input">
          <input type="checkbox" checked={mod === 'kisitli'} className="mt-0.5"
            onChange={e => setMod(e.target.checked ? 'kisitli' : 'serbest')} />
          <span>
            <b>Kısıtlı şablon</b> — müşteri yalnız aşağıdaki alanları doldurur, kendi
            görselini/yazısını ekleyemez ve hiçbir şeyi taşıyamaz. Kapalıyken şablon
            normal bir katman gibi kullanılır.
          </span>
        </label>

        <div className="grid md:grid-cols-[1fr_260px] gap-4">
          {/* Önizleme — vitrindeki tuvalin birebir aynısı: şablon görseli
              baskı alanına gerilir, alanlar o kutuya oranlanır */}
          <div className="bg-panel-input rounded-xl p-3 flex flex-col items-center gap-1.5">
            <div ref={tuvalRef} className="relative select-none touch-none bg-black/20"
              style={{ height: '58vh', aspectRatio: alanOran || 0.5 }}>
              <img src={overlay.image_url} alt={overlay.label} draggable={false}
                style={{ width: '100%', height: '100%', objectFit: 'fill', display: 'block' }} />
              {alanlar.map((a, i) => (
                <div key={i} onPointerDown={e => basla(e, i, 'tasi')}
                  className={`absolute cursor-move ${i === sel
                    ? 'outline outline-2 outline-panel-accent' : 'outline outline-1 outline-white/60'}`}
                  style={{
                    left: yuzde(a.x), top: yuzde(a.y), width: yuzde(a.w),
                    // Yazıda da gerçek bir ÇERÇEVE var: metin bu kutuya
                    // oturtulur, dışına taşmaz (vitrindeki davranışın aynısı)
                    height: a.tip === 'gorsel' || a.tip === 'yazi'
                      ? yuzde(a.h ?? (a.tip === 'yazi' ? (a.size || 0.1) * 1.3 : 0.1))
                      : undefined,
                    zIndex: i === sel ? 2 : 1,
                  }}>
                  {a.tip === 'foto' ? (
                    <div className="w-full h-full bg-panel-accent/25 border border-dashed
                      border-panel-accent text-[9px] flex items-center justify-center text-center">
                      📷 müşteri fotoğrafı
                    </div>
                  ) : a.tip === 'ilerleme' ? (
                    <div className="w-full flex items-center" style={{ height: 8 }}>
                      <div className="flex-1 rounded-full" style={{ height: 3, background: a.renk_pasif || '#5a5a5a' }} />
                      <div className="rounded-full" style={{ width: 8, height: 8, background: a.renk || '#fff', marginLeft: -4 }} />
                    </div>
                  ) : a.tip === 'gorsel' ? (
                    a.image_url
                      ? <img src={a.image_url} alt="" draggable={false}
                          style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
                      : <div className="w-full h-full bg-panel-accent/20 text-[9px]
                          flex items-center justify-center">görsel yok</div>
                  ) : (
                    <div style={{
                      color: a.renk || '#fff', textAlign: a.hiza || 'center',
                      lineHeight: 1.15, fontWeight: 800,
                      width: '100%', height: '100%', display: 'flex',
                      alignItems: 'center', overflow: 'hidden',
                      justifyContent: a.hiza === 'center' ? 'center'
                        : a.hiza === 'right' ? 'flex-end' : 'flex-start',
                    }}>
                      {/* Vitrindeki davranışın aynısı: "çerçeveyi doldur"
                          açıkken metin kutuya oturur — genişlik VE yükseklik
                          birlikte sınırlar */}
                      <DolduranYazi metin={a.varsayilan || a.etiket}
                        punto={(a.size || 0.1) * (tuvalPx.h || 400)}
                        doldur={a.otomatik_kucult !== false}
                        cerceveYuk={(a.h || 0) * (tuvalPx.h || 400)}
                        tavan={TAVAN_PUNTO * (tuvalPx.h || 400)} />
                    </div>
                  )}
                  {/* Boyutlandırma tutamağı */}
                  <span onPointerDown={e => basla(e, i, 'boyut')}
                    className="absolute -right-1.5 -bottom-1.5 w-3 h-3 rounded-full
                      bg-white border-2 border-panel-accent cursor-nwse-resize" />
                </div>
              ))}
            </div>
          </div>

          {/* Alan listesi + özellikler */}
          <div className="space-y-2">
            <div className="grid grid-cols-2 gap-1.5">
              <button onClick={() => ekle('yazi')} className="btn-ghost !py-1.5 text-xs"
                title="Müşteri metni yazar (isim, numara, süre…)">+ Yazı alanı</button>
              <button onClick={() => ekle('foto')} className="btn-ghost !py-1.5 text-xs"
                title="Müşteri görsel yükler, çerçeveye otomatik oturur">+ Müşteri fotoğrafı</button>
              <button onClick={() => ekle('gorsel')} className="btn-ghost !py-1.5 text-xs"
                title="Panelden yüklenen sabit öğe; müşteri açıp kapatır">+ Açılabilir öğe</button>
              <button onClick={() => ekle('ilerleme')} className="btn-ghost !py-1.5 text-xs"
                title="Spotify tarzı çubuk — nokta süreye göre kayar">+ İlerleme çubuğu</button>
            </div>

            <div className="space-y-1">
              {alanlar.map((a, i) => (
                <div key={i}
                  className={`flex items-center gap-1 px-2 py-1.5 rounded-lg border text-xs cursor-pointer ${
                    i === sel ? 'border-panel-accent' : 'border-panel-border'}`}
                  onClick={() => setSel(i)}>
                  <span>{{ yazi: '🔤', gorsel: '🖼️', foto: '📷', ilerleme: '⏱' }[a.tip]}</span>
                  <span className="truncate">{a.etiket}</span>
                  <button className="ml-auto text-red-300"
                    onClick={(e) => {
                      e.stopPropagation()
                      setAlanlar(ls => ls.filter((_, j) => j !== i))
                      setSel(0)
                    }}>×</button>
                </div>
              ))}
              {alanlar.length === 0 && (
                <p className="text-[11px] text-panel-muted">
                  Henüz alan yok. Müşterinin değiştirebileceği yazıları ve açıp
                  kapatabileceği öğeleri buradan ekleyin.
                </p>
              )}
            </div>

            {secili && (
              <div className="border-t border-panel-border pt-2 space-y-2">
                {/* Yaslama — alanı şablonun ortasına/kenarına oturtur.
                    Yazıda yükseklik puntodan doğduğu için dikeyde tek satır
                    yüksekliği (punto × 1.15) esas alınır. */}
                <div>
                  <div className="text-[11px] text-panel-muted mb-1">Yasla</div>
                  <div className="grid grid-cols-3 gap-1">
                    {[
                      ['sol', '⇤ Sola'], ['yatay', '↔ Yatay ortala'], ['sag', '⇥ Sağa'],
                      ['ust', '⇡ Üste'], ['dikey', '↕ Dikey ortala'], ['alt', '⇣ Alta'],
                    ].map(([yon, etiket]) => (
                      <button key={yon} type="button" onClick={() => yasla(yon)}
                        className="text-[11px] py-1.5 rounded-lg border border-panel-border
                          hover:border-panel-accent transition">
                        {etiket}
                      </button>
                    ))}
                    <button type="button" onClick={() => yasla('orta')}
                      className="col-span-3 text-[11px] py-1.5 rounded-lg border
                        border-panel-border hover:border-panel-accent transition">
                      ✛ Tam ortala
                    </button>
                  </div>
                </div>

                <label className="block text-[11px] text-panel-muted">
                  Müşteriye görünen etiket
                  <input value={secili.etiket} maxLength={60}
                    onChange={e => yamala({ etiket: e.target.value })}
                    className="input !py-1 !text-xs mt-0.5" />
                </label>
                <label className="block text-[11px] text-panel-muted">
                  Alan anahtarı (a-z, rakam, tire)
                  <input value={secili.key} maxLength={30}
                    onChange={e => yamala({ key: e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, '') })}
                    className="input !py-1 !text-xs mt-0.5 font-mono" />
                </label>

                <label className="flex items-center gap-2 text-[11px]">
                  <input type="checkbox" checked={!!secili.arkada}
                    onChange={e => yamala({ arkada: e.target.checked })} />
                  Şablonun ARKASINDA dursun
                  <span className="text-panel-muted" title="Şablon PNG'sinde delik/şeffaf alan varsa fotoğraf oradan görünür">ⓘ</span>
                </label>

                {secili.tip === 'foto' ? (
                  <>
                    <label className="block text-[11px] text-panel-muted">
                      Çerçeveye oturma
                      <select value={secili.sigdir || 'kapla'}
                        onChange={e => yamala({ sigdir: e.target.value })}
                        className="input !py-1 !text-xs mt-0.5">
                        <option value="kapla">Kapla (çerçeve dolar, taşan kırpılır)</option>
                        <option value="sigdir">Sığdır (tamamı görünür)</option>
                      </select>
                    </label>
                    <p className="text-[10px] text-panel-muted">
                      Müşteri buraya kendi görselini yükler; oranı bozulmadan çerçeveye
                      yerleşir. Şablonda bu alan delik/şeffaf ise “arkasında dursun”u işaretleyin.
                    </p>
                  </>
                ) : secili.tip === 'ilerleme' ? (
                  <>
                    <label className="block text-[11px] text-panel-muted">
                      Geçen süre alanı
                      <select value={secili.kaynak_gecen || ''}
                        onChange={e => yamala({ kaynak_gecen: e.target.value })}
                        className="input !py-1 !text-xs mt-0.5">
                        <option value="">— seçin —</option>
                        {alanlar.filter(x => x.tip === 'yazi').map(x => (
                          <option key={x.key} value={x.key}>{x.etiket}</option>
                        ))}
                      </select>
                    </label>
                    <label className="block text-[11px] text-panel-muted">
                      Toplam süre alanı
                      <select value={secili.kaynak_toplam || ''}
                        onChange={e => yamala({ kaynak_toplam: e.target.value })}
                        className="input !py-1 !text-xs mt-0.5">
                        <option value="">— seçin —</option>
                        {alanlar.filter(x => x.tip === 'yazi').map(x => (
                          <option key={x.key} value={x.key}>{x.etiket}</option>
                        ))}
                      </select>
                    </label>
                    <div className="flex gap-1.5">
                      <label className="block text-[11px] text-panel-muted flex-1">
                        Dolu renk
                        <input type="color" value={secili.renk || '#ffffff'}
                          onChange={e => yamala({ renk: e.target.value })}
                          className="w-full h-[26px] mt-0.5 rounded border border-panel-border bg-white" />
                      </label>
                      <label className="block text-[11px] text-panel-muted flex-1">
                        Boş renk
                        <input type="color" value={secili.renk_pasif || '#5a5a5a'}
                          onChange={e => yamala({ renk_pasif: e.target.value })}
                          className="w-full h-[26px] mt-0.5 rounded border border-panel-border bg-white" />
                      </label>
                    </div>
                    <div className="flex gap-1.5">
                      <label className="block text-[11px] text-panel-muted flex-1">
                        Çubuk kalınlığı
                        <input type="number" step="0.001" min="0.001" max="0.05"
                          value={secili.kalinlik ?? 0.004}
                          onChange={e => yamala({ kalinlik: Number(e.target.value) })}
                          className="input !py-1 !text-xs mt-0.5" />
                      </label>
                      <label className="block text-[11px] text-panel-muted flex-1">
                        Nokta yarıçapı
                        <input type="number" step="0.002" min="0.002" max="0.06"
                          value={secili.boyut ?? 0.012}
                          onChange={e => yamala({ boyut: Number(e.target.value) })}
                          className="input !py-1 !text-xs mt-0.5" />
                      </label>
                    </div>
                    <p className="text-[10px] text-panel-muted">
                      Nokta, müşterinin yazdığı geçen/toplam süreye göre kendi kayar
                      (“1:23” ya da saniye olarak “83” yazılabilir).
                    </p>
                  </>
                ) : secili.tip === 'yazi' ? (
                  <>
                    <label className="block text-[11px] text-panel-muted">
                      Varsayılan metin
                      <input value={secili.varsayilan || ''} maxLength={40}
                        onChange={e => yamala({ varsayilan: e.target.value })}
                        className="input !py-1 !text-xs mt-0.5" />
                    </label>
                    <div className="flex gap-1.5">
                      <label className="block text-[11px] text-panel-muted flex-1">
                        En fazla karakter
                        <input type="number" min={1} max={40} value={secili.max || 12}
                          onChange={e => yamala({ max: Number(e.target.value) })}
                          className="input !py-1 !text-xs mt-0.5" />
                      </label>
                      <label className="block text-[11px] text-panel-muted flex-1">
                        Renk
                        <input type="color" value={secili.renk || '#ffffff'}
                          onChange={e => yamala({ renk: e.target.value })}
                          className="w-full h-[26px] mt-0.5 rounded border border-panel-border bg-white" />
                      </label>
                    </div>
                    <label className="block text-[11px] text-panel-muted">
                      Yazı tipi (müşteride bu font kullanılır)
                      <select value={secili.font || 'anton'}
                        onChange={e => yamala({ font: e.target.value })}
                        className="input !py-1 !text-xs mt-0.5">
                        {['anton','russo','bebas','staatliches','montserrat','poppins','oswald',
                          'bangers','bungee','alfaslab','gotik','pirata','marker','sprey',
                          'playfair','lobster','monoton','righteous','elite','dancing',
                          'caveat','greatvibes','pacifico','creepster','mono'].map(f => (
                          <option key={f} value={f}>{f}</option>
                        ))}
                      </select>
                    </label>
                    <label className="block text-[11px] text-panel-muted">
                      Hizalama
                      <select value={secili.hiza || 'center'}
                        onChange={e => yamala({ hiza: e.target.value })}
                        className="input !py-1 !text-xs mt-0.5">
                        <option value="left">Sola</option>
                        <option value="center">Ortalı</option>
                        <option value="right">Sağa</option>
                      </select>
                    </label>
                    <label className="flex items-start gap-2 text-[11px]">
                      <input type="checkbox" checked={secili.otomatik_kucult !== false} className="mt-0.5"
                        onChange={e => yamala({ otomatik_kucult: e.target.checked })} />
                      <span>
                        <b>Çerçeveyi doldur</b> — yazı çerçeveye oturur: kısa
                        metin BÜYÜR, uzun metin küçülür. Punto çerçevenin hem
                        genişliğiyle hem YÜKSEKLİĞİYLE sınırlıdır, yani tek
                        haneli metin de dışarı taşmaz. Kapalıyken punto
                        çerçeve yüksekliğinden hesaplanan sabit değerde kalır.
                      </span>
                    </label>
                    <div className="text-[10px] text-panel-muted">
                      Çerçeve: {((secili.w || 0.6) * 100).toFixed(0)}% ×
                      {' '}{(((secili.h ?? (secili.size || 0.1) * 1.3)) * 100).toFixed(1)}%
                      · kutuyu sağ alt köşeden sürükleyerek çerçeveyi
                      büyütüp küçültün. Metin bu çerçeveye ortalanır.
                    </div>
                  </>
                ) : (
                  <>
                    <label className="flex items-center gap-2 text-[11px]">
                      <input type="checkbox" checked={secili.varsayilan !== false}
                        onChange={e => yamala({ varsayilan: e.target.checked })} />
                      Başlangıçta açık gelsin
                    </label>
                    <button onClick={() => gorselRef.current?.click()} disabled={busy}
                      className="btn-ghost !py-1.5 text-xs w-full disabled:opacity-40">
                      {secili.image_url || secili.image_path ? 'Görseli değiştir' : 'Görsel yükle (şeffaf PNG)'}
                    </button>
                    <input ref={gorselRef} type="file" accept="image/png,image/webp"
                      className="hidden" onChange={e => alanGorseliYukle(e.target.files?.[0])} />
                  </>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="flex gap-2 mt-4">
          <button onClick={onClose} className="btn-ghost !py-2 text-sm">Vazgeç</button>
          <button onClick={kaydet} disabled={busy}
            className="btn !py-2 text-sm flex-1 disabled:opacity-40">
            {busy ? 'Kaydediliyor…' : 'Alanları Kaydet'}
          </button>
        </div>
      </div>
    </div>
  )
}
