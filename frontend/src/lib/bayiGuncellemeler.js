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
    surum: 9,
    tarih: '2026-10-03',
    baslik: 'Atölyeyle sohbet + masaüstü uygulaması',
    ozet: 'Artık panelden doğrudan bize yazabilir, görsel ve sipariş ekleyebilir, acil durumu işaretleyebilirsin. Bilgisayarına kurduğun uygulamayla kargo bildirimleri de ayağına gelir.',
    degisiklikler: [
      { tur: 'yeni', metin: 'Menüde “Sohbet”: bize doğrudan yaz, anında yanıt al. Okunmamış mesaj sayısı menüde görünür.' },
      { tur: 'yeni', metin: 'Mesaja görsel ekleyebilir, “şu siparişten bahsediyorum” diye sipariş iliştirebilirsin.' },
      { tur: 'yeni', metin: 'Aciliyet işareti: “Acil” ya da “Çok acil” seçersen mesaj bize anında bildirim olarak düşer.' },
      { tur: 'yeni', metin: 'Windows ve Mac için BERNZ Bayi uygulaması: siparişin kargoya verildiğinde ve biz yazdığımızda bilgisayarında bildirim görürsün.' },
      { tur: 'yeni', metin: 'Menüdeki “Uygulama” sayfasından kurulumu kendin indirebilirsin — Windows’ta tek tık, Mac’te logoyu Uygulamalar’a sürükle.' },
    ],
    tanitim: [
      {
        baslik: 'Bize doğrudan yaz',
        metin: 'Menüden Sohbet’e gir. Yazdığın mesaj bize anında ulaşır; yanıt gelince menüdeki rozetten görürsün.',
        gorsel: 'sohbet',
      },
      {
        baslik: 'Görsel, sipariş ve aciliyet',
        metin: '📎 ile fotoğraf ekle, listeden siparişi seç, gerçekten acil bir durumda “Acil” işaretle — acil mesajlar telefonumuza bildirim olarak düşer.',
        gorsel: 'sohbet',
      },
      {
        baslik: 'Bilgisayarına kur, bildirim al',
        metin: 'Menüden “Uygulama” sayfasına gir, bilgisayarına uygun dosyayı indir. Windows’ta tek tıkla kurulur, Mac’te logoyu Uygulamalar’a sürüklersin. Kurduktan sonra sipariş kargoya verilince ve biz sana yazınca bildirim çıkar.',
        gorsel: 'masaustu',
      },
    ],
  },
  {
    surum: 8,
    tarih: '2026-09-18',
    baslik: 'Oturum artık ortada düşmüyor',
    ozet: 'Panel uzun süre açık kalsa da oturumun kendini tazeliyor; süresi dolarsa doğrudan giriş ekranına dönüyorsun.',
    degisiklikler: [
      { tur: 'iyilestirme', metin: 'Panel açık kaldıkça oturumun sessizce tazelenir — gün ortasında kopmaz.' },
      { tur: 'duzeltme', metin: 'Oturum gerçekten sona erdiyse artık anlaşılmaz bir hata yerine giriş ekranına yönlendiriliyorsun.' },
    ],
  },
  {
    surum: 7,
    tarih: '2026-09-15',
    baslik: 'Önizleme görselini sonradan değiştir',
    ozet: 'Önizleme görseli artık sipariş verdikten sonra da eklenebilir, değiştirilebilir ya da kaldırılabilir.',
    degisiklikler: [
      { tur: 'yeni', metin: 'Sipariş detayında her ürüne sonradan önizleme görseli ekleyebilirsin.' },
      { tur: 'iyilestirme', metin: 'Yanlış önizleme görselini “Değiştir” ile yenileyebilir, “Kaldır” ile silebilirsin (sipariş üretime girene kadar).' },
      { tur: 'iyilestirme', metin: 'Hepsiburada kargo kodunda hata varsa ekibimiz de düzeltebiliyor; değişiklik sana bildirilir.' },
    ],
    tanitim: [
      {
        baslik: 'Önizlemeyi sonradan ekle ya da değiştir',
        metin: 'Siparişlerim → sipariş detayı → ürün kartında önizleme görselinin altındaki “Değiştir” veya “Kaldır”. Önizleme yoksa “+ Önizleme görseli ekle”. Baskıya girmez.',
        gorsel: 'onizleme',
      },
    ],
  },
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
