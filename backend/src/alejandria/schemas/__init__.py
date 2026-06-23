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
    "AdapterTestRequest",
    "AdapterTestResponse",
    "AnnotationCreate",
    "AnnotationRead",
    "AnnotationUpdate",
    "BookAuthor",
    "BookDetail",
    "BookFormat",
    "BookListResponse",
    "BookSummary",
    "HighlightCreate",
    "HighlightRead",
    "HighlightUpdate",
    "ImageCandidate",
    "LibraryStats",
    "LoginRequest",
    "NextCandidate",
    "ProgressRead",
    "ProgressUpdate",
    "RegisterRequest",
    "ScrapeDestination",
    "ScrapeFormat",
    "ScrapeJobCancel",
    "ScrapeJobCreate",
    "ScrapeJobList",
    "ScrapeJobRead",
    "SeriesInfo",
    "ShelfCreate",
    "ShelfRead",
    "ShelfUpdate",
    "ShelfWithBooks",
    "TagInfo",
    "TokenResponse",
    "UserCreate",
    "UserRead",
    "UserUpdate",
]
