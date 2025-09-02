"""add default_enabled to completion models

Revision ID: default_enabled_support
Revises: gpt5_support
Create Date: 2025-08-16 08:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = 'default_enabled_support'
down_revision = 'gpt5_support'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add default_enabled column to completion_models table
    op.add_column(
        'completion_models',
        sa.Column('default_enabled', sa.Boolean(), nullable=False, server_default='true')
    )
    
    # Update GPT-5 models to have default_enabled=false for controlled rollout
    op.execute("""
        UPDATE completion_models 
        SET default_enabled = false 
        WHERE name LIKE 'gpt-5%' OR name LIKE '%o3%' OR name LIKE '%o4%'
    """)


def downgrade() -> None:
    # Drop the default_enabled column
    op.drop_column('completion_models', 'default_enabled')