"""Deprecated migration stub (removed lastfm_session_key). Kept as no-op to preserve revision chain."""

# This migration was intentionally emptied. It previously added a column that has been removed.

revision = "20251010_01"
down_revision = "20251009_01"
branch_labels = None
depends_on = None


def upgrade():
    # No-op: lastfm_session_key is no longer part of the schema
    pass


def downgrade():
    # No-op: nothing to remove
    pass
