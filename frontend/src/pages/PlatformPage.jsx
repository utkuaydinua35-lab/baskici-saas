import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useToast } from '../components/Toast'

function fmtDate(d) {
  if (!d) return '—'
  try { return new Date(d).toLocaleDateString('tr-TR') } catch { return d }
}

export default function PlatformPage() {
  const toast = useToast()
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [editing, setEditing] = useState(null)

  const load = async () => {
    setLoading(true)
    try { const r = await api.get('/api/platform/tenants'); setItems(r.items || []) }
    catch (e) { toast.error(typeof e?.detail === 'string' ? e.detail : 'Yüklenemedi') }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  return (
    <div className="max-w-[1100px]">
      <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-gray-100">🏢 Platform — Atölyeler</h1>
          <p className="text-sm text-gray-500 mt-1">{items.length} atölye · white-label kiralama yönetimi</p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary !text-sm">+ Yeni Atölye</button>
      </div>

      {loading ? (
        <div className="card"><div className="skeleton h-5 w-48 rounded" /></div>
      ) : (
        <div className="card !p-0 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-brand-border text-left text-[11px] text-gray-500 uppercase">
                  <th className="px-4 py-2.5 font-medium">Atölye</th>
                  <th className="px-4 py-2.5 font-medium">Plan</th>
                  <th className="px-4 py-2.5 font-medium">Abonelik</th>
                  <th className="px-4 py-2.5 font-medium text-center">Kullanıcı</th>
                  <th className="px-4 py-2.5 font-medium text-center">Sipariş</th>
                  <th className="px-4 py-2.5 font-medium text-center">Durum</th>
                  <th className="px-4 py-2.5"></th>
                </tr>
              </thead>
              <tbody>
                {items.map(t => {
                  const expired = t.active_until && new Date(t.active_until) < new Date()
                  return (
                    <tr key={t.id} className="border-b border-brand-border/40 hover:bg-brand-input/40">
                      <td className="px-4 py-2.5">
                        <div className="flex items-center gap-2">
                          <span className="w-3 h-3 rounded-full shrink-0" style={{ background: t.brand_color || '#7c5cff' }} />
                          <div className="min-w-0">
                            <div className="text-gray-100">{t.app_name || t.name}</div>
                            <div className="text-[10px] text-gray-500 font-mono">{t.slug}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-2.5 text-gray-300">{t.plan}</td>
                      <td className={`px-4 py-2.5 text-xs ${expired ? 'text-red-300' : 'text-gray-400'}`}>{fmtDate(t.active_until)}</td>
                      <td className="px-4 py-2.5 text-center text-gray-300">{t.user_count}</td>
                      <td className="px-4 py-2.5 text-center text-gray-400">{t.order_count}</td>
                      <td className="px-4 py-2.5 text-center">
                        {t.is_active
                          ? <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300">aktif</span>
                          : <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/15 text-red-300">pasif</span>}
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        <button onClick={() => setEditing(t)} className="btn-secondary !text-xs">Düzenle</button>
                      </td>
                    </tr>
                  )
                })}
                {items.length === 0 && (
                  <tr><td colSpan={7} className="px-4 py-10 text-center text-gray-500 text-sm">Henüz atölye yok.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {showCreate && <CreateTenant onClose={() => setShowCreate(false)} onDone={() => { setShowCreate(false); load() }} />}
      {editing && <EditTenant tenant={editing} onClose={() => setEditing(null)} onDone={() => { setEditing(null); load() }} />}
    </div>
  )
}

function Modal({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 overflow-y-auto"
      onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-brand-card border border-brand-border rounded-xl w-full max-w-md p-5 my-8 animate-popin">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-gray-100">{title}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-200 text-2xl leading-none">×</button>
        </div>
        {children}
      </div>
    </div>
  )
}

function Field({ label, children }) {
  return <label className="block mb-3"><span className="block text-xs text-gray-400 mb-1">{label}</span>{children}</label>
}

function CreateTenant({ onClose, onDone }) {
  const toast = useToast()
  const [f, setF] = useState({ tenant_name: '', owner_email: '', owner_password: '', owner_name: '', plan: 'trial', active_until: '', brand_color: '#7c5cff', app_name: '' })
  const [busy, setBusy] = useState(false)
  const set = (k, v) => setF(s => ({ ...s, [k]: v }))

  const submit = async () => {
    if (!f.tenant_name.trim() || !f.owner_email.trim() || f.owner_password.length < 6) {
      toast.error('Atölye adı, e-posta ve en az 6 haneli şifre gerekli'); return
    }
    setBusy(true)
    try {
      await api.post('/api/platform/tenants', {
        ...f,
        active_until: f.active_until || null,
        brand_color: f.brand_color || null,
        app_name: f.app_name || null,
      })
      toast.success('Atölye oluşturuldu')
      onDone()
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Oluşturulamadı')
    } finally { setBusy(false) }
  }

  return (
    <Modal title="Yeni Atölye" onClose={onClose}>
      <Field label="Atölye adı"><input className="input w-full" value={f.tenant_name} onChange={e => set('tenant_name', e.target.value)} /></Field>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Plan"><input className="input w-full" value={f.plan} onChange={e => set('plan', e.target.value)} placeholder="trial / pro..." /></Field>
        <Field label="Abonelik bitiş"><input type="date" className="input w-full" value={f.active_until} onChange={e => set('active_until', e.target.value)} /></Field>
      </div>
      <div className="border-t border-brand-border my-2 pt-2 text-[11px] text-gray-500">Sahip (owner) kullanıcı</div>
      <Field label="Sahip e-posta"><input className="input w-full" value={f.owner_email} onChange={e => set('owner_email', e.target.value)} /></Field>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Sahip adı"><input className="input w-full" value={f.owner_name} onChange={e => set('owner_name', e.target.value)} /></Field>
        <Field label="Şifre (min 6)"><input type="text" className="input w-full" value={f.owner_password} onChange={e => set('owner_password', e.target.value)} /></Field>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Accent rengi"><input type="color" className="w-full h-9 rounded-lg bg-transparent border border-brand-border p-0.5" value={f.brand_color} onChange={e => set('brand_color', e.target.value)} /></Field>
        <Field label="Uygulama adı"><input className="input w-full" value={f.app_name} onChange={e => set('app_name', e.target.value)} /></Field>
      </div>
      <button onClick={submit} disabled={busy} className="btn-primary !text-sm w-full mt-1 disabled:opacity-50">{busy ? 'Oluşturuluyor…' : 'Oluştur'}</button>
    </Modal>
  )
}

function EditTenant({ tenant, onClose, onDone }) {
  const toast = useToast()
  const [f, setF] = useState({
    name: tenant.name || '', plan: tenant.plan || 'trial', is_active: tenant.is_active,
    active_until: tenant.active_until ? tenant.active_until.slice(0, 10) : '',
    brand_color: tenant.brand_color || '#7c5cff', app_name: tenant.app_name || '',
  })
  const [busy, setBusy] = useState(false)
  const set = (k, v) => setF(s => ({ ...s, [k]: v }))

  const submit = async () => {
    setBusy(true)
    try {
      await api.patch(`/api/platform/tenants/${tenant.id}`, {
        name: f.name, plan: f.plan, is_active: f.is_active,
        active_until: f.active_until || null,
        clear_active_until: !f.active_until,
        brand_color: f.brand_color || null, app_name: f.app_name || null,
      })
      toast.success('Güncellendi')
      onDone()
    } catch (e) {
      toast.error(typeof e?.detail === 'string' ? e.detail : 'Kaydedilemedi')
    } finally { setBusy(false) }
  }

  return (
    <Modal title={`Atölye — ${tenant.name}`} onClose={onClose}>
      <Field label="Atölye adı"><input className="input w-full" value={f.name} onChange={e => set('name', e.target.value)} /></Field>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Plan"><input className="input w-full" value={f.plan} onChange={e => set('plan', e.target.value)} /></Field>
        <Field label="Abonelik bitiş"><input type="date" className="input w-full" value={f.active_until} onChange={e => set('active_until', e.target.value)} /></Field>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Accent rengi"><input type="color" className="w-full h-9 rounded-lg bg-transparent border border-brand-border p-0.5" value={f.brand_color} onChange={e => set('brand_color', e.target.value)} /></Field>
        <Field label="Uygulama adı"><input className="input w-full" value={f.app_name} onChange={e => set('app_name', e.target.value)} /></Field>
      </div>
      <label className="flex items-center gap-2 mb-4 cursor-pointer">
        <input type="checkbox" checked={f.is_active} onChange={e => set('is_active', e.target.checked)} className="accent-accent" />
        <span className="text-sm text-gray-200">Aktif (kapatılırsa giriş engellenir)</span>
      </label>
      <button onClick={submit} disabled={busy} className="btn-primary !text-sm w-full disabled:opacity-50">{busy ? 'Kaydediliyor…' : 'Kaydet'}</button>
    </Modal>
  )
}
