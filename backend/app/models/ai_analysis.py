import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, Text

from app.core.database import Base


def _now():
    return datetime.now(timezone.utc)


class AIAnalysis(Base):
    """Spec 7.3 - AI analysis history, separate from optimization runs."""
    __tablename__ = "ai_analyses"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # No FK on purpose: when embedded, runs may live in the main system's table/schema.
    run_id = Column(String(64), nullable=False, index=True)
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    prompt_version = Column(String(50), nullable=False)
    temperature = Column(Float, nullable=True)          # Spec 5.3 reproducibility
    input_json = Column(JSON, nullable=False)           # curated payload, no secrets
    output_json = Column(JSON, nullable=True)           # validated output (or raw if rejected)
    validation_status = Column(String(20), nullable=False, index=True)  # valid|invalid|failed
    validation_report = Column(JSON, nullable=True)     # which layer failed and why
    attempts = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)         # sanitized
    requested_by = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, index=True)
