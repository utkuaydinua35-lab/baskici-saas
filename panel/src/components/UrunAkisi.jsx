// Ayarlar → Pazarlama: ürün akışı (katalog) adresleri.
//
// Shopify'ın Facebook & Instagram kanalındaki katalog gibi: adres bir kez
// Commerce Manager'a (Google için Merchant Center'a) "zamanlanmış akış" olarak
// verilir; platform ürünleri kendisi düzenli çeker — yeni ürün, fiyat, stok ve
// görsel elle bir şey yapmadan kataloğa yansır. Akışı backend üretir
// (public_shop.meta_catalog_feed / google_shopping_feed), saatlik önbellekler.
// Ürün kimliği (Meta) = ürün slug'ı = pikselin content_ids'i → dinamik
// reklamlar ve "katalogla eşleşme" doğrudan çalışır.
import { useEffect, useState } from 'react'
import { api } from '../lib/api'

function Kopyala({ deger }) {
  const [oldu, setOldu] = useState(false)
  return (
    <button type="button"
      onClick={async () => {
        try { await navigator.clipboard.writeText(deger); setOldu(true); setTimeout(() => setOldu(false), 1500) }
        catch { window.prompt('Adresi kopyalayın:', deger) }
      }}
      className="shrink-0 px-2.5 py-1.5 rounded-lg text-xs border border-panel-border hover:border-panel-accent">
      {oldu ? 'Kopyalandı ✓' : 'Kopyala'}
    </button>
  )
}

function Satir({ baslik, aciklama, url, acilmaz = false }) {
  return (
    <div>
      <div className="text-[12px] font-medium">{baslik}</div>
      <div className="text-[11px] text-panel-muted mb-1">{aciklama}</div>
      <div className="flex items-center gap-2">
        <code className="flex-1 min-w-0 truncate rounded-lg bg-panel-input px-2.5 py-1.5 text-[11px]">{url}</code>
        <Kopyala deger={url} />
        {!acilmaz && <a href={url} target="_blank" rel="noopener noreferrer"
          className="shrink-0 px-2.5 py-1.5 rounded-lg text-xs border border-panel-border text-panel-muted hover:text-panel-ink">Aç ↗</a>}
      </div>
    </div>
  )
}

// Koleksiyonlar → Meta ürün setleri (Shopify'ın Facebook kanalı gibi).
// Backend: services/meta_katalog.py — her gece de kendiliğinden eşitlenir.
function UrunSetleri({ cfg, set, storeId }) {
  const [busy, setBusy] = useState(false)
  const [sonuc, setSonuc] = useState(null)
  const [son, setSon] = useState(null)
  const [hata, setHata] = useState('')
  useEffect(() => {
    if (!storeId) return
    api.get(`/api/store-settings/${storeId}`).then(r => setSon(r.meta_urun_setleri_son || null)).catch(() => {})
  }, [storeId])
  const kayitli = !!(cfg.meta_catalog_id && cfg.meta_catalog_token)
  const gonder = async () => {
    setBusy(true); setHata(''); setSonuc(null)
    try {
      const r = await api.post(`/api/store-settings/${storeId}/meta-urun-setleri`, {})
      setSonuc(r)
      setSon({ zaman: new Date().toISOString(), ...r })
    } catch (e) { setHata(typeof e?.detail === 'string' ? e.detail : 'Gönderilemedi') }
    finally { setBusy(false) }
  }
  return (
    <div className="rounded-xl border border-panel-border p-3 space-y-2.5">
      <div>
        <div className="text-[12px] font-semibold">Koleksiyonları Meta'ya ürün seti olarak gönder</div>
        <p className="text-[11px] text-panel-muted mt-0.5">
          Reklam kurarken "Ürün seti" listesinde her koleksiyon ayrı görünür (Anime, Retro…). Set içeriği koleksiyonla
          birebir aynıdır ve her gece kendiliğinden güncellenir. Meta'da elle açtığınız setlere dokunulmaz.
        </p>
      </div>
      <div className="grid sm:grid-cols-2 gap-2">
        <label className="block text-[11px] text-panel-muted">
          Katalog kimliği (Catalog ID)
          <input className="input mt-1 font-mono text-xs" value={cfg.meta_catalog_id || ''}
            onChange={set('meta_catalog_id')} placeholder="1234567890123456" />
        </label>
        <label className="block text-[11px] text-panel-muted">
          Katalog erişim anahtarı
          <input className="input mt-1 font-mono text-xs" value={cfg.meta_catalog_token || ''}
            onChange={set('meta_catalog_token')} placeholder="EAA…" autoComplete="off" />
        </label>
      </div>
      <details className="text-[11px]">
        <summary className="cursor-pointer text-panel-muted hover:text-panel-ink">Bu iki bilgi nereden alınır?</summary>
        <ol className="list-decimal pl-5 mt-1.5 space-y-1 text-panel-ink/90">
          <li><b>Katalog kimliği:</b> Commerce Manager › kataloğunuz › Ayarlar › “Katalog Kimliği”.</li>
          <li><b>Anahtar:</b> <a className="underline" href="https://business.facebook.com/settings/system-users" target="_blank" rel="noopener noreferrer">İşletme Ayarları › Sistem Kullanıcıları ↗</a> › bir sistem kullanıcısı (yoksa “Ekle”, rol: Yönetici) ›
            “Varlık ata” › Kataloglar › kataloğunuz (Tam kontrol) › “Yeni Belirteç Oluştur” › izinlerden <b>catalog_management</b> seçin › belirteci buraya yapıştırın.</li>
          <li>Ayarları <b>Kaydet</b>'e basın, sonra aşağıdaki düğmeyle ilk gönderimi yapın.</li>
        </ol>
      </details>
      <div className="flex items-center gap-2 flex-wrap">
        <button type="button" onClick={gonder} disabled={busy || !kayitli}
          className="btn-primary !py-1.5 text-xs disabled:opacity-40">
          {busy ? 'Gönderiliyor…' : '📦 Koleksiyonları şimdi gönder'}
        </button>
        {!kayitli && <span className="text-[11px] text-panel-muted">Önce iki alanı doldurup ayarları kaydedin.</span>}
        {son?.zaman && !sonuc && (
          <span className="text-[11px] text-panel-muted">
            Son eşitleme: {new Date(son.zaman).toLocaleString('tr-TR')} — {son.acilan || 0} yeni, {son.guncellenen || 0} güncel
            {son.hata_sayisi ? `, ${son.hata_sayisi} hata` : ''}
          </span>
        )}
      </div>
      {sonuc && (
        <div className="text-[11px]">
          <span className="text-emerald-300">✓ {sonuc.acilan} yeni set, {sonuc.guncellenen} güncellendi, {sonuc.silinen} kaldırıldı</span>
          {sonuc.atlanan > 0 && <span className="text-panel-muted"> · {sonuc.atlanan} boş koleksiyon atlandı</span>}
          {sonuc.hatalar?.length > 0 && (
            <ul className="mt-1 text-amber-300 list-disc pl-4">{sonuc.hatalar.slice(0, 5).map((h, i) => <li key={i}>{h}</li>)}</ul>
          )}
        </div>
      )}
      {hata && <p className="text-[11px] text-red-300">{hata}</p>}
    </div>
  )
}

export default function UrunAkisi({ cfg, set, storeId }) {
  const site = (cfg.storefront_url || '').trim().replace(/\/$/, '')
  if (!site) {
    return (
      <p className="text-[11px] text-amber-300">
        Ürün akışı adresi için önce Ayarlar › Yayın &amp; Domain'de vitrin adresini girin.
      </p>
    )
  }
  return (
    <div className="space-y-3">
      <div>
        <div className="text-sm font-semibold">🛍 Ürün kataloğu (otomatik akış)</div>
        <p className="text-[11px] text-panel-muted mt-0.5">
          Sitedeki <b>yayında</b> ürünler bu adreslerden otomatik okunur — Shopify'daki katalog kanalı gibi.
          Yeni ürün, fiyat, indirim, stok ve görsel değişiklikleri en geç bir saat içinde akışa yansır;
          Meta/Google akışı kendi zamanlamasıyla çeker. Taslak, arşiv ve müşteriye özel (linkle) ürünler akışta yer almaz.
        </p>
      </div>
      <Satir baslik="Meta — Facebook & Instagram kataloğu"
        aciklama="Ürün başına bir satır; kimlik pikselin gönderdiği ürün kimliğiyle aynı (dinamik reklamlar eşleşir)."
        url={`${site}/feed/meta.xml`} />
      <Satir baslik="Google Merchant Center"
        aciklama="Model (varyant) başına bir satır, ~180 MB. Tarayıcıda açılmaz (sekme donar) — bu normal; adresi yalnız Merchant Center'a verin, Google indirir."
        url={`${site}/feed/google.xml`} acilmaz />
      {set && <UrunSetleri cfg={cfg} set={set} storeId={storeId} />}
      <details className="text-[12px]">
        <summary className="cursor-pointer text-panel-muted hover:text-panel-ink">Meta'ya nasıl bağlanır? (bir kez)</summary>
        <ol className="list-decimal pl-5 mt-2 space-y-1 text-panel-ink/90">
          <li><a className="underline" href="https://business.facebook.com/commerce" target="_blank" rel="noopener noreferrer">Commerce Manager ↗</a> › kataloğunuzu seçin (yoksa "Katalog oluştur" › E-ticaret).</li>
          <li><b>Katalog › Veri kaynakları › Öğe ekle › Veri akışı</b> seçin (dosya YÜKLEMEYİN).</li>
          <li>"Zamanlanmış akış" (URL'den) › yukarıdaki <b>Meta</b> adresini yapıştırın; sıklık <b>Saatlik</b> (ya da Günlük), para birimi TRY.</li>
          <li>Kataloğu <b>Olay Yöneticisi'ndeki pikselinize bağlayın</b> (Katalog › Ayarlar › Olay kaynakları) — dinamik reklamlar ve
            "katalog eşleşmesi" bundan sonra çalışır.</li>
          <li>Eski Shopify kataloğu duruyorsa ürünler iki kez görünmesin diye o veri kaynağını silin ya da duraklatın.</li>
        </ol>
        <p className="text-[11px] text-panel-muted mt-2">
          Google için: Merchant Center › Ürünler › Akışlar › Birincil akış ekle › "Planlanmış getirme" › Google adresi.
        </p>
      </details>
    </div>
  )
}
