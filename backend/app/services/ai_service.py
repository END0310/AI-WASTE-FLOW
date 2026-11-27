"""AI analysis orchestration + persistence (Spec 2.1 logical flow)."""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional

from sqlalchemy.orm import Session

from app.ai import validator as V
from app.ai.errors import (
    AIError,
    DuplicateAnalysisRequest,
    OutputInvalid,
    PayloadNotReady,
    RunNotEligible,
    RunNotFound,
)
from app.ai.gemini_client import AIClient, ProviderResult, get_ai_client
from app.ai.input_schema import AIInputPayload
from app.ai.payload_builder import PayloadBuilder
from app.ai.prompts import build_contents, build_system_prompt
from app.core.config import settings
from app.integration.run_provider import RunSnapshotProvider
from app.models.ai_analysis import AIAnalysis

logger = logging.getLogger(__name__)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class AIService:
    def __init__(self, db: Session, run_provider: RunSnapshotProvider,
                 client_factory: Callable[[], AIClient] = get_ai_client):
        self.db = db
        self.runs = run_provider
        self.client_factory = client_factory

    # ------------------------------------------------------------------ public
    def run_analysis(self, run_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        # Layer 1: request validation (nothing persisted, Gemini not called)
        run = self.runs.get_snapshot(run_id)
        if run is None or not self.runs.can_access(run, user_id):
            raise RunNotFound(f"Optimization run '{run_id}' tidak ditemukan.")

        eligible, reason = V.check_eligibility(run.solver_status)
        if not eligible:
            raise RunNotEligible(reason, details={"solver_status": run.solver_status})

        self._check_duplicate(run.run_id)

        # Layer 2: payload validation (persist as failed for audit, Gemini not called)
        try:
            payload = PayloadBuilder.from_snapshot(run.snapshot)
        except PayloadNotReady as e:
            self._persist_failure(run.run_id, {"run_id": run.run_id}, e, user_id)
            raise
        problems = V.validate_payload(payload)
        if problems:
            err = PayloadNotReady("Input belum siap dianalisis.", details=problems)
            self._persist_failure(run.run_id, payload.model_dump(), err, user_id)
            raise err

        # Provider call + layers 3-6
        try:
            client = self.client_factory()
        except AIError as e:
            self._persist_failure(run.run_id, payload.model_dump(), e, user_id)
            raise

        system_prompt = build_system_prompt(settings.PROMPT_VERSION, settings.AI_OUTPUT_LANGUAGE)
        contents = build_contents(settings.PROMPT_VERSION, payload)

        total_latency, total_attempts = 0, 0
        result: Optional[ProviderResult] = None
        report: Optional[V.OutputValidationReport] = None
        for round_ in range(settings.AI_VALIDATION_RETRIES + 1):
            try:
                result = client.generate(system_prompt, contents, payload.evidence_catalog)
            except AIError as e:
                self._persist_failure(run.run_id, payload.model_dump(), e, user_id,
                                      provider=client.provider, model=client.model,
                                      latency_ms=total_latency or None)
                raise
            total_latency += result.latency_ms
            total_attempts += result.attempts
            report = V.validate_output(result.raw, payload)
            if report.is_valid:
                break
            logger.warning("AI output rejected at %s (round %d): %s",
                           report.failed_layer, round_ + 1, report.summary())
            contents = build_contents(settings.PROMPT_VERSION, payload) + [V.feedback_for_retry(report)]

        assert result is not None and report is not None
        if not report.is_valid:
            err = OutputInvalid(f"Output AI ditolak pada {report.failed_layer}.", details=report.summary())
            rec = self._persist(run.run_id, payload, result, "invalid", total_latency, total_attempts,
                                user_id, output=result.raw, report=report.summary(), error=err)
            err.analysis_id = rec.id
            raise err

        added = V.enforce_limitations(report.output, payload)
        output = report.output.model_dump()
        rec = self._persist(run.run_id, payload, result, "valid", total_latency, total_attempts,
                            user_id, output=output,
                            report={"limitations_added_by_backend": added} if added else None)
        return self.to_response(rec)

    # ------------------------------------------------------------------ helpers
    def _check_duplicate(self, run_id: str) -> None:
        if settings.AI_ANALYSIS_COOLDOWN_SECONDS <= 0:
            return
        last = (self.db.query(AIAnalysis)
                .filter(AIAnalysis.run_id == run_id, AIAnalysis.validation_status == "valid")
                .order_by(AIAnalysis.created_at.desc()).first())
        if last and _aware(last.created_at) > datetime.now(timezone.utc) - timedelta(
                seconds=settings.AI_ANALYSIS_COOLDOWN_SECONDS):
            raise DuplicateAnalysisRequest(
                f"Analisis untuk run ini baru saja dibuat. Coba lagi setelah "
                f"{settings.AI_ANALYSIS_COOLDOWN_SECONDS} detik atau buka analisis terakhir.",
                analysis_id=last.id,
            )

    def _persist(self, run_id: str, payload: AIInputPayload, result: ProviderResult, status: str,
                 latency: int, attempts: int, user_id: Optional[str], output: Any = None,
                 report: Any = None, error: Optional[AIError] = None) -> AIAnalysis:
        rec = AIAnalysis(
            id=str(uuid.uuid4()), run_id=run_id, provider=result.provider, model=result.model,
            prompt_version=settings.PROMPT_VERSION, temperature=settings.GEMINI_TEMPERATURE,
            input_json=payload.model_dump(), output_json=output, validation_status=status,
            validation_report=report, attempts=attempts, latency_ms=latency,
            error_code=error.code if error else None,
            error_message=error.message[:1000] if error else None,
            requested_by=user_id,
        )
        self.db.add(rec)
        self.db.commit()
        self.db.refresh(rec)
        return rec

    def _persist_failure(self, run_id: str, input_json: Dict[str, Any], err: AIError,
                         user_id: Optional[str], provider: str = "gemini",
                         model: Optional[str] = None, latency_ms: Optional[int] = None) -> None:
        rec = AIAnalysis(
            id=str(uuid.uuid4()), run_id=run_id, provider=provider,
            model=model or settings.GEMINI_MODEL, prompt_version=settings.PROMPT_VERSION,
            temperature=settings.GEMINI_TEMPERATURE, input_json=input_json,
            validation_status="failed", validation_report={"details": err.details} if err.details else None,
            latency_ms=latency_ms, error_code=err.code, error_message=err.message[:1000],
            requested_by=user_id,
        )
        self.db.add(rec)
        self.db.commit()
        err.analysis_id = rec.id

    @staticmethod
    def to_response(rec: AIAnalysis, include_input: bool = False) -> Dict[str, Any]:
        """Spec 7.2 response shape (+ audit metadata)."""
        body = {
            "analysis_id": rec.id,
            "run_id": rec.run_id,
            "status": "completed" if rec.validation_status == "valid" else rec.validation_status,
            "provider": rec.provider,
            "model": rec.model,
            "prompt_version": rec.prompt_version,
            # Only validated output is exposed as a result (Spec 8: never show invalid output).
            "result": rec.output_json if rec.validation_status == "valid" else None,
            "validation_status": rec.validation_status,
            "validation_report": rec.validation_report,
            "error_code": rec.error_code,
            "error_message": rec.error_message,
            "latency_ms": rec.latency_ms,
            "attempts": rec.attempts,
            "temperature": rec.temperature,
            "created_at": _aware(rec.created_at).isoformat() if rec.created_at else None,
        }
        if include_input:
            body["input_payload"] = rec.input_json
        return body
