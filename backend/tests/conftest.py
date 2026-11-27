import copy
import json
from typing import Any, Callable, Dict, List, Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.gemini_client import ProviderResult
from app.api.v1.ai import get_ai_client_factory
from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app

BASE_SNAPSHOT: Dict[str, Any] = {
    "facility": {"facility_id": "fac-1", "facility_name": "TPS3R Sukamaju"},
    "data_source": "field",
    "period": {"start": "2026-11-01", "end": "2026-11-07", "capacity_period": "day"},
    "solver": {"status": "Optimal", "name": "PuLP", "version": "2.8"},
    "weights": {"cost": 0.333, "recovery": 0.333, "residual": 0.334},
    "metrics": {"total_input_kg": 1200, "total_cost_rp": 850000, "recovered_kg": 720,
                "recovery_rate": 0.60, "residual_kg": 180, "residual_rate": 0.15},
    "routes": [
        {"route_id": "route-sorting", "route_name": "Sorting Line", "allocated_kg": 500,
         "capacity_kg": 700, "utilization_rate": 0.714},
        {"route_id": "route-compost", "route_name": "Composting Bed", "allocated_kg": 450,
         "capacity_kg": 600, "utilization_rate": 0.75},
    ],
    "allocations": [
        {"material_id": "mat-plastic", "material_name": "Plastic", "route_id": "route-sorting", "allocated_kg": 300},
        {"material_id": "mat-organic", "material_name": "Organic", "route_id": "route-compost", "allocated_kg": 450},
    ],
    "baseline_metrics": {"status": "feasible", "total_cost_rp": 920000, "recovered_kg": 680, "residual_kg": 210},
    "validation": {"mass_balance_error_kg": 0, "capacity_violations": 0, "compatibility_violations": 0},
}


def snapshot(**overrides) -> Dict[str, Any]:
    s = copy.deepcopy(BASE_SNAPSHOT)
    s["run_id"] = "run-test"
    s.update(overrides)
    return s


def valid_output(solver_status: str = "optimal") -> Dict[str, Any]:
    """Realistic output in id-ID number style (modelled on a real Gemini response)."""
    return {
        "summary": "Optimasi TPS3R Sukamaju selesai dengan biaya Rp850.000 dan recovery rate 60%.",
        "operational_insights": [{
            "title": "Utilisasi Composting Bed",
            "finding": "Composting Bed berutilisasi 75,0% (450,0 kg dari 600,0 kg) tanpa pelanggaran kapasitas.",
            "evidence": ["route_utilization:route-compost", "capacity:route-compost", "validation:capacity"],
            "severity": "low",
        }],
        "optimization_interpretation": {
            "solver_status": solver_status,
            "tradeoffs": [{
                "statement": "Bobot seimbang (0,333/0,333/0,334) menghasilkan biaya Rp850.000 dan residu 180 kg.",
                "evidence": ["weight:cost", "weight:recovery", "weight:residual", "metric:total_cost_rp"],
            }],
        },
        "recommendations": [{
            "action": "Manfaatkan sisa kapasitas Sorting Line.",
            "rationale": "Sorting Line berutilisasi 71,4% sehingga masih ada ruang operasional.",
            "evidence": ["route_utilization:route-sorting"],
            "priority": "low",
        }],
        "limitations": ["Data mencakup satu periode mingguan 2026-11-01 sampai 2026-11-07."],
    }


class FakeClient:
    """Scripted provider: each call pops the next item (dict -> output, Exception -> raise)."""
    provider = "gemini"
    model = "fake-model"

    def __init__(self, script: List[Any]):
        self.script = list(script)
        self.calls: List[List[str]] = []

    def generate(self, system_instruction, contents, payload_catalog) -> ProviderResult:
        self.calls.append(contents)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return ProviderResult(raw=item, raw_text=json.dumps(item), latency_ms=5,
                              attempts=1, provider=self.provider, model=self.model)


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False)
    yield Session
    engine.dispose()


@pytest.fixture()
def client(db_session, monkeypatch):
    monkeypatch.setattr(settings, "AI_ANALYSIS_COOLDOWN_SECONDS", 0)

    def _db():
        s = db_session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def use_fake(client):
    def _install(script: List[Any]) -> FakeClient:
        fake = FakeClient(script)
        app.dependency_overrides[get_ai_client_factory] = lambda: (lambda: fake)
        return fake
    return _install


@pytest.fixture()
def seed_run(client):
    def _seed(snap: Optional[Dict[str, Any]] = None, status: Optional[str] = None) -> str:
        snap = snap or snapshot()
        snap.pop("run_id", None)
        res = client.post("/api/v1/optimization/runs", json={
            "status": status or snap["solver"]["status"],
            "data_source": snap["data_source"],
            "snapshot_data": snap,
        })
        assert res.status_code == 200, res.text
        return res.json()["run_id"]
    return _seed
