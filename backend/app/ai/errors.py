"""Typed error hierarchy for the AI layer.

Each error carries a stable `code` (persisted as ai_analyses.error_code and
returned to the frontend) and an HTTP status, so the UI can render the right
state (Spec 8: AI unavailable + Retry, rate limit message, solver issue, ...).
"""
from typing import Any, Optional


class AIError(Exception):
    code: str = "AI_ERROR"
    http_status: int = 500
    layer: str = "Internal"

    def __init__(self, message: str, details: Any = None, analysis_id: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.details = details
        self.analysis_id = analysis_id

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "layer": self.layer,
            "message": self.message,
            "details": self.details,
            "analysis_id": self.analysis_id,
            "retryable": self.http_status in (429, 503),
        }


# ---- Layer 1: request validation (reject before calling Gemini) ----
class RunNotFound(AIError):
    code, http_status, layer = "RUN_NOT_FOUND", 404, "RequestValidation"


class RunNotEligible(AIError):
    code, http_status, layer = "RUN_NOT_ELIGIBLE", 422, "RequestValidation"


class DuplicateAnalysisRequest(AIError):
    code, http_status, layer = "DUPLICATE_REQUEST", 429, "RequestValidation"


# ---- Layer 2: payload validation (do not call provider) ----
class PayloadNotReady(AIError):
    code, http_status, layer = "PAYLOAD_NOT_READY", 422, "PayloadValidation"


# ---- Provider failures (Spec 8) ----
class ProviderNotConfigured(AIError):
    code, http_status, layer = "AI_NOT_CONFIGURED", 503, "Provider"


class ProviderUnavailable(AIError):
    code, http_status, layer = "AI_UNAVAILABLE", 503, "Provider"


class ProviderRateLimited(AIError):
    code, http_status, layer = "AI_RATE_LIMITED", 429, "Provider"


class ProviderTimeout(AIError):
    code, http_status, layer = "AI_TIMEOUT", 503, "Provider"


class ProviderRequestError(AIError):
    code, http_status, layer = "AI_PROVIDER_ERROR", 502, "Provider"


# ---- Layers 3-6: output rejected ----
class OutputInvalid(AIError):
    code, http_status, layer = "AI_OUTPUT_INVALID", 502, "OutputValidation"
