"""Validated AI input contract (Spec 3.2 Canonical Input Schema)."""
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FacilityInfo(_Strict):
    facility_id: str
    facility_name: str


class PeriodInfo(_Strict):
    start: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    end: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    capacity_period: str = "day"


class SolverInfo(_Strict):
    status: str
    name: str = "PuLP"
    version: Optional[str] = None


class ObjectiveWeights(_Strict):
    cost: float = Field(..., ge=0.0, le=1.0)
    recovery: float = Field(..., ge=0.0, le=1.0)
    residual: float = Field(..., ge=0.0, le=1.0)


class MetricsInfo(_Strict):
    total_input_kg: float = Field(..., ge=0)
    total_cost_rp: float = Field(..., ge=0)
    recovered_kg: float = Field(..., ge=0)
    recovery_rate: float = Field(..., ge=0.0, le=1.0)
    residual_kg: float = Field(..., ge=0)
    residual_rate: float = Field(..., ge=0.0, le=1.0)


class RouteInfo(_Strict):
    route_id: str
    route_name: str
    allocated_kg: float = Field(..., ge=0)
    capacity_kg: float = Field(..., ge=0)
    utilization_rate: float = Field(..., ge=0.0)


class AllocationInfo(_Strict):
    material_id: str
    material_name: str
    route_id: str
    allocated_kg: float = Field(..., ge=0)


class BaselineMetrics(_Strict):
    status: str
    total_cost_rp: float
    recovered_kg: float
    residual_kg: float


class ValidationSummary(_Strict):
    mass_balance_error_kg: float = 0.0
    capacity_violations: int = 0
    compatibility_violations: int = 0


DataQualityFlag = Literal[
    "missing_route_profile",
    "synthetic_data",
    "baseline_unavailable",
    "yield_assumption",
    "period_mismatch",
]

# Spec 3.1: "Sertakan unit, denominator, periode kapasitas, sumber data, dan bobot."
DEFAULT_UNITS: Dict[str, str] = {
    "mass": "kg",
    "currency": "IDR (Rp)",
    "rates": "fraction 0-1 (recovery_rate = recovered_kg / total_input_kg; residual_rate = residual_kg / total_input_kg)",
    "utilization_rate": "fraction 0-1 (allocated_kg / capacity_kg per capacity_period)",
}


class AIInputPayload(_Strict):
    run_id: str
    batch_id: Optional[str] = None
    facility: FacilityInfo
    data_source: Literal["synthetic", "field"]
    period: PeriodInfo
    solver: SolverInfo
    weights: ObjectiveWeights
    units: Dict[str, str] = Field(default_factory=lambda: dict(DEFAULT_UNITS))
    metrics: MetricsInfo
    routes: List[RouteInfo] = Field(default_factory=list, max_length=50)
    allocations: List[AllocationInfo] = Field(default_factory=list, max_length=300)
    baseline_metrics: Optional[BaselineMetrics] = None
    # Only included when the solver adapter actually identified them (Spec 3.1).
    active_constraints: List[str] = Field(default_factory=list, max_length=50)
    validation: ValidationSummary = Field(default_factory=ValidationSummary)
    evidence_catalog: List[str] = Field(default_factory=list)
    data_quality_flags: List[DataQualityFlag] = Field(default_factory=list)
