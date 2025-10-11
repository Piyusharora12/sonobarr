"""add artist requests table

Revision ID: 20251011_01
Revises: 20251009_01
Create Date: 2025-10-11 12:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20251011_01"
down_revision = "20251009_01"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = inspector.get_table_names()
    
    if "artist_requests" not in existing_tables:
        op.create_table(
            "artist_requests",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("artist_name", sa.String(length=255), nullable=False),
            sa.Column("requested_by_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("approved_by_id", sa.Integer(), nullable=True),
            sa.Column("approved_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(
                ["approved_by_id"],
                ["users.id"],
                ondelete="SET NULL",
            ),
            sa.ForeignKeyConstraint(
                ["requested_by_id"],
                ["users.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_artist_requests_artist_name"), "artist_requests", ["artist_name"], unique=False)
    else:
        # Table exists, check if index exists
        existing_indexes = [idx["name"] for idx in inspector.get_indexes("artist_requests") if idx["name"]]
        if "ix_artist_requests_artist_name" not in existing_indexes:
            op.create_index(op.f("ix_artist_requests_artist_name"), "artist_requests", ["artist_name"], unique=False)


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = inspector.get_table_names()
    
    if "artist_requests" in existing_tables:
        # Check if index exists before dropping
        existing_indexes = [idx["name"] for idx in inspector.get_indexes("artist_requests") if idx["name"]]
        if "ix_artist_requests_artist_name" in existing_indexes:
            op.drop_index(op.f("ix_artist_requests_artist_name"), table_name="artist_requests")
        op.drop_table("artist_requests")
