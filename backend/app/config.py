"""
Uygulama yapılandırması. Env değişkenlerini Pydantic ile tip güvenli okur.
"""
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = Field(..., alias="DATABASE_URL")

    # Auth
    jwt_secret: str = Field(..., alias="JWT_SECRET")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 gün
    session_secret: str = Field(..., alias="SESSION_SECRET")

    # Self-servis kayıt (üye ol). VARSAYILAN KAPALI: panel tek atölye için
    # kullanılıyorsa açık kayıt ekranı gereksiz bir saldırı yüzeyi (yabancılar
    # onay bekleyen hesap bırakabiliyordu). Kiralamaya açılacaksa .env'de
    # ALLOW_PUBLIC_SIGNUP=true yap.
    allow_public_signup: bool = Field(False, alias="ALLOW_PUBLIC_SIGNUP")

    # Environment
    env: str = Field("development", alias="ENV")
    host: str = Field("127.0.0.1", alias="HOST")
    port: int = Field(8000, alias="PORT")

    # OAuth
    google_client_id: str = Field("", alias="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field("", alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str = Field(
        "http://localhost:8000/api/auth/google/callback",
        alias="GOOGLE_REDIRECT_URI",
    )

    # Frontend
    frontend_url: str = Field("http://localhost:5173", alias="FRONTEND_URL")
    backend_url: str = Field("http://localhost:8000", alias="BACKEND_URL")

    @field_validator("frontend_url", "backend_url", mode="after")
    @classmethod
    def _url_tek_parca(cls, v: str) -> str:
        """.env'de değere boşlukla fazlalık yapışırsa (örn
        "https://... env=production") yalnız ilk parça alınır — bozuk taban
        URL iyzico dönüşü gibi dış yönlendirmeleri kırıyordu."""
        parts = str(v or "").strip().split()
        return parts[0] if parts else v
    # Vitrin ozel domain dogrulamasi: musterinin A kaydinin isaret etmesi gereken IP
    server_ip: str = Field("", alias="SERVER_IP")

    # Senkronizasyon penceresi (gün): yalnızca son N günde OLUŞAN ya da DURUMU
    # DEĞİŞEN (updated_at) siparişler çekilir. Daha eski/durağan siparişler zaten
    # DB'de olduğundan tekrar çekilmez -> senk çok daha hızlı. 0 = pencere kapalı
    # (eski davranış: son ~3750 sipariş).
    sync_window_days: int = Field(45, alias="SYNC_WINDOW_DAYS")

    # Public sipariş takip — hangi Shopify mağazasi sorgulanacak (store_url ile eşleşir)
    tracker_shop_domain: str = Field("2eb3e1-48.myshopify.com", alias="TRACKER_SHOP_DOMAIN")

    # Destek görsellerinin servis edildiği public taban URL
    support_public_base_url: str = Field("https://siparistakip.bernzcompany.com", alias="SUPPORT_PUBLIC_BASE_URL")

    # KURULUMUN markası — panel giriş ekranı, passkey/authenticator diyalogu
    # ve personel bildirimlerinde görünür. MÜŞTERİ yüzeyinde kullanılmaz:
    # orada marka her zaman MAĞAZANIN kendi adıdır (store.name).
    brand_name: str = Field("Panel", alias="BRAND_NAME")

    # Telegram bildirimi (yeni destek mesaji)
    telegram_bot_token: str = Field("", alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field("", alias="TELEGRAM_CHAT_ID")

    # Panel taban URL (Telegram deep-link icin)
    panel_base_url: str = Field("https://baskici.bernzcompany.com", alias="PANEL_BASE_URL")
    # Passkey (WebAuthn) — RP ID tüm panellerin ORTAK üst alan adı olmalı
    # (bernzcompany.com), yoksa baskici./magazapanel. ayrı ayrı kayıt ister.
    # Boşsa panel_base_url'in host'u kullanılır (yerel geliştirme).
    webauthn_rp_id: str = Field("", alias="WEBAUTHN_RP_ID")
    # Passkey kullanacak panellerin origin listesi (virgülle) — boşsa yalnız panel_base_url
    webauthn_origins: str = Field("", alias="WEBAUTHN_ORIGINS")

    # Claude API (AI destek taslak yaniti). Bos ise AI taslak ozelligi kapali.
    anthropic_api_key: str = Field("", alias="ANTHROPIC_API_KEY")

    # Görsel genişletme (outpaint) — Ürün Stüdyosu'nda oran uymayan görselleri 1:2'ye tamamlar.
    fal_key: str = Field("", alias="FAL_KEY")                       # fal.ai (FLUX Fill)
    fal_model: str = Field("fal-ai/flux-pro/v1/fill", alias="FAL_MODEL")
    fal_upscale_model: str = Field("fal-ai/clarity-upscaler", alias="FAL_UPSCALE_MODEL")
    # Metinden görsel (sosyal medya persona sahnesi) — FLUX text-to-image.
    fal_text2img_model: str = Field("fal-ai/flux/dev", alias="FAL_TEXT2IMG_MODEL")
    # Karakter yüz kimliği (referans fotoğraftan BİREBİR aynı yüz) — PuLID/FLUX.
    fal_face_model: str = Field("fal-ai/flux-pulid", alias="FAL_FACE_MODEL")
    gemini_api_key: str = Field("", alias="GEMINI_API_KEY")         # Google AI Studio (ABONELİK DEĞİL)
    gemini_image_model: str = Field("gemini-2.5-flash-image", alias="GEMINI_IMAGE_MODEL")
    # AI model degisikligi icin master password. Bos ise model degisikligi engellenir.
    ai_model_master_password: str = Field("", alias="AI_MODEL_MASTER_PASSWORD")

    # Web Push (PWA mobil bildirim) — VAPID anahtar cifti. Ikisi de bos ise push kapali.
    # Uretmek icin: `python -m app.services.push --genkeys` (bir kez), ciktiyi .env'e yaz.
    vapid_public_key: str = Field("", alias="VAPID_PUBLIC_KEY")
    vapid_private_key: str = Field("", alias="VAPID_PRIVATE_KEY")
    vapid_subject: str = Field("mailto:imalchera.gfx@gmail.com", alias="VAPID_SUBJECT")

    # SMTP (e-posta gonderimi — sifre sifirlama). Bos ise e-posta ozelligi kapali.
    smtp_host: str = Field("", alias="SMTP_HOST")
    smtp_port: int = Field(587, alias="SMTP_PORT")
    smtp_user: str = Field("", alias="SMTP_USER")
    smtp_password: str = Field("", alias="SMTP_PASSWORD")
    smtp_from: str = Field("", alias="SMTP_FROM")  # bos ise smtp_user kullanilir
    # Resend (HTTPS API'li mail) — SMTP portlari kapali VPS'lerde 443 uzerinden gonderir.
    # Doluysa SMTP yerine bu kullanilir. resend_from: dogrulanmis domain adresi (orn noreply@bernzcompany.com)
    resend_api_key: str = Field("", alias="RESEND_API_KEY")
    resend_from: str = Field("", alias="RESEND_FROM")

    # Sürat Kargo (eski — Basit Kargo ile değiştirildi; adres ayrıştırma helper'ları kalıyor)
    surat_kullanici_adi: str = Field("", alias="SURAT_KULLANICI_ADI")
    surat_sifre: str = Field("", alias="SURAT_SIFRE")
    surat_relay_url: str = Field("", alias="SURAT_RELAY_URL")

    # Instagram DM otomasyonu (Meta webhook). Boş ise webhook kapalı (404).
    # Hesap bazlı business_id + access_token store.config'te tutulur (panelden girilir).
    ig_verify_token: str = Field("", alias="IG_VERIFY_TOKEN")   # webhook doğrulama (Meta panelinde aynısı)
    ig_app_secret: str = Field("", alias="IG_APP_SECRET")       # imza doğrulama (X-Hub-Signature-256)
    ig_graph_version: str = Field("v21.0", alias="IG_GRAPH_VERSION")

    # Basit Kargo (çoklu kargo agregatörü). Boş ise kargo gönderimi kapalı.
    basit_kargo_token: str = Field("", alias="BASIT_KARGO_TOKEN")
    basit_kargo_address_id: str = Field("", alias="BASIT_KARGO_ADDRESS_ID")  # opsiyonel gönderici
    basit_kargo_brand_id: str = Field("", alias="BASIT_KARGO_BRAND_ID")      # opsiyonel marka
    # Webhook secret (URL'de): boş ise webhook kapalı (tüm istekler 404).
    basit_kargo_webhook_secret: str = Field("", alias="BASIT_KARGO_WEBHOOK_SECRET")

    @property
    def is_production(self) -> bool:
        return self.env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
