import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import BayiRoute, { BayiOlmayan } from './components/BayiRoute'
import BayiLayout from './components/BayiLayout'

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
const OzelSeriStokPage = lazyWithReload(() => import('./pages/OzelSeriStokPage'))
const StockPage = lazyWithReload(() => import('./pages/StockPage'))
const PackagingPage = lazyWithReload(() => import('./pages/PackagingPage'))
const PipelinePage = lazyWithReload(() => import('./pages/PipelinePage'))
const RegisterPage = lazyWithReload(() => import('./pages/RegisterPage'))
const ShortcutsPage = lazyWithReload(() => import('./pages/ShortcutsPage'))
const StoresPage = lazyWithReload(() => import('./pages/StoresPage'))
const SettingsPage = lazyWithReload(() => import('./pages/SettingsPage'))
const EtiketSablonPage = lazyWithReload(() => import('./pages/EtiketSablonPage'))
const ProfileSelectPage = lazyWithReload(() => import('./pages/ProfileSelectPage'))
const DestekPage = lazyWithReload(() => import('./pages/DestekPage'))
const AccessoriesPage = lazyWithReload(() => import('./pages/AccessoriesPage'))
const CoupleProductsPage = lazyWithReload(() => import('./pages/CoupleProductsPage'))
const DealersPage = lazyWithReload(() => import('./pages/DealersPage'))
const BayiSohbetYonetimPage = lazyWithReload(() => import('./pages/BayiSohbetPage'))
const AktarimPage = lazyWithReload(() => import('./pages/AktarimPage'))
const DealerDashboardPage = lazyWithReload(() => import('./pages/DealerDashboardPage'))
const BayiSiparisleriPage = lazyWithReload(() => import('./pages/BayiSiparisleriPage'))
const AuditPage = lazyWithReload(() => import('./pages/AuditPage'))
const PlatformPage = lazyWithReload(() => import('./pages/PlatformPage'))
const PazarlamaPage = lazyWithReload(() => import('./pages/PazarlamaPage'))
const MusterilerPage = lazyWithReload(() => import('./pages/MusterilerPage'))
const AnalitikPage = lazyWithReload(() => import('./pages/AnalitikPage'))
const SosyalMedyaPage = lazyWithReload(() => import('./pages/SosyalMedyaPage'))
// Bayi portali — bayilerin kendi girisi (yonetim panelinden ayri kabuk)
const BayiGirisPage = lazyWithReload(() => import('./pages/bayii/BayiGirisPage'))
const BayiPanelPage = lazyWithReload(() => import('./pages/bayii/BayiPanelPage'))
const BayiSiparislerPage = lazyWithReload(() => import('./pages/bayii/BayiSiparislerPage'))
const BayiSiparisDetayPage = lazyWithReload(() => import('./pages/bayii/BayiSiparisDetayPage'))
const BayiYeniSiparisPage = lazyWithReload(() => import('./pages/bayii/BayiYeniSiparisPage'))
const BayiCariPage = lazyWithReload(() => import('./pages/bayii/BayiCariPage'))
const BayiSohbetPage = lazyWithReload(() => import('./pages/bayii/BayiSohbetPage'))
const BayiUygulamaPage = lazyWithReload(() => import('./pages/bayii/BayiUygulamaPage'))
const BayiYeniliklerPage = lazyWithReload(() => import('./pages/bayii/BayiYeniliklerPage'))

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

        <Route path="/bayii/giris" element={<BayiGirisPage />} />

        {/* Bayi portali — kendi kabugu, yonetim menusu YOK */}
        <Route element={<BayiRoute />}>
          <Route element={<BayiLayout />}>
            <Route path="/bayii" element={<BayiPanelPage />} />
            <Route path="/bayii/siparisler" element={<BayiSiparislerPage />} />
            <Route path="/bayii/siparis/:id" element={<BayiSiparisDetayPage />} />
            <Route path="/bayii/yeni" element={<BayiYeniSiparisPage />} />
            <Route path="/bayii/cari" element={<BayiCariPage />} />
            <Route path="/bayii/sohbet" element={<BayiSohbetPage />} />
            <Route path="/bayii/uygulama" element={<BayiUygulamaPage />} />
            <Route path="/bayii/yenilikler" element={<BayiYeniliklerPage />} />
          </Route>
        </Route>

        <Route element={<ProtectedRoute />}>
          {/* BayiOlmayan: bayi hesabi yonetim rotalarina girerse /bayii'ye doner */}
          <Route element={<BayiOlmayan />}>
          <Route path="/profil-sec" element={<ProfileSelectPage />} />
          <Route element={<Layout />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/stores" element={<StoresPage />} />
            <Route path="/ayarlar" element={<SettingsPage />} />
            <Route path="/ayarlar/etiket" element={<EtiketSablonPage />} />
            <Route path="/orders" element={<OrdersPage />} />
            <Route path="/orders/:orderId" element={<OrderDetailPage />} />
            <Route path="/telafiler" element={<TelafilerPage />} />
            <Route path="/aski" element={<AskiPage />} />
            <Route path="/telefon-modelleri" element={<PhoneModelsPage />} />
            <Route path="/ozel-seri-stok" element={<OzelSeriStokPage />} />
            <Route path="/stok" element={<StockPage />} />
            <Route path="/paketleme" element={<PackagingPage />} />
            <Route path="/destek" element={<DestekPage />} />
            <Route path="/designs" element={<DesignsPage />} />
            <Route path="/varyantli-urunler" element={<VaryantliUrunlerPage />} />
            <Route path="/urun-studyosu" element={<ProductStudioPage />} />
            <Route path="/aksesuarlar" element={<AccessoriesPage />} />
            <Route path="/couple" element={<CoupleProductsPage />} />
            <Route path="/bayiler" element={<DealersPage />} />
            <Route path="/bayi-sohbet" element={<BayiSohbetYonetimPage />} />
            <Route path="/aktarim" element={<AktarimPage />} />
            <Route path="/bayiler/:id" element={<DealerDashboardPage />} />
            <Route path="/bayi-siparisleri" element={<BayiSiparisleriPage />} />
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
            <Route path="/musteriler" element={<MusterilerPage />} />
            <Route path="/analitik" element={<AnalitikPage />} />
            <Route path="/sosyal-medya" element={<SosyalMedyaPage />} />
          </Route>
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
