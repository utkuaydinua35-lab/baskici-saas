/**
 * "Uygulamayı indir" — bayi masaüstü uygulamasının kurulum sayfası.
 *
 * Kurulum basit olmalı: bayinin işletim sistemi tanınır, DOĞRU dosya en üstte
 * büyük düğmeyle durur, adımlar numaralı yazılır. Uygulama imzasız olduğu için
 * ilk açılıştaki sistem uyarısının nasıl geçileceği de burada — bayi o uyarıyı
 * görünce "virüs mü?" diye bize sormasın.
 */
import { useEffect, useState } from 'react'
import { api } from '../../lib/api'
import { Hata, Iskelet } from '../../components/BayiParcalar'

function isletimSistemi() {
  const ua = navigator.userAgent || ''
  if (/Windows/i.test(ua)) return 'windows'
  if (/Mac OS X|Macintosh/i.test(ua)) return 'mac'
  return null
}

/** Uygulamanın İÇİNDE miyiz (kabuk preload'u bunu koyuyor). */
const kabukta = typeof window !== 'undefined' && !!window.bernzMasaustu

export default function BayiUygulamaPage() {
  const [veri, setVeri] = useState(null)
  const [hata, setHata] = useState('')
  const [sistem, setSistem] = useState(isletimSistemi())

  useEffect(() => {
    api.get('/api/bayii/uygulama').then(setVeri).catch(e => setHata(e.detail || 'Liste alınamadı'))
  }, [])

  const mac = veri?.mac || []
  const win = veri?.windows || []
  const varMi = (veri?.kurulumlar || []).length > 0

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold text-white tracking-tight">Uygulamayı indir</h1>
        <p className="text-[13px] text-gray-500 mt-1">
          Paneli bilgisayarında ayrı bir uygulama olarak kullan; siparişin kargoya verildiğinde
          ve biz sana yazdığımızda bildirim al.
        </p>
      </div>

      <Hata mesaj={hata} />

      {kabukta && (
        <div className="card border-emerald-500/30 bg-emerald-500/5">
          <div className="text-sm text-emerald-300 font-medium">✓ Uygulamayı zaten kullanıyorsun</div>
          <div className="text-xs text-emerald-400/80 mt-1">
            Sürüm {window.bernzMasaustu?.surum}
            {veri?.son_surum && veri.son_surum !== window.bernzMasaustu?.surum &&
              ` · yeni sürüm var: ${veri.son_surum} (aşağıdan indirip üzerine kur)`}
          </div>
        </div>
      )}

      {veri === null ? <Iskelet satir={2} /> : !varMi ? (
        <div className="card text-center py-10">
          <div className="text-3xl mb-2">🛠️</div>
          <div className="text-gray-300 font-medium">Kurulum dosyası henüz yayınlanmadı</div>
          <p className="text-[13px] text-gray-500 mt-1">Hazır olunca burada görünecek ve sana haber vereceğiz.</p>
        </div>
      ) : (
        <>
          {/* Sistem seçici — otomatik tanınır, elle de değiştirilebilir */}
          <div className="flex gap-2">
            {[['windows', '🪟 Windows'], ['mac', '🍎 Mac']].map(([k, ad]) => (
              <button key={k} onClick={() => setSistem(k)}
                className={`text-sm px-3 py-1.5 rounded-full border transition-colors ${
                  sistem === k ? 'bg-accent text-white border-accent'
                              : 'bg-brand-input/50 text-gray-300 border-brand-border hover:text-gray-100'}`}>
                {ad}
              </button>
            ))}
          </div>

          {sistem === 'mac' ? (
            <Kart baslik="Mac için" dosyalar={mac} bos="Mac sürümü henüz yayınlanmadı."
              adimlar={[
                'İndirdiğin .dmg dosyasına çift tıkla.',
                'Açılan pencerede BERNZ Bayi logosunu "Applications" (Uygulamalar) klasörüne sürükle.',
                'Uygulamalar klasöründen simgeye SAĞ TIK → Aç → tekrar Aç. (Yalnız ilk açılışta; uygulama henüz Apple onaylı olmadığı için uyarı çıkar.)',
                'Açılışta "Bildirimleri açalım mı?" sorusuna izin ver.',
              ]}
              ipucu="Hangi Mac? Apple menüsü → Bu Mac Hakkında. “Apple M…” yazıyorsa Apple Silicon, “Intel” yazıyorsa Intel sürümünü indir." />
          ) : (
            <Kart baslik="Windows için" dosyalar={win} bos="Windows sürümü henüz yayınlanmadı."
              adimlar={[
                'İndirdiğin .exe dosyasına çift tıkla — kurulum tek tıkla tamamlanır, yönetici şifresi istemez.',
                '"Windows bilgisayarınızı korudu" uyarısı çıkarsa: Ek bilgi → Yine de çalıştır. (Yalnız ilk kurulumda.)',
                'Masaüstündeki BERNZ Bayi kısayolundan aç.',
                'Açılışta "Bildirimleri açalım mı?" sorusuna izin ver.',
              ]} />
          )}

          <div className="card">
            <div className="text-sm font-medium text-gray-200 mb-2">Bildirimler</div>
            <ul className="text-[13px] text-gray-400 space-y-1 list-disc list-inside">
              <li>Siparişin <b>kargoya verildiğinde</b> takip numarasıyla bildirim gelir.</li>
              <li>Atölye sana <b>sohbetten mesaj yazdığında</b> bildirim gelir.</li>
              <li>Bildirime tıklayınca ilgili sayfa açılır.</li>
              <li>İstemediğinde uygulamadaki <b>Dosya → Bildirimler açık</b> seçeneğiyle kapatabilirsin.</li>
            </ul>
          </div>
        </>
      )}
    </div>
  )
}

function Kart({ baslik, dosyalar, adimlar, bos, ipucu }) {
  return (
    <div className="card space-y-4">
      <div className="text-sm font-medium text-gray-200">{baslik}</div>

      {dosyalar.length === 0 ? (
        <div className="text-[13px] text-gray-500">{bos}</div>
      ) : (
        <div className="space-y-2">
          {dosyalar.map(d => (
            <a key={d.dosya} href={d.url} download
               className="flex items-center gap-3 px-3 py-2.5 rounded-xl border border-accent/30 bg-accent/10
                          hover:bg-accent/15 transition-colors">
              <span className="text-xl">⬇️</span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm text-white">
                  {d.mimari_etiket || 'İndir'} · sürüm {d.surum}
                </span>
                <span className="block text-[11px] text-gray-500">{d.dosya} · {d.boyut}</span>
              </span>
            </a>
          ))}
        </div>
      )}

      {ipucu && <p className="text-[11px] text-gray-500">{ipucu}</p>}

      <ol className="text-[13px] text-gray-400 space-y-1.5 list-decimal list-inside">
        {adimlar.map((a, i) => <li key={i}>{a}</li>)}
      </ol>
    </div>
  )
}
