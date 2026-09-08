import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useStore } from '../lib/store'
import { NAV_GROUPS } from './Layout'

// ⌘K komut paleti — sayfa, sipariş, ürün ve müşteriye tek kutudan gitmek.
//
// Panelde en sık yapılan iş "şu sipariş numarasını bul". Menüden gitmek
// 3-4 tıklama; burası iki tuş. Arama backend'de /api/search'te, sayfa
// eşleşmesi ise tamamen istemcide (menü zaten elimizde, sunucuya sormaya
// gerek yok).
//
// Sayfalar q boşken de listelenir: palet aynı zamanda "nereye gidebilirim"
// menüsü olarak çalışır.

const IKON = { siparis: '📦', urun: '🛍️', musteri: '👤' }

export default function KomutPaleti({ acik, kapat }) {
  const [q, setQ] = useState('')
  const [uzak, setUzak] = useState({ orders: [], products: [], customers: [] })
  const [yukleniyor, setYukleniyor] = useState(false)
  const [idx, setIdx] = useState(0)
  const navigate = useNavigate()
  const { storeId } = useStore()
  const listeRef = useRef(null)

  // Açılışta temiz başla — önceki aramanın kalıntısı kalmasın
  useEffect(() => {
    if (acik) { setQ(''); setUzak({ orders: [], products: [], customers: [] }); setIdx(0) }
  }, [acik])

  // Sunucu araması — her tuşta değil, 250 ms duraklamada
  useEffect(() => {
    if (!acik) return
    const s = q.trim()
    if (s.length < 2) { setUzak({ orders: [], products: [], customers: [] }); setYukleniyor(false); return }
    setYukleniyor(true)
    const t = setTimeout(async () => {
      try {
        const url = `/api/search?q=${encodeURIComponent(s)}&kovalar=orders,products,customers`
          + (storeId ? `&store_id=${storeId}` : '')
        setUzak(await api.get(url))
      } catch { setUzak({ orders: [], products: [], customers: [] }) }
      finally { setYukleniyor(false) }
    }, 250)
    return () => clearTimeout(t)
  }, [q, acik, storeId])

  const sayfalar = useMemo(() => {
    const cikti = []
    for (const g of NAV_GROUPS) {
      for (const it of g.items) {
        cikti.push({ to: it.to, etiket: it.label, ikon: it.icon, grup: g.label || 'Genel' })
      }
    }
    cikti.push({ to: '/ayarlar', etiket: 'Ayarlar', ikon: '⚙️', grup: 'Genel' })
    return cikti
  }, [])

  const sonuclar = useMemo(() => {
    const s = q.trim().toLocaleLowerCase('tr')
    const sayfaVurus = (s
      ? sayfalar.filter(i => `${i.etiket} ${i.grup}`.toLocaleLowerCase('tr').includes(s))
      : sayfalar
    ).map(i => ({ ...i, grup: 'Sayfa' }))

    return [
      ...sayfaVurus,
      ...(uzak.orders || []).map(o => ({
        to: `/siparisler/${o.id}`, ikon: IKON.siparis, grup: 'Sipariş',
        etiket: o.name || `#${o.order_number}`, alt: o.customer || '',
      })),
      ...(uzak.products || []).map(p => ({
        to: `/urunler/${p.id}`, ikon: IKON.urun, grup: 'Ürün',
        etiket: p.title, alt: p.status === 'active' ? 'yayında' : p.status,
      })),
      // Müşterinin ayrı detay sayfası yok — listeye arama dolu gidiliyor
      ...(uzak.customers || []).map(c => ({
        to: `/musteriler?ara=${encodeURIComponent(c.email)}`, ikon: IKON.musteri,
        grup: 'Müşteri', etiket: c.name || c.email,
        alt: `${c.orders_count} sipariş`,
      })),
    ]
  }, [q, sayfalar, uzak])

  useEffect(() => { setIdx(0) }, [q, uzak])

  // Seçili satır listenin dışına kayarsa görünür alana getir
  useEffect(() => {
    listeRef.current?.querySelector('[data-secili="1"]')
      ?.scrollIntoView({ block: 'nearest' })
  }, [idx])

  if (!acik) return null

  const git = (i) => { const r = sonuclar[i]; if (r) { navigate(r.to); kapat() } }
  const tus = (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setIdx(i => Math.min(i + 1, sonuclar.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setIdx(i => Math.max(i - 1, 0)) }
    else if (e.key === 'Enter') { e.preventDefault(); git(idx) }
    else if (e.key === 'Escape') { e.preventDefault(); kapat() }
  }

  let sonGrup = null
  return createPortal(
    <div className="fixed inset-0 z-[200] flex items-start justify-center pt-[10vh] px-4
      bg-[#060b28]/70 backdrop-blur-sm"
      onMouseDown={e => e.target === e.currentTarget && kapat()}>
      <div className="katman w-full max-w-xl overflow-hidden menu-pop">

        <div className="flex items-center gap-2.5 px-4 border-b border-panel-border">
          <span className="text-panel-muted">🔍</span>
          <input autoFocus value={q} onChange={e => setQ(e.target.value)} onKeyDown={tus}
            placeholder="Sayfa, sipariş no, ürün veya müşteri ara…"
            aria-label="Hızlı arama"
            className="flex-1 bg-transparent py-3.5 text-sm text-panel-ink
              placeholder:text-panel-muted/60 focus:outline-none" />
          {yukleniyor && <span className="text-[11px] text-panel-muted animate-pulse">…</span>}
          <kbd className="text-[10px] px-1.5 py-0.5 rounded bg-white/[0.07]
            border border-panel-border text-panel-muted">esc</kbd>
        </div>

        <div ref={listeRef} className="max-h-[62vh] overflow-y-auto p-2">
          {sonuclar.length === 0 ? (
            <div className="px-3 py-8 text-center text-sm text-panel-muted">
              {q.trim() ? 'Sonuç yok' : 'Aramaya başla…'}
            </div>
          ) : sonuclar.map((r, i) => {
            const grupGoster = r.grup !== sonGrup; sonGrup = r.grup
            const secili = i === idx
            return (
              <div key={`${r.to}-${r.etiket}-${i}`}>
                {grupGoster && (
                  <div className="text-[9px] uppercase tracking-[0.14em] text-panel-muted/70 px-2.5 pt-3 pb-1.5">
                    {r.grup}
                  </div>
                )}
                <button data-secili={secili ? '1' : '0'}
                  onMouseEnter={() => setIdx(i)} onClick={() => git(i)}
                  className={`w-full flex items-center gap-3 px-2.5 py-2 rounded-[14px] text-left
                    text-[13px] transition-colors ${secili
                      ? 'bg-panel-accent/20 text-white'
                      : 'text-panel-muted hover:bg-white/[0.06]'}`}>
                  <span className={`w-7 h-7 rounded-[10px] flex items-center justify-center shrink-0
                    ${secili ? 'bg-gradient-to-br from-panel-accent to-panel-cyan' : 'bg-white/[0.07]'}`}>
                    {r.ikon}
                  </span>
                  <span className="flex-1 truncate">{r.etiket}</span>
                  {r.alt && (
                    <span className="text-[10px] text-panel-muted truncate max-w-[42%]">{r.alt}</span>
                  )}
                </button>
              </div>
            )
          })}
        </div>

        <div className="flex items-center gap-3 px-4 py-2 border-t border-panel-border
          text-[10px] text-panel-muted">
          <span>↑↓ gez</span><span>⏎ aç</span><span className="ml-auto">⌘K</span>
        </div>
      </div>
    </div>, document.body)
}
