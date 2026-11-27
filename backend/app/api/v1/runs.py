"""DEV-ONLY endpoints for seeding runs in standalone mode.

In the integrated system runs are produced by the PuLP solver, not by this API.
Enabled only when ENABLE_DEV_ENDPOINTS=true.
"""
import uuid
from typing import Any, Dict, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.optimization_run import OptimizationRun

router = APIRouter(prefix="/optimization", tags=["Dev: Optimization Runs"])


class CreateRunRequest(BaseModel):
    status: str
    data_source: Literal["synthetic", "field"]
    snapshot_data: Dict[str, Any]


@router.post("/runs")
def create_run(req: CreateRunRequest, db: Session = Depends(get_db)):
    run = OptimizationRun(id=str(uuid.uuid4()), status=req.status,
                          data_source=req.data_source, snapshot_data=req.snapshot_data)
    db.add(run)
    db.commit()
    return {"run_id": run.id, "status": run.status, "data_source": run.data_source}


@router.get("/runs/{run_id}")
def get_run(run_id: str, db: Session = Depends(get_db)):
    run = db.get(OptimizationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Optimization run not found")
    return {"run_id": run.id, "status": run.status, "data_source": run.data_source,
            "snapshot_data": run.snapshot_data, "created_at": run.created_at.isoformat()}
