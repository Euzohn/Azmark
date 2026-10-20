"""normalize stored UTC-offset timezones to IANA names

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-20

Providers used to persist timezones in mixed formats: AeroDataBox stored IANA
("Asia/Shanghai") but VariFlight stored "+08:00", and the UI used to be a
free-text field so users could type either. The UI now exposes an IANA
dropdown, so backfill the rows that still hold an offset so every stored value
is a real IANA name. ``app.core.timezones.normalize_timezone`` is the single
source of truth — the migration reuses it so future map edits stay consistent.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    from app.core.timezones import normalize_timezone

    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, departure_timezone, arrival_timezone "
            "FROM transport_records "
            "WHERE departure_timezone LIKE '+%' OR departure_timezone LIKE '-%' "
            "OR arrival_timezone LIKE '+%' OR arrival_timezone LIKE '-%'"
        )
    ).fetchall()
    for row in rows:
        dep = normalize_timezone(row.departure_timezone) if row.departure_timezone else None
        arr = normalize_timezone(row.arrival_timezone) if row.arrival_timezone else None
        bind.execute(
            sa.text(
                "UPDATE transport_records "
                "SET departure_timezone = :dep, arrival_timezone = :arr "
                "WHERE id = :id"
            ),
            {"dep": dep, "arr": arr, "id": row.id},
        )


def downgrade() -> None:
    # No faithful reverse: an IANA name cannot be turned back into the original
    # offset the provider emitted. Leaving the normalized values in place is
    # strictly an improvement, so this is a no-op.
    pass
