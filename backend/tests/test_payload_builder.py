import copy

import pytest

from app.ai.errors import PayloadNotReady
from app.ai.payload_builder import PayloadBuilder
from tests.conftest import snapshot


def test_builds_payload_and_catalog():
    p = PayloadBuilder.from_snapshot(snapshot())
    assert p.run_id == "run-test"
    assert p.data_quality_flags == []
    for key in ("metric:total_cost_rp", "route_utilization:route-sorting", "capacity:route-compost",
                "allocation:mat-plastic:route-sorting", "baseline:total_cost_rp", "weight:cost"):
        assert key in p.evidence_catalog
    assert p.units["mass"] == "kg"


def test_missing_sections_are_not_invented():
    s = snapshot()
    del s["weights"], s["period"]
    with pytest.raises(PayloadNotReady) as e:
        PayloadBuilder.from_snapshot(s)
    assert "weights" in e.value.details["missing"] and "period" in e.value.details["missing"]


def test_flags_synthetic_and_unusable_baseline():
    s = snapshot(data_source="synthetic", baseline_metrics={"status": "infeasible", "total_cost_rp": 0,
                                                             "recovered_kg": 0, "residual_kg": 0})
    p = PayloadBuilder.from_snapshot(s)
    assert {"synthetic_data", "baseline_unavailable"} <= set(p.data_quality_flags)
    assert p.baseline_metrics is None
    assert "baseline:total_cost_rp" not in p.evidence_catalog
    assert "data_quality:synthetic_data" in p.evidence_catalog


def test_snapshot_is_not_mutated_and_extra_fields_dropped():
    s = snapshot(internal_notes="secret", is_yield_assumed=True)
    before = copy.deepcopy(s)
    p = PayloadBuilder.from_snapshot(s)
    assert s == before
    assert "internal_notes" not in p.model_dump()
    assert "yield_assumption" in p.data_quality_flags


def test_contract_violation_is_payload_not_ready():
    s = snapshot()
    s["metrics"]["recovery_rate"] = 1.7
    with pytest.raises(PayloadNotReady):
        PayloadBuilder.from_snapshot(s)
