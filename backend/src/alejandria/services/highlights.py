"""Highlight and annotation services."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from alejandria.models.annotation import Annotation
from alejandria.models.highlight import Highlight
from alejandria.schemas.highlight import (
    AnnotationCreate,
    AnnotationUpdate,
    HighlightCreate,
    HighlightUpdate,
)
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
            chapter=data.chapter,
            page=data.page,
        )
        db.add(h)
        db.commit()
        db.refresh(h)
        return h

    def update_highlight(
        self, db: Session, user_id: int, highlight_id: int, data: HighlightUpdate
    ) -> Highlight | None:
        h = db.get(Highlight, highlight_id)
        if not h or h.user_id != user_id:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(h, field, value)
        h.updated_at = datetime.now(UTC)
        db.commit()
        db.refresh(h)
        return h

    def delete_highlight(self, db: Session, user_id: int, highlight_id: int) -> bool:
        h = db.get(Highlight, highlight_id)
        if not h or h.user_id != user_id:
            return False
        db.delete(h)
        db.commit()
        return True

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
        """Export highlights as Markdown (Obsidian/Notion compatible)."""
        highlights = self.list_highlights(db, user_id, book_id=book_id)
        annotations = list(
            db.execute(
                select(Annotation).where(Annotation.user_id == user_id)
            ).scalars()
        )
        ann_by_highlight = {a.highlight_id: a for a in annotations if a.highlight_id}

        lines: list[str] = ["# Highlights", ""]
        for h in highlights:
            quote = h.text.replace("\n", " ")
            lines.append(f"> {quote}")
            if h.chapter:
                lines.append(f"— *{h.chapter}*")
            ann = ann_by_highlight.get(h.id)
            if ann:
                lines.append(f"\n{ann.content}\n")
            lines.append(f"  *{h.created_at.strftime('%Y-%m-%d')}*\n")
        return "\n".join(lines)
