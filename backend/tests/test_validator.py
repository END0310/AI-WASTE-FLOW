import pytest

from app.ai import validator as V
from app.ai.output_schema import AIAnalysisOutput
from app.ai.payload_builder import PayloadBuilder
from tests.conftest import snapshot, valid_output


def payload(**kw):
    return PayloadBuilder.from_snapshot(snapshot(**kw))


# ---- Layer 1
@pytest.mark.parametrize("status,ok", [
    ("Optimal", True), ("optimal", True), ("feasible", True),
    ("Infeasible", False), ("Unbounded", False), ("Not Solved", False),
    ("Undefined", False), ("error", False), ("weird", False), (None, False),
])
def test_eligibility(status, ok):
    assert V.check_eligibility(status)[0] is ok


# ---- Layer 2
def test_weights_must_sum_to_one():
    p = payload(weights={"cost": 0.5, "recovery": 0.5, "residual": 0.5})
    assert any("bobot" in e for e in V.validate_payload(p))


def test_period_mismatch_blocks():
    p = payload(is_period_mismatched=True)
    assert any("period_mismatch" in e for e in V.validate_payload(p))


def test_orphan_allocation_route():
    s = snapshot()
    s["allocations"].append({"material_id": "m9", "material_name": "X", "route_id": "ghost", "allocated_kg": 1})
    assert any("ghost" in e for e in V.validate_payload(PayloadBuilder.from_snapshot(s)))


# ---- Layers 3-6 on a realistic valid output
def test_realistic_output_passes_all_layers():
    rep = V.validate_output(valid_output(), payload())
    assert rep.is_valid, rep.summary()


def test_schema_rejects_bad_enum_and_non_json():
    bad = valid_output()
    bad["operational_insights"][0]["severity"] = "critical"
    assert V.validate_output(bad, payload()).failed_layer == "SchemaValidation"
    assert V.validate_output(None, payload()).failed_layer == "SchemaValidation"


def test_evidence_must_exist_in_catalog():
    bad = valid_output()
    bad["recommendations"][0]["evidence"] = ["route_utilization:route-imaginary"]
    rep = V.validate_output(bad, payload())
    assert rep.failed_layer == "EvidenceValidation"


# ---- Layer 5 numeric consistency (id-ID and en-US formats)
@pytest.mark.parametrize("text,ok", [
    ("Biaya Rp850.000 untuk 1.200,0 kg input.", True),
    ("Total cost Rp 850,000 for 1,200 kg.", True),
    ("Recovery rate 0,6 atau 60% dan utilisasi 71%.", True),   # 71.4% rounded
    ("Utilisasi 83%.", False),                                  # not in payload
    ("Ada selisih 200,0 kg pada Sorting Line.", False),      # derived number (500-300)
    ("Biaya turun 7,6% dibanding baseline.", False),          # derived percentage
    ("Hemat Rp70.000 dari baseline.", False),                 # derived saving
])
def test_numeric_consistency(text, ok):
    out = valid_output()
    out["summary"] = text
    issues = V.validate_numbers(AIAnalysisOutput.model_validate(out), payload())
    assert (not issues) is ok, issues


def test_ids_and_dates_are_not_numbers():
    out = valid_output()
    out["summary"] = "Periode 2026-11-01 hingga 2026-11-07 pada route-1 dan TPS3R."
    assert V.validate_numbers(AIAnalysisOutput.model_validate(out), payload()) == []


# ---- Layer 6 policy
def _policy(summary=None, solver_status="optimal", recs=None, **kw):
    out = valid_output(solver_status=solver_status)
    if summary:
        out["summary"] = summary
    if recs is not None:
        out["recommendations"] = recs
    return V.validate_policy(AIAnalysisOutput.model_validate(out), payload(**kw))


def test_city_wide_claim():
    assert _policy("WasteFlow mengurangi sampah di kota secara signifikan.")


def test_guarantee_without_baseline():
    assert _policy("Biaya pasti turun pada periode berikutnya.", baseline_metrics=None)
    assert not _policy("Biaya operasional berada pada level yang dilaporkan backend.", baseline_metrics=None)


def test_optimal_claim_when_feasible():
    feasible = {**snapshot()["solver"], "status": "feasible"}
    assert _policy("Rute ini optimal.", solver_status="feasible", solver=feasible)
    assert not _policy("Solusi feasible, bukan optimal.", solver_status="feasible", solver=feasible)


def test_solver_status_must_be_echoed():
    assert _policy(solver_status="feasible")


def test_capacity_increase_requires_bottleneck_evidence():
    rec = [{"action": "Tambah kapasitas Sorting Line.", "rationale": "Agar lebih lancar.",
            "evidence": ["route_utilization:route-sorting"], "priority": "high"}]
    assert any("kapasitas" in v for v in _policy(recs=rec))   # utilization 71% < 85%


def test_capacity_increase_ok_with_bottleneck_and_cost():
    s = snapshot()
    s["routes"][0]["utilization_rate"] = 0.95
    rec = [{"action": "Evaluasi penambahan kapasitas Sorting Line.",
            "rationale": "Utilisasi tinggi; pertimbangkan biaya tambahan shift.",
            "evidence": ["route_utilization:route-sorting"], "priority": "medium"}]
    out = valid_output()
    out["recommendations"] = rec
    assert V.validate_policy(AIAnalysisOutput.model_validate(out), PayloadBuilder.from_snapshot(s)) == []


def test_residual_as_unallocated():
    assert _policy("Residu 180 kg belum dialokasikan ke rute mana pun.")


def test_no_baseline_comparison_when_unavailable():
    assert _policy("Biaya lebih rendah dibanding baseline.", baseline_metrics=None)


# ---- limitation enforcement
def test_backend_adds_missing_mandatory_limitations():
    p = payload(data_source="synthetic", is_yield_assumed=True)
    out = AIAnalysisOutput.model_validate(valid_output())
    added = V.enforce_limitations(out, p)
    assert len(added) == 2
    assert any("sintetis" in l for l in out.limitations)
