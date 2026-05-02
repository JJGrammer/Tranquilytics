from __future__ import annotations

"""
Report generation endpoints.

Primary goal:
- Return an explainable, non-imperative tone-based analysis (
  Safer Buy / Buy / Neutral / Sell / Sell Soon) for short and long horizons, with
  reasoning, risk, and citations.

Notes:
- v1 intentionally prefers a score-first pipeline (probability/confidence + expected move)
  and then maps to advice via a policy layer.
"""

from fastapi import APIRouter, HTTPException

from app.schemas.report import ReportRequest, ReportResponse
from app.services.report_service import ReportService

router = APIRouter()


@router.post("", response_model=ReportResponse)
def generate_report(req: ReportRequest) -> ReportResponse:
    symbol = (req.symbol or "").strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol is required")

    service = ReportService()
    return service.generate(symbol=symbol, include_citations=req.include_citations)

