import { useAuth } from '../lib/auth'

export default function DashboardPage() {
  const { user, tenant } = useAuth()

  return (
    <div className="max-w-3xl">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-100">
          Hoş geldin, {user?.full_name?.split(' ')[0] || 'sen'} 👋
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          {tenant?.name} · {tenant?.plan} plan
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <Stat label="Mağazalar" value="—" hint="Henüz mağaza yok" />
        <Stat label="Bu ay sipariş" value="—" hint="Pipeline kurulduktan sonra" />
        <Stat label="Kalıp" value="—" hint="Henüz çalıştırılmadı" />
      </div>

      <div className="card">
        <h2 className="text-sm font-semibold text-gray-200 mb-3">Sıradaki adımlar</h2>
        <ul className="space-y-2 text-sm text-gray-400">
          <li className="flex items-start gap-2">
            <span className="text-accent">→</span>
            <span><strong className="text-gray-200">Mağaza ekle:</strong> Shopify veya İkas API bilgilerinle bağlan.</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-accent">→</span>
            <span><strong className="text-gray-200">Kısayolları yükle:</strong> Mevcut kisayollar JSON'larını içe aktar.</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-accent">→</span>
            <span><strong className="text-gray-200">İlk pipeline:</strong> Sipariş aralığı seç, çek, kalıba grupla.</span>
          </li>
        </ul>
        <p className="text-xs text-gray-600 mt-4">
          Bu sayfa şu an boş — sonraki adımlarda mağaza yönetimi, pipeline ve kalıp arayüzleri eklenecek.
        </p>
      </div>
    </div>
  )
}

function Stat({ label, value, hint }) {
  return (
    <div className="card">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className="text-2xl font-semibold text-gray-100">{value}</div>
      <div className="text-[10px] text-gray-600 mt-1">{hint}</div>
    </div>
  )
}
