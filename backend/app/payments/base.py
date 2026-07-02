"""
Ödeme sağlayıcı soyutlaması — adapters/base.py'deki StorePlatform deseni.

GÜVENLİK SÖZLEŞMESİ:
- Kart verisi ASLA bizim sunucuya gelmez; sağlayıcının barındırdığı
  sayfa/iframe kullanılır (PCI-DSS yükü sağlayıcıda).
- handle_callback KRİPTOGRAFİK doğrulama yapmak ZORUNDADIR (imza/hash veya
  sunucudan sunucuya retrieve). Tarayıcıdan gelen POST'a asla güvenilmez.
- Tutar her zaman session'daki sunucu-hesaplı tutarla karşılaştırılır.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import CheckoutSession


@dataclass
class CheckoutInit:
    """create_checkout dönüşü. mode='redirect' → url'e yönlendir;
    mode='iframe' → url iframe içinde açılır."""
    mode: str                 # "redirect" | "iframe"
    url: str
    provider_ref: str | None = None


@dataclass
class PaymentResult:
    """handle_callback dönüşü — yalnızca doğrulama BAŞARILIYSA status='paid'."""
    status: str               # "paid" | "failed"
    provider_ref: str | None = None
    error: str | None = None
    raw: dict = field(default_factory=dict)


class PaymentProvider(ABC):
    """Tüm ödeme sağlayıcı adapter'larının temel sınıfı."""

    PROVIDER_NAME: str = ""

    def __init__(self, config: dict):
        """config: Store.config JSONB (sağlayıcı anahtarları)."""
        self.config = config or {}

    @abstractmethod
    def create_checkout(self, session: CheckoutSession, callback_url: str) -> CheckoutInit:
        """Sağlayıcıda ödeme oturumu başlat; müşterinin gideceği URL'i döndür.
        Hata durumunda ValueError (mesaj müşteriye gösterilebilir olmalı)."""

    @abstractmethod
    def handle_callback(self, form: dict, session: CheckoutSession) -> PaymentResult:
        """Sağlayıcı callback'ini DOĞRULA ve sonucu döndür.
        Doğrulanamayan istek → PaymentResult(status='failed', error=...)."""
