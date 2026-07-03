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
from decimal import ROUND_DOWN, Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import CheckoutSession


def scaled_basket_lines(session: CheckoutSession) -> list[tuple[dict, Decimal]]:
    """Kalem toplamlarını indirim SONRASI ürün tutarına ölçekle.

    iyzico sum(basketItems.price) == price ister ve negatif/sıfır kalem kabul
    etmez; indirim ayrı satır olamaz → oransal dağıtılır. ROUND_DOWN + kuruş
    kalanının en büyük kaleme eklenmesi toplamın hedefe TAM eşitliğini garanti
    eder (checkout MIN_CHARGE tabanı sıfır kalemi zaten engeller).
    Dönüş: [(snapshot_item, ölçeklenmiş_kalem_toplamı)]
    """
    items = session.cart_snapshot or []
    line_totals = [
        Decimal(str(i.get("unit_price", "0"))) * int(i.get("quantity", 1)) for i in items
    ]
    items_total = sum(line_totals, Decimal("0"))
    discount = Decimal(str(session.discount_amount or 0))
    target = items_total - discount
    if discount == 0 or items_total == 0:
        return list(zip(items, line_totals))

    scaled = [
        (lt * target / items_total).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
        for lt in line_totals
    ]
    remainder = target - sum(scaled, Decimal("0"))  # 0 <= kalan < n*0.01
    idx = scaled.index(max(scaled))
    scaled[idx] += remainder
    return list(zip(items, scaled))


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


@dataclass
class RefundResult:
    """refund dönüşü — sağlayıcı iade sonucu."""
    status: str               # "succeeded" | "failed"
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

    def refund(self, session: CheckoutSession, amount) -> RefundResult:
        """Kısmi/tam para iadesi. Varsayılan: desteklenmiyor."""
        return RefundResult(status="failed", error="Bu sağlayıcı panelden iadeyi desteklemiyor")
