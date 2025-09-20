"""add_image_generation_models

Revision ID: add_image_generation_models
Revises: f6ae7dc6c04f
Create Date: 2025-09-20 17:32:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = 'add_image_generation_models'
down_revision = 'f6ae7dc6c04f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create image_generation_models table
    op.create_table(
        'image_generation_models',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('nickname', sa.String(), nullable=False),
        sa.Column('open_source', sa.Boolean(), nullable=False),
        sa.Column('is_deprecated', sa.Boolean(), server_default='False', nullable=False),
        sa.Column('family', sa.String(), nullable=False),
        sa.Column('stability', sa.String(), nullable=False),
        sa.Column('hosting', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('org', sa.String(), nullable=True),
        sa.Column('litellm_model_name', sa.String(), nullable=True),
        sa.Column('deployment_name', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # Create image_generation_model_settings table
    op.create_table(
        'image_generation_model_settings',
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('image_generation_model_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('is_org_enabled', sa.Boolean(), server_default='False', nullable=False),
        sa.Column('is_org_default', sa.Boolean(), server_default='False', nullable=False),
        sa.Column('security_classification_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['image_generation_model_id'], ['image_generation_models.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['security_classification_id'], ['security_classifications.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('tenant_id', 'image_generation_model_id')
    )

    # Create spaces_image_generation_models junction table
    op.create_table(
        'spaces_image_generation_models',
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('space_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('image_generation_model_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['image_generation_model_id'], ['image_generation_models.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['space_id'], ['spaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('space_id', 'image_generation_model_id')
    )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('spaces_image_generation_models')
    op.drop_table('image_generation_model_settings')
    op.drop_table('image_generation_models')