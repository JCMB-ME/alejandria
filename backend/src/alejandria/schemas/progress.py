"""Reading progress schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProgressUpdate(BaseModel):
    """Update reading progress payload."""

    book_id: int
    position: str
    position_type: str = "cfi"  # cfi|page|loc
    progress_pct: float = Field(ge=0.0, le=1.0)
    device_type: str | None = None
    device_name: str | None = None
    reading_time_seconds: int | None = None


class ProgressRead(BaseModel):
    """Reading progress as returned by API."""

    model_config = ConfigDict(from_attributes=True)

    book_id: int
    position: str
    position_type: str
    progress_pct: float
    last_read_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    total_reading_time: int
    device_type: str | None
    device_name: str | None
