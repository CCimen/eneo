"""add GPT-5 fields to completion models

Revision ID: gpt5_support
Revises: da3ec8750c0a
Create Date: 2025-08-11 08:20:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision = 'gpt5_support'
down_revision = 'da3ec8750c0a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the stable ENUM type for the API router
    api_type_enum = postgresql.ENUM('chat_completions', 'responses', name='api_type_enum')
    api_type_enum.create(op.get_bind(), checkfirst=True)
    
    # Add new columns for GPT-5 support
    op.add_column(
        'completion_models',
        sa.Column('api_type', api_type_enum, nullable=False, server_default='chat_completions')
    )
    
    op.add_column(
        'completion_models',
        sa.Column('reasoning_effort', sa.Text(), nullable=False, server_default='medium')
    )
    
    op.add_column(
        'completion_models',
        sa.Column('verbosity', sa.Text(), nullable=False, server_default='medium')
    )
    
    op.add_column(
        'completion_models',
        sa.Column('capabilities', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    
    # Add CHECK constraints for reasoning_effort and verbosity
    op.create_check_constraint(
        'ck_completion_models_reasoning_effort',
        'completion_models',
        "reasoning_effort IN ('minimal', 'low', 'medium', 'high')"
    )
    
    op.create_check_constraint(
        'ck_completion_models_verbosity',
        'completion_models',
        "verbosity IN ('low', 'medium', 'high')"
    )
    
    # Add a GIN index to the capabilities column for efficient querying
    op.create_index(
        'idx_completion_models_capabilities',
        'completion_models',
        ['capabilities'],
        unique=False,
        postgresql_using='gin'
    )


def downgrade() -> None:
    # Drop index
    op.drop_index('idx_completion_models_capabilities', table_name='completion_models')
    
    # Drop CHECK constraints
    op.drop_constraint('ck_completion_models_verbosity', 'completion_models', type_='check')
    op.drop_constraint('ck_completion_models_reasoning_effort', 'completion_models', type_='check')
    
    # Drop columns
    op.drop_column('completion_models', 'capabilities')
    op.drop_column('completion_models', 'verbosity')
    op.drop_column('completion_models', 'reasoning_effort')
    op.drop_column('completion_models', 'api_type')
    
    # Drop ENUM type
    api_type_enum = postgresql.ENUM('chat_completions', 'responses', name='api_type_enum')
    api_type_enum.drop(op.get_bind(), checkfirst=True)