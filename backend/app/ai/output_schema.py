"""Pydantic output contract (Spec 4.1 / 4.2)."""
from typing import List, Literal

from pydantic import BaseModel, Field

Level = Literal["low", "medium", "high"]


class OperationalInsight(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    finding: str = Field(..., min_length=1, max_length=600)
    evidence: List[str] = Field(..., min_length=1, max_length=10)
    severity: Level


class TradeoffItem(BaseModel):
    statement: str = Field(..., min_length=1, max_length=600)
    evidence: List[str] = Field(..., min_length=1, max_length=10)


class OptimizationInterpretation(BaseModel):
    solver_status: str = Field(..., max_length=40)
    tradeoffs: List[TradeoffItem] = Field(default_factory=list, max_length=5)


class RecommendationItem(BaseModel):
    action: str = Field(..., min_length=1, max_length=250)
    rationale: str = Field(..., min_length=1, max_length=600)
    evidence: List[str] = Field(..., min_length=1, max_length=10)
    priority: Level


class AIAnalysisOutput(BaseModel):
    summary: str = Field(..., min_length=1, max_length=800)
    operational_insights: List[OperationalInsight] = Field(default_factory=list, max_length=5)
    optimization_interpretation: OptimizationInterpretation
    recommendations: List[RecommendationItem] = Field(default_factory=list, max_length=5)
    limitations: List[str] = Field(default_factory=list, max_length=8)
