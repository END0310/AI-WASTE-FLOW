"""Builds the compact, allow-listed AI payload from an immutable run snapshot.

Rules (Spec 3.1):
- Only data needed for the analysis; every number comes from the backend.
- NEVER invent missing values: if a required section is absent, the payload is
  "not ready" and Gemini is not called (Spec 6.1 layer 2).
"""
import copy
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from app.ai.errors import PayloadNotReady
from app.ai.input_schema import AIInputPayload, BaselineMetrics

REQUIRED_SECTIONS = ("facility", "period", "solver", "weights", "metrics")

# Snapshot fields the payload builder is allowed to forward (allow-list).
_ALLOWED_FIELDS = {
    "run_id", "batch_id", "facility", "data_source", "period", "solver", "weights",
    "metrics", "routes", "allocations", "baseline_metrics", "active_constraints",
    "validation",
}

# Snapshot boolean hints set by the solver adapter -> data quality flags.
_FLAG_HINTS = {
    "is_yield_assumed": "yield_assumption",
    "has_missing_routes": "missing_route_profile",
    "is_period_mismatched": "period_mismatch",
}


class PayloadBuilder:
    @staticmethod
    def build_evidence_catalog(payload: AIInputPayload) -> List[str]:
        catalog = {"solver:status"}
        catalog.update(f"metric:{k}" for k in type(payload.metrics).model_fields)
        catalog.update(f"weight:{k}" for k in type(payload.weights).model_fields)
        for r in payload.routes:
            catalog.add(f"route_utilization:{r.route_id}")
            catalog.add(f"capacity:{r.route_id}")
            catalog.add(f"route_allocated:{r.route_id}")
        for a in payload.allocations:
            catalog.add(f"allocation:{a.material_id}:{a.route_id}")
        if payload.baseline_metrics:
            catalog.update(
                f"baseline:{k}" for k in ("total_cost_rp", "recovered_kg", "residual_kg")
            )
        for c in payload.active_constraints:
            catalog.add(f"constraint:{c}")
        catalog.update(
            {"validation:mass_balance", "validation:capacity", "validation:compatibility"}
        )
        catalog.update(f"data_quality:{f}" for f in payload.data_quality_flags)
        return sorted(catalog)

    @classmethod
    def from_snapshot(cls, snapshot: Dict[str, Any]) -> AIInputPayload:
        data = copy.deepcopy(snapshot)  # never mutate the stored snapshot

        missing = [s for s in REQUIRED_SECTIONS if not data.get(s)]
        if not data.get("run_id"):
            missing.insert(0, "run_id")
        if data.get("data_source") not in ("synthetic", "field"):
            missing.append("data_source (must be 'synthetic' or 'field')")
        if missing:
            raise PayloadNotReady(
                "Snapshot run belum lengkap untuk dianalisis.",
                details={"missing": missing},
            )

        flags: List[str] = []
        if data["data_source"] == "synthetic":
            flags.append("synthetic_data")
        for hint, flag in _FLAG_HINTS.items():
            if data.get(hint):
                flags.append(flag)

        baseline: Optional[Dict[str, Any]] = data.get("baseline_metrics")
        # Spec 3.1: include baseline only if it was computed successfully on the same input.
        if not baseline or str(baseline.get("status", "")).lower() not in ("optimal", "feasible"):
            data["baseline_metrics"] = None
            flags.append("baseline_unavailable")

        forwarded = {k: v for k, v in data.items() if k in _ALLOWED_FIELDS}
        forwarded["run_id"] = str(forwarded["run_id"])
        forwarded["data_quality_flags"] = flags

        try:
            payload = AIInputPayload.model_validate(forwarded)
        except ValidationError as e:
            raise PayloadNotReady(
                "Snapshot run tidak sesuai kontrak input AI.",
                details=[
                    {"loc": ".".join(map(str, err["loc"])), "msg": err["msg"]}
                    for err in e.errors()
                ],
            ) from e

        payload.evidence_catalog = cls.build_evidence_catalog(payload)
        return payload
