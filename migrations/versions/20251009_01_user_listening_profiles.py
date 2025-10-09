"""add user listening profile columns

Revision ID: 20251009_01
Revises: 
Create Date: 2025-10-09 12:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251009_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("lastfm_username", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("listenbrainz_username", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("listenbrainz_token", sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("listenbrainz_token")
        batch_op.drop_column("listenbrainz_username")
        batch_op.drop_column("lastfm_username")
