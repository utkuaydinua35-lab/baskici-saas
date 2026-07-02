# Vitrin — Kendi E-Ticaret Kanalımız

Shopify'a bağımlı olmayan, kendi markamıza ait satış kanalı. Siparişler mevcut
üretim hattına (kalıp planlama, kargo, paketleme) **hiç değişiklik gerektirmeden** akar.

## Mimari

```
Müşteri ──> Next.js vitrin (storefront/, port 3001)
              │  server-to-server (BACKEND_URL — CORS yok)
              ▼
            FastAPI /api/shop/* (public, rate-limitli)
              │
              ├─ katalog okuma (catalog_products/variants/images)
              ├─ checkout → CheckoutSession + iyzico/PayTR başlatma
              │     kart verisi BİZE HİÇ GELMEZ (sağlayıcı sayfası/iframe)
              └─ doğrulanmış ödeme callback'i
                    → _upsert_order (Shopify-şekilli raw, tags=storefront)
                    → stok düşümü + onay e-postası
                    → mevcut üretim hattı devralır
```

## Kurulum (admin)

1. **Atölyeler** → yeni mağaza → platform: **Kendi Mağazam (Vitrin)**
   - `payment_provider`: `iyzico` veya `paytr`
   - iyzico: `iyzico_api_key`, `iyzico_secret_key`, `iyzico_base_url`
     (sandbox: `https://sandbox-api.iyzipay.com`, canlı: `https://api.iyzipay.com`)
   - PayTR: `paytr_merchant_id`, `paytr_merchant_key`, `paytr_merchant_salt`
     (+ canlıya geçerken `paytr_test_mode: "0"`)
   - `storefront_url`: vitrinin tam adresi (örn `https://magaza.bernzcompany.com`)
   - `shipping_fee` / `free_shipping_over`: kargo ücreti kuralı (opsiyonel)
   - `sla_days`: kargo sözü (varsayılan 3)
2. **Katalog → Vitrin** sayfasından ürün ekle, "telefon modellerinden üret" ile
   varyantları oluştur, görsel yükle, **Yayınla**.
3. Kullanıcılara `vitrin` izni ver (yönetici/owner otomatik sahip).

### PayTR panel ayarı
PayTR mağaza panelinde Bildirim URL'i olarak şunu tanımla:
`https://<backend-domain>/api/shop/payments/paytr/webhook`

## Vitrin (Next.js) çalıştırma

```bash
cd storefront
cp .env.example .env.local   # BACKEND_URL, STORE_SLUG, NEXT_PUBLIC_SITE_URL
npm ci
npm run build
PORT=3001 npm run start      # prod; dev için: npm run dev
```

## VPS / Caddy

```caddyfile
magaza.bernzcompany.com {
    reverse_proxy 127.0.0.1:3001
}
# Backend'in mevcut host'u /api/shop/* ve /storage/* yollarını zaten sunar;
# ödeme sağlayıcı callback'leri backend host'una gelir (BACKEND_URL env'i).
```

Systemd örneği (`/etc/systemd/system/baskici-storefront.service`):

```ini
[Unit]
Description=Baskici Vitrin (Next.js)
After=network.target

[Service]
WorkingDirectory=/srv/baskici/storefront
Environment=PORT=3001
EnvironmentFile=/srv/baskici/storefront/.env.local
ExecStart=/usr/bin/npm run start
Restart=always

[Install]
WantedBy=multi-user.target
```

## Güvenlik özeti

- **Kart verisi**: hiçbir zaman bizim sunucuya değmez (iyzico Checkout Form /
  PayTR iframe). PCI-DSS yükü sağlayıcıda.
- **Callback doğrulama**: iyzico → sunucudan sunucuya retrieve + tutar +
  conversationId; PayTR → HMAC hash (`hmac.compare_digest`) + tutar.
- **Idempotency**: callback'te `FOR UPDATE` kilidi + status kontrolü; orders
  tablosunda `(store_id, external_id)` tekilliği sert emniyet.
- **Fiyat**: her zaman sunucuda hesaplanır; istemciden yalnızca
  `variant_id + quantity` alınır.
- **Rate limit**: tüm public endpoint'lerde (IP başına; CF-Connecting-IP okunur).
- **Token'lar**: `secrets.token_urlsafe(32)` — tahmin edilemez; sipariş takibi
  minimal veri döner (adres/telefon yankılanmaz).
- **KVKK**: `kvkk_accepted_at` kaydı; ödemesi tamamlanmayan oturumların PII'si
  90 gün sonra otomatik silinir (gece 04:00 sweeper). Aydınlatma metni,
  mesafeli satış sözleşmesi ve iade sayfaları vitrinde hazır — **yayına almadan
  önce şirket unvan/adres bilgilerini doldurun.**

## Canlıya geçiş kontrol listesi

- [ ] iyzico/PayTR CANLI anahtarları mağaza config'ine girildi
      (iyzico_base_url → `https://api.iyzipay.com`, paytr_test_mode → `"0"`)
- [ ] `storefront_url` doğru domain'i gösteriyor
- [ ] PayTR panelinde bildirim URL'i tanımlı
- [ ] Yasal sayfalardaki şirket bilgisi placeholder'ları dolduruldu
- [ ] SMTP ayarlı (onay e-postaları için)
- [ ] Düşük tutarlı gerçek kartla test siparişi verildi ve iade edildi
