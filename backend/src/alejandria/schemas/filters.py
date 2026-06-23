"""Filter and bulk operation schemas for the library page."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AuthorCount(BaseModel):
    id: int
    name: str
    count: int


class TagCount(BaseModel):
    id: int
    name: str
    count: int


class SeriesCount(BaseModel):
    id: int
    name: str
    count: int


class NameCount(BaseModel):
    name: str
    count: int


class FilterOptions(BaseModel):
    authors: list[AuthorCount]
    tags: list[TagCount]
    series: list[SeriesCount]
    formats: list[NameCount]
    languages: list[NameCount]


class BulkShelfRequest(BaseModel):
    book_ids: list[int] = Field(..., max_length=500)
    shelf_id: int


class BulkTagsRequest(BaseModel):
    book_ids: list[int] = Field(..., max_length=500)
    tags: list[str] = Field(..., max_length=50)


class BulkDeleteRequest(BaseModel):
    book_ids: list[int] = Field(..., max_length=500)


class BulkResult(BaseModel):
    affected: int = 0
    failed: int = 0
    skipped: int = 0
