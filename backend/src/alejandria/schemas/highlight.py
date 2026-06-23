"""Highlight and annotation schemas."""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Hex color regex — Pydantic v2 style. Only #RRGGBB is accepted.
# The validator upper-cases the result so stored colors are always
# canonical, which matches the CSS attribute selectors in app.css.
_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


class HighlightBase(BaseModel):
    """Common highlight fields."""

    cfi: str
    text: str = Field(max_length=8192)
    color: str = "#FFEB3B"
    style: str = "highlight"
    note: str | None = None
    chapter: str | None = None
    page: int | None = None

    @field_validator("color")
    @classmethod
    def _validate_color(cls, v: str) -> str:
        """Accept only #RRGGBB hex values (case-insensitive)."""
        if not _HEX.match(v):
            raise ValueError("color must be a #RRGGBB hex string")
        return v.upper()


class HighlightCreate(HighlightBase):
    """Create highlight payload."""

    book_id: int


class HighlightUpdate(BaseModel):
    """Update highlight payload.

    All fields optional — Pydantic's `exclude_unset` on the service side
    means only set fields get written to the row. `color` runs through
    the same hex validator as the create path when supplied.
    """

    color: str | None = None
    style: str | None = None
    text: str | None = Field(default=None, max_length=8192)
    note: str | None = None

    @field_validator("color")
    @classmethod
    def _validate_color(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not _HEX.match(v):
            raise ValueError("color must be a #RRGGBB hex string")
        return v.upper()


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
