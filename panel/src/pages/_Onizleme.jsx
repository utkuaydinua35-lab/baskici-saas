// GEÇİCİ — tema doğrulaması için. Panelin gerçek kabuğunu (Layout) ve
// örnek bileşenleri sahte veriyle çizer. Doğrulama bitince SİLİNİR.
import { AuthContext } from '../lib/auth'
import { StoreContext } from '../lib/store'
import Layout from '../components/Layout'
import CanliGorunumPage from './CanliGorunumPage'

const s = (n, tepe) => Array.from({ length: 24 }, (_, i) =>
  i > tepe ? 0 : Math.round(n * (0.3 + Math.sin(i / 3) ** 2)))

const SAHTE = {
  zaman: new Date().toISOString(), ziyaretci: 7, su_anki_saat: 19,
  oturumlar: { bugun: 512, onceki: 368, degisim: 39, seri: s(30, 19), seri_onceki: s(24, 23) },
  siparisler: { bugun: 17, onceki: 7, degisim: 143, seri: s(2, 19), seri_onceki: s(1, 23) },
  satislar: { bugun: '10800', onceki: '3830', degisim: 182, seri: s(900, 19), seri_onceki: s(400, 23) },
  davranis: { aktif_sepet: 3, odeme_yapiyor: 1, satin_aldi: 2, pencere_dk: 30 },
  konumlar: [
    { kod: 'TR', ad: 'Türkiye', lat: 39, lon: 35.2, oturum: 431 },
    { kod: 'DE', ad: 'Almanya', lat: 51.2, lon: 10.4, oturum: 49 },
    { kod: 'NL', ad: 'Hollanda', lat: 52.1, lon: 5.3, oturum: 21 },
    { kod: 'US', ad: 'ABD', lat: 39.8, lon: -98.6, oturum: 11 },
  ],
  musteriler: { yeni: 12, geri_donen: 5 },
  aktivite: [
    { tur: 'siparis', zaman: new Date().toISOString(), kim: 'Ayşe K.', metin: '#1042 sipariş verdi', tutar: '484.00' },
    { tur: 'odeme_pending', zaman: new Date().toISOString(), kim: 'Mehmet Y.', metin: 'ödeme sayfasında', tutar: '399.90' },
    { tur: 'odeme_paid', zaman: new Date().toISOString(), kim: 'Misafir', metin: 'ödemeyi tamamladı', tutar: '749.00' },
  ],
}

const gercek = window.fetch
window.fetch = (url, ...k) => String(url).includes('/api/orders/live-view')
  ? Promise.resolve(new Response(JSON.stringify(SAHTE), { status: 200, headers: { 'content-type': 'application/json' } }))
  : String(url).includes('/api/')
    ? Promise.resolve(new Response('{}', { status: 200, headers: { 'content-type': 'application/json' } }))
    : gercek(url, ...k)

export default function Onizleme() {
  const auth = { user: { full_name: 'Utku Aydın', email: 'utku@bernzcompany.com', permissions: ['*'] },
                 logout() {}, refresh() {}, loading: false }
  const magaza = { stores: [{ id: '1', name: 'Lunera Case' }], store: { id: '1', name: 'Lunera Case' },
                   storeId: '1', setStoreId() {}, loading: false }
  return (
    <AuthContext.Provider value={auth}>
      <StoreContext.Provider value={magaza}>
        <Layout />
      </StoreContext.Provider>
    </AuthContext.Provider>
  )
}
export { CanliGorunumPage }
