import { Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import DashboardPage from './pages/DashboardPage'
import DesignsPage from './pages/DesignsPage'
import KisiyeOzelPage from './pages/KisiyeOzelPage'
import LoginPage from './pages/LoginPage'
import OrderDetailPage from './pages/OrderDetailPage'
import AskiPage from './pages/AskiPage'
import MoldDetailPage from './pages/MoldDetailPage'
import MoldTemplatePage from './pages/MoldTemplatePage'
import MoldGeneratorPage from './pages/MoldGeneratorPage'
import OrdersPage from './pages/OrdersPage'
import PhoneModelsPage from './pages/PhoneModelsPage'
import StockPage from './pages/StockPage'
import PackagingPage from './pages/PackagingPage'
import PipelinePage from './pages/PipelinePage'
import RegisterPage from './pages/RegisterPage'
import ShortcutsPage from './pages/ShortcutsPage'
import StoresPage from './pages/StoresPage'
import DestekPage from './pages/DestekPage'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/stores" element={<StoresPage />} />
          <Route path="/orders" element={<OrdersPage />} />
          <Route path="/orders/:orderId" element={<OrderDetailPage />} />
          <Route path="/aski" element={<AskiPage />} />
          <Route path="/telefon-modelleri" element={<PhoneModelsPage />} />
          <Route path="/stok" element={<StockPage />} />
          <Route path="/paketleme" element={<PackagingPage />} />
          <Route path="/destek" element={<DestekPage />} />
          <Route path="/designs" element={<DesignsPage />} />
          <Route path="/kisiye-ozel" element={<KisiyeOzelPage />} />
          <Route path="/kalip-sablon" element={<MoldTemplatePage />} />
          <Route path="/kalip-olustur" element={<MoldGeneratorPage />} />
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
  )
}
