"""add highlight.note and migrate color to hex

Revision ID: 3c5739e09be5
Revises: 21e83df6ddb0
Create Date: 2026-06-23 13:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "3c5739e09be5"
down_revision: Union[str, None] = "21e83df6ddb0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add the note column (free-text annotation per highlight).
    # SQLite has no `ADD COLUMN IF NOT EXISTS`, so we guard with a
    # PRAGMA table_info check. The guard is a no-op when the column is
    # missing (the common case on a real alembic upgrade from v0.1.0)
    # and is the difference between a clean run and a crash when the
    # table was created via `Base.metadata.create_all` against the
    # latest model definitions in tests.
    conn = op.get_bind()
    existing_cols = {
        row[1]
        for row in conn.exec_driver_sql("PRAGMA table_info(highlights)").fetchall()
    }
    if "note" not in existing_cols:
        with op.batch_alter_table("highlights", schema=None) as batch_op:
            batch_op.add_column(sa.Column("note", sa.Text(), nullable=True))

    # Translate legacy named color tokens to their hex equivalents.
    # Unknown legacy values fall back to yellow so a stale row never
    # renders as a transparent / no-color blob after this migration.
    op.execute(
        "UPDATE highlights SET color = CASE color "
        "  WHEN 'yellow' THEN '#FFEB3B' "
        "  WHEN 'green'  THEN '#81C784' "
        "  WHEN 'blue'   THEN '#64B5F6' "
        "  WHEN 'pink'   THEN '#F48FB1' "
        "  WHEN 'orange' THEN '#FFAB40' "
        "  ELSE '#FFEB3B' "
        "END"
    )


def downgrade() -> None:
    conn = op.get_bind()
    existing_cols = {
        row[1]
        for row in conn.exec_driver_sql("PRAGMA table_info(highlights)").fetchall()
    }
    if "note" in existing_cols:
        with op.batch_alter_table("highlights", schema=None) as batch_op:
            batch_op.drop_column("note")
    # Best-effort: translate hex back to a name. We can't recover the
    # original intent, so we map every value back to "yellow".
    op.execute("UPDATE highlights SET color = 'yellow'")