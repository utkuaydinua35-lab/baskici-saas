import { useState, useEffect } from 'react'
import { api } from '../lib/api'
import { accentFg } from '../lib/auth'
import { useToast } from '../components/Toast'
import { useAuth } from '../lib/auth'
import StoresPage from './StoresPage'
import EtiketSablonPage from './EtiketSablonPage'
import BayiYonetim from './BayiYonetim'
import PlatformPage from './PlatformPage'

export default function SettingsPage() {
  const { user: _me } = useAuth()
  const _isAdmin = (_me?.role === 'yonetici' || _me?.role === 'owner')
  const _isPlatform = !!_me?.is_platform_admin
  const [tab, setTab] = useState(_isAdmin ? 'stores' : 'brand')
  return (
    <div className="mx-auto max-w-5xl animate-fadein">
      <div className="mb-5">
        <h1 className="text-2xl font-semibold text-gray-100">⚙️ Ayarlar</h1>
        <p className="text-sm text-gray-500 mt-1">Mağaza, marka ve hesap ayarları</p>
      </div>

      <div className="flex gap-1 border-b border-brand-border mb-5 overflow-x-auto">
        {_isAdmin && <TabBtn active={tab === 'stores'} onClick={() => setTab('stores')}>🏪 Mağazalar</TabBtn>}
        <TabBtn active={tab === 'brand'} onClick={() => setTab('brand')}>🎨 Marka & Logo</TabBtn>
        <TabBtn active={tab === 'account'} onClick={() => setTab('account')}>👤 Hesap</TabBtn>
        {_isAdmin && <TabBtn active={tab === 'bayiler'} onClick={() => setTab('bayiler')}>🤝 Bayiler</TabBtn>}
        {_isAdmin && <TabBtn active={tab === 'users'} onClick={() => setTab('users')}>👥 Kullanıcılar</TabBtn>}
        {_isAdmin && <TabBtn active={tab === 'ai'} onClick={() => setTab('ai')}>🤖 AI Destek</TabBtn>}
        {_isAdmin && <TabBtn active={tab === 'etiket'} onClick={() => setTab('etiket')}>🏷 Etiket Şablonu</TabBtn>}
        {_isPlatform && <TabBtn active={tab === 'platform'} onClick={() => setTab('platform')}>🏢 Atölyeler</TabBtn>}
      </div>

      {tab === 'stores' && _isAdmin && <div className="-mt-2"><StoresPage embedded /></div>}
      {tab === 'brand' && <BrandTab />}
      {tab === 'account' && <AccountTab />}
      {tab === 'bayiler' && _isAdmin && <BayiYonetim />}
      {tab === 'users' && _isAdmin && <UsersTab />}
      {tab === 'ai' && _isAdmin && <AISettingsTab />}
      {tab === 'etiket' && _isAdmin && <EtiketSablonPage embedded />}
      {tab === 'platform' && _isPlatform && <div className="-mt-2"><PlatformPage /></div>}
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
      {_isAdmin && <BrandIdentity onSaved={refresh} />}
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

function BrandIdentity({ onSaved }) {
  const toast = useToast()
  const [color, setColor] = useState('#14b8a6')
  const [appName, setAppName] = useState('')
  const [orig, setOrig] = useState({ color: '', appName: '' })
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.get('/api/tenant/settings').then(r => {
      setColor(r.brand_color || '#14b8a6')
      setAppName(r.app_name || '')
      setOrig({ color: r.brand_color || '', appName: r.app_name || '' })
    }).catch(() => {})
  }, [])

  const dirty = (color !== (orig.color || '#14b8a6')) || (appName !== orig.appName)

  const save = async () => {
    setSaving(true)
    try {
      const r = await api.patch('/api/tenant/settings', { brand_color: color, app_name: appName })
      setOrig({ color: r.brand_color || '', appName: r.app_name || '' })
      // anında uygula
      const m = /^#?([0-9a-fA-F]{6})$/.exec(color)
      if (m) {
        const n = parseInt(m[1], 16)
        const rgb = `${(n>>16)&255} ${(n>>8)&255} ${n&255}`
        document.documentElement.style.setProperty('--accent-rgb', rgb)
        document.documentElement.style.setProperty('--accent-fg', accentFg(rgb))
      }
      if (appName) document.title = appName
      toast.success('Marka kimliği kaydedildi')
      onSaved?.()
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Kaydedilemedi')
    } finally { setSaving(false) }
  }

  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-gray-100 mb-1">Marka Kimliği</h3>
      <p className="text-xs text-gray-500 mb-4">Panel ve müşteri sayfalarındaki vurgu rengi + uygulama adı.</p>
      <div className="space-y-3">
        <div>
          <label className="text-xs text-gray-400 block mb-1">Vurgu rengi (accent)</label>
          <div className="flex items-center gap-2">
            <input type="color" value={color} onChange={e => setColor(e.target.value)}
              className="w-10 h-9 rounded-lg bg-transparent border border-brand-border cursor-pointer p-0.5" />
            <input type="text" value={color} onChange={e => setColor(e.target.value)}
              placeholder="#14b8a6" className="input !text-sm font-mono w-28" />
            <span className="text-xs px-2 py-1 rounded-lg text-white" style={{ background: color }}>Önizleme</span>
          </div>
        </div>
        <div>
          <label className="text-xs text-gray-400 block mb-1">Uygulama adı (sekme başlığı)</label>
          <input type="text" value={appName} onChange={e => setAppName(e.target.value)}
            placeholder="ör. Atölyem Panel" maxLength={80} className="input !text-sm w-full max-w-xs" />
        </div>
        {dirty && (
          <button onClick={save} disabled={saving} className="btn-primary !text-xs disabled:opacity-50">
            {saving ? 'Kaydediliyor…' : 'Kaydet'}
          </button>
        )}
      </div>
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
  const { user, refresh } = useAuth()
  const [showPw, setShowPw] = useState(false)
  const [show2fa, setShow2fa] = useState(false)
  const [showPasskey, setShowPasskey] = useState(false)
  const twoFaOn = !!user?.totp_enabled
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
        <p className="text-xs text-gray-500 mb-3">Şifreni değiştir veya iki adımlı doğrulamayı (2FA) yönet.</p>
        <div className="flex flex-wrap gap-2">
          <button onClick={() => setShowPw(true)} className="btn-secondary !text-sm">🔑 Şifre Değiştir</button>
          <button onClick={() => setShow2fa(true)} className="btn-secondary !text-sm">
            🔐 İki Adımlı Doğrulama
            <span className={`ml-1.5 text-[11px] px-1.5 py-0.5 rounded ${twoFaOn ? 'bg-emerald-500/15 text-emerald-300' : 'bg-gray-500/15 text-gray-400'}`}>
              {twoFaOn ? 'Açık' : 'Kapalı'}
            </span>
          </button>
          <button onClick={() => setShowPasskey(true)} className="btn-secondary !text-sm">🔑 Geçiş Anahtarları</button>
        </div>
      </div>
      <NotificationsCard />
      {showPw && <ChangePasswordModal onClose={() => setShowPw(false)} />}
      {show2fa && <TwoFactorModal enabled={twoFaOn} onClose={() => setShow2fa(false)} onChanged={refresh} />}
      {showPasskey && <PasskeyModal onClose={() => setShowPasskey(false)} />}
    </div>
  )
}

// Mobil bildirim (Web Push) — bu CIHAZ icin ac/kapa. iOS'ta once 'Ana ekrana ekle' gerekir.
function NotificationsCard() {
  const toast = useToast()
  const [state, setState] = useState(null)  // getPushState sonucu
  const [busy, setBusy] = useState(false)

  const load = async () => {
    try {
      const { getPushState } = await import('../lib/push')
      setState(await getPushState())
    } catch { setState({ supported: false }) }
  }
  useEffect(() => { load() }, [])

  const iosStandalone = typeof window !== 'undefined'
    && window.navigator.standalone === false
    && /iphone|ipad|ipod/i.test(window.navigator.userAgent)

  const enable = async () => {
    setBusy(true)
    try {
      const { enablePush } = await import('../lib/push')
      await enablePush()
      toast.success('Mobil bildirimler açıldı')
      await load()
    } catch (e) { toast.error(e?.message || 'Bildirim açılamadı') }
    finally { setBusy(false) }
  }
  const disable = async () => {
    setBusy(true)
    try {
      const { disablePush } = await import('../lib/push')
      await disablePush()
      toast.success('Mobil bildirimler kapatıldı')
      await load()
    } catch (e) { toast.error(e?.message || 'Kapatılamadı') }
    finally { setBusy(false) }
  }
  const test = async () => {
    try {
      const { testPush } = await import('../lib/push')
      const r = await testPush()
      if (r.sent > 0) toast.success('Deneme bildirimi gönderildi')
      else toast.error(r.reason || 'Gönderilemedi — önce bildirimi aç')
    } catch { toast.error('Gönderilemedi') }
  }

  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-gray-200 mb-1">📱 Mobil Bildirimler</h3>
      <p className="text-xs text-gray-500 mb-3">
        Bu cihaza; yeni destek mesajı, müşteri onayı, sabah özeti ve yeni mağaza başvurusu bildirimleri gönderilir.
      </p>
      {!state ? (
        <p className="text-xs text-gray-500">Yükleniyor…</p>
      ) : !state.supported ? (
        <p className="text-xs text-amber-300/80">Bu tarayıcı bildirim desteklemiyor.</p>
      ) : !state.serverEnabled ? (
        <p className="text-xs text-amber-300/80">Sunucuda bildirim altyapısı henüz kurulmadı (VAPID anahtarı yok).</p>
      ) : state.permission === 'denied' ? (
        <p className="text-xs text-amber-300/80">Bildirim izni tarayıcıda engellenmiş — site ayarlarından izin ver.</p>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          {state.subscribed ? (
            <>
              <span className="text-[11px] px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300">Bu cihazda açık</span>
              <button onClick={test} className="btn-secondary !text-sm">🔔 Deneme gönder</button>
              <button onClick={disable} disabled={busy} className="btn-secondary !text-sm">Kapat</button>
            </>
          ) : (
            <button onClick={enable} disabled={busy} className="btn-primary !text-sm">
              {busy ? 'Açılıyor…' : '🔔 Bildirimleri Aç'}
            </button>
          )}
        </div>
      )}
      {iosStandalone && (
        <p className="text-[11px] text-gray-500 mt-2">
          iPhone/iPad: bildirimler yalnızca uygulama <b>“Ana ekrana ekle”</b> ile kurulduktan sonra çalışır.
        </p>
      )}
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
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-md p-5 animate-popin">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-100">Şifre Değiştir</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-200 text-2xl leading-none">×</button>
        </div>
        {ok ? <div className="text-sm text-emerald-300 py-4 text-center">✓ Şifre güncellendi</div> : (
          <>
            {err && <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded px-3 py-2 mb-3">{err}</div>}
            <Field label="Mevcut şifre"><SecretInput value={cur} onChange={e => setCur(e.target.value)} autoComplete="current-password" /></Field>
            <Field label="Yeni şifre"><SecretInput value={nw} onChange={e => setNw(e.target.value)} autoComplete="new-password" /></Field>
            <Field label="Yeni şifre (tekrar)"><SecretInput value={nw2} onChange={e => setNw2(e.target.value)} autoComplete="new-password" /></Field>
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

// Geçiş anahtarları (passkey / WebAuthn) — listele, ekle, sil
function PasskeyModal({ onClose }) {
  const [list, setList] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [onlyPk, setOnlyPk] = useState(null)   // { enabled, passkey_count }
  const load = async () => {
    try { setList(await api.get('/api/auth/passkey')) } catch (e) { setErr(e.detail || 'Yüklenemedi'); setList([]) }
    try { setOnlyPk(await api.get('/api/auth/passkey/only')) } catch { /* eski sürüm */ }
  }
  useEffect(() => { load() }, [])
  const toggleOnly = async () => {
    const next = !onlyPk?.enabled
    if (next && !confirm(
      'Şifreyle giriş KAPATILACAK.\n\n' +
      'Bundan sonra bu hesaba yalnızca geçiş anahtarıyla girebilirsin — ' +
      'şifreni bilen biri bile giremez.\n\n' +
      'Devam etmeden önce geçiş anahtarının çalıştığından emin ol.\n\nAçılsın mı?'
    )) return
    setErr(''); setBusy(true)
    try { await api.post('/api/auth/passkey/only', { enabled: next }); load() }
    catch (e) { setErr(e.detail || 'Değiştirilemedi') }
    finally { setBusy(false) }
  }
  const add = async () => {
    setErr(''); setBusy(true)
    try {
      const name = (prompt('Bu cihaz için bir ad (örn. "MacBook Touch ID"):') || 'Passkey').trim()
      const { registerPasskey } = await import('../lib/webauthn')
      await registerPasskey(name || 'Passkey')
      load()
    } catch (e) {
      const name = e?.name || ''
      const m = e?.detail || e?.message || ''
      if (name === 'InvalidStateError') {
        setErr('Bu cihazda bu hesap için zaten bir geçiş anahtarı var (iCloud/Google ile senkronlanmış olabilir). Tekrar eklemene gerek yok — çıkış yapıp “🔑 Geçiş anahtarı ile giriş” ile deneyebilirsin.')
      } else if (name === 'NotAllowedError' || /aborterror|notallowed|cancel/i.test(m)) {
        /* kullanıcı vazgeçti — sessiz geç */
      } else {
        setErr(m || 'Passkey eklenemedi')
      }
    } finally { setBusy(false) }
  }
  const del = async (id) => {
    if (!confirm('Bu geçiş anahtarı silinsin mi?')) return
    try { await api.del(`/api/auth/passkey/${id}`); load() } catch (e) { setErr(e.detail || 'Silinemedi') }
  }
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-md p-5">
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-lg font-semibold text-gray-100">🔑 Geçiş Anahtarları</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-200 text-2xl leading-none">×</button>
        </div>
        <p className="text-xs text-gray-500 mb-3">Parolasız giriş için cihaz biyometrini (Touch ID / Windows Hello / telefon) kullan. Giriş ekranında “🔑 Geçiş anahtarı ile giriş” ile açılır.</p>
        {err && <div className="text-xs text-red-300 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 mb-3">{err}</div>}
        <div className="space-y-1.5 mb-3">
          {list === null ? <div className="text-sm text-gray-500 py-3 text-center">Yükleniyor…</div>
            : list.length === 0 ? <div className="text-sm text-gray-600 py-3 text-center">Henüz geçiş anahtarı yok.</div>
            : list.map(p => (
              <div key={p.id} className="flex items-center justify-between bg-brand-input/40 rounded-lg px-3 py-2">
                <div className="min-w-0">
                  <div className="text-sm text-gray-200 truncate">{p.name}</div>
                  <div className="text-[10px] text-gray-600">Eklendi: {p.created_at ? new Date(p.created_at).toLocaleDateString('tr-TR') : '—'}{p.last_used_at ? ` · Son giriş: ${new Date(p.last_used_at).toLocaleDateString('tr-TR')}` : ''}</div>
                </div>
                <button onClick={() => del(p.id)} className="text-gray-500 hover:text-red-400 text-sm shrink-0 ml-2">Sil</button>
              </div>
            ))}
        </div>
        <button onClick={add} disabled={busy} className="btn-primary w-full !text-sm disabled:opacity-50">{busy ? 'Bekleniyor…' : '＋ Geçiş anahtarı ekle'}</button>

        {onlyPk && (
          <div className="mt-4 pt-4 border-t border-brand-border/70">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="text-sm text-gray-200">Yalnızca geçiş anahtarıyla giriş</div>
                <p className="text-[11px] text-gray-500 mt-0.5">
                  Açıkken e-posta+şifre girişi reddedilir. Şifre tahmin saldırıları
                  tamamen anlamsızlaşır.
                </p>
              </div>
              <button
                onClick={toggleOnly}
                disabled={busy || (!onlyPk.enabled && (onlyPk.passkey_count || 0) < 1)}
                className={`shrink-0 text-xs px-3 py-1.5 rounded-full border transition-colors disabled:opacity-40 ${
                  onlyPk.enabled
                    ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                    : 'bg-brand-input/60 text-gray-400 border-brand-border'
                }`}
              >
                {onlyPk.enabled ? 'Açık' : 'Kapalı'}
              </button>
            </div>
            {(onlyPk.passkey_count || 0) < 1 && !onlyPk.enabled && (
              <p className="text-[11px] text-amber-300/80 mt-2">
                Açmak için önce en az bir geçiş anahtarı ekle.
              </p>
            )}
            {onlyPk.enabled && (
              <p className="text-[11px] text-gray-600 mt-2">
                Kilitlenirsen sunucudan geri alınır — Claude'a “passkey kilidini aç” de.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// İki adımlı dogrulama (2FA / TOTP) — kurulum, acma, kapatma, yedek kodlar
function TwoFactorModal({ enabled, onClose, onChanged }) {
  const [phase, setPhase] = useState(enabled ? 'disable' : 'setup') // setup | codes | disable
  const [qr, setQr] = useState(''); const [secret, setSecret] = useState('')
  const [code, setCode] = useState(''); const [pw, setPw] = useState('')
  const [codes, setCodes] = useState([])
  const [busy, setBusy] = useState(false); const [err, setErr] = useState('')
  const [copied, setCopied] = useState('')
  const errMsg = (e) => (typeof e?.detail === 'string' ? e.detail : null)

  // Kurulum: secret + QR al (yalnizca kapaliyken)
  useEffect(() => {
    if (enabled) return
    let alive = true
    setBusy(true); setErr('')
    api.post('/api/auth/2fa/setup')
      .then(d => { if (alive) { setQr(d.qr); setSecret(d.secret); setBusy(false) } })
      .catch(e => { if (alive) { setErr(errMsg(e) || 'Kurulum başlatılamadı'); setBusy(false) } })
    return () => { alive = false }
  }, [enabled])

  const enable = async () => {
    if (!code.trim()) { setErr('Kodu gir'); return }
    setBusy(true); setErr('')
    try {
      const d = await api.post('/api/auth/2fa/enable', { code: code.trim() })
      setCodes(d.backup_codes || []); setPhase('codes')
    } catch (e) { setErr(errMsg(e) || 'Kod doğrulanamadı'); setBusy(false) }
  }

  const disable = async () => {
    if (!pw && !code) { setErr('Şifre veya kod gir'); return }
    setBusy(true); setErr('')
    try {
      await api.post('/api/auth/2fa/disable', { password: pw || null, code: code.trim() || null })
      onChanged?.(); onClose()
    } catch (e) { setErr(errMsg(e) || 'Kapatılamadı'); setBusy(false) }
  }

  const finish = () => { onChanged?.(); onClose() }
  const copy = (text, key) => {
    navigator.clipboard?.writeText(text)
      .then(() => { setCopied(key); setTimeout(() => setCopied(''), 1500) }).catch(() => {})
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-md p-5 animate-popin max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-100">İki Adımlı Doğrulama</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-200 text-2xl leading-none">×</button>
        </div>
        {err && <div className="text-sm text-red-300 bg-red-500/10 border border-red-500/30 rounded px-3 py-2 mb-3">{err}</div>}

        {phase === 'disable' && (
          <>
            <p className="text-sm text-gray-300 mb-3">2FA şu an <b className="text-emerald-300">açık</b>. Kapatmak için şifreni ya da uygulamandaki kodu gir.</p>
            <Field label="Şifre"><SecretInput value={pw} onChange={e => setPw(e.target.value)} autoComplete="current-password" /></Field>
            <div className="text-center text-[11px] text-gray-600 my-1">— veya —</div>
            <Field label="Authenticator kodu"><input className="input w-full text-center tracking-widest" inputMode="numeric" value={code} onChange={e => setCode(e.target.value)} placeholder="000000" /></Field>
            <div className="flex justify-end gap-2 mt-4">
              <button onClick={onClose} className="btn-secondary !text-sm">İptal</button>
              <button onClick={disable} disabled={busy} className="!text-sm px-3 py-1.5 rounded-lg bg-red-500/90 hover:bg-red-500 text-white font-medium disabled:opacity-50">{busy ? '...' : "2FA'yı Kapat"}</button>
            </div>
          </>
        )}

        {phase === 'setup' && (
          <>
            <p className="text-sm text-gray-300 mb-3">Authenticator uygulamanla (Google Authenticator, Authy, 1Password…) QR'ı tara, sonra çıkan 6 haneli kodu gir.</p>
            {busy && !qr ? (
              <div className="text-center text-sm text-gray-500 py-8">Hazırlanıyor…</div>
            ) : qr ? (
              <>
                <img src={qr} alt="2FA QR" className="w-44 h-44 mx-auto rounded-lg bg-white p-2" />
                <div className="mt-3">
                  <p className="text-[11px] text-gray-500 mb-1">QR taranmıyorsa bu anahtarı elle gir:</p>
                  <button onClick={() => copy(secret, 'secret')} className="w-full font-mono text-xs bg-brand-bg border border-brand-border rounded px-3 py-2 text-gray-300 hover:border-accent break-all text-left">
                    {secret} <span className="text-accent">{copied === 'secret' ? '✓ kopyalandı' : '⧉'}</span>
                  </button>
                </div>
                <div className="mt-4">
                  <Field label="Uygulamadaki 6 haneli kod">
                    <input className="input w-full text-center tracking-widest text-lg" inputMode="numeric" autoFocus value={code} onChange={e => setCode(e.target.value)} placeholder="000000" />
                  </Field>
                </div>
                <div className="flex justify-end gap-2 mt-1">
                  <button onClick={onClose} className="btn-secondary !text-sm">İptal</button>
                  <button onClick={enable} disabled={busy} className="btn-primary !text-sm">{busy ? '...' : 'Doğrula ve Aç'}</button>
                </div>
              </>
            ) : null}
          </>
        )}

        {phase === 'codes' && (
          <>
            <div className="text-sm text-emerald-300 mb-2">✓ 2FA açıldı!</div>
            <p className="text-sm text-gray-300 mb-1">Telefonunu kaybedersen bu <b>yedek kodlarla</b> giriş yapabilirsin. Her kod <b>bir kez</b> kullanılır.</p>
            <p className="text-[11px] text-amber-300/90 mb-3">⚠ Bu kodlar yalnızca şimdi gösterilir — güvenli bir yere kaydet.</p>
            <div className="grid grid-cols-2 gap-2 mb-3">
              {codes.map(c => <div key={c} className="font-mono text-sm text-center bg-brand-bg border border-brand-border rounded py-1.5 text-gray-200">{c}</div>)}
            </div>
            <button onClick={() => copy(codes.join('\n'), 'codes')} className="btn-secondary !text-sm w-full mb-2">{copied === 'codes' ? '✓ Kopyalandı' : '⧉ Tümünü Kopyala'}</button>
            <button onClick={finish} className="btn-primary !text-sm w-full">Kaydettim, Kapat</button>
          </>
        )}
      </div>
    </div>
  )
}

function Field({ label, children }) {
  return <label className="block mb-3"><span className="block text-xs text-gray-400 mb-1">{label}</span>{children}</label>
}

// Sifre/PIN girisi — goz simgesi ile gizle/goster
function SecretInput({ value, onChange, placeholder, inputMode, autoComplete }) {
  const [show, setShow] = useState(false)
  return (
    <div className="relative">
      <input
        className="input w-full !pr-9"
        type={show ? 'text' : 'password'}
        inputMode={inputMode}
        autoComplete={autoComplete}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
      />
      <button type="button" onClick={() => setShow(s => !s)} tabIndex={-1}
        title={show ? 'Gizle' : 'Göster'}
        className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-200 text-sm">
        {show ? '🙈' : '👁'}
      </button>
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

const AI_MODELS = [
  { value: 'haiku', label: 'Haiku', icon: '⚡', desc: 'En hızlı ve ekonomik — basit yanıtlar' },
  { value: 'sonnet', label: 'Sonnet', icon: '⚖️', desc: 'Dengeli — hız ve kalite' },
  { value: 'opus', label: 'Opus', icon: '💎', desc: 'En yetenekli — en kaliteli yanıtlar' },
]

function Toggle({ on, onChange }) {
  return (
    <button
      type="button"
      onClick={onChange}
      role="switch"
      aria-checked={on}
      className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors duration-300 ease-in-out focus:outline-none focus:ring-2 focus:ring-accent/40 ${
        on ? 'bg-gradient-to-r from-accent to-teal-600' : 'bg-brand-input'
      }`}
    >
      <span
        className={`inline-block h-5 w-5 transform rounded-full bg-white shadow-md transition-transform duration-300 ease-in-out ${
          on ? 'translate-x-[22px]' : 'translate-x-0.5'
        }`}
      />
    </button>
  )
}

function AISettingsTab() {
  const toast = useToast()
  const [loading, setLoading] = useState(true)
  const [meta, setMeta] = useState({ api_key_configured: false, master_configured: false })
  const [enabled, setEnabled] = useState(true)
  const [model, setModel] = useState('opus')
  const [master, setMaster] = useState('')
  const [orig, setOrig] = useState({ enabled: true, model: 'opus' })
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.get('/api/tenant/ai-settings').then(r => {
      setEnabled(!!r.enabled)
      setModel(r.model || 'opus')
      setOrig({ enabled: !!r.enabled, model: r.model || 'opus' })
      setMeta({ api_key_configured: !!r.api_key_configured, master_configured: !!r.master_configured })
    }).catch(() => {}).finally(() => setLoading(false))
  }, [])

  const dirty = enabled !== orig.enabled || model !== orig.model

  const save = async () => {
    if (!dirty) return
    if (!master.trim()) { toast.error('Master password gerekli'); return }
    setSaving(true)
    try {
      const r = await api.patch('/api/tenant/ai-settings', { enabled, model, master_password: master })
      setOrig({ enabled: !!r.enabled, model: r.model })
      setMaster('')
      toast.success('AI ayarları kaydedildi')
    } catch (e) {
      toast.error(e.detail || 'Kaydedilemedi')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="card animate-fadein max-w-2xl space-y-3">
        <div className="skeleton h-5 w-40 rounded" />
        <div className="skeleton h-12 w-full rounded-lg" />
        <div className="skeleton h-10 w-full rounded-lg" />
      </div>
    )
  }

  return (
    <div className="space-y-5 animate-fadeinup max-w-2xl">
      <div className="card overflow-hidden">
        {/* Başlık + durum rozeti */}
        <div className="flex items-start justify-between gap-3 mb-1">
          <h2 className="text-base font-semibold text-gray-100 flex items-center gap-2">
            <span className="text-xl">🤖</span> AI Destek Yanıtı
          </h2>
          <span className={`text-[11px] px-2.5 py-1 rounded-full border font-medium transition-colors duration-300 ${
            enabled
              ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
              : 'bg-gray-500/15 text-gray-400 border-gray-500/30'
          }`}>
            {enabled ? '● Açık' : '○ Kapalı'}
          </span>
        </div>
        <p className="text-xs text-gray-500 mb-4 leading-relaxed">
          Destek konuşmalarında müşteri mesajlarına Claude ile taslak cevap üretir. Operatör düzenleyip gönderir.
        </p>

        {!meta.api_key_configured && (
          <div className="text-xs rounded-lg px-3 py-2 mb-4 bg-amber-500/10 border border-amber-500/20 text-amber-300 animate-fadein">
            ⚠️ Sunucuda <span className="font-mono">ANTHROPIC_API_KEY</span> yapılandırılmamış — özellik açık olsa bile çalışmaz.
          </div>
        )}

        {/* Açık/Kapalı */}
        <div className="flex items-center justify-between gap-4 rounded-xl bg-brand-input/40 border border-brand-border px-4 py-3">
          <div>
            <div className="text-sm text-gray-200 font-medium">Özellik durumu</div>
            <div className="text-xs text-gray-500 mt-0.5">Kapalıysa "AI Taslak" butonu çalışmaz</div>
          </div>
          <Toggle on={enabled} onChange={() => setEnabled(e => !e)} />
        </div>

        {/* Model seçimi — yalnızca AÇIKKEN görünür */}
        {enabled && (
          <div className="mt-4 animate-fadeinup">
            <div className="text-sm text-gray-200 font-medium mb-1">Model seçimi</div>
            <div className="text-[11px] text-gray-500 mb-3">Yanıtların hızı ve kalitesini belirler</div>
            <div className="grid gap-2.5">
              {AI_MODELS.map((m, i) => {
                const sel = model === m.value
                return (
                  <button
                    key={m.value}
                    type="button"
                    onClick={() => setModel(m.value)}
                    style={{ animationDelay: `${i * 60}ms` }}
                    className={`group relative text-left flex items-center gap-3 px-4 py-3 rounded-xl border transition-all duration-200 animate-fadeinup hover:-translate-y-0.5 ${
                      sel
                        ? 'border-accent bg-accent/10 shadow-[0_0_0_1px_rgba(124,92,255,0.4)]'
                        : 'border-brand-border hover:border-brand-border/80 hover:bg-brand-input/60'
                    }`}
                  >
                    <span className={`text-2xl transition-transform duration-200 ${sel ? 'scale-110' : 'group-hover:scale-105'}`}>
                      {m.icon}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className={`text-sm font-medium ${sel ? 'text-accent' : 'text-gray-200'}`}>{m.label}</div>
                      <div className="text-[11px] text-gray-500">{m.desc}</div>
                    </div>
                    <span className={`w-5 h-5 rounded-full border-2 flex items-center justify-center transition-all duration-200 ${
                      sel ? 'border-accent bg-accent scale-100' : 'border-brand-border scale-90'
                    }`}>
                      {sel && <span className="text-white text-[11px] leading-none animate-popin">✓</span>}
                    </span>
                  </button>
                )
              })}
            </div>
          </div>
        )}

        {/* Master password + kaydet — değişiklik olunca */}
        {dirty && (
          <div className="mt-4 pt-4 border-t border-brand-border animate-popin">
            <label className="text-xs text-gray-300 block mb-1.5 flex items-center gap-1.5">
              <span>🔒</span> Master Password
              <span className="text-gray-500 font-normal">— değişikliği onaylamak için</span>
            </label>
            <div className="flex gap-2">
              <input type="password" value={master} onChange={e => setMaster(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') save() }}
                placeholder="••••••••" autoComplete="off"
                className="input !text-sm flex-1" />
              <button onClick={save} disabled={saving || !master.trim()}
                className="btn-primary !text-sm disabled:opacity-40 min-w-[110px]">
                {saving ? 'Kaydediliyor…' : '✓ Kaydet'}
              </button>
            </div>
            {!meta.master_configured && (
              <p className="text-[11px] text-amber-400 mt-1.5">
                ⚠️ Sunucuda master password (<span className="font-mono">AI_MODEL_MASTER_PASSWORD</span>) ayarlı değil — kayıt reddedilir.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
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
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4 overflow-y-auto" onMouseDown={e => e.target === e.currentTarget && onClose()}>
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
          <SecretInput value={password} onChange={e => setPassword(e.target.value)} autoComplete="new-password" /></label>

        <label className="block mb-3"><span className="block text-xs text-gray-400 mb-1">Rol</span>
          <select className="input w-full" value={role} onChange={e => applyTemplate(e.target.value)}>
            <option value="yonetici">Yönetici (tüm yetkiler)</option>
            <option value="baskici">Baskıcı</option>
            <option value="paketlemeci">Paketlemeci</option>
            <option value="grafiker">Grafiker (kişiye özel + tasarım)</option>
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
          <SecretInput value={pin} onChange={e => setPin(e.target.value.replace(/\D/g, '').slice(0, 8))}
            inputMode="numeric" placeholder={user.has_pin ? '•••• (mevcut)' : 'PIN yok'} /></label>
        {!isNew && user.has_pin && <button onClick={clearPin} className="text-xs text-red-400/70 hover:text-red-300 mb-2">PIN'i kaldır</button>}

        <div className="flex justify-end gap-2 mt-4">
          <button onClick={onClose} className="btn-secondary !text-sm">İptal</button>
          <button onClick={save} disabled={busy} className="btn-primary !text-sm">{busy ? '…' : 'Kaydet'}</button>
        </div>
      </div>
    </div>
  )
}

