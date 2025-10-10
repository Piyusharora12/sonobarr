"""add Last.fm username column

Revision ID: 20251009_01
Revises: 
Create Date: 2025-10-09 12:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20251009_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("users")}

    with op.batch_alter_table("users", schema=None) as batch_op:
        if "lastfm_username" not in existing_columns:
            batch_op.add_column(
                sa.Column("lastfm_username", sa.String(length=120), nullable=True)
            )


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_columns = {col["name"] for col in inspector.get_columns("users")}

    with op.batch_alter_table("users", schema=None) as batch_op:
        if "lastfm_username" in existing_columns:
            batch_op.drop_column("lastfm_username")
