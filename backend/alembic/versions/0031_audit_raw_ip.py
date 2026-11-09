"""store raw client IP on audit rows

Revision ID: 0031
Revises: 0030
Create Date: 2026-11-09

The product owner authorised storing the raw client network address for
self-hosted traceability (spec #47 originally salted-hashed it only, which
cannot be read back). ``ip`` holds the address as seen by the server (honouring
``X-Forwarded-For`` behind a proxy); ``ip_hash`` from 0002/0030 is kept as a
stable pseudonymous key for indexed correlation.

Nullable so historical rows keep their shape; background / non-HTTP entries
simply leave it unset. The column is bounded and the address is not trusted
verbatim, but no hashing is applied.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("audit_logs", sa.Column("ip", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("audit_logs", "ip")
