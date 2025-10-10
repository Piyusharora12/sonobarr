"""add lastfm_session_key column

Revision ID: 20251010_01
Revises: 20251009_01
Create Date: 2025-10-10 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20251010_01"
down_revision = "20251009_01"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("users")}

    if "lastfm_session_key" not in existing_columns:
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.add_column(sa.Column("lastfm_session_key", sa.String(length=64), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("users")}

    if "lastfm_session_key" in existing_columns:
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.drop_column("lastfm_session_key")
