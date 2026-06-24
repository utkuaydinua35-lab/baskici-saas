import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'

// Route bazli code-splitting — her sayfa ayri chunk, ilk yuk kucuk.
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const DesignsPage = lazy(() => import('./pages/DesignsPage'))
const NotesPage = lazy(() => import('./pages/NotesPage'))
const TelafilerPage = lazy(() => import('./pages/TelafilerPage'))
const KisiyeOzelPage = lazy(() => import('./pages/KisiyeOzelPage'))
const LoginPage = lazy(() => import('./pages/LoginPage'))
const OrderDetailPage = lazy(() => import('./pages/OrderDetailPage'))
const AskiPage = lazy(() => import('./pages/AskiPage'))
const MoldDetailPage = lazy(() => import('./pages/MoldDetailPage'))
const MoldTemplatePage = lazy(() => import('./pages/MoldTemplatePage'))
const MoldGeneratorPage = lazy(() => import('./pages/MoldGeneratorPage'))
const BaskiciPaneliPage = lazy(() => import('./pages/BaskiciPaneliPage'))
const OrdersPage = lazy(() => import('./pages/OrdersPage'))
const PhoneModelsPage = lazy(() => import('./pages/PhoneModelsPage'))
const StockPage = lazy(() => import('./pages/StockPage'))
const PackagingPage = lazy(() => import('./pages/PackagingPage'))
const PipelinePage = lazy(() => import('./pages/PipelinePage'))
const RegisterPage = lazy(() => import('./pages/RegisterPage'))
const ShortcutsPage = lazy(() => import('./pages/ShortcutsPage'))
const StoresPage = lazy(() => import('./pages/StoresPage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))
const ProfileSelectPage = lazy(() => import('./pages/ProfileSelectPage'))
const DestekPage = lazy(() => import('./pages/DestekPage'))
const AccessoriesPage = lazy(() => import('./pages/AccessoriesPage'))
const CoupleProductsPage = lazy(() => import('./pages/CoupleProductsPage'))
const DealersPage = lazy(() => import('./pages/DealersPage'))

function PageLoader() {
  return (
    <div className="h-full min-h-[40vh] flex items-center justify-center">
      <div className="w-6 h-6 rounded-full border-2 border-brand-border border-t-accent animate-spin" />
    </div>
  )
}

export default function App() {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        <Route element={<ProtectedRoute />}>
          <Route path="/profil-sec" element={<ProfileSelectPage />} />
          <Route element={<Layout />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/stores" element={<StoresPage />} />
            <Route path="/ayarlar" element={<SettingsPage />} />
            <Route path="/orders" element={<OrdersPage />} />
            <Route path="/orders/:orderId" element={<OrderDetailPage />} />
            <Route path="/notlar" element={<NotesPage />} />
            <Route path="/telafiler" element={<TelafilerPage />} />
            <Route path="/aski" element={<AskiPage />} />
            <Route path="/telefon-modelleri" element={<PhoneModelsPage />} />
            <Route path="/stok" element={<StockPage />} />
            <Route path="/paketleme" element={<PackagingPage />} />
            <Route path="/destek" element={<DestekPage />} />
            <Route path="/designs" element={<DesignsPage />} />
            <Route path="/aksesuarlar" element={<AccessoriesPage />} />
            <Route path="/couple" element={<CoupleProductsPage />} />
            <Route path="/bayiler" element={<DealersPage />} />
            <Route path="/kisiye-ozel" element={<KisiyeOzelPage />} />
            <Route path="/kalip-sablon" element={<MoldTemplatePage />} />
            <Route path="/kalip-olustur" element={<MoldGeneratorPage />} />
            <Route path="/baskici-paneli" element={<BaskiciPaneliPage />} />
            <Route path="/kalip/:moldId" element={<MoldDetailPage />} />
            <Route path="/shortcuts" element={<ShortcutsPage />} />
            <Route path="/pipeline" element={<PipelinePage />} />
          </Route>
        </Route>

        <Route path="*" element={
          <div className="h-full flex items-center justify-center text-gray-500">
            Sayfa bulunamadı
          </div>
        } />
      </Routes>
    </Suspense>
  )
}
