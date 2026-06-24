"""Sipariş dışa aktarma — Excel (xlsx) ve CSV.

Kullanım:
    buf = build_xlsx(db, tenant_id, store_id=..., date_from="2026-01-01", date_to="2026-06-30")
    buf = build_csv(db, tenant_id, ...)
    # buf → bytes, StreamingResponse'a ver
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import Order, Store
from app.stages import stage_label

_TR = ZoneInfo("Europe/Istanbul")

_HEADERS = [
    "Sipariş No", "Mağaza", "Müşteri", "E-posta",
    "Sipariş Tarihi", "Tutar (TL)", "Aşama",
    "Acil", "İptal", "Telafi", "Etiketler", "Ürünler",
]


def _query(db: Session, tenant_id, store_id=None, date_from: str | None = None, date_to: str | None = None):
    q = (
        select(Order)
        .where(Order.tenant_id == tenant_id)
        .options(
            joinedload(Order.store),
            selectinload(Order.line_items),
        )
        .order_by(Order.created_at_platform.desc().nullslast())
    )
    if store_id:
        q = q.where(Order.store_id == store_id)
    if date_from:
        try:
            dt = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=_TR)
            q = q.where(Order.created_at_platform >= dt)
        except ValueError:
            pass
    if date_to:
        try:
            from datetime import timedelta
            dt = datetime.strptime(date_to, "%Y-%m-%d").replace(tzinfo=_TR) + timedelta(days=1)
            q = q.where(Order.created_at_platform < dt)
        except ValueError:
            pass
    return db.scalars(q).unique().all()


def _row(o: Order) -> list:
    tarih = ""
    if o.created_at_platform:
        tarih = o.created_at_platform.astimezone(_TR).strftime("%d.%m.%Y %H:%M")

    tutar = ""
    try:
        tutar = float(o.raw.get("total_price", "") or "")
    except (ValueError, TypeError):
        pass

    urunler = "; ".join(
        f"{li.title} ({li.quantity})" for li in o.line_items
    )

    return [
        o.order_number or "",
        o.store.name if o.store else "",
        o.customer_name or "",
        o.customer_email or "",
        tarih,
        tutar,
        stage_label(o.current_stage),
        "Evet" if o.is_acil else "",
        "Evet" if o.cancelled_at else "",
        "Evet" if o.is_telafi else "",
        o.tags or "",
        urunler,
    ]


def build_xlsx(
    db: Session,
    tenant_id,
    store_id=None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter

    orders = _query(db, tenant_id, store_id=store_id, date_from=date_from, date_to=date_to)

    wb = Workbook()
    ws = wb.active
    ws.title = "Siparişler"

    # Başlık satırı
    header_fill = PatternFill("solid", fgColor="1E293B")
    header_font = Font(bold=True, color="E2E8F0", size=10)
    for col_idx, h in enumerate(_HEADERS, 1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # Veri satırları
    for r_idx, o in enumerate(orders, 2):
        for c_idx, val in enumerate(_row(o), 1):
            cell = ws.cell(row=r_idx, column=c_idx, value=val)
            cell.alignment = Alignment(vertical="top", wrap_text=(c_idx == len(_HEADERS)))

    # Kolon genişlikleri
    col_widths = [14, 18, 20, 24, 16, 12, 16, 6, 6, 7, 20, 50]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(_HEADERS))}1"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_csv(
    db: Session,
    tenant_id,
    store_id=None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> bytes:
    orders = _query(db, tenant_id, store_id=store_id, date_from=date_from, date_to=date_to)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_HEADERS)
    for o in orders:
        writer.writerow(_row(o))

    # utf-8-sig: Excel'in BOM olmadan Türkçe karakterleri doğru açması için
    return ("﻿" + buf.getvalue()).encode("utf-8")
