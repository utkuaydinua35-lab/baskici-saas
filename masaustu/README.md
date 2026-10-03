# BERNZ masaüstü uygulamaları

Tek Electron kabuğu, **iki profil** (`kaynak/profiller.js`):

| Profil | Uygulama | Açtığı panel | Bildirim kaynağı |
|---|---|---|---|
| `bayi` | **BERNZ Bayi** (turkuaz simge) | `/bayii` bayi paneli | kargoya verilen siparişler + atölye mesajları |
| `studio` | **BERNZ Studio** (mor simge) | yönetim paneli | panelin kendi bildirimleri |

Kod ortak: pencere, bildirim yoklaması, menü ve güvenlik ayarları tek yerde.
Profil paketleme sırasında `package.json`'a gömülür (electron-builder
`extraMetadata.bernzProfil`), çalışırken oradan okunur.

- **Windows:** tek tıkla kurulan `.exe` (NSIS, kullanıcı hesabına kurar, yönetici
  şifresi istemez), masaüstü + başlat menüsü kısayolu.
- **macOS:** `.dmg` — logoyu **Uygulamalar** klasörüne sürükle.

## Çalıştırma (geliştirme)

```bash
cd masaustu
npm install
npm run basla                       # bayi profili, canlı panel
npm run basla:studio                # yönetim profili
BERNZ_PANEL_URL=http://localhost:5174/bayii npm run basla   # yerel panel
BERNZ_SMOKE=1 npm run basla         # duman testi: açılır, yüklenir, kapanır
```

## Paket üretme

```bash
npm run paket:bayi:mac      # cikti/bayi/BERNZ-Bayi-1.0.0-arm64.dmg (+x64)
npm run paket:bayi:win      # cikti/bayi/BERNZ-Bayi-Kurulum-1.0.0.exe
npm run paket:studio:mac    # cikti/studio/BERNZ-Studyo-1.0.0-arm64.dmg (+x64)
npm run paket:studio:win    # cikti/studio/BERNZ-Studyo-Kurulum-1.0.0.exe
npm run paket:mac           # iki profil birden (mac)
npm run paket:win           # iki profil birden (windows)
```

> **Windows paketi de Mac'te üretilebiliyor** — Wine GEREKMİYOR; electron-builder
> NSIS'i ve rcedit'i kendi taşınabilir araçlarıyla çalıştırıyor (ilk çalıştırmada
> Windows için Electron ikilisini indirir, birkaç dakika sürer). Wine yalnız
> `signtool` ile İMZALAMA için gerekir; imzasız üretimde atlanıyor.
> Mac paketi Mac'te üretilmeli ve Apple Silicon + Intel için iki ayrı dosya çıkar.

## Bayiye yayınlama

Üretilen kurulum dosyaları sunucuda `backend/uploads/uygulama/` klasörüne
kopyalanır; bayi panelindeki **Uygulama** sayfası (`/bayii/uygulama`) o klasörü
okur. Veritabanı kaydı yok — kopyalamak yayınlamaktır.

⚠ `baskici@91.132.49.107` ile GİTMEZ: Mac'teki SSH anahtarı sunucuda **root**'a
tanımlı, `baskici` Linux kullanıcısına değil — parola sorar ve geçemezsin.
SSH takma adı `baskici` zaten root'a bakıyor (`~/.ssh/config`). Dosyalar önce
root olarak `/tmp`'ye gider, sonra doğru sahiplikle yerine taşınır:

```bash
# Dosya adlarını DEĞİŞTİRME — sayfa addan profil/sürüm/mimari çözüyor
scp masaustu/cikti/bayi/BERNZ-Bayi-*.dmg masaustu/cikti/studio/BERNZ-Studyo-*.dmg baskici:/tmp/
ssh baskici 'install -o baskici -g baskici -m 644 /tmp/BERNZ-*.dmg \
  /home/baskici/baskici-saas/backend/uploads/uygulama/ && rm -f /tmp/BERNZ-*.dmg \
  && ls -lh /home/baskici/baskici-saas/backend/uploads/uygulama/'
```

Klasör yoksa bir kez: `mkdir -p ~/baskici-saas/backend/uploads/uygulama`.

İndirme yükü backend'e binmesin diye nginx bu klasörü DOĞRUDAN servis eder —
blok ve kurulum adımları `deploy/nginx-uygulama-indirme.conf` dosyasında.

Beklenen dosya adları:

| Dosya | Ne |
|---|---|
| `BERNZ-Bayi-<sürüm>-arm64.dmg` | bayi · macOS, Apple Silicon |
| `BERNZ-Bayi-<sürüm>-x64.dmg` | bayi · macOS, Intel |
| `BERNZ-Bayi-Kurulum-<sürüm>.exe` | bayi · Windows |
| `BERNZ-Studyo-<sürüm>-arm64.dmg` | yönetim · macOS, Apple Silicon |
| `BERNZ-Studyo-<sürüm>-x64.dmg` | yönetim · macOS, Intel |
| `BERNZ-Studyo-Kurulum-<sürüm>.exe` | yönetim · Windows |

Bayi sayfası yalnız `BERNZ-Bayi-*`, yönetim ayarları yalnız `BERNZ-Studyo-*`
dosyalarını listeler — ikisi aynı klasörde durabilir.

Kurala uymayan dosyalar listelenmez (klasöre düşen rastgele bir dosya bayiye
"kurulum" diye gösterilmesin).

## İki kural (yanıp öğrenildi)

**1. Ürün adı ASCII olmalı.** `productName: "BERNZ Stüdyo"` ile paketlenen
uygulama macOS'ta açılışta **SIGTRAP ile çöküyor** (uygulama paketi ve
çalıştırılabilir dosya adındaki "ü" Electron'un çerçeve/yardımcı süreç
yollarını bozuyor). Aynı paketleme ASCII adla (`BERNZ Studio`) sorunsuz açıldı
— ikisini yan yana derleyip doğruladık. Pencere başlığı, menü ve bildirim
metinleri Türkçe kalabilir; dosya sistemine yazılan ad ASCII olmalı.

**2. `identity: null` + `hardenedRuntime: false`.** Anahtar zincirinde bir
"Apple Development" sertifikası varsa electron-builder onu kendiliğinden bulup
imzalıyor. Geliştirme sertifikası dağıtım için değildir: provisioning profile
olmadan JIT izinleri reddedilir. Dağıtım imzasız olduğu sürece ad-hoc imza
doğrusu. (Bu tek başına çökmenin sebebi değildi ama paketi dağıtılamaz
yapıyordu.)

Çökme yaşarsan tanı tek satır — uygulamayı doğrudan çalıştır, çıkış kodu 133
(128+SIGTRAP) ise açılamıyor demektir:

```bash
BERNZ_SMOKE=1 "cikti/studio/mac-arm64/BERNZ Studio.app/Contents/MacOS/BERNZ Studio"; echo $?
```

## İmzalama (şu an YOK)

Paketler imzasız dağıtılıyor. Bayiye söylenecekler:

- **macOS:** ilk açılışta "doğrulanamayan geliştirici" uyarısı çıkar →
  Uygulamalar klasöründe simgeye **sağ tık → Aç** → **Aç**. Bir kez yapılır.
- **Windows:** SmartScreen "bilgisayarınız korundu" der → **Ek bilgi** →
  **Yine de çalıştır**. Bir kez yapılır.

İmzalamaya geçince bu uyarılar kalkar, kodda değişiklik gerekmez:

- macOS: Apple Developer hesabı ($99/yıl) → `CSC_LINK` + `CSC_KEY_PASSWORD` ve
  `APPLE_ID` + `APPLE_APP_SPECIFIC_PASSWORD` + `APPLE_TEAM_ID` ortam
  değişkenleri; `build.mac.notarize: true` eklenir.
- Windows: kod imzalama sertifikası (EV önerilir, SmartScreen itibarı anında
  gelir) → `CSC_LINK` + `CSC_KEY_PASSWORD`.

## Bildirimler nasıl çalışıyor

Electron'da tarayıcı Web Push altyapısı yok (VAPID/servis çalışanı zinciri
orada işlemiyor). Bu yüzden kabuk, 60 saniyede bir sunucuya sorar:

```
GET <profilin bildirim ucu>?since=<son görülen zaman>
→ { sunucu_saati, olaylar: [{ id, tur, baslik, govde, at, link }] }

bayi   → /api/bayii/bildirimler      (kargo + sohbet)
studio → /api/notifications/akis     (panel bildirimleri)
```

İki uç AYNI sözleşmeyi konuşur; kabuk tek kod. Alan adları ayrışırsa
`scripts/masaustu_akis_test.py` kırmızı yanar.

- Olaylar var olan kayıtlardan türetiliyor; sunucuda yeni tablo yok.
  `tur`: `kargo` (sipariş kargoya verildi) · `sohbet` (atölyeden mesaj).
- `since` yoksa sunucu olay döndürmez, yalnız saatini verir — ilk açılışta
  geçmiş bildirim yağmuru olmasın.
- Hangi olayın gösterildiği kullanıcı klasöründeki `durum.json`'da tutulur;
  uygulama kapanıp açılınca aynı bildirim tekrar düşmez.
- Oturum jetonu panelin kendi `localStorage`'ından OKUNUR; kabuk oturum
  açmaz, yazmaz. Oturum yoksa yoklama yapılmaz.
- Kullanıcı bildirimleri **Dosya → Bildirimler açık** ile kapatabilir.

## Güvenlik

- `nodeIntegration: false`, `contextIsolation: true` — panel sayfası Node'a
  erişemez. `preload.js` yalnız sürüm/platform bilgisi verir.
- Panel dışındaki bağlantılar (WhatsApp, kargo takip) kabuğun içinde değil,
  **varsayılan tarayıcıda** açılır.
