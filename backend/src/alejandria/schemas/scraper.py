"""Pydantic I/O schemas for the web scraper API."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from alejandria.models.scrape_job import ScrapeJobStatus

ScrapeFormat = Literal["PDF", "EPUB", "CBZ"]
ScrapeDestination = Literal["library", "download"]


class ScrapeJobCreate(BaseModel):
    """Body of POST /api/scraper/jobs."""

    url: str = Field(min_length=1, max_length=2048)
    formats: list[ScrapeFormat] = Field(min_length=1)
    destinations: list[ScrapeDestination] = Field(min_length=1)
    adapter_name: str | None = Field(default=None, max_length=64)
    title: str | None = Field(default=None, max_length=512)

    @field_validator("url")
    @classmethod
    def _strip_url(cls, v: str) -> str:
        return v.strip()


class ScrapeJobRead(BaseModel):
    """API representation of a ScrapeJob row.

    The SQLAlchemy model stores JSON-encoded lists/dicts in `*_json` columns.
    We expose them under clean names (`formats`, `output_paths`, etc.) by
    aliasing those columns in ConfigDict and decoding the JSON strings in
    field validators.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    id: int
    user_id: int
    url: str
    title: str | None
    adapter_name: str
    formats: list[ScrapeFormat] = Field(
        default_factory=list,
        validation_alias="formats_json",
    )
    destinations: list[ScrapeDestination] = Field(
        default_factory=list,
        validation_alias="destinations_json",
    )
    status: ScrapeJobStatus
    total_pages: int
    current_page: int
    progress_pct: float
    total_bytes: int
    error: str | None
    output_paths: dict[str, str] | None = Field(
        default=None,
        validation_alias="output_paths_json",
    )
    imported_book_ids: dict[str, int] | None = Field(
        default=None,
        validation_alias="imported_book_ids_json",
    )
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    @field_validator("formats", "destinations", mode="before")
    @classmethod
    def _decode_json_list(cls, v):
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except (TypeError, ValueError):
                return []
        return v

    @field_validator("output_paths", "imported_book_ids", mode="before")
    @classmethod
    def _decode_json_dict(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, dict):
                    return parsed
            except (TypeError, ValueError):
                return None
        return v


class ScrapeJobList(BaseModel):
    """List response."""

    items: list[ScrapeJobRead]


class ScrapeJobCancel(BaseModel):
    """Body of POST /api/scraper/jobs/{id}/cancel (currently empty payload)."""

    reason: str | None = None


class AdapterTestRequest(BaseModel):
    """Body of POST /api/scraper/adapters/test."""

    url: str = Field(min_length=1, max_length=2048)
    adapter_name: str | None = None


class ImageCandidate(BaseModel):
    url: str
    width: int
    height: int


class NextCandidate(BaseModel):
    selector: str
    href: str | None
    text: str | None


class AdapterTestResponse(BaseModel):
    image_candidates: list[ImageCandidate]
    next_candidates: list[NextCandidate]
    adapter_used: str
