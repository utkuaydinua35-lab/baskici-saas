"""
Pipeline yönetimi — /api/pipeline/*

İlk versiyon (Paket 9b): tek atışlık process endpoint.
İleride session yönetimi + WebSocket progress eklenecek.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_any_permission
from app.database import get_db
from app.models import User
from app.services.pipeline_helpers import parse_order_numbers
from app.services.pipeline_service import process_pipeline

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"],
    dependencies=[Depends(require_any_permission("siparisler", "kalip"))],
)


class ProcessRequest(BaseModel):
    store_id: uuid.UUID
    order_numbers_input: str = Field(..., description="örn '11078, 11082-11085, #11090'")
    letters: str = Field(..., min_length=2, max_length=10,
                         description="Kalıp harfleri — 'ABC' (BERNZ) veya 'AB' (Lunera)")


@router.post("/process", response_model=None)
def pipeline_process(
    req: ProcessRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Pipeline çalıştır:
    1. Sipariş numaralarını parse et
    2. DB'den order'ları al + kısayolları + kalıp kodlarını oluştur
    3. Her order için items üret, kalıp koduna göre grupla
    4. Bin-pack
    5. Output metni üret
    """
    order_numbers = parse_order_numbers(req.order_numbers_input)
    if not order_numbers:
        raise HTTPException(status_code=400, detail="Geçerli sipariş numarası bulunamadı")

    try:
        result = process_pipeline(
            db,
            tenant_id=user.tenant_id,
            store_id=req.store_id,
            order_numbers=order_numbers,
            letters=req.letters,
        )
        result["success"] = True
        result["input_order_count"] = len(order_numbers)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline hatası: {str(e)[:300]}") from e
