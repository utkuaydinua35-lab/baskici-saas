"""Bayi cari ekstre + kârlılık özeti PDF'i (reportlab).

Türkçe karakterler için reportlab'ın paketlediği Vera (Bitstream Vera Sans)
fontu kullanılır — ş/ğ/ı/İ dahil tüm Türkçe harfleri içerir. ₺ sembolü Vera'da
yok, bu yüzden para birimi "TL"/"USD" metni olarak yazılır.
"""
from __future__ import annotations

import io
import os
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Dealer, DealerTransaction, Tenant

_TR = ZoneInfo("Europe/Istanbul")
_ACCENT = colors.HexColor("#6d28d9")
_ACCENT_LIGHT = colors.HexColor("#f3eefe")
_GREY = colors.HexColor("#6b7280")
_BORDER = colors.HexColor("#e5e7eb")

_FONTS_REGISTERED = False


def _ensure_fonts() -> tuple[str, str]:
    """Vera fontlarını (regular + bold) kaydet, isimlerini döndür."""
    global _FONTS_REGISTERED
    if not _FONTS_REGISTERED:
        fdir = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
        pdfmetrics.registerFont(TTFont("TRSans", os.path.join(fdir, "Vera.ttf")))
        pdfmetrics.registerFont(TTFont("TRSans-Bold", os.path.join(fdir, "VeraBd.ttf")))
        _FONTS_REGISTERED = True
    return "TRSans", "TRSans-Bold"


def _fmt_money(x: float) -> str:
    """1234.5 -> '1.234,50' (Türkçe biçim)."""
    try:
        s = f"{abs(float(x)):,.2f}"
    except (TypeError, ValueError):
        return "0,00"
    # 1,234.50 -> 1.234,50
    s = s.replace(",", "§").replace(".", ",").replace("§", ".")
    return ("-" + s) if float(x) < 0 else s


def _kind_label(kind: str) -> str:
    return {"siparis": "Sipariş", "odeme": "Ödeme", "duzeltme": "Düzeltme"}.get(kind, kind or "—")


def _cur_label(c: str) -> str:
    c = (c or "TRY").upper()
    return "TL" if c == "TRY" else c


def _parse_day(s: str | None, end: bool = False) -> datetime | None:
    if not s:
        return None
    try:
        d = datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        return None
    t = time.max if end else time.min
    return datetime.combine(d.date(), t, tzinfo=_TR)


def _accent_colors(tenant) -> tuple[colors.Color, colors.Color]:
    """Tenant marka renginden (accent, açık_ton). Yoksa varsayılan mor."""
    hexc = (getattr(tenant, "brand_color", None) or "").strip() if tenant else ""
    if hexc and not hexc.startswith("#"):
        hexc = "#" + hexc
    try:
        accent = colors.HexColor(hexc) if hexc else _ACCENT
    except Exception:  # noqa: BLE001 — geçersiz hex
        accent = _ACCENT
    light = colors.Color(
        accent.red * 0.10 + 0.90,
        accent.green * 0.10 + 0.90,
        accent.blue * 0.10 + 0.90,
    )
    return accent, light


def _logo_flowable(tenant, max_h: float = 15 * mm, max_w: float = 50 * mm):
    """Tenant logosunu (varsa) reportlab Image olarak döndür — oranı korur. Yoksa None."""
    logo_url = getattr(tenant, "logo_url", None) if tenant else None
    if not logo_url or not str(logo_url).startswith("/storage/"):
        return None
    try:
        from reportlab.lib.utils import ImageReader
        from app.services.storage import STORAGE_ROOT
        path = STORAGE_ROOT / str(logo_url)[len("/storage/"):]
        if not path.exists():
            return None
        iw, ih = ImageReader(str(path)).getSize()
        if not iw or not ih:
            return None
        dh, dw = max_h, iw * (max_h / ih)
        if dw > max_w:
            dw, dh = max_w, ih * (max_w / iw)
        img = Image(str(path), width=dw, height=dh)
        img.hAlign = "RIGHT"
        return img
    except Exception:  # noqa: BLE001 — bozuk/eksik logo dosyası
        return None


def build_statement_pdf(
    db: Session,
    dealer: Dealer,
    date_from: str | None = None,
    date_to: str | None = None,
) -> bytes:
    reg, bold = _ensure_fonts()
    tenant = db.get(Tenant, dealer.tenant_id)
    atolye = (getattr(tenant, "app_name", None) or (tenant.name if tenant else None)) or "Atölye"
    accent, accent_light = _accent_colors(tenant)
    primary = (getattr(dealer, "currency", "TRY") or "TRY").upper()

    dt_from = _parse_day(date_from, end=False)
    dt_to = _parse_day(date_to, end=True)

    # Tüm hareketler (tarih artan) — ekstre kronolojik
    all_tx = db.scalars(
        select(DealerTransaction)
        .where(DealerTransaction.dealer_id == dealer.id)
        .order_by(DealerTransaction.created_at.asc())
    ).all()

    # ─── Stiller ───
    styles = {
        "title": ParagraphStyle("title", fontName=bold, fontSize=18, textColor=accent, leading=22),
        "sub": ParagraphStyle("sub", fontName=reg, fontSize=9, textColor=_GREY, leading=12),
        "h2": ParagraphStyle("h2", fontName=bold, fontSize=12, textColor=accent, leading=15),
        "body": ParagraphStyle("body", fontName=reg, fontSize=9, textColor=colors.HexColor("#111827"), leading=12),
        "small": ParagraphStyle("small", fontName=reg, fontSize=8, textColor=_GREY, leading=10),
    }

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=16 * mm, rightMargin=16 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
        title=f"Cari Ekstre - {dealer.name}",
    )
    story = []

    # ─── Başlık (logo + marka) ───
    bugun = datetime.now(_TR).strftime("%d.%m.%Y %H:%M")
    title_block = [Paragraph("CARİ EKSTRE", styles["title"]), Paragraph(atolye, styles["sub"])]
    logo = _logo_flowable(tenant)
    if logo is not None:
        head = Table([[title_block, logo]], colWidths=[120 * mm, 58 * mm])
        head.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(head)
    else:
        story.append(title_block[0])
        story.append(title_block[1])
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=2, color=accent, spaceBefore=0, spaceAfter=8))

    # ─── Bayi + dönem bilgisi (iki sütun) ───
    donem_txt = "Tüm zamanlar"
    if dt_from or dt_to:
        f = dt_from.strftime("%d.%m.%Y") if dt_from else "başlangıç"
        t_ = dt_to.strftime("%d.%m.%Y") if dt_to else "bugün"
        donem_txt = f"{f} — {t_}"

    info_left = [
        Paragraph("<b>Bayi</b>", styles["small"]),
        Paragraph(dealer.name or "—", styles["body"]),
    ]
    if dealer.phone:
        info_left.append(Paragraph(dealer.phone, styles["small"]))
    if dealer.email:
        info_left.append(Paragraph(dealer.email, styles["small"]))
    if dealer.address:
        info_left.append(Paragraph(dealer.address, styles["small"]))

    info_right = [
        Paragraph("<b>Dönem</b>", styles["small"]),
        Paragraph(donem_txt, styles["body"]),
        Spacer(1, 4),
        Paragraph("<b>Düzenlenme</b>", styles["small"]),
        Paragraph(bugun, styles["body"]),
    ]
    info_tbl = Table([[info_left, info_right]], colWidths=[95 * mm, 83 * mm])
    info_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(info_tbl)
    story.append(Spacer(1, 14))

    # ─── Para birimine göre grupla (her birinin ayrı bakiyesi var) ───
    by_cur: dict[str, list] = {}
    for t in all_tx:
        by_cur.setdefault((t.currency or "TRY").upper(), []).append(t)

    # Bayinin ana para birimi önce, sonra diğerleri
    order = [c for c in [primary] if c in by_cur] + [c for c in sorted(by_cur) if c != primary]
    if not order:
        order = [primary]
        by_cur.setdefault(primary, [])

    def _build_currency_section(currency: str, txs: list) -> list:
        cur_label = _cur_label(currency)
        # Devir + dönem ayrımı (bu para biriminin hareketleri içinde)
        opening = 0.0
        in_period = []
        for t in txs:
            created = t.created_at
            if dt_from and created and created < dt_from:
                opening = float(t.balance_after)
                continue
            if dt_to and created and created > dt_to:
                continue
            in_period.append(t)

        donem_borc = sum(float(t.amount) for t in in_period if float(t.amount) > 0)
        donem_alacak = sum(-float(t.amount) for t in in_period if float(t.amount) < 0)
        siparis_adedi = sum(1 for t in in_period if t.kind == "siparis")
        closing = float(in_period[-1].balance_after) if in_period else opening

        out = []
        out.append(Paragraph(f"{cur_label} Hesabı", styles["h2"]))
        out.append(Spacer(1, 6))

        def _summary_cell(label, value, accent=False):
            col = "#6d28d9" if accent else "#111827"
            return [
                Paragraph(label, styles["small"]),
                Paragraph(f'<font name="{bold}" size="13" color="{col}">{value} {cur_label}</font>', styles["body"]),
            ]

        summary = Table(
            [[
                _summary_cell("Dönem Cirosu (Sipariş)", _fmt_money(donem_borc)),
                _summary_cell("Dönem Tahsilatı (Ödeme)", _fmt_money(donem_alacak)),
                _summary_cell("Güncel Bakiye (Borç)", _fmt_money(closing), accent=True),
            ]],
            colWidths=[59 * mm, 59 * mm, 60 * mm],
        )
        summary.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), accent_light),
            ("BOX", (0, 0), (-1, -1), 0.5, _BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.white),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ]))
        out.append(summary)
        out.append(Spacer(1, 6))
        out.append(Paragraph(
            f"Sipariş adedi: {siparis_adedi}  ·  Açılış bakiyesi (devir): {_fmt_money(opening)} {cur_label}  "
            f"·  Bakiye pozitif = bayinin borcu", styles["small"]))
        out.append(Spacer(1, 10))

        # Hareket tablosu (tutarlar bu para biriminde)
        header = ["Tarih", "İşlem", "Açıklama", f"Borç ({cur_label})", f"Alacak ({cur_label})", f"Bakiye ({cur_label})"]
        rows = [header]
        if dt_from:
            rows.append(["", "Devir", "Önceki dönem bakiyesi", "", "", _fmt_money(opening)])
        for t in in_period:
            amt = float(t.amount)
            tarih = t.created_at.astimezone(_TR).strftime("%d.%m.%Y") if t.created_at else "—"
            rows.append([
                tarih,
                _kind_label(t.kind),
                Paragraph((t.description or "—"), styles["small"]),
                _fmt_money(amt) if amt > 0 else "",
                _fmt_money(-amt) if amt < 0 else "",
                _fmt_money(float(t.balance_after)),
            ])
        if not in_period:
            rows.append(["", "—", "Bu dönemde hareket yok", "", "", ""])

        tbl = Table(rows, colWidths=[20 * mm, 18 * mm, 64 * mm, 25 * mm, 25 * mm, 26 * mm], repeatRows=1)
        tbl.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), reg),
            ("FONTNAME", (0, 0), (-1, 0), bold),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BACKGROUND", (0, 0), (-1, 0), accent),
            ("ALIGN", (3, 0), (5, -1), "RIGHT"),
            ("ALIGN", (0, 0), (1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#faf9fc")]),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, _BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        out.append(tbl)
        return out, bool(in_period or opening)

    rendered = 0
    for ci, currency in enumerate(order):
        section, has_data = _build_currency_section(currency, by_cur.get(currency, []))
        # Boş para birimi bölümlerini atla (devir de yoksa)
        if not has_data and currency != primary and len(order) > 1:
            continue
        if rendered > 0:
            story.append(Spacer(1, 18))
        story.extend(section)
        rendered += 1

    story.append(Spacer(1, 16))
    story.append(Paragraph(
        f"Bu ekstre {atolye} tarafından {bugun} tarihinde otomatik düzenlenmiştir. "
        "Her para birimi kendi bakiyesiyle ayrı gösterilir; farklı para birimleri "
        "birbirine çevrilmez. Tutarlar bilgi amaçlıdır.", styles["small"]))

    doc.build(story)
    return buf.getvalue()
