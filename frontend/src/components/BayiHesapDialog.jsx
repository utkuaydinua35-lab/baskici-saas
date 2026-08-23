/**
 * Bayinin portal giris hesaplari.
 *
 * Hesap GENEL kullanici ekranindan degil buradan acilir: rol ve izin sunucuda
 * zorla sabitlenir ('bayii_portal'), boylece bayi hesabina yanlislikla yonetim
 * yetkisi verilemez.
 */
import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useToast } from './Toast'

function rastgeleSifre() {
  const harf = 'abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'
  const d = crypto.getRandomValues(new Uint32Array(12))
  return Array.from(d, (n) => harf[n % harf.length]).join('')
}

export default function BayiHesapDialog({ dealer, onClose }) {
  const [liste, setListe] = useState(null)
  const [email, setEmail] = useState('')
  const [sifre, setSifre] = useState(rastgeleSifre())
  const [bekle, setBekle] = useState(false)
  const toast = useToast()

  const yukle = useCallback(async () => {
    try { setListe(await api.get(`/api/dealers/${dealer.id}/hesaplar`)) }
    catch (e) { toast.error(e.detail || 'Hesaplar yüklenemedi'); setListe([]) }
  }, [dealer.id, toast])
  useEffect(() => { yukle() }, [yukle])

  const ekle = async (e) => {
    e.preventDefault()
    setBekle(true)
    try {
      await api.post(`/api/dealers/${dealer.id}/hesaplar`,
                     { email: email.trim(), password: sifre, full_name: dealer.name })
      toast.success('Bayi hesabı oluşturuldu')
      setEmail(''); setSifre(rastgeleSifre())
      await yukle()
    } catch (err) { toast.error(err.detail || 'Hesap oluşturulamadı') }
    finally { setBekle(false) }
  }

  const sifreYenile = async (u) => {
    const yeni = rastgeleSifre()
    if (!window.confirm(`${u.email} için yeni şifre:\n\n${yeni}\n\nOnaylarsan şifre değişir. Not al!`)) return
    try {
      await api.patch(`/api/dealers/${dealer.id}/hesaplar/${u.id}`, { password: yeni })
      toast.success('Şifre güncellendi')
    } catch (e) { toast.error(e.detail || 'Güncellenemedi') }
  }

  const durumDegis = async (u) => {
    try {
      await api.patch(`/api/dealers/${dealer.id}/hesaplar/${u.id}`, { is_active: !u.is_active })
      await yukle()
    } catch (e) { toast.error(e.detail || 'Güncellenemedi') }
  }

  const sil = async (u) => {
    if (!window.confirm(`${u.email} hesabı silinsin mi? Bayi artık giriş yapamaz.`)) return
    try { await api.del(`/api/dealers/${dealer.id}/hesaplar/${u.id}`); await yukle() }
    catch (e) { toast.error(e.detail || 'Silinemedi') }
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center p-4 bg-black/60 animate-fadein"
         onClick={onClose}>
      <div className="glass rounded-2xl w-full max-w-lg p-5 animate-popin"
           onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-100">{dealer.name} — Portal Hesapları</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-200 text-xl leading-none">×</button>
        </div>

        <p className="text-[12.5px] text-gray-500 mb-4">
          Bayi bu bilgilerle <span className="text-gray-300">/bayii/giris</span> adresinden girer.
          Şifre bir daha gösterilmez — oluşturduğunda not al.
        </p>

        {liste === null ? (
          <div className="h-16 rounded-xl bg-white/5 animate-pulse mb-4" />
        ) : liste.length > 0 && (
          <div className="space-y-2 mb-4">
            {liste.map((u) => (
              <div key={u.id} className="rounded-xl border border-brand-border bg-brand-input/30
                                         px-3.5 py-2.5 flex items-center gap-3 flex-wrap">
                <div className="min-w-0 flex-1">
                  <div className="text-[13px] text-gray-200 truncate">{u.email}</div>
                  <div className="text-[11.5px] text-gray-500">
                    {u.is_active ? 'Aktif' : 'Pasif'}
                    {u.last_login_at && ` · son giriş ${new Date(u.last_login_at).toLocaleDateString('tr-TR')}`}
                  </div>
                </div>
                <button onClick={() => sifreYenile(u)}
                        className="text-[11.5px] text-gray-400 hover:text-white transition">Şifre yenile</button>
                <button onClick={() => durumDegis(u)}
                        className="text-[11.5px] text-gray-400 hover:text-white transition">
                  {u.is_active ? 'Pasifleştir' : 'Aktifleştir'}
                </button>
                <button onClick={() => sil(u)}
                        className="text-[11.5px] text-red-400/80 hover:text-red-300 transition">Sil</button>
              </div>
            ))}
          </div>
        )}

        <form onSubmit={ekle} className="space-y-3 pt-3 border-t border-white/8">
          <div className="text-[12px] uppercase tracking-wider text-gray-500">Yeni hesap</div>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required
                 placeholder="bayi@ornek.com" className="input w-full" />
          <div className="flex items-center gap-2">
            <input value={sifre} onChange={(e) => setSifre(e.target.value)} required minLength={8}
                   className="input flex-1 font-mono text-[13px]" />
            <button type="button" onClick={() => setSifre(rastgeleSifre())}
                    className="btn-secondary !text-xs !py-2 !px-3" title="Yeni şifre üret">Yenile</button>
            <button type="button" onClick={() => { navigator.clipboard?.writeText(sifre); toast.success('Şifre kopyalandı') }}
                    className="btn-secondary !text-xs !py-2 !px-3">Kopyala</button>
          </div>
          <button className="btn-primary w-full !py-2" disabled={bekle}>
            {bekle ? 'Oluşturuluyor…' : 'Hesap oluştur'}
          </button>
        </form>
      </div>
    </div>
  )
}
