// Forma şablonunun GERÇEK önizlemesi ve ürün kapak görseli.
//
// Kumaş dokusu, fırça darbesi, kavisli yazı ve parlama tarayıcıda birebir
// taklit edilemez: önizlemeyi baskıyı üreten sunucu kodu çizer (kaydedilmemiş
// ayarla da). "Kapak görseli" aynı çizimi kılıf görseline giydirir ve tek
// tıkla şablonun bağlı olduğu ürünlere fotoğraf olarak ekler.
import { useEffect, useRef, useState } from 'react'
import { api, fetchYetkili } from '../lib/api'

export default function SablonKapak({ overlayId, alanlar, forma, templates = [], kilifId, degisti }) {
  const [gorunum, setGorunum] = useState('kapak')      // kapak | baski
  const [kilif, setKilif] = useState(kilifId || '')
  const [url, setUrl] = useState('')
  const [ciziliyor, setCiziliyor] = useState(false)
  const [urunler, setUrunler] = useState(null)
  const [secili, setSecili] = useState([])
  const [oneAl, setOneAl] = useState(true)
  const [busy, setBusy] = useState(false)
  const [mesaj, setMesaj] = useState('')
  const [eklenen, setEklenen] = useState([])           // geri alınabilir son ekleme
  const sira = useRef(0)

  const govde = JSON.stringify({
    alanlar: alanlar.map(({ image_url, ...a }) => a),
    forma: forma?.aktif ? { ...forma, ozel_amblemler: (forma.ozel_amblemler || []).map(({ url: _u, ...a }) => a) } : { aktif: false },
    template_id: kilif || null, w: gorunum === 'kapak' ? 640 : 420, kapak: gorunum === 'kapak',
  })

  // Ayar değiştikçe yeniden çiz (yazarken her tuşta istek atmamak için bekletilir)
  useEffect(() => {
    const no = ++sira.current
    const z = setTimeout(async () => {
      setCiziliyor(true)
      try {
        const res = await fetchYetkili(`/api/case-templates/overlays/${overlayId}/onizleme`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: govde,
        })
        if (!res.ok) throw new Error()
        const blob = await res.blob()
        if (no !== sira.current) return
        setUrl(eski => { if (eski) URL.revokeObjectURL(eski); return URL.createObjectURL(blob) })
      } catch { /* önizleme çizilemedi: eskisi kalır */ }
      finally { if (no === sira.current) setCiziliyor(false) }
    }, 450)
    return () => clearTimeout(z)
  }, [govde, overlayId])

  const urunleriYukle = () =>
    api.get(`/api/case-templates/overlays/${overlayId}/kapak-urunleri`)
      .then(d => { setUrunler(d.urunler || []); setSecili((d.urunler || []).map(u => u.id)) })
      .catch(() => setUrunler([]))
  useEffect(() => { urunleriYukle() }, [overlayId])   // eslint-disable-line react-hooks/exhaustive-deps

  const ekle = async () => {
    setBusy(true); setMesaj('')
    try {
      const d = await api.post(`/api/case-templates/overlays/${overlayId}/kapak`,
        { product_ids: secili, template_id: kilif || null, one_al: oneAl })
      setEklenen(d.eklenen || [])
      setMesaj(`${d.eklenen.length} ürüne kapak görseli eklendi ✓`)
      urunleriYukle()
    } catch (e) {
      setMesaj(typeof e?.detail === 'string' ? e.detail : 'Eklenemedi')
    } finally { setBusy(false) }
  }

  const geriAl = async () => {
    setBusy(true)
    try {
      for (const e of eklenen) await api.del(`/api/catalog/images/${e.image_id}`).catch(() => {})
      setEklenen([]); setMesaj('Eklenen görseller kaldırıldı')
      urunleriYukle()
    } finally { setBusy(false) }
  }

  const sekme = (k, ad) => (
    <button type="button" onClick={() => setGorunum(k)}
      className={`px-2.5 py-1 rounded-full text-[11px] border ${gorunum === k
        ? 'bg-brand-600 border-brand-600 text-white' : 'border-panel-border text-panel-muted'}`}>
      {ad}
    </button>
  )

  return (
    <div className="mt-4 rounded-xl border border-panel-border p-3">
      <div className="text-xs font-semibold mb-2">Gerçek önizleme ve ürün kapak görseli</div>
      <div className="grid sm:grid-cols-[220px_1fr] gap-3">
        <div>
          <div className="flex gap-1.5 mb-2">{sekme('kapak', 'Kılıf üstünde')}{sekme('baski', 'Baskı dosyası')}</div>
          <div className={`rounded-lg overflow-hidden bg-panel-bg border border-panel-border flex items-center justify-center min-h-[200px] transition-opacity ${ciziliyor ? 'opacity-60' : ''}`}>
            {url ? <img src={url} alt="Önizleme" className="max-w-full max-h-[340px] block" />
              : <span className="text-[11px] text-panel-muted">Çiziliyor…</span>}
          </div>
          {templates.length > 1 && (
            <label className="block text-[10px] text-panel-muted mt-2">
              Kılıf
              <select value={kilif} onChange={e => setKilif(e.target.value)} className="input !py-1 !text-xs mt-0.5">
                <option value="">Şablonun kılıfı</option>
                {templates.map(t => <option key={t.id} value={t.id}>{t.label}</option>)}
              </select>
            </label>
          )}
          {url && (
            <a href={url} download={gorunum === 'kapak' ? 'kapak.jpg' : 'onizleme.jpg'}
              className="btn-ghost !py-1 text-[11px] w-full mt-2 block text-center">Görseli indir</a>
          )}
        </div>

        <div className="text-[11px]">
          <p className="text-panel-muted mb-2">
            Soldaki görsel baskıyı üreten kodla çizilir: müşterinin göreceği ve basılacak olan budur.
            Aşağıdan seçtiğiniz ürünlere <b>fotoğraf olarak</b> eklenir; ürünün mevcut görsellerine dokunulmaz.
          </p>
          {urunler === null ? <div className="text-panel-muted">Ürünler yükleniyor…</div>
            : urunler.length === 0 ? (
              <div className="text-amber-300">
                Bu şablon henüz bir ürüne bağlı değil. Ürün düzenleme ekranında "Hazır tasarım modülleri"nden
                bu şablonu seçin; sonra burada görünür. (Görseli indirip elle de yükleyebilirsiniz.)
              </div>
            ) : (
              <>
                <div className="max-h-40 overflow-y-auto rounded-lg border border-panel-border divide-y divide-panel-border">
                  {urunler.map(u => (
                    <label key={u.id} className="flex items-center gap-2 px-2 py-1.5 cursor-pointer">
                      <input type="checkbox" checked={secili.includes(u.id)}
                        onChange={() => setSecili(s => s.includes(u.id) ? s.filter(x => x !== u.id) : [...s, u.id])} />
                      <span className="flex-1 truncate">{u.title}</span>
                      <span className="text-panel-muted shrink-0">{u.gorsel_sayisi} görsel{u.status !== 'active' ? ' · taslak' : ''}</span>
                    </label>
                  ))}
                </div>
                <label className="flex items-center gap-2 mt-2">
                  <input type="checkbox" checked={oneAl} onChange={e => setOneAl(e.target.checked)} />
                  İlk görsel (kapak) yap — kapalıysa sona eklenir
                </label>
                {degisti && (
                  <div className="text-amber-300 mt-2">
                    Kaydedilmemiş değişiklik var: ürüne eklenen görsel <b>kayıtlı</b> hâlden üretilir. Önce "Kaydet, açık kalsın"a basın.
                  </div>
                )}
                <button type="button" onClick={ekle} disabled={busy || degisti || secili.length === 0}
                  className="btn !py-1.5 text-xs mt-2 disabled:opacity-40">
                  {busy ? 'Ekleniyor…' : `Kapak görselini ${secili.length} ürüne ekle`}
                </button>
              </>
            )}
          {mesaj && (
            <div className="mt-2 flex items-center gap-2">
              <span>{mesaj}</span>
              {eklenen.length > 0 && (
                <button type="button" onClick={geriAl} disabled={busy} className="underline text-brand-400">Geri al</button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
