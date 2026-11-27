"""AI endpoints (Spec 7.1)."""
from datetime import datetime
from typing import Callable, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai.errors import AIError
from app.ai.gemini_client import AIClient, get_ai_client
from app.core.database import get_db
from app.integration.run_provider import RunSnapshotProvider, get_current_user, get_run_provider
from app.models.ai_analysis import AIAnalysis
from app.services.ai_service import AIService

router = APIRouter(tags=["AI Intelligence"])


def get_ai_client_factory() -> Callable[[], AIClient]:
    """Overridable in tests."""
    return get_ai_client


class AnalysisRequest(BaseModel):
    analysis_type: Literal["full"] = "full"


def _error_response(e: AIError) -> JSONResponse:
    headers = {"Retry-After": "30"} if e.http_status in (429, 503) else None
    return JSONResponse(status_code=e.http_status, content={"error": e.to_dict()}, headers=headers)


@router.post("/optimization/runs/{run_id}/analysis")
def trigger_ai_analysis(
    run_id: str,
    req: AnalysisRequest = AnalysisRequest(),
    db: Session = Depends(get_db),
    runs: RunSnapshotProvider = Depends(get_run_provider),
    user_id: Optional[str] = Depends(get_current_user),
    client_factory: Callable[[], AIClient] = Depends(get_ai_client_factory),
):
    """Manual trigger (Spec 1.4). Errors return {"error": {code, layer, message, details,
    analysis_id, retryable}} so the UI can show AI-unavailable/Retry states."""
    if len(run_id) > 64:
        raise HTTPException(status_code=422, detail="run_id tidak valid")
    try:
        return AIService(db, runs, client_factory).run_analysis(run_id, user_id)
    except AIError as e:
        return _error_response(e)


@router.get("/ai/history")
def get_ai_history(
    run_id: Optional[str] = Query(None),
    validation_status: Optional[Literal["valid", "invalid", "failed"]] = Query(None),
    date_from: Optional[datetime] = Query(None, description="ISO-8601, inclusive"),
    date_to: Optional[datetime] = Query(None, description="ISO-8601, exclusive"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user_id: Optional[str] = Depends(get_current_user),
):
    q = db.query(AIAnalysis)
    if user_id is not None:
        q = q.filter(AIAnalysis.requested_by == user_id)
    if run_id:
        q = q.filter(AIAnalysis.run_id == run_id)
    if validation_status:
        q = q.filter(AIAnalysis.validation_status == validation_status)
    if date_from:
        q = q.filter(AIAnalysis.created_at >= date_from)
    if date_to:
        q = q.filter(AIAnalysis.created_at < date_to)
    total = q.count()
    rows = q.order_by(AIAnalysis.created_at.desc()).offset(offset).limit(limit).all()
    items = []
    for r in rows:
        body = AIService.to_response(r)
        body.pop("result")  # list view stays light
        items.append(body)
    return {"total": total, "items": items}


@router.get("/ai/analyses/{analysis_id}")
def get_ai_analysis_detail(
    analysis_id: str,
    include_input: bool = Query(False, description="Sertakan payload yang dikirim ke Gemini (audit)"),
    db: Session = Depends(get_db),
    user_id: Optional[str] = Depends(get_current_user),
):
    rec = db.get(AIAnalysis, analysis_id)
    if rec is None or (user_id is not None and rec.requested_by != user_id):
        raise HTTPException(status_code=404, detail="AI analysis tidak ditemukan")
    return AIService.to_response(rec, include_input=include_input)
