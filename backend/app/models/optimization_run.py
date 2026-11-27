import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, String

from app.core.database import Base


class OptimizationRun(Base):
    """Standalone-mode run store.

    In the integrated WasteFlow system this table is NOT used: runs come from the
    main system through a RunSnapshotProvider (see app/integration/run_provider.py).
    """
    __tablename__ = "optimization_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    status = Column(String(50), nullable=False)
    data_source = Column(String(50), nullable=False)
    snapshot_data = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
