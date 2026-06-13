import { useState, useEffect } from 'react'
import { api } from '../lib/api'
import { useToast } from '../components/Toast'
import { useAuth } from '../lib/auth'
import StoresPage from './StoresPage'

export default function SettingsPage() {
  const { user: _me } = useAuth()
  const _isAdmin = (_me?.role === 'yonetici' || _me?.role === 'owner')
  const [tab, setTab] = useState(_isAdmin ? 'stores' : 'brand')
  return (
    <div className="max-w-5xl animate-fadein">
      <div className="mb-5">
        <h1 className="text-2xl font-semibold text-gray-100">⚙️ Ayarlar</h1>
        <p className="text-sm text-gray-500 mt-1">Mağaza, marka ve hesap ayarları</p>
      </div>

      <div className="flex gap-1 border-b border-brand-border mb-5 overflow-x-auto">
        {_isAdmin && <TabBtn active={tab === 'stores'} onClick={() => setTab('stores')}>🏪 Mağazalar</TabBtn>}
        <TabBtn active={tab === 'brand'} onClick={() => setTab('brand')}>🎨 Marka & Logo</TabBtn>
        <TabBtn active={tab === 'account'} onClick={() => setTab('account')}>👤 Hesap</TabBtn>
        {_isAdmin && <TabBtn active={tab === 'users'} onClick={() => setTab('users')}>👥 Kullanıcılar</TabBtn>}
      </div>

      {tab === 'stores' && _isAdmin && <div className="-mt-2"><StoresPage embedded /></div>}
      {tab === 'brand' && <BrandTab />}
      {tab === 'account' && <AccountTab />}
      {tab === 'users' && _isAdmin && <UsersTab />}
    </div>
  )
}

function BrandTab() {
  const { tenant, user, refresh } = useAuth()
  const _isAdmin = (user?.role === 'yonetici' || user?.role === 'owner')
  return (
    <div className="space-y-5 animate-fadein">
      {_isAdmin && <LogoUploader
        title="Marka Logosu"
        desc="Sol üstte ve markalamada görünür. PNG/SVG/JPG, max 5MB."
        current={tenant?.logo_url}
        uploadUrl="/api/tenant/brand-logo"
        deleteUrl="/api/tenant/brand-logo"
        onDone={refresh}
        shape="rounded-xl"
      />}
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

function UsersTab() {
  const _toastU = useToast()
  const { user: me } = useAuth()
  const [users, setUsers] = useState([])
  const [meta, setMeta] = useState({ all_permissions: [], templates: {} })
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const [editing, setEditing] = useState(null)  // user obj veya {} (yeni) veya null (kapali)

  const load = async () => {
    setLoading(true); setErr('')
    try {
      const [u, m] = await Promise.all([api.get('/api/users'), api.get('/api/users/_roles')])
      setUsers(Array.isArray(u) ? u : [])
      setMeta(m || { all_permissions: [], templates: {} })
    } catch (e) { setErr('Kullanıcılar yüklenemedi') }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const remove = async (u) => {
    if (!confirm(`${u.full_name || u.email} silinsin mi?`)) return
    try { await api.del(`/api/users/${u.id}`); load() }
    catch (e) { _toastU.error(typeof e?.detail === 'string' ? e.detail : 'Silinemedi') }
  }

  if (loading) return <div className="text-gray-500 text-sm py-8 text-center">Yükleniyor…</div>

  return (
    <div className="space-y-4 animate-fadein">
      {err && <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded px-3 py-2">{err}</div>}
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-400">Hesabını kullanan kişiler ve yetkileri</p>
        <button onClick={() => setEditing({})} className="btn-primary !text-sm">+ Kullanıcı Ekle</button>
      </div>

      <div className="space-y-2 stagger">
        {users.map(u => (
          <div key={u.id} className="card !py-3 flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-brand-input border border-brand-border overflow-hidden flex items-center justify-center shrink-0">
              {u.avatar_url ? <img src={u.avatar_url} alt="" className="w-full h-full object-cover" />
                : <span className="text-sm text-gray-400">{(u.full_name || u.email || '?').charAt(0).toUpperCase()}</span>}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-medium text-gray-100 truncate">{u.full_name || '—'}</span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-accent/15 text-accent">{u.role}</span>
                {!u.is_active && <span className="text-[10px] px-2 py-0.5 rounded-full bg-gray-600/30 text-gray-400">pasif</span>}
                {u.has_pin && <span className="text-[10px] text-gray-500" title="PIN korumalı">🔒</span>}
              </div>
              <div className="text-xs text-gray-500 truncate">{u.email}</div>
            </div>
            <button onClick={() => setEditing(u)} className="btn-secondary !text-xs">Düzenle</button>
            {u.id !== me?.id && (
              <button onClick={() => remove(u)} className="text-xs text-red-400/70 hover:text-red-300 px-2">Sil</button>
            )}
          </div>
        ))}
        {users.length === 0 && <div className="text-sm text-gray-500 py-6 text-center">Henüz kullanıcı yok.</div>}
      </div>

      {editing && <UserDialog user={editing} meta={meta} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load() }} />}
    </div>
  )
}

function UserDialog({ user, meta, onClose, onSaved }) {
  const isNew = !user.id
  const [fullName, setFullName] = useState(user.full_name || '')
  const [email, setEmail] = useState(user.email || '')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState(user.role || 'baskici')
  const [perms, setPerms] = useState(user.permissions || meta.templates?.[user.role || 'baskici'] || [])
  const [pin, setPin] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const isAdminRole = role === 'yonetici' || role === 'owner'

  const applyTemplate = (r) => {
    setRole(r)
    if (meta.templates?.[r]) setPerms(meta.templates[r])
  }
  const togglePerm = (p) => setPerms(cur => cur.includes(p) ? cur.filter(x => x !== p) : [...cur, p])

  const save = async () => {
    if (!fullName.trim()) { setErr('Ad gerekli'); return }
    if (isNew && (!email.trim() || password.length < 6)) { setErr('Email + en az 6 karakter şifre gerekli'); return }
    setBusy(true); setErr('')
    try {
      let saved
      if (isNew) {
        saved = await api.post('/api/users', { email, full_name: fullName, password, role, permissions: perms })
      } else {
        const body = { full_name: fullName, role, permissions: perms }
        if (password) body.password = password
        saved = await api.patch(`/api/users/${user.id}`, body)
      }
      // PIN ayri endpoint
      if (pin) await api.post(`/api/users/${saved.id || user.id}/pin`, { pin })
      onSaved()
    } catch (e) { setErr(typeof e?.detail === 'string' ? e.detail : 'Kaydedilemedi'); setBusy(false) }
  }
  const clearPin = async () => {
    if (!user.id) return
    try { await api.post(`/api/users/${user.id}/pin`, { pin: null }); onSaved() }
    catch { setErr('PIN kaldırılamadı') }
  }

  const permLabels = {
    dashboard: 'Dashboard', siparisler: 'Siparişler', paketleme: 'Paketleme', destek: 'Destek',
    tasarim: 'Tasarımlar', kisiye_ozel: 'Kişiye Özel', aksesuar: 'Aksesuarlar', couple: 'Couple',
    kalip: 'Kalıp', stok: 'Stok', telefon_modelleri: 'Telefon Modelleri', ayarlar: 'Ayarlar',
    kullanici_yonetimi: 'Kullanıcı Yönetimi',
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 overflow-y-auto" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-lg p-5 my-8 animate-popin">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-100">{isNew ? 'Yeni Kullanıcı' : 'Kullanıcıyı Düzenle'}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-200 text-2xl leading-none">×</button>
        </div>
        {err && <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded px-3 py-2 mb-3">{err}</div>}

        <label className="block mb-3"><span className="block text-xs text-gray-400 mb-1">Ad Soyad</span>
          <input className="input w-full" value={fullName} onChange={e => setFullName(e.target.value)} /></label>
        {isNew && (
          <label className="block mb-3"><span className="block text-xs text-gray-400 mb-1">E-posta</span>
            <input className="input w-full" type="email" value={email} onChange={e => setEmail(e.target.value)} /></label>
        )}
        <label className="block mb-3"><span className="block text-xs text-gray-400 mb-1">{isNew ? 'Şifre' : 'Yeni şifre (boş = değişmez)'}</span>
          <input className="input w-full" type="password" value={password} onChange={e => setPassword(e.target.value)} /></label>

        <label className="block mb-3"><span className="block text-xs text-gray-400 mb-1">Rol</span>
          <select className="input w-full" value={role} onChange={e => applyTemplate(e.target.value)}>
            <option value="yonetici">Yönetici (tüm yetkiler)</option>
            <option value="baskici">Baskıcı</option>
            <option value="paketlemeci">Paketlemeci</option>
            <option value="ozel">Özel</option>
          </select>
        </label>

        <div className="mb-3">
          <span className="block text-xs text-gray-400 mb-2">Yetkiler {isAdminRole && <span className="text-accent">(yönetici tümüne sahip)</span>}</span>
          <div className={`grid grid-cols-2 gap-1.5 ${isAdminRole ? 'opacity-40 pointer-events-none' : ''}`}>
            {(meta.all_permissions || []).map(p => (
              <label key={p} className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
                <input type="checkbox" checked={isAdminRole || perms.includes(p)} onChange={() => togglePerm(p)} className="accent-accent" />
                {permLabels[p] || p}
              </label>
            ))}
          </div>
        </div>

        <label className="block mb-1"><span className="block text-xs text-gray-400 mb-1">PIN (4-8 hane, opsiyonel — profil kilidi)</span>
          <input className="input w-full" inputMode="numeric" value={pin} onChange={e => setPin(e.target.value.replace(/\D/g, '').slice(0, 8))} placeholder={user.has_pin ? '•••• (mevcut)' : 'PIN yok'} /></label>
        {!isNew && user.has_pin && <button onClick={clearPin} className="text-xs text-red-400/70 hover:text-red-300 mb-2">PIN'i kaldır</button>}

        <div className="flex justify-end gap-2 mt-4">
          <button onClick={onClose} className="btn-secondary !text-sm">İptal</button>
          <button onClick={save} disabled={busy} className="btn-primary !text-sm">{busy ? '…' : 'Kaydet'}</button>
        </div>
      </div>
    </div>
  )
}

