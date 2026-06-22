"""Highlight and annotation schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HighlightBase(BaseModel):
    """Common highlight fields."""

    cfi: str
    text: str = Field(max_length=8192)
    color: str = "yellow"
    style: str = "highlight"
    chapter: str | None = None
    page: int | None = None


class HighlightCreate(HighlightBase):
    """Create highlight payload."""

    book_id: int


class HighlightUpdate(BaseModel):
    """Update highlight payload."""

    color: str | None = None
    style: str | None = None
    text: str | None = Field(default=None, max_length=8192)


class HighlightRead(HighlightBase):
    """Highlight as returned by API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    book_id: int
    created_at: datetime
    updated_at: datetime


class AnnotationBase(BaseModel):
    """Common annotation fields."""

    content: str
    cfi: str | None = None
    page: int | None = None
    is_private: bool = True


class AnnotationCreate(AnnotationBase):
    """Create annotation payload."""

    book_id: int
    highlight_id: int | None = None


class AnnotationUpdate(BaseModel):
    """Update annotation payload."""

    content: str | None = None
    is_private: bool | None = None


class AnnotationRead(AnnotationBase):
    """Annotation as returned by API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    book_id: int
    highlight_id: int | None
    created_at: datetime
    updated_at: datetime
