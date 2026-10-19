"""GET /api/stats — воронка и метрики ботов (расчёт в services/metrics.py)."""
from fastapi import APIRouter, Depends, Query

from ..deps import verify_site_token
from ..services.metrics import collect_stats

router = APIRouter(dependencies=[Depends(verify_site_token)])


@router.get("/api/stats")
def stats(days: int = Query(7, ge=1, le=90)) -> dict:
    return collect_stats(days)