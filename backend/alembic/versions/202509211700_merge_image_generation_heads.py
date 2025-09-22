"""merge image generation migrations

Revision ID: 6e668abe2d9f
Revises: 3578a7d17112, 2f8e9a1b3c5d
Create Date: 2025-09-21 17:00:00.000000

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "6e668abe2d9f"
down_revision = ("3578a7d17112", "2f8e9a1b3c5d")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No-op merge migration to reconcile concurrent heads.
    pass


def downgrade() -> None:
    # No-op downgrade for merge migration.
    pass
