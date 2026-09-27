"""Türkçe metin yardımcıları — TEK KAYNAK.

⚠ PYTHON'DA TÜRKÇE BÜYÜK/KÜÇÜK HARF TUZAĞI. Python `İ` (U+0130) harfini
küçültürken `i` + U+0307 (birleşen üst nokta) üretiyor:

    "SİYAH".capitalize()  ->  "Si̇yah"     ← müşteriye giden e-postada bu çıktı
    "SERİSİ".lower()      ->  "seri̇si̇"    ← arama/eşleşme sessizce bozulur

Bu tuzak projede İKİ KEZ ısırdı (katalog kategori adları, sonra kalıp slot
tanımı). Bir yerde daha büyük/küçük harf çevirisi gerekiyorsa `.capitalize()`
/ `.title()` DEĞİL buradaki yardımcılar kullanılmalı.
"""
from __future__ import annotations


def baslik(s: str) -> str:
    """TÜMÜ BÜYÜK yazılmış adı okunur hale getirir; karışık yazımı BOZMAZ.

    "SİYAH" → "Siyah", "BREAKING BAD" → "Breaking Bad", ama zaten düzgün
    yazılmış "Red Dead Redemption" aynen kalır.

    NOT: I → ı (Türkçe kuralı) DEĞİL, I → i uygulanıyor. Sahadaki tümü-büyük
    adlarda I geçen örnekler İngilizce ("BREAKING BAD"); Türkçe kuralı
    uygulayınca "Breakıng Bad" çıkıyordu. Türkçe adlar zaten noktalı İ ile
    yazılmış (ANİME, FİLM / DİZİ) ve o doğru dönüşüyor.
    """
    if not s or s != s.upper():
        return s
    cikti = []
    for kelime in s.split(" "):
        if not kelime:
            continue
        kucuk = kelime.replace("İ", "i").lower()
        ilk = "İ" if kucuk[0] == "i" else kucuk[0].upper()
        cikti.append(ilk + kucuk[1:])
    return " ".join(cikti)


def kelime_basi_buyuk(s: str) -> str:
    """Her kelimenin İLK harfini Türkçe kurala göre büyütür, kalanına dokunmaz.

    "telefon kılıfı" → "Telefon Kılıfı", "iç giyim" → "İç Giyim",
    "ıhlamur çayı" → "Ihlamur Çayı". Kullanıcının küçük harfle girdiği
    etiketleri (ürün türü vb.) başlık gibi göstermek için. Karışık yazım
    ("iPhone kılıfı") ilk harf dışında korunur.
    """
    def buyut(k: str) -> str:
        if not k:
            return k
        ilk = {"i": "İ", "ı": "I"}.get(k[0], k[0].upper())
        return ilk + k[1:]
    return " ".join(buyut(k) for k in (s or "").split(" "))
