import { useState } from 'react'
import StoresPage from './StoresPage'

export default function SettingsPage() {
  const [tab, setTab] = useState('stores')
  return (
    <div className="max-w-5xl animate-fadein">
      <div className="mb-5">
        <h1 className="text-2xl font-semibold text-gray-100">⚙️ Ayarlar</h1>
        <p className="text-sm text-gray-500 mt-1">Mağaza, marka ve hesap ayarları</p>
      </div>

      <div className="flex gap-1 border-b border-brand-border mb-5 overflow-x-auto">
        <TabBtn active={tab === 'stores'} onClick={() => setTab('stores')}>🏪 Mağazalar</TabBtn>
        <TabBtn active={tab === 'brand'} onClick={() => setTab('brand')}>🎨 Marka & Logo</TabBtn>
        <TabBtn active={tab === 'account'} onClick={() => setTab('account')}>👤 Hesap</TabBtn>
      </div>

      {tab === 'stores' && (
        <div className="-mt-2">
          <StoresPage embedded />
        </div>
      )}
      {tab === 'brand' && (
        <div className="card text-center py-12 text-gray-500">
          <div className="text-3xl mb-2">🎨</div>
          Marka ve logo ayarları yakında burada olacak.
        </div>
      )}
      {tab === 'account' && (
        <div className="card text-center py-12 text-gray-500">
          <div className="text-3xl mb-2">👤</div>
          Hesap ayarları yakında burada olacak.
        </div>
      )}
    </div>
  )
}

function TabBtn({ active, onClick, children }) {
  return (
    <button onClick={onClick}
      className={`px-4 py-2 text-sm font-medium whitespace-nowrap border-b-2 -mb-px transition-colors ${
        active ? 'border-accent text-accent' : 'border-transparent text-gray-400 hover:text-gray-200'
      }`}>
      {children}
    </button>
  )
}
