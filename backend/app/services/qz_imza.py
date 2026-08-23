"""QZ Tray istek imzalama — yazdırma penceresi hiç çıkmasın diye.

QZ Tray, imzalanmamış sitelerde her baskıda izin soruyor ve "bu kararı hatırla"
seçeneğini KASITLI olarak devre dışı bırakıyor (imzasız bir siteye kalıcı güven
vermek güvenlik açığı olurdu). Çözüm QZ'nin kendi belgelediği yol: kendi
sertifikamızı üretip yazıcı bilgisayarına tanıtmak ve her isteği ÖZEL
ANAHTARLA imzalamak.

Özel anahtar YALNIZCA sunucuda durur; tarayıcı imzayı sunucudan ister.
Anahtar tarayıcıya verilseydi herkes o güveni kullanabilirdi.

Anahtar/sertifika ilk kullanımda üretilir ve storage altında saklanır.
"""
from __future__ import annotations

import base64
import datetime as _dt
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

from app.services.storage import STORAGE_ROOT

GECERLILIK_YIL = 20        # yazıcıya bir kez tanıtılıyor; kısa ömür işi zorlaştırır


def _dizin() -> Path:
    d = STORAGE_ROOT / "qz"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _yollar() -> tuple[Path, Path]:
    d = _dizin()
    return d / "ozel_anahtar.pem", d / "sertifika.pem"


def _uret() -> None:
    """Anahtar + kendinden imzalı sertifika üret (bir kez)."""
    anahtar_yolu, sertifika_yolu = _yollar()
    anahtar = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ad = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "Baskici Panel"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Baskici"),
    ])
    simdi = _dt.datetime.now(_dt.UTC)
    sertifika = (
        x509.CertificateBuilder()
        .subject_name(ad)
        .issuer_name(ad)
        .public_key(anahtar.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(simdi - _dt.timedelta(days=1))
        .not_valid_after(simdi + _dt.timedelta(days=365 * GECERLILIK_YIL))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(anahtar, hashes.SHA256())
    )
    # Anahtar YALNIZ sahibine okunur olsun
    anahtar_yolu.write_bytes(anahtar.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    try:
        anahtar_yolu.chmod(0o600)
    except OSError:
        pass
    sertifika_yolu.write_bytes(sertifika.public_bytes(serialization.Encoding.PEM))


def _hazirla() -> tuple[Path, Path]:
    anahtar_yolu, sertifika_yolu = _yollar()
    if not anahtar_yolu.exists() or not sertifika_yolu.exists():
        _uret()
    return anahtar_yolu, sertifika_yolu


def sertifika_pem() -> str:
    """QZ Tray'e tanıtılacak sertifika (override.crt olarak kurulur)."""
    _, sertifika_yolu = _hazirla()
    return sertifika_yolu.read_text(encoding="utf-8")


def imzala(veri: str) -> str:
    """QZ'nin gönderdiği isteği imzala. Dönüş: base64 imza.

    QZ Tray varsayılan olarak SHA512withRSA bekliyor.
    """
    anahtar_yolu, _ = _hazirla()
    anahtar = serialization.load_pem_private_key(
        anahtar_yolu.read_bytes(), password=None)
    imza = anahtar.sign(veri.encode("utf-8"), padding.PKCS1v15(), hashes.SHA512())
    return base64.b64encode(imza).decode("ascii")
