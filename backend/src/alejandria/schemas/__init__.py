"""Pydantic schemas for API I/O."""

from alejandria.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserCreate,
    UserRead,
    UserUpdate,
)
from alejandria.schemas.book import (
    BookAuthor,
    BookDetail,
    BookFormat,
    BookListResponse,
    BookSummary,
    LibraryStats,
    SeriesInfo,
    TagInfo,
)
from alejandria.schemas.highlight import (
    AnnotationCreate,
    AnnotationRead,
    AnnotationUpdate,
    HighlightCreate,
    HighlightRead,
    HighlightUpdate,
)
from alejandria.schemas.progress import (
    ProgressRead,
    ProgressUpdate,
)
from alejandria.schemas.scraper import (
    AdapterTestRequest,
    AdapterTestResponse,
    ImageCandidate,
    NextCandidate,
    ScrapeDestination,
    ScrapeFormat,
    ScrapeJobCancel,
    ScrapeJobCreate,
    ScrapeJobList,
    ScrapeJobRead,
)
from alejandria.schemas.shelf import (
    ShelfCreate,
    ShelfRead,
    ShelfUpdate,
    ShelfWithBooks,
)

__all__ = [
    "LoginRequest",
    "RegisterRequest",
    "TokenResponse",
    "UserCreate",
    "UserRead",
    "UserUpdate",
    "BookAuthor",
    "BookDetail",
    "BookFormat",
    "BookListResponse",
    "BookSummary",
    "LibraryStats",
    "SeriesInfo",
    "TagInfo",
    "AnnotationCreate",
    "AnnotationRead",
    "AnnotationUpdate",
    "HighlightCreate",
    "HighlightRead",
    "HighlightUpdate",
    "ProgressRead",
    "ProgressUpdate",
    "AdapterTestRequest",
    "AdapterTestResponse",
    "ImageCandidate",
    "NextCandidate",
    "ScrapeDestination",
    "ScrapeFormat",
    "ScrapeJobCancel",
    "ScrapeJobCreate",
    "ScrapeJobList",
    "ScrapeJobRead",
    "ShelfCreate",
    "ShelfRead",
    "ShelfUpdate",
    "ShelfWithBooks",
]
