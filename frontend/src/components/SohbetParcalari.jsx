/**
 * Sohbet parçaları — bayi portalı ve yönetim paneli AYNI görünümü kullanır.
 *
 * WhatsApp düzeni: gönderenin küçük logosu, gün ayracı, baloncuk içinde saat ve
 * kendi mesajlarında ✓ (iletildi) / ✓✓ (görüldü). İki ekrana kopyalanırsa biri
 * düzeltilip diğeri eskide kalır — tek dosyada duruyor.
 */
import { useMemo, useRef, useState } from 'react'

export const ACILIYET_ROZET = {
  acil: { ad: 'ACİL', sinif: 'bg-amber-500/20 text-amber-300' },
  cok_acil: { ad: 'ÇOK ACİL', sinif: 'bg-red-500/20 text-red-300' },
}

const GUN = 86400000

export function saatYaz(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })
}

/** "Bugün" / "Dün" / "3 Ekim 2026" — gün ayracı metni. */
export function gunYaz(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const bugun = new Date()
  const sifirla = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime()
  const fark = Math.round((sifirla(bugun) - sifirla(d)) / GUN)
  if (fark === 0) return 'Bugün'
  if (fark === 1) return 'Dün'
  return d.toLocaleDateString('tr-TR', { day: 'numeric', month: 'long', year: 'numeric' })
}

/** Mesajları güne böl: [{gun, mesajlar: [...]}] */
export function gunlereBol(mesajlar) {
  const out = []
  for (const m of (mesajlar || [])) {
    const g = gunYaz(m.created_at)
    if (!out.length || out[out.length - 1].gun !== g) out.push({ gun: g, mesajlar: [] })
    out[out.length - 1].mesajlar.push(m)
  }
  return out
}

/** Küçük yuvarlak logo; görsel yoksa baş harf. */
export function Avatar({ url, ad, boyut = 28 }) {
  const harf = (ad || '?').trim().charAt(0).toLocaleUpperCase('tr-TR')
  return url ? (
    <img src={url} alt="" width={boyut} height={boyut} loading="lazy"
         className="rounded-full object-cover border border-white/10 shrink-0"
         style={{ width: boyut, height: boyut }} />
  ) : (
    <span className="rounded-full grid place-items-center shrink-0 bg-white/10 text-gray-300
                     border border-white/10 text-[11px] font-semibold"
          style={{ width: boyut, height: boyut }}>{harf}</span>
  )
}

/** ✓ iletildi · ✓✓ görüldü (yalnız KENDİ mesajında). */
export function Tik({ durum }) {
  const goruldu = durum === 'goruldu'
  return (
    <span className={`inline-flex items-center ${goruldu ? 'text-sky-300' : 'text-gray-500'}`}
          title={goruldu ? 'Görüldü' : 'İletildi'} aria-label={goruldu ? 'Görüldü' : 'İletildi'}>
      <svg viewBox="0 0 20 12" className="w-[15px] h-[11px]" fill="none"
           stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M1 6.5 4.5 10 11 2" />
        {goruldu && <path d="M7.5 9.6 8.6 10.7 15.5 2" />}
      </svg>
    </span>
  )
}

export function GunAyraci({ gun }) {
  return (
    <div className="flex items-center gap-3 my-1">
      <span className="flex-1 h-px bg-white/8" />
      <span className="text-[10px] text-gray-500 px-2 py-0.5 rounded-full bg-white/5">{gun}</span>
      <span className="flex-1 h-px bg-white/8" />
    </div>
  )
}

/**
 * Tek mesaj baloncuğu.
 * benimMi: sağa yaslanır ve tik gösterilir. onSiparis verilirse sipariş eki tıklanır.
 */
export function Balon({ m, benimMi, ad, onSiparis }) {
  const rozet = ACILIYET_ROZET[m.aciliyet]
  return (
    <div className={`flex items-end gap-2 ${benimMi ? 'justify-end' : 'justify-start'}`}>
      {!benimMi && <Avatar url={m.avatar} ad={ad} />}
      <div className={`max-w-[85%] sm:max-w-[72%] rounded-2xl px-3 py-2 border ${
        benimMi ? 'bg-accent/10 border-accent/25 rounded-br-md'
                : 'bg-brand-input/60 border-brand-border rounded-bl-md'}`}>
        {(!benimMi || rozet) && (
          <div className="flex items-center gap-2 mb-1">
            {!benimMi && <span className="text-[11px] text-gray-400">{m.gonderen_ad || ad}</span>}
            {rozet && (
              <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded ${rozet.sinif}`}>{rozet.ad}</span>
            )}
          </div>
        )}
        {m.order_no && (
          onSiparis && m.order_id ? (
            <button onClick={() => onSiparis(m.order_id)}
              className="text-[11px] text-accent hover:underline mb-1">🧾 {m.order_no} siparişi →</button>
          ) : (
            <div className="text-[11px] text-accent mb-1">🧾 {m.order_no} siparişi</div>
          )
        )}
        {m.image_url && (
          <a href={m.image_url} target="_blank" rel="noreferrer">
            <img src={m.image_url} alt="" loading="lazy"
                 className="rounded-lg max-h-56 mb-1.5 border border-brand-border" />
          </a>
        )}
        {m.body && <div className="text-sm text-gray-100 whitespace-pre-line break-words">{m.body}</div>}
        <div className="flex items-center justify-end gap-1 mt-1">
          <span className="text-[10px] text-gray-600">{saatYaz(m.created_at)}</span>
          {benimMi && <Tik durum={m.durum} />}
        </div>
      </div>
      {benimMi && <Avatar url={m.avatar} ad={ad} />}
    </div>
  )
}

/**
 * Aranabilir sipariş seçici — sipariş NUMARASINI bilmek gerekmesin.
 * Müşteri adı, numara ve tarihle arar; listede durumu da gösterir.
 */
export function SiparisSecici({ siparisler, secili, onSec, etiket = 'Sipariş ekle…' }) {
  const [acik, setAcik] = useState(false)
  const [arama, setArama] = useState('')
  const kutu = useRef(null)

  const secilen = (siparisler || []).find(s => s.id === secili)
  const sonuc = useMemo(() => {
    const q = arama.trim().toLocaleLowerCase('tr-TR')
    const liste = siparisler || []
    if (!q) return liste.slice(0, 40)
    return liste.filter(s =>
      String(s.order_number || '').toLocaleLowerCase('tr-TR').includes(q)
      || String(s.musteri || '').toLocaleLowerCase('tr-TR').includes(q)
      || String(s.asama_adi || '').toLocaleLowerCase('tr-TR').includes(q)
      || (s.tarih || '').slice(0, 10).includes(q)
    ).slice(0, 40)
  }, [siparisler, arama])

  const tarih = (iso) => iso
    ? new Date(iso).toLocaleDateString('tr-TR', { day: '2-digit', month: 'short', year: '2-digit' })
    : '—'

  return (
    <div className="relative" ref={kutu}>
      <button type="button" onClick={() => { setAcik(a => !a); setArama('') }}
        className="btn-secondary !text-xs !py-1.5 whitespace-nowrap max-w-[220px] truncate">
        {secilen ? `🧾 ${secilen.order_number}` : etiket}
      </button>
      {acik && (
        <>
          <div className="fixed inset-0 z-[60]" onClick={() => setAcik(false)} />
          <div className="absolute bottom-full mb-2 left-0 z-[61] w-[320px] max-w-[88vw] rounded-xl
                          border border-brand-border bg-brand-card shadow-2xl overflow-hidden">
            <div className="p-2 border-b border-brand-border">
              <input autoFocus value={arama} onChange={e => setArama(e.target.value)}
                placeholder="Müşteri adı, sipariş no ya da tarih ara…"
                className="input w-full !text-xs" />
            </div>
            <div className="max-h-64 overflow-y-auto">
              {secili && (
                <button onClick={() => { onSec(''); setAcik(false) }}
                  className="w-full text-left px-3 py-2 text-[11px] text-red-300/90 hover:bg-brand-input/60">
                  ✕ Sipariş ekini kaldır
                </button>
              )}
              {sonuc.length === 0 ? (
                <div className="px-3 py-6 text-center text-[11px] text-gray-500">Eşleşen sipariş yok</div>
              ) : sonuc.map(s => (
                <button key={s.id} onClick={() => { onSec(s.id); setAcik(false) }}
                  className={`w-full text-left px-3 py-2 hover:bg-brand-input/60 border-b border-brand-border/40 ${
                    s.id === secili ? 'bg-accent/10' : ''}`}>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-100 font-medium">{s.order_number}</span>
                    <span className="text-[10px] text-gray-500 ml-auto">{tarih(s.tarih)}</span>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-[11px] text-gray-400 truncate flex-1">{s.musteri || 'Müşteri —'}</span>
                    <span className="text-[10px] text-accent/80 shrink-0">{s.asama_adi || ''}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
