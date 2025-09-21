"""Add progress tracking fields to deep_research_sessions

Revision ID: 8ac6aab9c612
Revises: 202509130000_add_deep_research_tables
Create Date: 2025-09-13 16:01:43.996009
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = '8ac6aab9c612'
down_revision = '7e2f9b8a3c4d'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Add progress tracking fields to deep_research_sessions table
    op.add_column('deep_research_sessions',
        sa.Column('progress_percentage', sa.Integer(), server_default='0', nullable=False,
                  comment='Overall progress percentage (0-100)'))
    op.add_column('deep_research_sessions',
        sa.Column('current_step', sa.String(500), nullable=True,
                  comment='Current research step description'))
    op.add_column('deep_research_sessions',
        sa.Column('sources_found', sa.Integer(), server_default='0', nullable=False,
                  comment='Number of sources discovered so far'))
    op.add_column('deep_research_sessions',
        sa.Column('branches_complete', sa.Integer(), server_default='0', nullable=False,
                  comment='Number of research branches completed'))
    op.add_column('deep_research_sessions',
        sa.Column('total_branches', sa.Integer(), server_default='0', nullable=False,
                  comment='Total number of research branches planned'))

def downgrade() -> None:
    # Remove progress tracking fields
    op.drop_column('deep_research_sessions', 'total_branches')
    op.drop_column('deep_research_sessions', 'branches_complete')
    op.drop_column('deep_research_sessions', 'sources_found')
    op.drop_column('deep_research_sessions', 'current_step')
    op.drop_column('deep_research_sessions', 'progress_percentage')