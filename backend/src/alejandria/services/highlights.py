"""Highlight and annotation services."""

from __future__ import annotations

import io
import re
import zipfile
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from alejandria.models.annotation import Annotation
from alejandria.models.highlight import Highlight
from alejandria.models.user import User, UserRole
from alejandria.schemas.highlight import (
    AnnotationCreate,
    AnnotationUpdate,
    HighlightCreate,
    HighlightUpdate,
)
from alejandria.services.calibre_db import get_calibre_db
from alejandria.utils.log import get_logger

logger = get_logger(__name__)


class HighlightService:
    """CRUD for highlights + annotations."""

    def create_highlight(self, db: Session, user_id: int, data: HighlightCreate) -> Highlight:
        h = Highlight(
            user_id=user_id,
            book_id=data.book_id,
            cfi=data.cfi,
            text=data.text,
            color=data.color,
            style=data.style,
            note=data.note,
            chapter=data.chapter,
            page=data.page,
        )
        db.add(h)
        db.commit()
        db.refresh(h)
        return h

    def update_highlight(
        self, db: Session, user: User, highlight_id: int, data: HighlightUpdate
    ) -> Highlight:
        """Update a highlight, raising LookupError (404) or PermissionError (403).

        Distinguishing the two failure modes is the audit's H4 finding —
        a missing row and a row owned by someone else must return
        different HTTP statuses so the SPA can show a meaningful error.
        """
        h = db.get(Highlight, highlight_id)
        if not h:
            raise LookupError("highlight not found")
        if h.user_id != user.id and user.role != UserRole.ADMIN:
            raise PermissionError("not your highlight")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(h, field, value)
        h.updated_at = datetime.now(UTC)
        db.commit()
        db.refresh(h)
        return h

    def delete_highlight(self, db: Session, user: User, highlight_id: int) -> None:
        """Delete a highlight, raising LookupError (404) or PermissionError (403)."""
        h = db.get(Highlight, highlight_id)
        if not h:
            raise LookupError("highlight not found")
        if h.user_id != user.id and user.role != UserRole.ADMIN:
            raise PermissionError("not your highlight")
        db.delete(h)
        db.commit()

    def list_highlights(
        self, db: Session, user_id: int, *, book_id: int | None = None
    ) -> list[Highlight]:
        stmt = select(Highlight).where(Highlight.user_id == user_id)
        if book_id is not None:
            stmt = stmt.where(Highlight.book_id == book_id)
        stmt = stmt.order_by(Highlight.created_at.desc())
        return list(db.execute(stmt).scalars())

    def create_annotation(self, db: Session, user_id: int, data: AnnotationCreate) -> Annotation:
        a = Annotation(
            user_id=user_id,
            book_id=data.book_id,
            highlight_id=data.highlight_id,
            cfi=data.cfi,
            page=data.page,
            content=data.content,
            is_private=data.is_private,
        )
        db.add(a)
        db.commit()
        db.refresh(a)
        return a

    def update_annotation(
        self, db: Session, user_id: int, annotation_id: int, data: AnnotationUpdate
    ) -> Annotation | None:
        a = db.get(Annotation, annotation_id)
        if not a or a.user_id != user_id:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(a, field, value)
        a.updated_at = datetime.now(UTC)
        db.commit()
        db.refresh(a)
        return a

    def delete_annotation(self, db: Session, user_id: int, annotation_id: int) -> bool:
        a = db.get(Annotation, annotation_id)
        if not a or a.user_id != user_id:
            return False
        db.delete(a)
        db.commit()
        return True

    def export_markdown(
        self, db: Session, user_id: int, book_id: int | None = None
    ) -> str:
        """Export highlights as Markdown for one book.

        With book_id: returns a single markdown document with H1 = book
        title. Without book_id: raises ValueError so callers can't
        accidentally write the old "single # Highlights" document when
        they meant the per-user bundle — use export_markdown_zip() for
        that.
        """
        if book_id is None:
            raise ValueError(
                "export_markdown requires a book_id; use export_markdown_zip "
                "for the full-library bundle."
            )

        calibre = get_calibre_db()
        book = calibre.get_book(book_id)
        if not book:
            raise LookupError("book not found")

        highlights = self.list_highlights(db, user_id, book_id=book_id)
        annotations = list(
            db.execute(
                select(Annotation).where(Annotation.user_id == user_id)
            ).scalars()
        )
        ann_by_highlight = {a.highlight_id: a for a in annotations if a.highlight_id}

        title = book.get("title", "Untitled")
        authors = book.get("authors", "") or ""
        lines: list[str] = [f"# {title}", ""]
        if authors:
            lines.append(f"*{authors}*")
            lines.append("")
        for h in sorted(highlights, key=lambda x: ((x.page or 0), x.created_at)):
            quote = h.text.replace("\n", " ")
            lines.append(f"> {quote}")
            if h.chapter:
                lines.append(f"> — *{h.chapter}*")
            lines.append("")
            # Prefer Highlight.note (H1's new column); fall back to
            # Annotation.content for legacy rows that pre-date the
            # unified note column.
            note_text = h.note
            if not note_text:
                ann = ann_by_highlight.get(h.id)
                if ann:
                    note_text = ann.content
            if note_text:
                lines.append(note_text)
                lines.append("")
            lines.append(f"*— {h.created_at.strftime('%Y-%m-%d')}*")
            lines.append("")
        return "\n".join(lines)

    def export_markdown_zip(self, db: Session, user_id: int) -> bytes:
        """Build a zip with one .md per book the user has highlights in.

        Books with zero highlights are skipped. When the user has no
        highlights at all, a single README.md is included explaining
        how to create them.
        """
        calibre = get_calibre_db()
        highlights = list(
            db.execute(
                select(Highlight).where(Highlight.user_id == user_id)
            ).scalars()
        )

        by_book: dict[int, list[Highlight]] = {}
        for h in highlights:
            by_book.setdefault(h.book_id, []).append(h)

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            if not by_book:
                zf.writestr(
                    "README.md",
                    "# No highlights yet\n\n"
                    "Select text in any book and click the highlight button to add one.\n",
                )
            else:
                for book_id, _hs in sorted(by_book.items()):
                    md = self.export_markdown(db, user_id, book_id=book_id)
                    book = calibre.get_book(book_id)
                    if book and book.get("title"):
                        title_slug = _slugify(book["title"])
                    else:
                        title_slug = f"book-{book_id}"
                    zf.writestr(f"{title_slug}.md", md)
        return buf.getvalue()


def _slugify(s: str) -> str:
    """Turn a book title into a safe filename slug.

    Strips everything that isn't a word character, space, or dash;
    collapses runs of dashes/spaces into a single dash; truncates to
    64 chars and lowercases. Always returns a non-empty string.
    """
    s = re.sub(r"[^\w\s-]", "", s.lower())
    return re.sub(r"[-\s]+", "-", s).strip("-")[:64] or "untitled"
