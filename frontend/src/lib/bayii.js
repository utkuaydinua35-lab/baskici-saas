/**
 * Bayi portali ortak yardimcilari.
 *
 * Bayi kullanicisinin AYIRT EDICISI role === 'bayii_portal'.
 * permissions dizisine bakmak yaniltici: yonetici (role 'yonetici') tum
 * yetkilere sahip sayilir ama permissions dizisi BOS olabilir. Rol tek
 * guvenilir olcut.
 */
export const BAYI_ROL = 'bayii_portal'

export function bayiMi(user) {
  return (user?.role || '') === BAYI_ROL
}

/** Aşama numarasından portal rozeti (renk + etiket). */
export function asamaRozet(o) {
  if (o?.iptal) return { etiket: 'İptal', renk: 'zinc' }
  if (o?.onay_bekliyor) return { etiket: 'Onay bekliyor', renk: 'amber' }
  const a = o?.asama || 1
  if (a >= 9) return { etiket: 'Teslim edildi', renk: 'emerald' }
  if (a >= 8) return { etiket: 'Kargoda', renk: 'sky' }
  if (a >= 7) return { etiket: 'Paketlendi', renk: 'violet' }
  if (a >= 4) return { etiket: 'Üretimde', renk: 'violet' }
  if (a >= 3) return { etiket: 'Barkod oluştu', renk: 'indigo' }
  return { etiket: 'Hazırlanıyor', renk: 'indigo' }
}

// Rozet renkleri — Tailwind'in JIT'i dinamik sinif adlarini goremedigi icin
// (`bg-${renk}-500/15` derlenmez) tam sinif adlari burada sabit tutulur.
export const ROZET_SINIF = {
  amber:   'bg-amber-500/12 text-amber-300 border-amber-500/25',
  indigo:  'bg-indigo-500/12 text-indigo-300 border-indigo-500/25',
  violet:  'bg-violet-500/12 text-violet-300 border-violet-500/25',
  sky:     'bg-sky-500/12 text-sky-300 border-sky-500/25',
  emerald: 'bg-emerald-500/12 text-emerald-300 border-emerald-500/25',
  zinc:    'bg-zinc-500/12 text-zinc-400 border-zinc-500/25',
}

export const KANALLAR = [
  { id: 'trendyol',  ad: 'Trendyol',  renk: '#f27a1a', ipucu: 'Adres Trendyol’dan gelir — sadece alıcı adı yeterli' },
  { id: 'shopier',   ad: 'Shopier',   renk: '#8b5cf6', ipucu: 'Kargo için tam adres gerekli' },
  { id: 'instagram', ad: 'Instagram', renk: '#e1306c', ipucu: 'Kargo için tam adres gerekli' },
  { id: 'hepsiburada', ad: 'Hepsiburada', renk: '#ff6000', ipucu: 'Adres Hepsiburada’dan gelir — alıcı adı ve kargo entegrasyon kodu gerekli' },
]

/** Hepsiburada gönderisinin kargo firması. İlki varsayılan (Sürat).
 *  Sunucudaki services/hepsiburada.KARGO_FIRMALARI ile AYNI anahtarlar. */
export const HB_KARGO_FIRMALARI = [
  { id: 'surat', ad: 'Sürat Kargo' },
  { id: 'hepsijet', ad: 'HepsiJET' },
  { id: 'aras', ad: 'Aras Kargo' },
  { id: 'yurtici', ad: 'Yurtiçi Kargo' },
  { id: 'mng', ad: 'MNG Kargo' },
  { id: 'ptt', ad: 'PTT Kargo' },
]

export function kargoFirmaAdi(id) {
  return HB_KARGO_FIRMALARI.find((f) => f.id === id)?.ad || HB_KARGO_FIRMALARI[0].ad
}

/** Kodu barkoda basılacak biçime getir — sunucuyla aynı kural: tüm boşluklar atılır. */
export function kargoKoduTemizle(kod) {
  return String(kod || '').replace(/\s+/g, '')
}

/** Geçerliyse null, değilse hata metni. */
export function kargoKoduHatasi(kod) {
  const k = kargoKoduTemizle(kod)
  if (!k) return 'Kargo entegrasyon kodu zorunlu'
  if (k.length < 6 || k.length > 40) return 'Kod 6-40 karakter olmalı'
  if (!/^[A-Za-z0-9-]+$/.test(k)) return 'Kodda yalnız harf, rakam ve tire olabilir'
  return null
}

export const ADRES_ZORUNLU = ['shopier', 'instagram']

/** Kanal kimliginden marka adi. CSS uppercase Turkce yerelde 'shopier' ->
 *  'SHOPİER' uretiyordu (noktali İ); marka adlari boyle yazilmaz. */
export function kanalAdi(id) {
  return KANALLAR.find((k) => k.id === id)?.ad || id || ''
}

export function paraYaz(tutar, birim = 'TRY') {
  const n = Number(tutar || 0)
  const sembol = birim === 'USD' ? '$' : '₺'
  return `${sembol}${n.toLocaleString('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

export function tarihYaz(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('tr-TR', {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}
