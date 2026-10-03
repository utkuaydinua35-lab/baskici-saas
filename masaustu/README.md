# BERNZ Bayi — masaüstü uygulaması

Bayi panelini kendi penceresinde açan Electron kabuğu. Kargo ve sohbet
bildirimlerini işletim sisteminin bildirimi olarak gösterir.

- **Windows:** tek tıkla kurulan `.exe` (NSIS, kullanıcı hesabına kurar, yönetici
  şifresi istemez), masaüstü + başlat menüsü kısayolu.
- **macOS:** `.dmg` — logoyu **Uygulamalar** klasörüne sürükle.

## Çalıştırma (geliştirme)

```bash
cd masaustu
npm install
npm run basla                       # canlı paneli açar
BERNZ_PANEL_URL=http://localhost:5174/bayii npm run basla   # yerel panel
```

## Paket üretme

```bash
npm run paket:win     # cikti/BERNZ-Bayi-Kurulum-1.0.0.exe
npm run paket:mac     # cikti/BERNZ-Bayi-1.0.0-arm64.dmg + x64
npm run paket         # ikisi birden
```

> Windows paketini **Windows'ta**, Mac paketini **Mac'te** üretmek gerekir
> (çapraz derleme imzasız işlerde sorun çıkarıyor). Mac'te üretilen `.dmg`
> hem Apple Silicon hem Intel için ayrı dosya olarak çıkar.

## Bayiye yayınlama

Üretilen kurulum dosyaları sunucuda `backend/uploads/uygulama/` klasörüne
kopyalanır; bayi panelindeki **Uygulama** sayfası (`/bayii/uygulama`) o klasörü
okur. Veritabanı kaydı yok — kopyalamak yayınlamaktır.

```bash
# Mac'ten sunucuya (dosya adlarını DEĞİŞTİRME — sayfa addan sürüm/mimari çözüyor)
scp masaustu/cikti/BERNZ-Bayi-1.0.0-*.dmg baskici@91.132.49.107:/home/baskici/baskici-saas/backend/uploads/uygulama/
scp masaustu/cikti/BERNZ-Bayi-Kurulum-1.0.0.exe baskici@91.132.49.107:/home/baskici/baskici-saas/backend/uploads/uygulama/
```

Klasör yoksa bir kez: `mkdir -p ~/baskici-saas/backend/uploads/uygulama`.

İndirme yükü backend'e binmesin diye nginx bu klasörü DOĞRUDAN servis eder —
blok ve kurulum adımları `deploy/nginx-uygulama-indirme.conf` dosyasında.

Beklenen dosya adları:

| Dosya | Ne |
|---|---|
| `BERNZ-Bayi-<sürüm>-arm64.dmg` | macOS, Apple Silicon |
| `BERNZ-Bayi-<sürüm>-x64.dmg` | macOS, Intel |
| `BERNZ-Bayi-Kurulum-<sürüm>.exe` | Windows |

Kurala uymayan dosyalar listelenmez (klasöre düşen rastgele bir dosya bayiye
"kurulum" diye gösterilmesin).

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
GET /api/bayii/bildirimler?since=<son görülen zaman>
→ { sunucu_saati, olaylar: [{ id, tur, baslik, govde, at, link }] }
```

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
