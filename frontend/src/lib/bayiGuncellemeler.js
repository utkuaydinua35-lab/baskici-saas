/**
 * Bayi paneli GÜNCELLEME NOTLARI + tanıtımları — tek kaynak.
 *
 * ⚠ BAYİ PANELİNE YENİ BİR ÖZELLİK EKLENİNCE BURAYA KAYIT EKLE.
 *   • `surum` bir öncekinden BÜYÜK olmalı (sıra buna göre; sunucu bayinin
 *     hangi sürüme kadar gördüğünü tutar — users.bayi_guncelleme_goruldu).
 *   • `tanitim` doluysa bayi BİR SONRAKİ GİRİŞİNDE bu adımları görür.
 *   • `gorsel` BayiTanitimGorselleri.jsx'teki bir çizimin adı. Ekran görüntüsü
 *     yerine canlı çizim: arayüz değişince bayat görüntü kalmaz, telefonda ve
 *     geniş ekranda aynı netlikte.
 *
 * Sistem 2026-09-14'te kuruldu. O güne kadarki kayıtlar geçmiş notlar olarak
 * duruyor ve BASLANGIC_SURUMU'na kadar "görülmüş" sayılıyor — bayiye aylar
 * önceki özelliklerin tanıtımını bir anda göstermemek için. Tanıtımlarını
 * Yenilikler sayfasından isteyen yine izleyebilir.
 */

export const BASLANGIC_SURUMU = 5

// tur: yeni | iyilestirme | duzeltme
export const GUNCELLEMELER = [
  {
    surum: 6,
    tarih: '2026-09-14',
    baslik: 'Hepsiburada siparişleri',
    ozet: 'Hepsiburada’dan gelen siparişlerini artık doğrudan girebilirsin; paketin barkodu hazır basılır.',
    degisiklikler: [
      { tur: 'yeni', metin: 'Sipariş kaynağına Hepsiburada eklendi. Adres istenmez, yalnızca alıcı adı yeterli.' },
      { tur: 'yeni', metin: 'Hepsiburada siparişinde kargo entegrasyon kodu zorunlu; kargo firması Sürat Kargo olarak seçili gelir.' },
      { tur: 'yeni', metin: 'Paketin üzerine alıcının maskeli adı, kargo firması ve kodun barkodu basılır.' },
      { tur: 'iyilestirme', metin: 'Kodu yanlış girdiysen barkod oluşana kadar sipariş detayındaki “Düzenle” ile düzeltebilirsin.' },
    ],
    tanitim: [
      {
        baslik: 'Kaynak olarak Hepsiburada’yı seç',
        metin: 'Yeni sipariş → Alıcı adımında “Sipariş nereden geldi?” sorusuna Hepsiburada de. Adres alanları açılmaz; adres Hepsiburada’dan gelir.',
        gorsel: 'hbKanal',
      },
      {
        baslik: 'Kargo entegrasyon kodunu yapıştır',
        metin: 'Kodu Hepsiburada sipariş detayından kopyala. Boşluklu yapıştırsan da olur, biz temizleriz. Kargo firması Sürat Kargo olarak seçili gelir; farklıysa değiştir.',
        gorsel: 'hbKod',
      },
      {
        baslik: 'Barkod hazır basılır',
        metin: 'Paketlemede etikete alıcının adı maskeli (AYŞ* YIL***), kargo firması ve kodun barkodu basılır. Şube paketi bu barkodla tanır.',
        gorsel: 'hbEtiket',
      },
    ],
  },
  {
    surum: 5,
    tarih: '2026-09-11',
    baslik: 'Telefonda daha rahat menü',
    ozet: 'Panel telefonda daha akıcı; menü ve çıkış düğmesi yeniden düzenlendi.',
    degisiklikler: [
      { tur: 'iyilestirme', metin: 'Telefonda çıkış düğmesi menünün içine alındı — menüyü açarken yanlışlıkla çıkış yapılmıyor.' },
      { tur: 'iyilestirme', metin: 'Düğmeler parmakla rahat basılacak büyüklükte; menü Escape ile kapanıyor.' },
    ],
    tanitim: [
      {
        baslik: 'Menü ve çıkış',
        metin: 'Telefonda sağ üstteki ☰ ile menüyü aç. Çıkış yap artık menünün en altında.',
        gorsel: 'mobilMenu',
      },
    ],
  },
  {
    surum: 4,
    tarih: '2026-09-08',
    baslik: 'Önizleme görseli',
    ozet: 'Tasarımın kılıf üzerinde nasıl duracağını gösteren bir görsel ekleyebilirsin.',
    degisiklikler: [
      { tur: 'yeni', metin: 'Her ürüne isteğe bağlı önizleme görseli eklenebilir. Baskıya girmez, yalnızca bize fikir verir.' },
      { tur: 'iyilestirme', metin: 'Sipariş detayında görseller büyütüldü, önizleme de görünüyor.' },
      { tur: 'iyilestirme', metin: 'Panel telefonda kullanılabilir hale getirildi.' },
    ],
    tanitim: [
      {
        baslik: 'Önizleme görseli ekle',
        metin: 'Ürün kartındaki “+ Önizleme görseli ekle” ile kılıfın son halini gösteren görseli yükle. Baskı dosyası yine tasarımdır.',
        gorsel: 'onizleme',
      },
    ],
  },
  {
    surum: 3,
    tarih: '2026-09-01',
    baslik: 'Stok bilgisi ve görsel büyütme',
    ozet: 'Stokta olmayan ürünler işaretleniyor; görseller sayfada büyütülebiliyor.',
    degisiklikler: [
      { tur: 'yeni', metin: 'Stoğu olmayan ürünlerde “Stokta mevcut değil” ibaresi görünür.' },
      { tur: 'yeni', metin: 'Tasarım görseline dokununca sayfada büyür.' },
      { tur: 'iyilestirme', metin: 'Aynı dosyayı tekrar yüklersen kopya kayıt açılmaz, mevcut tasarım kullanılır.' },
    ],
  },
  {
    surum: 2,
    tarih: '2026-08-24',
    baslik: 'Birden fazla ürün, tasarım kataloğu, iptal talebi',
    ozet: 'Tek siparişte birden fazla ürün, daha önce yüklediğin tasarımlardan seçim ve iptal talebi.',
    degisiklikler: [
      { tur: 'yeni', metin: 'Tek siparişe birden fazla ürün eklenebilir.' },
      { tur: 'yeni', metin: '“Tasarımlarımdan seç” ile daha önce yüklediğin tasarımı yeniden kullanabilirsin.' },
      { tur: 'yeni', metin: 'Üretime girmiş siparişte iptal talebi açabilirsin.' },
    ],
    tanitim: [
      {
        baslik: 'Aynı siparişe birden fazla ürün',
        metin: 'Ürünler adımında “+ Ürün ekle” ile her ürüne ayrı tasarım ve model seç.',
        gorsel: 'cokluUrun',
      },
      {
        baslik: 'Tasarımlarımdan seç',
        metin: 'Aynı tasarımı tekrar yüklemene gerek yok; “Tasarımlarımdan seç” sekmesinden seç.',
        gorsel: 'katalog',
      },
    ],
  },
  {
    surum: 1,
    tarih: '2026-08-23',
    baslik: 'Bayi paneli açıldı',
    ozet: 'Siparişlerini kendin girebilir, durumunu ve cari hesabını takip edebilirsin.',
    degisiklikler: [
      { tur: 'yeni', metin: 'Sipariş verme, sipariş durumu takibi ve cari hesap.' },
    ],
  },
]

export const SON_SURUM = Math.max(...GUNCELLEMELER.map((g) => g.surum))

/** Bayinin gördüğü sürüm (sunucudan, null olabilir) → gerçek sınır. */
export function goruldu(sunucudan) {
  return sunucudan == null ? BASLANGIC_SURUMU : sunucudan
}

/** Otomatik gösterilecek tanıtımlar — eskiden yeniye. */
export function bekleyenTanitimlar(sunucudan) {
  const sinir = goruldu(sunucudan)
  return GUNCELLEMELER
    .filter((g) => g.surum > sinir && g.tanitim?.length)
    .sort((a, b) => a.surum - b.surum)
}

export function yeniSayisi(sunucudan) {
  const sinir = goruldu(sunucudan)
  return GUNCELLEMELER.filter((g) => g.surum > sinir).length
}

export const TUR_ETIKET = {
  yeni: { ad: 'Yeni', sinif: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/25' },
  iyilestirme: { ad: 'İyileştirme', sinif: 'bg-sky-500/15 text-sky-300 border-sky-500/25' },
  duzeltme: { ad: 'Düzeltme', sinif: 'bg-amber-500/15 text-amber-300 border-amber-500/25' },
}
