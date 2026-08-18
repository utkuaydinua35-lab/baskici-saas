"""ISO-3166 alpha-2 ülke kodu → Türkçe ad + yaklaşık merkez koordinatı.

NEDEN BURADA
────────────
Canlı görünüm ziyaretçinin ÜLKESİNİ Cloudflare'den öğrenir (IP saklanmaz).
Panelde iki yerde kullanılır: "Konuma göre oturumlar" listesindeki isim ve
küre üzerindeki noktanın yeri. Koordinatlar ülkenin yaklaşık ağırlık
merkezidir — şehir hassasiyeti yoktur ve amaçlanmaz.

Liste kasten kısa tutuldu: gerçekçi trafiğin geldiği ülkeler var. Tanınmayan
bir kod gelirse listede kodun kendisiyle görünür, küreye nokta konmaz
(yanlış yere nokta koymaktansa koymamak yeğdir).
"""
from __future__ import annotations

# kod: (Türkçe ad, enlem, boylam)
ULKELER: dict[str, tuple[str, float, float]] = {
    "TR": ("Türkiye", 39.0, 35.2),
    "DE": ("Almanya", 51.2, 10.4), "NL": ("Hollanda", 52.1, 5.3),
    "FR": ("Fransa", 46.6, 2.2), "GB": ("Birleşik Krallık", 54.0, -2.0),
    "US": ("Amerika Birleşik Devletleri", 39.8, -98.6), "CA": ("Kanada", 56.1, -106.3),
    "AT": ("Avusturya", 47.5, 14.6), "BE": ("Belçika", 50.5, 4.5),
    "CH": ("İsviçre", 46.8, 8.2), "IT": ("İtalya", 41.9, 12.6),
    "ES": ("İspanya", 40.5, -3.7), "PT": ("Portekiz", 39.4, -8.2),
    "SE": ("İsveç", 60.1, 18.6), "NO": ("Norveç", 60.5, 8.5),
    "DK": ("Danimarka", 56.3, 9.5), "FI": ("Finlandiya", 61.9, 25.7),
    "PL": ("Polonya", 51.9, 19.1), "CZ": ("Çekya", 49.8, 15.5),
    "RO": ("Romanya", 45.9, 25.0), "BG": ("Bulgaristan", 42.7, 25.5),
    "GR": ("Yunanistan", 39.1, 21.8), "HU": ("Macaristan", 47.2, 19.5),
    "SK": ("Slovakya", 48.7, 19.7), "HR": ("Hırvatistan", 45.1, 15.2),
    "RS": ("Sırbistan", 44.0, 21.0), "BA": ("Bosna-Hersek", 43.9, 17.7),
    "MK": ("Kuzey Makedonya", 41.6, 21.7), "AL": ("Arnavutluk", 41.2, 20.2),
    "SI": ("Slovenya", 46.2, 15.0), "IE": ("İrlanda", 53.4, -8.2),
    "UA": ("Ukrayna", 48.4, 31.2), "RU": ("Rusya", 61.5, 105.3),
    "BY": ("Belarus", 53.7, 27.9), "MD": ("Moldova", 47.4, 28.4),
    "LT": ("Litvanya", 55.2, 23.9), "LV": ("Letonya", 56.9, 24.6),
    "EE": ("Estonya", 58.6, 25.0), "CY": ("Kıbrıs", 35.1, 33.4),
    "MT": ("Malta", 35.9, 14.4), "LU": ("Lüksemburg", 49.8, 6.1),
    "IS": ("İzlanda", 65.0, -18.6), "XK": ("Kosova", 42.6, 20.9),
    "ME": ("Karadağ", 42.7, 19.4),
    # Orta Doğu / Kuzey Afrika
    "AZ": ("Azerbaycan", 40.1, 47.6), "GE": ("Gürcistan", 42.3, 43.4),
    "AM": ("Ermenistan", 40.1, 45.0), "IR": ("İran", 32.4, 53.7),
    "IQ": ("Irak", 33.2, 43.7), "SY": ("Suriye", 34.8, 39.0),
    "LB": ("Lübnan", 33.9, 35.9), "JO": ("Ürdün", 30.6, 36.2),
    "IL": ("İsrail", 31.0, 34.9), "PS": ("Filistin", 31.9, 35.2),
    "SA": ("Suudi Arabistan", 24.0, 45.1), "AE": ("BAE", 24.0, 54.0),
    "QA": ("Katar", 25.4, 51.2), "KW": ("Kuveyt", 29.3, 47.5),
    "BH": ("Bahreyn", 26.0, 50.6), "OM": ("Umman", 21.5, 55.9),
    "YE": ("Yemen", 15.6, 48.5), "EG": ("Mısır", 26.8, 30.8),
    "LY": ("Libya", 26.3, 17.2), "TN": ("Tunus", 33.9, 9.5),
    "DZ": ("Cezayir", 28.0, 1.7), "MA": ("Fas", 31.8, -7.1),
    # Asya
    "KZ": ("Kazakistan", 48.0, 66.9), "UZ": ("Özbekistan", 41.4, 64.6),
    "TM": ("Türkmenistan", 38.9, 59.6), "KG": ("Kırgızistan", 41.2, 74.8),
    "TJ": ("Tacikistan", 38.9, 71.3), "AF": ("Afganistan", 33.9, 67.7),
    "PK": ("Pakistan", 30.4, 69.3), "IN": ("Hindistan", 20.6, 79.0),
    "BD": ("Bangladeş", 23.7, 90.4), "LK": ("Sri Lanka", 7.9, 80.8),
    "NP": ("Nepal", 28.4, 84.1), "CN": ("Çin", 35.9, 104.2),
    "JP": ("Japonya", 36.2, 138.3), "KR": ("Güney Kore", 35.9, 127.8),
    "TW": ("Tayvan", 23.7, 121.0), "HK": ("Hong Kong", 22.4, 114.1),
    "TH": ("Tayland", 15.9, 101.0), "VN": ("Vietnam", 14.1, 108.3),
    "MY": ("Malezya", 4.2, 101.98), "SG": ("Singapur", 1.35, 103.8),
    "ID": ("Endonezya", -0.8, 113.9), "PH": ("Filipinler", 12.9, 121.8),
    # Afrika
    "NG": ("Nijerya", 9.1, 8.7), "GH": ("Gana", 7.9, -1.0),
    "KE": ("Kenya", -0.02, 37.9), "ET": ("Etiyopya", 9.1, 40.5),
    "TZ": ("Tanzanya", -6.4, 34.9), "UG": ("Uganda", 1.4, 32.3),
    "ZA": ("Güney Afrika", -30.6, 22.9), "SN": ("Senegal", 14.5, -14.5),
    "CI": ("Fildişi Sahili", 7.5, -5.5), "CM": ("Kamerun", 7.4, 12.4),
    "SD": ("Sudan", 12.9, 30.2), "SO": ("Somali", 5.2, 46.2),
    # Amerika
    "MX": ("Meksika", 23.6, -102.6), "BR": ("Brezilya", -14.2, -51.9),
    "AR": ("Arjantin", -38.4, -63.6), "CL": ("Şili", -35.7, -71.5),
    "CO": ("Kolombiya", 4.6, -74.3), "PE": ("Peru", -9.2, -75.0),
    "VE": ("Venezuela", 6.4, -66.6), "EC": ("Ekvador", -1.8, -78.2),
    "UY": ("Uruguay", -32.5, -55.8), "PY": ("Paraguay", -23.4, -58.4),
    "BO": ("Bolivya", -16.3, -63.6), "CU": ("Küba", 21.5, -77.8),
    "DO": ("Dominik Cumhuriyeti", 18.7, -70.2), "CR": ("Kosta Rika", 9.7, -83.8),
    "PA": ("Panama", 8.5, -80.8), "GT": ("Guatemala", 15.8, -90.2),
    # Okyanusya
    "AU": ("Avustralya", -25.3, 133.8), "NZ": ("Yeni Zelanda", -40.9, 174.9),
}


def ulke_bilgi(kod: str | None) -> dict:
    """Kod → {kod, ad, lat, lon}. Tanınmayan kodda lat/lon None döner."""
    k = (kod or "").strip().upper()
    if k in ULKELER:
        ad, lat, lon = ULKELER[k]
        return {"kod": k, "ad": ad, "lat": lat, "lon": lon}
    return {"kod": k or "??", "ad": k or "Bilinmiyor", "lat": None, "lon": None}
