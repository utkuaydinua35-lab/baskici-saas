import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'

const LoginPage = lazy(() => import('./pages/LoginPage'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const SiparislerPage = lazy(() => import('./pages/SiparislerPage'))
const SiparisDetayPage = lazy(() => import('./pages/SiparisDetayPage'))
const UrunlerPage = lazy(() => import('./pages/UrunlerPage'))
const KoleksiyonlarPage = lazy(() => import('./pages/KoleksiyonlarPage'))
const KuponlarPage = lazy(() => import('./pages/KuponlarPage'))
const TerkSepetlerPage = lazy(() => import('./pages/TerkSepetlerPage'))
const MusterilerPage = lazy(() => import('./pages/MusterilerPage'))
const AnalitikPage = lazy(() => import('./pages/AnalitikPage'))
const TemaPage = lazy(() => import('./pages/TemaPage'))
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
            <Route path="/koleksiyonlar" element={<KoleksiyonlarPage />} />
            <Route path="/kuponlar" element={<KuponlarPage />} />
            <Route path="/terk-sepetler" element={<TerkSepetlerPage />} />
            <Route path="/musteriler" element={<MusterilerPage />} />
            <Route path="/analitik" element={<AnalitikPage />} />
            <Route path="/tema" element={<TemaPage />} />
            <Route path="/ayarlar" element={<AyarlarPage />} />
          </Route>
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
