import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'

// Yeni deploy sonrasi eski index.html cache'liyse chunk adlari degisir ve
// dynamic import 404 -> bos ekran. Chunk yuklenemezse bir kez otomatik reload
// (taze index.html alir). 10sn guard sonsuz reload dongusunu onler.
function lazyWithReload(factory) {
  return lazy(() => factory().catch((err) => {
    const KEY = '__chunk_reload_at'
    const last = Number(sessionStorage.getItem(KEY)) || 0
    if (Date.now() - last > 10000) {
      sessionStorage.setItem(KEY, String(Date.now()))
      window.location.reload()
      return new Promise(() => {}) // reload'a kadar bekle
    }
    throw err
  }))
}

// Route bazli code-splitting — her sayfa ayri chunk, ilk yuk kucuk.
const DashboardPage = lazyWithReload(() => import('./pages/DashboardPage'))
const DesignsPage = lazyWithReload(() => import('./pages/DesignsPage'))
const VaryantliUrunlerPage = lazyWithReload(() => import('./pages/VaryantliUrunlerPage'))
const ProductStudioPage = lazyWithReload(() => import('./pages/ProductStudioPage'))
const NotesPage = lazyWithReload(() => import('./pages/NotesPage'))
const TelafilerPage = lazyWithReload(() => import('./pages/TelafilerPage'))
const KisiyeOzelPage = lazyWithReload(() => import('./pages/KisiyeOzelPage'))
const LoginPage = lazyWithReload(() => import('./pages/LoginPage'))
const ForgotPasswordPage = lazyWithReload(() => import('./pages/ForgotPasswordPage'))
const ResetPasswordPage = lazyWithReload(() => import('./pages/ResetPasswordPage'))
const OrderDetailPage = lazyWithReload(() => import('./pages/OrderDetailPage'))
const AskiPage = lazyWithReload(() => import('./pages/AskiPage'))
const MoldDetailPage = lazyWithReload(() => import('./pages/MoldDetailPage'))
const MoldTemplatePage = lazyWithReload(() => import('./pages/MoldTemplatePage'))
const MoldGeneratorPage = lazyWithReload(() => import('./pages/MoldGeneratorPage'))
const BaskiciPaneliPage = lazyWithReload(() => import('./pages/BaskiciPaneliPage'))
const OrdersPage = lazyWithReload(() => import('./pages/OrdersPage'))
const PhoneModelsPage = lazyWithReload(() => import('./pages/PhoneModelsPage'))
const StockPage = lazyWithReload(() => import('./pages/StockPage'))
const PackagingPage = lazyWithReload(() => import('./pages/PackagingPage'))
const PipelinePage = lazyWithReload(() => import('./pages/PipelinePage'))
const RegisterPage = lazyWithReload(() => import('./pages/RegisterPage'))
const ShortcutsPage = lazyWithReload(() => import('./pages/ShortcutsPage'))
const StoresPage = lazyWithReload(() => import('./pages/StoresPage'))
const SettingsPage = lazyWithReload(() => import('./pages/SettingsPage'))
const ProfileSelectPage = lazyWithReload(() => import('./pages/ProfileSelectPage'))
const DestekPage = lazyWithReload(() => import('./pages/DestekPage'))
const AccessoriesPage = lazyWithReload(() => import('./pages/AccessoriesPage'))
const CoupleProductsPage = lazyWithReload(() => import('./pages/CoupleProductsPage'))
const DealersPage = lazyWithReload(() => import('./pages/DealersPage'))
const DealerDashboardPage = lazyWithReload(() => import('./pages/DealerDashboardPage'))
const AuditPage = lazyWithReload(() => import('./pages/AuditPage'))
const PlatformPage = lazyWithReload(() => import('./pages/PlatformPage'))
const PazarlamaPage = lazyWithReload(() => import('./pages/PazarlamaPage'))

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
        <Route path="/sifre-unuttum" element={<ForgotPasswordPage />} />
        <Route path="/sifre-sifirla" element={<ResetPasswordPage />} />

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
            <Route path="/varyantli-urunler" element={<VaryantliUrunlerPage />} />
            <Route path="/urun-studyosu" element={<ProductStudioPage />} />
            <Route path="/aksesuarlar" element={<AccessoriesPage />} />
            <Route path="/couple" element={<CoupleProductsPage />} />
            <Route path="/bayiler" element={<DealersPage />} />
            <Route path="/bayiler/:id" element={<DealerDashboardPage />} />
            <Route path="/kisiye-ozel" element={<KisiyeOzelPage />} />
            <Route path="/kalip-sablon" element={<MoldTemplatePage />} />
            <Route path="/kalip-olustur" element={<MoldGeneratorPage />} />
            <Route path="/baskici-paneli" element={<BaskiciPaneliPage />} />
            <Route path="/kalip/:moldId" element={<MoldDetailPage />} />
            <Route path="/shortcuts" element={<ShortcutsPage />} />
            <Route path="/pipeline" element={<PipelinePage />} />
            <Route path="/denetim" element={<AuditPage />} />
            <Route path="/platform" element={<PlatformPage />} />
            <Route path="/pazarlama" element={<PazarlamaPage />} />
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
