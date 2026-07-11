import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'

const LoginPage = lazy(() => import('./pages/LoginPage'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const SiparislerPage = lazy(() => import('./pages/SiparislerPage'))
const SiparisDetayPage = lazy(() => import('./pages/SiparisDetayPage'))
const UrunlerPage = lazy(() => import('./pages/UrunlerPage'))
const UrunDetayPage = lazy(() => import('./pages/UrunDetayPage'))
const KoleksiyonlarPage = lazy(() => import('./pages/KoleksiyonlarPage'))
const EnvanterPage = lazy(() => import('./pages/EnvanterPage'))
const KuponlarPage = lazy(() => import('./pages/KuponlarPage'))
const TerkSepetlerPage = lazy(() => import('./pages/TerkSepetlerPage'))
const MusterilerPage = lazy(() => import('./pages/MusterilerPage'))
const AnalitikPage = lazy(() => import('./pages/AnalitikPage'))
const TemaPage = lazy(() => import('./pages/TemaPage'))
const TemaEditorPage = lazy(() => import('./pages/TemaEditorPage'))
const SayfalarPage = lazy(() => import('./pages/SayfalarPage'))
const BlogPage = lazy(() => import('./pages/BlogPage'))
const YorumlarPage = lazy(() => import('./pages/YorumlarPage'))
const TasarimTalepleriPage = lazy(() => import('./pages/TasarimTalepleriPage'))
const UygulamalarPage = lazy(() => import('./pages/UygulamalarPage'))
const AyarlarPage = lazy(() => import('./pages/AyarlarPage'))

function Loader() {
  return (
    <div className="min-h-[40vh] flex items-center justify-center">
      <div className="w-6 h-6 rounded-full border-2 border-panel-border border-t-panel-accent animate-spin" />
    </div>
  )
}

export default function App() {
  return (
    <Suspense fallback={<Loader />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/siparisler" element={<SiparislerPage />} />
            <Route path="/siparisler/:orderId" element={<SiparisDetayPage />} />
            <Route path="/urunler" element={<UrunlerPage />} />
            <Route path="/urunler/:productId" element={<UrunDetayPage />} />
            <Route path="/koleksiyonlar" element={<KoleksiyonlarPage />} />
            <Route path="/envanter" element={<EnvanterPage />} />
            <Route path="/kuponlar" element={<KuponlarPage />} />
            <Route path="/terk-sepetler" element={<TerkSepetlerPage />} />
            <Route path="/musteriler" element={<MusterilerPage />} />
            <Route path="/analitik" element={<AnalitikPage />} />
            <Route path="/tema" element={<TemaPage />} />
            <Route path="/sayfalar" element={<SayfalarPage />} />
            <Route path="/blog" element={<BlogPage />} />
            <Route path="/yorumlar" element={<YorumlarPage />} />
            <Route path="/tasarim-talepleri" element={<TasarimTalepleriPage />} />
            <Route path="/uygulamalar" element={<UygulamalarPage />} />
            <Route path="/ayarlar" element={<AyarlarPage />} />
          </Route>
          {/* Tam ekran tema editörü — sol menüsüz (Shopify tarzı) */}
          <Route path="/tema/duzenle" element={<TemaEditorPage />} />
        </Route>
        <Route path="*" element={
          <div className="min-h-screen flex items-center justify-center text-panel-muted">
            Sayfa bulunamadı
          </div>
        } />
      </Routes>
    </Suspense>
  )
}
