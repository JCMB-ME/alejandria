"""SQLAlchemy models for the application database."""

from alejandria.models.annotation import Annotation
from alejandria.models.highlight import Highlight
from alejandria.models.progress import ReadingProgress
from alejandria.models.scrape_job import ScrapeJob, ScrapeJobStatus
from alejandria.models.session import UserSession
from alejandria.models.shelf import Shelf, ShelfBook
from alejandria.models.user import User

__all__ = [
    "Annotation",
    "Highlight",
    "ReadingProgress",
    "ScrapeJob",
    "ScrapeJobStatus",
    "Shelf",
    "ShelfBook",
    "User",
    "UserSession",
]
