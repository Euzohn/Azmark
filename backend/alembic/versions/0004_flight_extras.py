"""add flight actual times, distance, encrypted sensitive fields

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-09

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SENSITIVE = (
    ("booking_reference", "booking_reference_enc"),
    ("ticket_number", "ticket_number_enc"),
)


def _encrypt_existing(connection: Connection, column: str) -> None:
    """Encrypt existing plaintext PNR/ticket numbers in place (spec #45/#96)."""
    from app.core.crypto import encrypt_value

    rows = connection.execute(
        sa.text(f"SELECT id, {column} FROM transport_records WHERE {column} IS NOT NULL")
    ).mappings()
    for row in rows:
        connection.execute(
            sa.text(f"UPDATE transport_records SET {column} = :enc WHERE id = :id"),
            {"enc": encrypt_value(row[column]), "id": row["id"]},
        )


def upgrade() -> None:
    # 实际起降时间（spec #12 actual_departure/actual_arrival）。
    op.add_column(
        "transport_records",
        sa.Column("actual_departure_time", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "transport_records",
        sa.Column("actual_arrival_time", sa.DateTime(timezone=True), nullable=True),
    )
    # 里程（km）。规格未列，按用户要求新增。
    op.add_column(
        "transport_records",
        sa.Column("distance", sa.Numeric(10, 2), nullable=True),
    )
    # 购票证件号（身份证/护照）敏感 PII（spec #45/#96），加密存储。
    op.add_column(
        "transport_records",
        sa.Column("purchase_credential_enc", sa.Text(), nullable=True),
    )
    # PNR 预订编码与客票号改为加密存储；先改名保留原值，再对存量明文加密。
    for column, enc_column in _SENSITIVE:
        op.alter_column(
            "transport_records",
            column,
            new_column_name=enc_column,
            existing_type=sa.String(length=64),
            type_=sa.Text(),
        )
    connection = op.get_bind()
    for _, enc_column in _SENSITIVE:
        _encrypt_existing(connection, enc_column)


def downgrade() -> None:
    from app.core.crypto import decrypt_value

    connection = op.get_bind()
    # 先解密存量密文，再改回明文列名。
    for column, enc_column in _SENSITIVE:
        rows = connection.execute(
            sa.text(
                f"SELECT id, {enc_column} FROM transport_records WHERE {enc_column} IS NOT NULL"
            )
        ).mappings()
        for row in rows:
            plain = decrypt_value(row[enc_column])
            connection.execute(
                sa.text(f"UPDATE transport_records SET {enc_column} = :plain WHERE id = :id"),
                {"plain": plain, "id": row["id"]},
            )
        op.alter_column(
            "transport_records",
            enc_column,
            new_column_name=column,
            existing_type=sa.Text(),
            type_=sa.String(length=64),
        )
    op.drop_column("transport_records", "purchase_credential_enc")
    op.drop_column("transport_records", "distance")
    op.drop_column("transport_records", "actual_arrival_time")
    op.drop_column("transport_records", "actual_departure_time")
