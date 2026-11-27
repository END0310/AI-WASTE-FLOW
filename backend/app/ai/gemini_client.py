"""Provider clients.

GeminiClient  - real Google Gen AI SDK call (server-side only, Spec 2.2).
MockAIClient  - deterministic, payload-aware stub for local dev/tests.
                Only usable when settings.AI_ALLOW_MOCK is True.
"""
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

from google import genai
from google.genai import types
from google.genai.errors import APIError

from app.ai.errors import (
    ProviderNotConfigured,
    ProviderRateLimited,
    ProviderRequestError,
    ProviderTimeout,
    ProviderUnavailable,
)
from app.ai.output_schema import AIAnalysisOutput
from app.core.config import settings

logger = logging.getLogger(__name__)

_TRANSIENT_CODES = {429, 500, 502, 503, 504}


@dataclass
class ProviderResult:
    raw: Optional[Dict[str, Any]]   # parsed JSON, or None if not parseable
    raw_text: str
    latency_ms: int
    attempts: int
    provider: str
    model: str


class AIClient(Protocol):
    provider: str
    model: str

    def generate(self, system_instruction: str, contents: List[str],
                 payload_catalog: List[str]) -> ProviderResult: ...


class GeminiClient:
    provider = "gemini"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL
        if not self.api_key:
            raise ProviderNotConfigured(
                "GEMINI_API_KEY belum dikonfigurasi di environment backend."
            )
        self._client = genai.Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(
                timeout=int(settings.GEMINI_TIMEOUT_SECONDS * 1000),
                # Disable SDK-internal retries; bounded retries are handled below
                # so latency stays predictable (Spec 8: limited retry).
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )

    def generate(self, system_instruction: str, contents: List[str],
                 payload_catalog: List[str]) -> ProviderResult:
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=settings.GEMINI_TEMPERATURE,
            response_mime_type="application/json",
            response_schema=AIAnalysisOutput,
        )
        start = time.perf_counter()
        max_attempts = settings.GEMINI_MAX_RETRIES + 1
        last_exc: Optional[Exception] = None

        for attempt in range(1, max_attempts + 1):
            try:
                response = self._client.models.generate_content(
                    model=self.model, contents=contents, config=config
                )
                text = response.text or ""
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    parsed = None
                    if attempt < max_attempts:  # malformed JSON: limited retry (Spec 8)
                        logger.warning("Gemini returned malformed JSON (attempt %d)", attempt)
                        continue
                return ProviderResult(
                    raw=parsed, raw_text=text[:20000],
                    latency_ms=int((time.perf_counter() - start) * 1000),
                    attempts=attempt, provider=self.provider, model=self.model,
                )
            except APIError as e:
                last_exc = e
                if e.code in _TRANSIENT_CODES and attempt < max_attempts:
                    backoff = 2 ** attempt
                    logger.warning("Gemini %s (attempt %d/%d), retry in %ss",
                                   e.code, attempt, max_attempts, backoff)
                    time.sleep(backoff)
                    continue
                break
            except Exception as e:  # network/timeout errors from the HTTP layer
                last_exc = e
                if "timeout" in type(e).__name__.lower() and attempt < max_attempts:
                    logger.warning("Gemini timeout (attempt %d/%d)", attempt, max_attempts)
                    continue
                break

        raise _map_exception(last_exc)


def _map_exception(e: Optional[Exception]) -> Exception:
    if isinstance(e, APIError):
        msg = (e.message or "")[:300]  # sanitized, no request data
        if e.code == 429:
            return ProviderRateLimited(f"Kuota/rate limit Gemini tercapai: {msg}")
        if e.code in (500, 502, 503, 504):
            return ProviderUnavailable(f"Gemini sedang tidak tersedia ({e.code}): {msg}")
        return ProviderRequestError(f"Gemini menolak permintaan ({e.code}): {msg}")
    if e is not None and "timeout" in type(e).__name__.lower():
        return ProviderTimeout(
            f"Gemini tidak merespons dalam {settings.GEMINI_TIMEOUT_SECONDS:.0f} detik."
        )
    return ProviderUnavailable(f"Gagal menghubungi Gemini: {type(e).__name__}")


class MockAIClient:
    """Deterministic output that only cites keys from the payload catalog."""
    provider = "mock"
    model = "mock-deterministic"

    def generate(self, system_instruction: str, contents: List[str],
                 payload_catalog: List[str]) -> ProviderResult:
        cat = set(payload_catalog)
        try:
            data = json.loads(contents[-1].split("\n", 1)[1])
            solver_status = data["solver"]["status"]
        except Exception:
            solver_status = "unknown"
        route_keys = sorted(k for k in cat if k.startswith("route_utilization:"))
        insight_ev = route_keys[:1] or ["metric:recovery_rate"]
        limitations = ["Output ini dihasilkan oleh mock provider untuk pengujian, bukan oleh Gemini."]
        if "data_quality:synthetic_data" in cat:
            limitations.append("Analisis berbasis data sintetis (simulasi), bukan bukti kondisi lapangan.")
        raw = {
            "summary": "Run optimasi selesai; lihat KPI backend untuk angka resmi.",
            "operational_insights": [{
                "title": "Utilisasi rute",
                "finding": "Rute yang dirujuk beroperasi di bawah kapasitas tanpa pelanggaran kapasitas.",
                "evidence": insight_ev + ["validation:capacity"],
                "severity": "low",
            }],
            "optimization_interpretation": {
                "solver_status": solver_status,
                "tradeoffs": [{
                    "statement": "Bobot objective menentukan keseimbangan biaya, recovery, dan residu.",
                    "evidence": ["weight:cost", "weight:recovery", "weight:residual"],
                }],
            },
            "recommendations": [{
                "action": "Tinjau rute dengan utilisasi tertinggi sebelum periode berikutnya.",
                "rationale": "Utilisasi tinggi berpotensi menjadi bottleneck operasional.",
                "evidence": insight_ev,
                "priority": "low",
            }],
            "limitations": limitations,
        }
        return ProviderResult(raw=raw, raw_text=json.dumps(raw), latency_ms=0,
                              attempts=1, provider=self.provider, model=self.model)


def get_ai_client() -> AIClient:
    """Factory used by the service. Mock is opt-in via AI_ALLOW_MOCK."""
    if settings.AI_ALLOW_MOCK and not settings.GEMINI_API_KEY:
        return MockAIClient()
    return GeminiClient()
