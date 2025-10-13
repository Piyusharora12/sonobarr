"""add ListenBrainz username column

Revision ID: 20251013_01
Revises: 20251011_01
Create Date: 2025-10-13 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20251013_01"
down_revision = "20251011_01"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("users")}

    if "listenbrainz_username" not in existing_columns:
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.add_column(sa.Column("listenbrainz_username", sa.String(length=120), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("users")}

    if "listenbrainz_username" in existing_columns:
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.drop_column("listenbrainz_username")
