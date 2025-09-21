"""Add deep research tables

Revision ID: 7e2f9b8a3c4d
Revises: 1e58cb567f44
Create Date: 2025-09-13 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '7e2f9b8a3c4d'
down_revision = '1e58cb567f44'
branch_labels = None
depends_on = None


def upgrade():
    # Create deep_research_configurations table
    op.create_table('deep_research_configurations',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('assistant_id', sa.UUID(), nullable=False),
        sa.Column('max_breadth', sa.Integer(), nullable=False, server_default=sa.text('3')),
        sa.Column('max_depth', sa.Integer(), nullable=False, server_default=sa.text('2')),
        sa.Column('quick_timeout_seconds', sa.Integer(), nullable=False, server_default=sa.text('60')),
        sa.Column('standard_timeout_seconds', sa.Integer(), nullable=False, server_default=sa.text('180')),
        sa.Column('deep_timeout_seconds', sa.Integer(), nullable=False, server_default=sa.text('300')),
        sa.Column('sources_per_query', sa.Integer(), nullable=False, server_default=sa.text('5')),
        sa.Column('enable_web_search', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('enable_academic_sources', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.ForeignKeyConstraint(['assistant_id'], ['assistants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('assistant_id')
    )

    # Create deep_research_sessions table
    op.create_table('deep_research_sessions',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('query', sa.Text(), nullable=False, comment='Original research query from user'),
        sa.Column('mode', sa.String(length=20), nullable=False, comment='Research depth: quick, standard, deep'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default=sa.text("'planning'"), comment='Current state: planning, pending_approval, running, completed, failed, cancelled'),
        sa.Column('tenant_id', sa.UUID(), nullable=False, comment='Tenant isolation'),
        sa.Column('user_id', sa.UUID(), nullable=False, comment='User who initiated research'),
        sa.Column('space_id', sa.UUID(), nullable=True, comment='Optional space context'),
        sa.Column('assistant_id', sa.UUID(), nullable=False, comment='Assistant used for research'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True, comment='When research execution began'),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True, comment='When research finished'),
        sa.Column('max_breadth', sa.Integer(), nullable=False, server_default=sa.text('3'), comment='Parallel queries per level (1-6)'),
        sa.Column('max_depth', sa.Integer(), nullable=False, server_default=sa.text('2'), comment='Research tree depth (1-3)'),
        sa.Column('timeout_minutes', sa.Integer(), nullable=False, server_default=sa.text('3'), comment='Research timeout based on mode'),
        sa.ForeignKeyConstraint(['assistant_id'], ['assistants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['space_id'], ['spaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_deep_research_sessions_tenant_id', 'deep_research_sessions', ['tenant_id'])

    # Create deep_research_plans table
    op.create_table('deep_research_plans',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('session_id', sa.UUID(), nullable=False, comment='One plan per research session'),
        sa.Column('questions', postgresql.JSON(astext_type=sa.Text()), nullable=False, comment='Structured research questions tree'),
        sa.Column('estimated_duration', sa.Integer(), nullable=False, comment='Expected runtime in seconds'),
        sa.Column('estimated_sources', sa.Integer(), nullable=False, comment='Expected number of sources'),
        sa.Column('approved', sa.Boolean(), nullable=False, server_default=sa.text('false'), comment='User approval status'),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True, comment='Approval timestamp'),
        sa.ForeignKeyConstraint(['session_id'], ['deep_research_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id')
    )

    # Create deep_research_branches table
    op.create_table('deep_research_branches',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('session_id', sa.UUID(), nullable=False, comment='Parent research session'),
        sa.Column('branch_id', sa.String(length=50), nullable=False, comment="Identifier from plan (e.g., 'branch_1_1')"),
        sa.Column('parent_branch_id', sa.String(length=50), nullable=True, comment='Parent branch for tree structure'),
        sa.Column('question', sa.Text(), nullable=False, comment='Research question for this branch'),
        sa.Column('level', sa.Integer(), nullable=False, comment='Depth level (1-3)'),
        sa.Column('branch_type', sa.String(length=20), nullable=False, comment='Search strategy: broad or deep'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default=sa.text("'pending'"), comment='Progress: pending, searching, completed, failed'),
        sa.Column('progress', sa.Integer(), nullable=False, server_default=sa.text('0'), comment='Completion percentage (0-100)'),
        sa.Column('sources_found', sa.Integer(), nullable=False, server_default=sa.text('0'), comment='Number of sources discovered'),
        sa.Column('search_queries', postgresql.JSON(astext_type=sa.Text()), nullable=True, comment='List of actual search queries used'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True, comment='When branch search started'),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True, comment='When branch search finished'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='Error description if failed'),
        sa.ForeignKeyConstraint(['session_id'], ['deep_research_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create deep_research_results table
    op.create_table('deep_research_results',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('session_id', sa.UUID(), nullable=False, comment='One result per research session'),
        sa.Column('executive_summary', sa.Text(), nullable=False, comment='High-level findings summary'),
        sa.Column('report_content', postgresql.JSON(astext_type=sa.Text()), nullable=False, comment='Structured report with sections and citations'),
        sa.Column('total_sources', sa.Integer(), nullable=False, comment='Number of sources used'),
        sa.Column('total_findings', sa.Integer(), nullable=False, comment='Number of findings discovered'),
        sa.Column('confidence_score', sa.Float(), nullable=False, comment='Overall confidence in results (0.0-1.0)'),
        sa.Column('limitations', sa.Text(), nullable=True, comment='Known limitations or gaps in research'),
        sa.Column('export_formats', postgresql.JSON(astext_type=sa.Text()), nullable=True, comment='Available export options and metadata'),
        sa.ForeignKeyConstraint(['session_id'], ['deep_research_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id')
    )

    # Create deep_research_findings table
    op.create_table('deep_research_findings',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('branch_id', sa.UUID(), nullable=False, comment='Source branch that found this information'),
        sa.Column('content', sa.Text(), nullable=False, comment='Extracted content or summary'),
        sa.Column('relevance_score', sa.Float(), nullable=False, comment='AI-assessed relevance (0.0-1.0)'),
        sa.Column('content_type', sa.String(length=50), nullable=False, comment='Source type: article, academic, news, documentation'),
        sa.Column('language', sa.String(length=5), nullable=False, server_default=sa.text("'en'"), comment='Content language (ISO 639-1)'),
        sa.Column('word_count', sa.Integer(), nullable=False, comment='Length metric for content'),
        sa.ForeignKeyConstraint(['branch_id'], ['deep_research_branches.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create source_citations table
    op.create_table('source_citations',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('finding_id', sa.UUID(), nullable=False, comment='Parent finding this citation supports'),
        sa.Column('url', sa.Text(), nullable=False, comment='Original source URL'),
        sa.Column('title', sa.String(length=500), nullable=False, comment='Page or article title'),
        sa.Column('author', sa.String(length=200), nullable=True, comment='Author if available'),
        sa.Column('publish_date', sa.Date(), nullable=True, comment='Publication date if available'),
        sa.Column('access_date', sa.DateTime(timezone=True), nullable=False, comment='When source was accessed'),
        sa.Column('domain', sa.String(length=100), nullable=False, comment='Extracted domain name'),
        sa.Column('citation_format', sa.Text(), nullable=False, comment='Formatted citation string'),
        sa.Column('is_accessible', sa.Boolean(), nullable=False, server_default=sa.text('true'), comment='Whether URL is still accessible'),
        sa.ForeignKeyConstraint(['finding_id'], ['deep_research_findings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create performance indexes
    op.create_index('ix_deep_research_sessions_user_id', 'deep_research_sessions', ['user_id'])
    op.create_index('ix_deep_research_sessions_status', 'deep_research_sessions', ['status'])
    op.create_index('ix_deep_research_sessions_created_at', 'deep_research_sessions', ['created_at'])
    op.create_index('ix_deep_research_branches_session_id', 'deep_research_branches', ['session_id'])
    op.create_index('ix_deep_research_branches_status', 'deep_research_branches', ['status'])
    op.create_index('ix_deep_research_findings_branch_id', 'deep_research_findings', ['branch_id'])
    op.create_index('ix_deep_research_findings_relevance_score', 'deep_research_findings', ['relevance_score'])
    op.create_index('ix_source_citations_finding_id', 'source_citations', ['finding_id'])
    op.create_index('ix_source_citations_domain', 'source_citations', ['domain'])


def downgrade():
    # Drop tables in reverse order due to foreign key constraints
    op.drop_table('source_citations')
    op.drop_table('deep_research_findings')
    op.drop_table('deep_research_results')
    op.drop_table('deep_research_branches')
    op.drop_table('deep_research_plans')
    op.drop_table('deep_research_sessions')
    op.drop_table('deep_research_configurations')