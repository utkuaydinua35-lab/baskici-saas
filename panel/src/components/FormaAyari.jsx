import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { desenSekilleri } from '../lib/formaDesen'

// Forma tasarlayıcı ayarı — kısıtlı şablonda müşteriye hangi seçeneklerin
// açılacağı: desenler, renk takımları, yazı tipleri, amblemler, yasak kelimeler.
// Açıkken şablonun zemini sabit görsel yerine KODLA çizilir; yerleşim (isim,
// numara, logo konumu) yukarıdaki alanlardan gelir ve müşteri değiştiremez.
// Doğrulama sunucuda: backend/app/services/forma.py → yapilandirma_temizle.

const FONT_AD = {
  anton: 'Anton', bebas: 'Bebas Neue', oswald: 'Oswald', russo: 'Russo One',
  staatliches: 'Staatliches', montserrat: 'Montserrat', bungee: 'Tabela', alfaslab: 'Kalın Serif',
  kolej: 'Kolej (forma)', poppins: 'Poppins', bangers: 'Çizgi Roman', righteous: 'Righteous', pirata: 'Gotik İnce',
}

export const BOS_FORMA = (s) => ({
  aktif: true,
  desenler: s.desenler.map(d => d.key),
  paletler: s.paletler.map(p => ({ ...p, renkler: [...p.renkler] })),
  serbest_renk: true,
  fontlar: [...s.fontlar],
  amblemler: s.amblemler.map(a => a.key),
  ozel_amblemler: [],
  amblem_kutu: { x: 0.62, y: 0.30, w: 0.24, h: 0.12 },
  varsayilan: {
    desen: 'dikey', yogunluk: 'orta', renkler: [...s.paletler[0].renkler],
    font: 'anton', yazi_renk: '#ffffff', kontur: '', kontur_kalinlik: 'orta', amblem: 'kalkan', amblem_renk: '#ffffff',
    parlama: '',
  },
  doku: 'kumas',
  efekt: 'yok',
  kilitli: false,
  yasak: true,
  yasak_ek: [],
})

export function DesenSvg({ desen, yogunluk, renkler, className = 'w-full h-full block' }) {
  return (
    <svg viewBox="0 0 1 1" preserveAspectRatio="none" className={className} aria-hidden>
      <rect x="0" y="0" width="1" height="1" fill={renkler[0]} />
      {desenSekilleri(desen, yogunluk).map((c, i) => (
        <polygon key={i} fill={renkler[Math.min(c.renk, 2)]}
          points={c.nokta.map(([x, y]) => `${x},${y}`).join(' ')} />
      ))}
    </svg>
  )
}

export function AmblemMaske({ url, renk = '#fff', className = '', style = {} }) {
  const maske = `url("${url}") center / contain no-repeat`
  return <span className={`block ${className}`}
    style={{ background: renk, WebkitMask: maske, mask: maske, ...style }} />
}

export default function FormaAyari({ overlayId, forma, onChange, onAmblemEklendi, kisitli, onProDuzen }) {
  const [sec, setSec] = useState(null)        // sabit listeler (desen, hazır amblem…)
  const [err, setErr] = useState('')
  const [yukleniyor, setYukleniyor] = useState(false)
  const [yeniKelime, setYeniKelime] = useState('')
  const dosyaRef = useRef(null)

  useEffect(() => {
    api.get('/api/case-templates/forma/secenekler').then(setSec).catch(() => {})
  }, [])

  if (!sec) return null
  const f = forma
  const yama = (p) => onChange({ ...f, ...p })
  const vYama = (p) => onChange({ ...f, varsayilan: { ...f.varsayilan, ...p } })
  const degistir = (liste, k) => liste.includes(k) ? liste.filter(x => x !== k) : [...liste, k]
  const tumAmblemler = [...sec.amblemler, ...(f?.ozel_amblemler || []).map(a => ({ ...a, ozel: true }))]

  const amblemYukle = async (file) => {
    if (!file) return
    setYukleniyor(true); setErr('')
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('ad', file.name.replace(/\.[^.]+$/, '').slice(0, 30))
      const r = await api.postForm(`/api/case-templates/overlays/${overlayId}/amblem`, fd)
      onAmblemEklendi(r.forma)
    } catch (e) {
      setErr(typeof e?.detail === 'string' ? e.detail : 'Amblem yüklenemedi')
    } finally { setYukleniyor(false); if (dosyaRef.current) dosyaRef.current.value = '' }
  }

  const baslik = 'text-[11px] font-semibold text-panel-ink mb-1.5'
  const cip = (aktif) => `px-2.5 py-1 rounded-full text-[11px] border transition ${aktif
    ? 'border-panel-accent bg-emerald-500/10 text-emerald-300'
    : 'border-panel-border text-panel-muted hover:text-panel-ink'}`

  return (
    <div className="mt-4 rounded-xl border border-panel-border p-3 space-y-3">
      <label className="flex items-start gap-2 text-xs">
        <input type="checkbox" checked={!!f?.aktif} disabled={!kisitli} className="mt-0.5"
          onChange={e => onChange(e.target.checked ? (f?.desenler ? { ...f, aktif: true } : BOS_FORMA(sec)) : (f ? { ...f, aktif: false } : null))} />
        <span>
          <b>👕 Forma tasarlayıcı</b> — müşteri deseni, renkleri, yazı tipini ve amblemi kendisi seçer.
          Zemin yüklediğiniz görsel yerine <b>kodla çizilir</b> (her renk/desen baskıya hazır çıkar);
          yukarıdaki alanların konumu aynen kalır.
          {!kisitli && <span className="block text-amber-300 mt-0.5">Önce “Kısıtlı şablon”u açın.</span>}
        </span>
      </label>
      {err && <p className="text-xs text-red-300">{err}</p>}

      {f?.aktif && (
        <div className="space-y-3.5">
          <div>
            <div className={baslik}>Görünüm stili</div>
            <div className="grid sm:grid-cols-2 gap-2">
              {[['klasik', 'Klasik', 'Yazı tipi, kontur, doku ve efektleri aşağıdan tek tek seçersiniz.'],
                ['pro', 'Forma Pro', 'Örgülü kumaş, kenarlarda fırça darbeleri, yazının arkasında sıcak ışık; kolej harfli kavisli isim, çift konturlu uzun numara. Müşteri yazıyı yalnız siyah ya da beyaz seçer; renkler değişse de efekt aynı kalır.']]
                .map(([v, ad, acik]) => (
                  <button key={v} type="button" onClick={() => yama({ stil: v })}
                    className={`text-left rounded-xl border p-2.5 text-[11px] ${(f.stil || 'klasik') === v
                      ? 'border-panel-accent bg-emerald-500/10' : 'border-panel-border'}`}>
                    <b className="text-xs">{ad}</b>
                    <span className="block text-panel-muted mt-0.5">{acik}</span>
                  </button>
                ))}
            </div>
            {f.stil === 'pro' && onProDuzen && (
              <div className="mt-2 flex items-center gap-2 flex-wrap text-[11px]">
                <button type="button" onClick={onProDuzen} className="btn-ghost !py-1 text-xs">
                  📐 Pro düzenini alanlara uygula
                </button>
                <span className="text-panel-muted">
                  İsim yay çizerek üstte, numara altında (referanstaki yerleşim). Rakamlı varsayılanı olan alan numara sayılır.
                  Kaydetmeden önce yukarıdaki önizlemede görebilir, beğenmezseniz Vazgeç'e basabilirsiniz.
                </span>
              </div>
            )}
          </div>
          <label className="flex items-start gap-2 text-xs rounded-xl bg-panel-input p-2.5">
            <input type="checkbox" checked={!!f.kilitli} className="mt-0.5"
              onChange={e => yama({ kilitli: e.target.checked })} />
            <span>
              <b>Hazır ürün</b> — müşteri deseni, rengi, yazı tipini ve amblemi <b>değiştiremez</b>;
              yalnız yazı alanlarını (isim, numara) doldurur ve isterse yazıya <b>kontur</b> ekler.
              Tasarım aşağıdaki “Başlangıç görünümü”nden çizilir.
              <span className="block text-panel-muted mt-0.5">
                Kapalıyken müşteri her şeyi kendisi seçer (“kendi formanı tasarla” ürünü). Aynı şablonu
                “Kopyala” ile çoğaltıp her kopyada renkleri değiştirerek Sarı-Kırmızı, Siyah-Beyaz… ürünlerini hazırlayın.
              </span>
            </span>
          </label>
          <div>
            <div className={baslik}>Müşteriye sunulan desenler</div>
            <div className="grid grid-cols-5 sm:grid-cols-9 gap-1.5">
              {sec.desenler.map(d => {
                const acik = f.desenler.includes(d.key)
                return (
                  <button key={d.key} type="button" title={d.ad}
                    onClick={() => {
                      const yeni = degistir(f.desenler, d.key)
                      if (yeni.length === 0) return           // en az bir desen kalmalı
                      const v = yeni.includes(f.varsayilan.desen) ? {} : { desen: yeni[0] }
                      onChange({ ...f, desenler: sec.desenler.map(x => x.key).filter(k => yeni.includes(k)),
                        varsayilan: { ...f.varsayilan, ...v } })
                    }}
                    className={`rounded-lg border overflow-hidden text-[9px] ${acik
                      ? 'border-panel-accent' : 'border-panel-border opacity-40'}`}>
                    <div className="aspect-[1/1.5]">
                      <DesenSvg desen={d.key} yogunluk="orta" renkler={f.varsayilan.renkler} />
                    </div>
                    <div className="px-0.5 py-0.5 truncate">{d.ad}</div>
                  </button>
                )
              })}
            </div>
          </div>

          <div>
            <div className={baslik}>Hazır renk takımları
              <span className="font-normal text-panel-muted"> — adlar RENK adı olsun, kulüp adı yazmayın</span>
            </div>
            <div className="space-y-1.5">
              {f.paletler.map((p, i) => (
                <div key={i} className="flex items-center gap-1.5">
                  <input className="input !py-1 !text-xs flex-1 min-w-0" maxLength={30} value={p.ad}
                    onChange={e => yama({ paletler: f.paletler.map((x, j) => j === i ? { ...x, ad: e.target.value } : x) })} />
                  {[0, 1, 2].map(r => (
                    <input key={r} type="color" value={p.renkler[r] || '#ffffff'}
                      title={['Zemin', 'Desen', 'Çizgi'][r]}
                      onChange={e => yama({ paletler: f.paletler.map((x, j) => j === i
                        ? { ...x, renkler: x.renkler.map((c, k) => k === r ? e.target.value : c) } : x) })}
                      className="w-7 h-7 rounded border border-panel-border bg-transparent p-0 shrink-0" />
                  ))}
                  <button type="button" title="Başlangıç rengi yap" className="text-[10px] text-panel-accent shrink-0 px-1"
                    onClick={() => vYama({ renkler: [...p.renkler] })}>varsayılan</button>
                  <button type="button" className="text-red-300 px-1 shrink-0" title="Takımı kaldır"
                    onClick={() => yama({ paletler: f.paletler.filter((_, j) => j !== i) })}>×</button>
                </div>
              ))}
              {f.paletler.length < 12 && (
                <button type="button" className="btn-ghost !py-1 text-[11px]"
                  onClick={() => yama({ paletler: [...f.paletler, { ad: 'Yeni takım', renkler: ['#1e3a8a', '#f2f2f2', '#facc15'] }] })}>
                  + Renk takımı ekle
                </button>
              )}
            </div>
            <label className="flex items-center gap-2 text-[11px] mt-2">
              <input type="checkbox" checked={f.serbest_renk !== false}
                onChange={e => yama({ serbest_renk: e.target.checked })} />
              Müşteri kendi rengini de seçebilsin (kapalıysa yalnız bu takımlar)
            </label>
          </div>

          {f.stil !== 'pro' && <div>
            <div className={baslik}>Yazı tipleri</div>
            <div className="flex flex-wrap gap-1.5">
              {[...new Set([...sec.fontlar, ...Object.keys(FONT_AD)])].map(k => (
                <button key={k} type="button" className={cip(f.fontlar.includes(k))}
                  onClick={() => {
                    const yeni = degistir(f.fontlar, k)
                    if (yeni.length === 0) return
                    onChange({ ...f, fontlar: yeni,
                      varsayilan: { ...f.varsayilan, font: yeni.includes(f.varsayilan.font) ? f.varsayilan.font : yeni[0] } })
                  }}>
                  {FONT_AD[k] || k}
                </button>
              ))}
            </div>
          </div>}

          <div>
            <div className={baslik}>Amblemler
              <span className="font-normal text-panel-muted"> — genel şekiller; kulüp arması yüklemeyin</span>
            </div>
            <div className="grid grid-cols-6 sm:grid-cols-10 gap-1.5">
              {tumAmblemler.map(a => {
                const acik = f.amblemler.includes(a.key)
                return (
                  <div key={a.key} className="relative">
                    <button type="button" title={a.ad}
                      onClick={() => {
                        const yeni = degistir(f.amblemler, a.key)
                        onChange({ ...f, amblemler: yeni,
                          varsayilan: { ...f.varsayilan, amblem: yeni.includes(f.varsayilan.amblem) ? f.varsayilan.amblem : '' } })
                      }}
                      className={`w-full aspect-square rounded-lg border p-1.5 ${acik
                        ? 'border-panel-accent bg-panel-input' : 'border-panel-border opacity-35'}`}>
                      <AmblemMaske url={a.url} className="w-full h-full" />
                    </button>
                    {a.ozel && (
                      <button type="button" title="Yüklenen amblemi sil"
                        onClick={() => onChange({ ...f,
                          ozel_amblemler: f.ozel_amblemler.filter(x => x.key !== a.key),
                          amblemler: f.amblemler.filter(k => k !== a.key),
                          varsayilan: { ...f.varsayilan, amblem: f.varsayilan.amblem === a.key ? '' : f.varsayilan.amblem } })}
                        className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-red-500 text-white text-[10px] leading-none">×</button>
                    )}
                  </div>
                )
              })}
              <button type="button" disabled={yukleniyor} onClick={() => dosyaRef.current?.click()}
                title="Kendi amblemini yükle (saydam zeminli PNG)"
                className="aspect-square rounded-lg border border-dashed border-panel-border text-lg text-panel-muted hover:text-panel-ink disabled:opacity-40">
                {yukleniyor ? '…' : '+'}
              </button>
              <input ref={dosyaRef} type="file" accept="image/png,image/webp,image/jpeg" className="hidden"
                onChange={e => amblemYukle(e.target.files?.[0])} />
            </div>
            <p className="text-[10px] text-panel-muted mt-1">
              “+” ile kendi amblemini ekle: saydam zeminli tek renk PNG en iyi sonucu verir — şekil maskeye
              çevrilir, rengini müşteri seçer. Yükleme hemen kaydedilir; silme “Alanları Kaydet” ile geçerli olur.
            </p>
            <p className="text-[10px] text-amber-300 mt-2">
              Amblemin yeri: yukarıdaki önizlemede sarı kesikli kutuyu <b>sürükleyin</b>, köşesinden
              boyutlandırın — numara ve isimle üst üste gelmeyecek bir yere koyun.
            </p>
            <div className="grid grid-cols-4 gap-1.5 mt-1.5">
              {[['x', 'Sol'], ['y', 'Üst'], ['w', 'Genişlik'], ['h', 'Yükseklik']].map(([k, ad]) => (
                <label key={k} className="text-[10px] text-panel-muted">
                  Amblem {ad.toLowerCase()} %
                  <input type="number" min={k === 'w' || k === 'h' ? 3 : 0} max={100} step={1}
                    value={Math.round((f.amblem_kutu[k] || 0) * 100)}
                    onChange={e => yama({ amblem_kutu: { ...f.amblem_kutu, [k]: Math.max(0, Math.min(100, Number(e.target.value) || 0)) / 100 } })}
                    className="input !py-1 !text-xs mt-0.5" />
                </label>
              ))}
            </div>
          </div>

          {f.stil !== 'pro' && <div>
            <div className={baslik}>Zengin görünüm <span className="font-normal text-panel-muted">— gerçek forma hissi (müşteri değiştiremez)</span></div>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[11px]">
              <label className="flex items-center gap-1.5">
                Zemin
                <select className="input !py-0.5 !text-xs !w-auto" value={f.doku || 'kumas'}
                  onChange={e => yama({ doku: e.target.value })}>
                  <option value="yok">Düz renk</option><option value="kumas">Kumaş dokusu</option>
                </select>
              </label>
              <label className="flex items-center gap-1.5">
                Efekt
                <select className="input !py-0.5 !text-xs !w-auto" value={f.efekt || 'yok'}
                  onChange={e => yama({ efekt: e.target.value })}>
                  <option value="yok">Yok</option><option value="firca">Fırça darbeleri</option>
                </select>
              </label>
              <label className="flex items-center gap-1.5">
                <input type="checkbox" checked={!!f.varsayilan.parlama}
                  onChange={e => vYama({ parlama: e.target.checked ? '#ffffff' : '' })} />Yazı parlaması
                {f.varsayilan.parlama && (
                  <input type="color" value={f.varsayilan.parlama} onChange={e => vYama({ parlama: e.target.value })}
                    className="w-6 h-6 rounded border border-panel-border bg-transparent p-0" />
                )}
              </label>
            </div>
            <p className="text-[10px] text-panel-muted mt-1.5">
              İsim alanına kavis, numaraya "çerçeveye esnet" vermek için yukarıdan alanı seçin.
              Doku, fırça ve parlama yukarıdaki kutuda görünmez — en alttaki <b>gerçek önizleme</b>ye bakın.
            </p>
          </div>}

          <div>
            <div className={baslik}>Başlangıç görünümü <span className="font-normal text-panel-muted">— müşteri sayfayı açtığında</span></div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5 text-[10px] text-panel-muted">
              <label>Desen
                <select className="input !py-1 !text-xs mt-0.5" value={f.varsayilan.desen}
                  onChange={e => vYama({ desen: e.target.value })}>
                  {sec.desenler.filter(d => f.desenler.includes(d.key)).map(d => <option key={d.key} value={d.key}>{d.ad}</option>)}
                </select>
              </label>
              <label>Kalınlık
                <select className="input !py-1 !text-xs mt-0.5" value={f.varsayilan.yogunluk}
                  onChange={e => vYama({ yogunluk: e.target.value })}>
                  <option value="ince">İnce</option><option value="orta">Orta</option><option value="kalin">Kalın</option>
                </select>
              </label>
              <label>Yazı tipi
                <select className="input !py-1 !text-xs mt-0.5" value={f.varsayilan.font}
                  onChange={e => vYama({ font: e.target.value })}>
                  {f.fontlar.map(k => <option key={k} value={k}>{FONT_AD[k] || k}</option>)}
                </select>
              </label>
              <label>Amblem
                <select className="input !py-1 !text-xs mt-0.5" value={f.varsayilan.amblem || ''}
                  onChange={e => vYama({ amblem: e.target.value })}>
                  <option value="">Yok</option>
                  {tumAmblemler.filter(a => f.amblemler.includes(a.key)).map(a => <option key={a.key} value={a.key}>{a.ad}</option>)}
                </select>
              </label>
            </div>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 mt-2 text-[11px]">
              {[0, 1, 2].map(r => (
                <label key={r} className="flex items-center gap-1.5">
                  <input type="color" value={f.varsayilan.renkler[r]}
                    onChange={e => vYama({ renkler: f.varsayilan.renkler.map((c, k) => k === r ? e.target.value : c) })}
                    className="w-6 h-6 rounded border border-panel-border bg-transparent p-0" />
                  {['Zemin', 'Desen', 'Çizgi'][r]}
                </label>
              ))}
              <label className="flex items-center gap-1.5">
                <input type="color" value={f.varsayilan.yazi_renk} onChange={e => vYama({ yazi_renk: e.target.value })}
                  className="w-6 h-6 rounded border border-panel-border bg-transparent p-0" />Yazı
              </label>
              <label className="flex items-center gap-1.5">
                <input type="checkbox" checked={!!f.varsayilan.kontur}
                  onChange={e => vYama({ kontur: e.target.checked ? '#111111' : '' })} />Kontur
                {f.varsayilan.kontur && (
                  <input type="color" value={f.varsayilan.kontur} onChange={e => vYama({ kontur: e.target.value })}
                    className="w-6 h-6 rounded border border-panel-border bg-transparent p-0" />
                )}
              </label>
              <label className="flex items-center gap-1.5">
                Kontur kalınlığı
                <select className="input !py-0.5 !text-xs !w-auto" value={f.varsayilan.kontur_kalinlik || 'orta'}
                  onChange={e => vYama({ kontur_kalinlik: e.target.value })}>
                  <option value="ince">İnce</option><option value="orta">Orta</option><option value="kalin">Kalın</option>
                </select>
              </label>
              <label className="flex items-center gap-1.5">
                <input type="color" value={f.varsayilan.amblem_renk} onChange={e => vYama({ amblem_renk: e.target.value })}
                  className="w-6 h-6 rounded border border-panel-border bg-transparent p-0" />Amblem
              </label>
            </div>
          </div>

          <div>
            <label className="flex items-start gap-2 text-[11px]">
              <input type="checkbox" checked={f.yasak !== false} className="mt-0.5"
                onChange={e => yama({ yasak: e.target.checked })} />
              <span>
                <b>Kulüp/marka adı engeli</b> — müşteri isim alanına kulüp adı yazarsa tasarım kaydedilmez
                ({sec.yasak_yerlesik} yerleşik ad: Türkiye ve Avrupa kulüpleri, FIFA/UEFA; “G.S.”, “Galata Saray”,
                “G4L4T4S4R4Y” gibi kaçamaklar da yakalanır).
              </span>
            </label>
            {f.yasak !== false && (
              <div className="mt-1.5">
                <div className="flex flex-wrap gap-1 mb-1.5">
                  {(f.yasak_ek || []).map(k => (
                    <span key={k} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-panel-input text-[11px]">
                      {k}
                      <button type="button" className="text-red-300"
                        onClick={() => yama({ yasak_ek: f.yasak_ek.filter(x => x !== k) })}>×</button>
                    </span>
                  ))}
                </div>
                <form className="flex gap-1.5" onSubmit={e => {
                  e.preventDefault()
                  const k = yeniKelime.trim()
                  if (k.length >= 2 && !(f.yasak_ek || []).includes(k)) yama({ yasak_ek: [...(f.yasak_ek || []), k] })
                  setYeniKelime('')
                }}>
                  <input className="input !py-1 !text-xs flex-1" maxLength={40} value={yeniKelime}
                    onChange={e => setYeniKelime(e.target.value)} placeholder="Engellenecek ek kelime (ör. bir takma ad)" />
                  <button className="btn-ghost !py-1 text-[11px]">Ekle</button>
                </form>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
