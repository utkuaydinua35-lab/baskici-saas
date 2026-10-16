// Koleksiyon görseli yardımcısı — Gemini için hazırlık.
//
// Claude API görsel ÜRETEMEZ (çıktısı yalnız metin); görsel üretimi mağazanın
// Gemini üyeliğinde yapılır. Burada: koleksiyondan 3-5 ürün seçilir, ürün
// görselleri indirilir ve Gemini'ye yapıştırılacak prompt hazırlanır. API
// çağrısı yok, maliyet yok. Üretilen görsel "Sayfa görünümü"nden yüklenir.
import { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { api } from '../lib/api'

const SAHNELER = {
  pembe: 'a dreamy soft-pink glitter backdrop with tiny floating sparkles, the cases standing on a fluffy white surface, pastel diffused lighting',
  bej: 'a warm beige interior: soft linen curtains in the background, dried pampas grass in a ceramic vase, cases standing on a light marble tabletop, gentle afternoon sunlight',
  mermer: 'a clean minimalist studio with a white marble surface and seamless light-grey background, soft studio lighting with gentle realistic shadows',
  sonbahar: 'a cozy autumn scene: warm wooden table with scattered orange and brown leaves, soft golden-hour light, blurred warm background',
  gece: 'a moody dark backdrop with subtle neon rim light in the collection colors, glossy black reflective surface',
}
const SAHNE_AD = { pembe: 'Pembe parıltı', bej: 'Bej perde + pampas', mermer: 'Mermer stüdyo', sonbahar: 'Sonbahar', gece: 'Gece / neon', ozel: 'Kendi tarifim' }
const ORANLAR = [['4:5', 'Dikey 4:5 (kart)'], ['1:1', 'Kare'], ['16:9', 'Yatay 16:9 (banner)'], ['9:16', 'Hikâye 9:16']]

export default function GeminiKoleksiyonGorseli({ collection, onClose }) {
  const [urunler, setUrunler] = useState(null)
  const [secili, setSecili] = useState([])
  const [sahne, setSahne] = useState('mermer')
  const [ozelSahne, setOzelSahne] = useState('')
  const [oran, setOran] = useState('4:5')
  const [kopya, setKopya] = useState(false)

  useEffect(() => {
    api.get(`/api/catalog/collections/${collection.id}/products?detay=1`)
      .then(d => {
        const liste = (d.urunler || []).filter(u => u.gorseller.length)
        setUrunler(liste)
        setSecili(liste.slice(0, 3).map(u => u.id))   // ilk üç hazır seçili
      })
      .catch(() => setUrunler([]))
  }, [collection.id])

  const secilenler = (urunler || []).filter(u => secili.includes(u.id))
    .sort((a, b) => secili.indexOf(a.id) - secili.indexOf(b.id))
  const degistir = (id) => setSecili(s => s.includes(id) ? s.filter(x => x !== id)
    : s.length >= 5 ? s : [...s, id])

  const prompt = useMemo(() => {
    const n = secilenler.length
    const sahneMetni = sahne === 'ozel' ? (ozelSahne.trim() || '[sahneyi buraya yazın]') : SAHNELER[sahne]
    const sira = secilenler.map((u, i) => `${i + 1}. image → case ${i + 1} (${u.title})`).join('\n')
    return `Create a photorealistic e-commerce lifestyle photo for a phone case collection called "${collection.title}".

Show exactly ${n} phone cases standing upright side by side, evenly spaced, back side facing the camera with the camera cut-outs visible, on modern iPhone Pro style phones (triple camera).

Use the ${n} attached images as the EXACT artwork of the cases. Reproduce every design faithfully — same colors, patterns, characters and text. Do not redesign, recolor, crop away important parts or add any logos.
Order from left to right:
${sira}

Scene: ${sahneMetni}.

Composition: cases centered and large in the frame, natural soft shadows, shallow depth of field on the background, keep the bottom 25% of the image calmer and slightly darker so a title can be placed over it.
Aspect ratio ${oran}. High detail, sharp case edges, realistic materials. No extra text, no watermark, no hands, no brand names.`
  }, [secilenler, sahne, ozelSahne, oran, collection.title])

  const kopyala = async () => {
    try { await navigator.clipboard.writeText(prompt); setKopya(true); setTimeout(() => setKopya(false), 1500) }
    catch { window.prompt('Prompt\'u kopyalayın:', prompt) }
  }

  return createPortal(
    <div className="fixed inset-0 z-[80] bg-black/60 flex items-center justify-center p-3 sm:p-6" onClick={onClose}>
      <div className="card w-full max-w-3xl max-h-[92vh] overflow-y-auto !p-4 space-y-4" onClick={e => e.stopPropagation()}>
        <div className="flex items-center gap-2">
          <h2 className="text-base font-semibold">✨ “{collection.title}” için koleksiyon görseli (Gemini)</h2>
          <button onClick={onClose} className="ml-auto text-panel-muted hover:text-panel-ink text-xl leading-none">×</button>
        </div>
        <ol className="text-[12px] text-panel-muted list-decimal pl-5 space-y-0.5">
          <li>Aşağıdan 3-5 ürün seçin (sıra = görseldeki soldan sağa sıra).</li>
          <li>Ürün görsellerini indirin, Gemini'de yeni sohbete <b>hepsini birlikte</b> ekleyin.</li>
          <li>Hazır prompt'u kopyalayıp yapıştırın. Beğenmezseniz “daha yakın çek”, “ışığı yumuşat” gibi düzeltin.</li>
          <li>Çıkan görseli Koleksiyonlar › <b>Sayfa görünümü</b>'nden yükleyip kırpın.</li>
        </ol>

        {urunler === null ? <div className="text-sm text-panel-muted">Ürünler yükleniyor…</div>
          : urunler.length === 0 ? <div className="text-sm text-amber-300">Bu koleksiyonda görselli ürün yok.</div>
          : (
            <div>
              <div className="text-xs text-panel-muted mb-1.5">Ürünler — {secili.length}/5 seçili</div>
              <div className="grid grid-cols-4 sm:grid-cols-6 gap-2 max-h-64 overflow-y-auto">
                {urunler.map(u => {
                  const i = secili.indexOf(u.id)
                  return (
                    <button key={u.id} type="button" onClick={() => degistir(u.id)} title={u.title}
                      className={`relative rounded-lg overflow-hidden border-2 ${i >= 0 ? 'border-panel-accent' : 'border-transparent opacity-70 hover:opacity-100'}`}>
                      <img src={u.gorseller[0]} alt="" className="aspect-square w-full object-cover" />
                      {i >= 0 && <span className="absolute top-1 left-1 grid h-5 w-5 place-items-center rounded-full bg-panel-accent text-[11px] font-bold text-white">{i + 1}</span>}
                    </button>
                  )
                })}
              </div>
            </div>
          )}

        {secilenler.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {secilenler.map((u, i) => (
              <a key={u.id} href={u.gorseller[0]} download={`${i + 1}-${u.slug}.jpg`}
                className="text-[11px] px-2 py-1 rounded-md border border-panel-border hover:border-panel-accent">
                ⬇ {i + 1}. görsel
              </a>
            ))}
          </div>
        )}

        <div className="grid sm:grid-cols-2 gap-3 text-xs">
          <div>
            <div className="text-panel-muted mb-1">Sahne</div>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(SAHNE_AD).map(([k, ad]) => (
                <button key={k} type="button" onClick={() => setSahne(k)}
                  className={`px-2.5 py-1.5 rounded-lg border ${sahne === k ? 'border-panel-accent bg-emerald-500/10 text-emerald-300' : 'border-panel-border text-panel-muted'}`}>{ad}</button>
              ))}
            </div>
            {sahne === 'ozel' && (
              <textarea className="input mt-2" rows={2} value={ozelSahne} onChange={e => setOzelSahne(e.target.value)}
                placeholder="İngilizce yazarsanız daha iyi sonuç verir — örn. a beach at sunset with soft sand" />
            )}
          </div>
          <div>
            <div className="text-panel-muted mb-1">Oran</div>
            <div className="flex flex-wrap gap-1.5">
              {ORANLAR.map(([v, ad]) => (
                <button key={v} type="button" onClick={() => setOran(v)}
                  className={`px-2.5 py-1.5 rounded-lg border ${oran === v ? 'border-panel-accent bg-emerald-500/10 text-emerald-300' : 'border-panel-border text-panel-muted'}`}>{ad}</button>
              ))}
            </div>
          </div>
        </div>

        <div>
          <div className="flex items-center mb-1">
            <span className="text-xs text-panel-muted">Gemini prompt'u (İngilizce — görsel modelleri İngilizcede daha isabetli)</span>
            <button type="button" onClick={kopyala} disabled={!secilenler.length}
              className="ml-auto btn-primary !py-1 text-xs disabled:opacity-40">{kopya ? 'Kopyalandı ✓' : 'Prompt\'u kopyala'}</button>
          </div>
          <textarea readOnly value={prompt} rows={12} className="input font-mono !text-[11px] leading-relaxed" />
        </div>
      </div>
    </div>,
    document.body
  )
}
