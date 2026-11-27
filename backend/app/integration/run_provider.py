"""Integration seam between the AI layer and the main WasteFlow system.

The AI layer never reads the main database directly (Spec 1.3). Instead it asks
a RunSnapshotProvider for an immutable run snapshot shaped like the canonical
input (Spec 3.2). To plug the AI layer into the real system you implement ONE
class and register it with FastAPI dependency overrides:

    from app.integration.run_provider import get_run_provider, get_current_user
    app.dependency_overrides[get_run_provider] = lambda: MyWasteFlowRunProvider(db)
    app.dependency_overrides[get_current_user] = my_auth_dependency

See docs/INTEGRATION.md for a full example.
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.optimization_run import OptimizationRun


@dataclass(frozen=True)
class RunSnapshot:
    run_id: str
    solver_status: str          # exactly what the solver adapter emitted (e.g. pulp.LpStatus)
    snapshot: Dict[str, Any]    # canonical-input-shaped dict (Spec 3.2), backend-computed KPIs
    owner_id: Optional[str] = None


class RunSnapshotProvider(Protocol):
    def get_snapshot(self, run_id: str) -> Optional[RunSnapshot]: ...

    def can_access(self, run: RunSnapshot, user_id: Optional[str]) -> bool: ...


class LocalRunProvider:
    """Default provider for standalone mode: reads this service's optimization_runs table."""

    def __init__(self, db: Session):
        self.db = db

    def get_snapshot(self, run_id: str) -> Optional[RunSnapshot]:
        run = self.db.get(OptimizationRun, run_id)
        if run is None:
            return None
        snap = dict(run.snapshot_data or {})
        snap["run_id"] = run.id
        snap.setdefault("data_source", run.data_source)
        status = (snap.get("solver") or {}).get("status") or run.status
        return RunSnapshot(run_id=run.id, solver_status=status, snapshot=snap)

    def can_access(self, run: RunSnapshot, user_id: Optional[str]) -> bool:
        return True  # standalone mode has no users


def get_run_provider(db: Session = Depends(get_db)) -> RunSnapshotProvider:
    return LocalRunProvider(db)


def get_current_user() -> Optional[str]:
    """Override with the main system's auth dependency (Spec 8.1: authorize run access)."""
    return None
