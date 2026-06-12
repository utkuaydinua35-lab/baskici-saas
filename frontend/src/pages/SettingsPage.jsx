import { useState } from 'react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
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

      {tab === 'stores' && <div className="-mt-2"><StoresPage embedded /></div>}
      {tab === 'brand' && <BrandTab />}
      {tab === 'account' && <AccountTab />}
    </div>
  )
}

function BrandTab() {
  const { tenant, user, refresh } = useAuth()
  return (
    <div className="space-y-5 animate-fadein">
      <LogoUploader
        title="Marka Logosu"
        desc="Sol üstte ve markalamada görünür. PNG/SVG/JPG, max 5MB."
        current={tenant?.logo_url}
        uploadUrl="/api/tenant/brand-logo"
        deleteUrl="/api/tenant/brand-logo"
        onDone={refresh}
        shape="rounded-xl"
      />
      <LogoUploader
        title="Profil Görseli"
        desc="Profil bölümünde görünür (sana özel). PNG/SVG/JPG, max 5MB."
        current={user?.avatar_url}
        uploadUrl="/api/tenant/avatar"
        deleteUrl="/api/tenant/avatar"
        onDone={refresh}
        shape="rounded-full"
      />
    </div>
  )
}

function LogoUploader({ title, desc, current, uploadUrl, deleteUrl, onDone, shape }) {
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const pick = () => {
    const inp = document.createElement('input')
    inp.type = 'file'; inp.accept = 'image/png,image/jpeg,image/svg+xml,image/webp'
    inp.onchange = async () => {
      const f = inp.files?.[0]; if (!f) return
      setBusy(true); setErr('')
      try {
        const fd = new FormData(); fd.append('file', f)
        await api.postForm(uploadUrl, fd)
        await onDone?.()
      } catch (e) { setErr(typeof e?.detail === 'string' ? e.detail : 'Yüklenemedi') }
      finally { setBusy(false) }
    }
    inp.click()
  }
  const remove = async () => {
    setBusy(true); setErr('')
    try { await api.del(deleteUrl); await onDone?.() }
    catch (e) { setErr('Kaldırılamadı') } finally { setBusy(false) }
  }
  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-gray-200 mb-1">{title}</h3>
      <p className="text-xs text-gray-500 mb-3">{desc}</p>
      <div className="flex items-center gap-4">
        <div className={`w-20 h-20 ${shape} bg-brand-input border border-brand-border flex items-center justify-center overflow-hidden shrink-0`}>
          {current ? <img src={current} alt="" className="w-full h-full object-contain" /> : <span className="text-gray-600 text-2xl">🖼️</span>}
        </div>
        <div className="flex flex-col gap-2">
          <button onClick={pick} disabled={busy} className="btn-primary !text-sm">{busy ? 'Yükleniyor...' : (current ? 'Değiştir' : 'Yükle')}</button>
          {current && <button onClick={remove} disabled={busy} className="text-xs text-red-400/70 hover:text-red-300">Kaldır</button>}
        </div>
      </div>
      {err && <div className="text-xs text-red-300 mt-2">{err}</div>}
    </div>
  )
}

function AccountTab() {
  const { user } = useAuth()
  const [showPw, setShowPw] = useState(false)
  return (
    <div className="space-y-4 animate-fadein">
      <div className="card">
        <h3 className="text-sm font-semibold text-gray-200 mb-3">Hesap Bilgileri</h3>
        <Row label="Ad Soyad" value={user?.full_name || '—'} />
        <Row label="E-posta" value={user?.email || '—'} />
        <Row label="Rol" value={user?.role || '—'} />
      </div>
      <div className="card">
        <h3 className="text-sm font-semibold text-gray-200 mb-1">Güvenlik</h3>
        <p className="text-xs text-gray-500 mb-3">Hesap şifreni buradan değiştirebilirsin.</p>
        <button onClick={() => setShowPw(true)} className="btn-secondary !text-sm">🔑 Şifre Değiştir</button>
      </div>
      {showPw && <ChangePasswordModal onClose={() => setShowPw(false)} />}
    </div>
  )
}

function Row({ label, value }) {
  return (
    <div className="flex justify-between py-1.5 border-b border-brand-border/40 last:border-0">
      <span className="text-xs text-gray-500">{label}</span>
      <span className="text-sm text-gray-200">{value}</span>
    </div>
  )
}

// Sifre degistirme modali — basit, /api/auth/change-password
function ChangePasswordModal({ onClose }) {
  const [cur, setCur] = useState(''); const [nw, setNw] = useState(''); const [nw2, setNw2] = useState('')
  const [busy, setBusy] = useState(false); const [err, setErr] = useState(''); const [ok, setOk] = useState(false)
  const save = async () => {
    if (!cur || !nw) { setErr('Tüm alanları doldur'); return }
    if (nw !== nw2) { setErr('Yeni şifreler eşleşmiyor'); return }
    if (nw.length < 6) { setErr('Yeni şifre en az 6 karakter olmalı'); return }
    setBusy(true); setErr('')
    try {
      await api.post('/api/auth/change-password', { current_password: cur, new_password: nw })
      setOk(true); setTimeout(onClose, 1200)
    } catch (e) { setErr(typeof e?.detail === 'string' ? e.detail : 'Şifre değiştirilemedi'); setBusy(false) }
  }
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-md p-5 animate-popin">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-100">Şifre Değiştir</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-200 text-2xl leading-none">×</button>
        </div>
        {ok ? <div className="text-sm text-emerald-300 py-4 text-center">✓ Şifre güncellendi</div> : (
          <>
            {err && <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded px-3 py-2 mb-3">{err}</div>}
            <Field label="Mevcut şifre"><input type="password" className="input w-full" value={cur} onChange={e => setCur(e.target.value)} /></Field>
            <Field label="Yeni şifre"><input type="password" className="input w-full" value={nw} onChange={e => setNw(e.target.value)} /></Field>
            <Field label="Yeni şifre (tekrar)"><input type="password" className="input w-full" value={nw2} onChange={e => setNw2(e.target.value)} /></Field>
            <div className="flex justify-end gap-2 mt-4">
              <button onClick={onClose} className="btn-secondary !text-sm">İptal</button>
              <button onClick={save} disabled={busy} className="btn-primary !text-sm">{busy ? '...' : 'Kaydet'}</button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function Field({ label, children }) {
  return <label className="block mb-3"><span className="block text-xs text-gray-400 mb-1">{label}</span>{children}</label>
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
