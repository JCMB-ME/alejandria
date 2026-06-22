"""SQLAlchemy models for the application database."""

from alejandria.models.user import User
from alejandria.models.session import UserSession
from alejandria.models.progress import ReadingProgress
from alejandria.models.highlight import Highlight
from alejandria.models.annotation import Annotation
from alejandria.models.shelf import Shelf, ShelfBook
from alejandria.models.scrape_job import ScrapeJob, ScrapeJobStatus

__all__ = [
    "User",
    "UserSession",
    "ReadingProgress",
    "Highlight",
    "Annotation",
    "Shelf",
    "ShelfBook",
    "ScrapeJob",
    "ScrapeJobStatus",
]
