// Abonelik — kiracının planı, ödeme durumu, sıradaki ödemenin tahmini tutarı,
// havale bilgileri ve ödeme geçmişi. Salt okunur: ödemeyi platform kaydeder.
// Askıdaki kiracı da açabilir — nasıl ödeyeceğini buradan öğrenir.
import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useToast } from '../components/Toast'

function tl(v) {
  return Number(v || 0).toLocaleString('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' TL'
}
function gun(d) {
  if (!d) return '—'
  try { return new Date(d.length === 10 ? d + 'T00:00:00' : d).toLocaleDateString('tr-TR') } catch { return d }
}

const ASAMA = {
  aktif: ['Aktif', 'bg-emerald-500/15 text-emerald-300'],
  ek_sure: ['Ek süre', 'bg-amber-500/15 text-amber-300'],
  salt_okunur: ['Salt okunur', 'bg-orange-500/15 text-orange-300'],
  askida: ['Askıda', 'bg-red-500/15 text-red-300'],
}

function Kopyala({ metin, etiket = 'Kopyala' }) {
  const toast = useToast()
  return (
    <button type="button" className="btn-ghost !py-1 !px-2 text-xs"
      onClick={() => {
        try { navigator.clipboard?.writeText(metin); toast.success('Kopyalandı') }
        catch { toast.error('Kopyalanamadı') }
      }}>
      {etiket}
    </button>
  )
}

export default function AbonelikPage() {
  const [d, setD] = useState(null)
  const [hata, setHata] = useState(null)

  useEffect(() => {
    api.get('/api/abonelik').then(setD)
      .catch(e => setHata(typeof e?.detail === 'string' ? e.detail : 'Abonelik bilgisi alınamadı'))
  }, [])

  if (hata) return <div className="card text-sm text-panel-muted">{hata}</div>
  if (!d) return <div className="card"><div className="skeleton h-5 w-48 rounded" /></div>

  const [asamaAd, asamaCls] = ASAMA[d.durum?.asama] || ['—', '']
  const t = d.tahmin
  const h = d.havale
  const havaleHazir = h && h.iban

  return (
    <div className="max-w-3xl space-y-4">
      <h1 className="text-xl font-semibold">Abonelik</h1>

      <section className="card space-y-3">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div>
            <div className="text-xs text-panel-muted">Planınız</div>
            <div className="text-lg font-semibold">{d.plan?.ad || 'Plan atanmamış'}</div>
            {d.plan && (Number(d.plan.aylik_ucret) > 0 || Number(d.plan.komisyon_orani) > 0) && (
              <div className="text-sm text-panel-muted mt-0.5">
                {tl(d.plan.aylik_ucret)} / ay
                {Number(d.plan.komisyon_orani) > 0 && <> + vitrin satışlarının %{Number(d.plan.komisyon_orani)}'i</>}
              </div>
            )}
          </div>
          <span className={`text-xs px-2.5 py-1 rounded-full ${asamaCls}`}>{asamaAd}</span>
        </div>
        {d.plan?.moduller?.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {d.plan.moduller.map(m => (
              <span key={m} className="text-[11px] px-2 py-0.5 rounded-full border border-panel-border text-panel-muted">{m}</span>
            ))}
          </div>
        )}
        <div className="text-sm">
          {d.active_until
            ? <>Ödenmiş son gün: <b>{gun(d.active_until)}</b></>
            : <span className="text-panel-muted">Süresiz abonelik</span>}
        </div>
        {d.durum?.mesaj && <p className="text-sm text-amber-300">{d.durum.mesaj}</p>}
      </section>

      {t && (
        <section className="card space-y-2">
          <h2 className="text-sm font-semibold">Sıradaki ödeme (tahmini)</h2>
          <table className="w-full text-sm">
            <tbody>
              <tr>
                <td className="py-1 text-panel-muted">Sabit ücret · {gun(t.donem_bas)} – {gun(t.donem_bit)}</td>
                <td className="py-1 pl-3 text-right whitespace-nowrap align-top">{tl(t.sabit_ucret)}</td>
              </tr>
              {Number(t.komisyon_orani) > 0 && (
                <tr>
                  <td className="py-1 text-panel-muted">
                    Komisyon %{Number(t.komisyon_orani)}
                    {t.ciro_bas
                      ? <> · {gun(t.ciro_bas)} – {gun(t.ciro_bit)} vitrin satışı {tl(t.ciro)} ({t.siparis_sayisi} sipariş)</>
                      : <> · ilk ücretli dönem, komisyon yok</>}
                  </td>
                  <td className="py-1 pl-3 text-right whitespace-nowrap align-top">{tl(t.komisyon)}</td>
                </tr>
              )}
              <tr className="border-t border-panel-border">
                <td className="pt-2 font-medium">Toplam</td>
                <td className="pt-2 pl-3 text-right text-lg font-semibold whitespace-nowrap">{tl(t.toplam)}</td>
              </tr>
            </tbody>
          </table>
          <p className="text-[11px] text-panel-muted">
            Komisyon yalnız vitrininizden gelen siparişlerden, sipariş toplamı (indirim düşülmüş, KDV ve kargo dahil)
            üzerinden hesaplanır; iptal ve iade edilen siparişler düşülür. Tutar, ödemenin kaydedildiği güne kadarki
            satışlarla kesinleşir.
          </p>
        </section>
      )}

      {t && (
        <section className="card space-y-2">
          <h2 className="text-sm font-semibold">Havale / EFT ile ödeme</h2>
          {havaleHazir ? (
            <div className="space-y-2 text-sm">
              {h.alici && <div><span className="text-panel-muted">Alıcı:</span> {h.alici}</div>}
              {h.banka && <div><span className="text-panel-muted">Banka:</span> {h.banka}</div>}
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-panel-muted">IBAN:</span>
                <span className="font-mono">{h.iban.replace(/(.{4})/g, '$1 ').trim()}</span>
                <Kopyala metin={h.iban} />
              </div>
              <div className="flex items-center gap-2 flex-wrap rounded-lg border border-panel-border px-3 py-2">
                <span className="text-panel-muted">Açıklamaya yazın:</span>
                <b className="font-mono">{d.odeme_kodu}</b>
                <Kopyala metin={d.odeme_kodu} />
              </div>
              {h.aciklama && <p className="text-xs text-panel-muted">{h.aciklama}</p>}
              <p className="text-xs text-panel-muted">
                Ödemeniz işlendiğinde aboneliğiniz uzar ve aşağıdaki geçmişte görünür.
              </p>
            </div>
          ) : (
            <p className="text-sm text-panel-muted">Ödeme bilgileri henüz eklenmedi; lütfen bizimle iletişime geçin.</p>
          )}
        </section>
      )}

      <section className="card">
        <h2 className="text-sm font-semibold mb-2">Ödeme geçmişi</h2>
        {d.odemeler.length === 0 ? (
          <p className="text-sm text-panel-muted">Henüz ödeme yok.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-panel-muted">
                  <th className="py-1.5 pr-3 font-normal">Tarih</th>
                  <th className="py-1.5 pr-3 font-normal">Dönem</th>
                  <th className="py-1.5 pr-3 font-normal text-right">Sabit</th>
                  <th className="py-1.5 pr-3 font-normal text-right">Komisyon</th>
                  <th className="py-1.5 pr-3 font-normal text-right">Toplam</th>
                  <th className="py-1.5 font-normal">Fatura</th>
                </tr>
              </thead>
              <tbody>
                {d.odemeler.map(o => (
                  <tr key={o.id} className="border-t border-panel-border">
                    <td className="py-1.5 pr-3">{gun(o.odendi_at)}</td>
                    <td className="py-1.5 pr-3 text-panel-muted">{gun(o.donem_bas)} – {gun(o.donem_bit)}</td>
                    <td className="py-1.5 pr-3 text-right">{tl(o.sabit_ucret)}</td>
                    <td className="py-1.5 pr-3 text-right" title={`Vitrin satışı ${tl(o.ciro)} · ${o.siparis_sayisi} sipariş`}>{tl(o.komisyon)}</td>
                    <td className="py-1.5 pr-3 text-right font-medium">{tl(o.toplam)}</td>
                    <td className="py-1.5 text-panel-muted">{o.fatura_no || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
