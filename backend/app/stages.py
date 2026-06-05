"""
Sipariş aşama (stage) tanımları — Paket 12.

9 kanonik aşama + iptal (ayrı flag ile).
BERNZ Shopify order tracker'daki stage isimleriyle uyumlu.
"""
from __future__ import annotations

# (stage_no, key, label, icon_hint)
STAGES: list[tuple[int, str, str, str]] = [
    (1, "yeni", "Yeni", "inbox"),
    (2, "isleniyor", "İşleniyor", "loader"),
    (3, "barkod_olustu", "Barkod Oluştu", "barcode"),
    (4, "kaliba_alindi", "Kalıba Alındı", "layers"),
    (5, "baskida", "Baskıda", "printer"),
    (6, "baski_tamam", "Baskı Tamam", "printer-check"),
    (7, "paketlendi", "Paketlendi", "package"),
    (8, "kargoda", "Kargoda", "truck"),
    (9, "teslim", "Teslim", "check-circle"),
]

STAGE_COUNT = len(STAGES)

# Hızlı erişim haritaları
STAGE_BY_NO: dict[int, dict] = {
    no: {"no": no, "key": key, "label": label, "icon": icon}
    for (no, key, label, icon) in STAGES
}
STAGE_BY_KEY: dict[str, dict] = {
    key: {"no": no, "key": key, "label": label, "icon": icon}
    for (no, key, label, icon) in STAGES
}


def stage_info(stage_no: int) -> dict:
    """Stage numarasından bilgi döndür. Geçersizse 1'e fallback."""
    return STAGE_BY_NO.get(stage_no, STAGE_BY_NO[1])


def stage_label(stage_no: int) -> str:
    return stage_info(stage_no)["label"]


def all_stages_payload() -> list[dict]:
    """Frontend için tüm aşamaların listesi."""
    return [
        {"no": no, "key": key, "label": label, "icon": icon}
        for (no, key, label, icon) in STAGES
    ]


def is_valid_stage(stage_no: int) -> bool:
    return stage_no in STAGE_BY_NO


def progress_percent(stage_no: int) -> int:
    """0-9 aşama için ilerleme yüzdesi. Stage 1 = ~6%, stage 9 = 100%."""
    if stage_no <= 0:
        return 0
    if stage_no >= STAGE_COUNT:
        return 100
    # Görsel 4'teki gibi: stage 1 = %6 civarı (tamamlanan / toplam yerine biraz offset)
    return round((stage_no - 1) / (STAGE_COUNT - 1) * 100)
