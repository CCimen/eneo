"""
Copyright (c) 2025 Sundsvalls Kommun

This file is part of Eneo.
Licensed under the AGPL-3.0 License.
See LICENSE file in the project root for full license information.
"""

from typing import Optional
from uuid import UUID
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSON

from intric.database.tables.base_class import BasePublic


class DeepResearchBranch(BasePublic):
    """
    Individual research paths within a session.
    
    Represents one branch of the research tree, tracking its progress,
    search queries, and findings discovered during execution.
    """
    __tablename__ = "deep_research_branches"

    # Parent session
    session_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("deep_research_sessions.id", ondelete="CASCADE"),
        comment="Parent research session"
    )

    # Branch identification
    branch_id: Mapped[str] = mapped_column(
        sa.String(50),
        comment="Identifier from plan (e.g., 'branch_1_1')"
    )
    parent_branch_id: Mapped[Optional[str]] = mapped_column(
        sa.String(50),
        nullable=True,
        comment="Parent branch for tree structure"
    )

    # Branch content
    question: Mapped[str] = mapped_column(
        sa.Text,
        comment="Research question for this branch"
    )
    level: Mapped[int] = mapped_column(
        comment="Depth level (1-3)"
    )
    branch_type: Mapped[str] = mapped_column(
        sa.String(20),
        comment="Search strategy: broad or deep"
    )

    # Progress tracking
    status: Mapped[str] = mapped_column(
        sa.String(20),
        default="pending",
        comment="Progress: pending, searching, completed, failed"
    )
    progress: Mapped[int] = mapped_column(
        default=0,
        comment="Completion percentage (0-100)"
    )
    sources_found: Mapped[int] = mapped_column(
        default=0,
        comment="Number of sources discovered"
    )

    # Search execution details
    search_queries: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        comment="List of actual search queries used"
    )

    # Timing
    started_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
        comment="When branch search started"
    )
    completed_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
        comment="When branch search finished"
    )

    # Error handling
    error_message: Mapped[Optional[str]] = mapped_column(
        sa.Text,
        nullable=True,
        comment="Error description if failed"
    )

    # Relationships
    session: Mapped["DeepResearchSession"] = relationship(back_populates="branches")
    findings: Mapped[list["DeepResearchFinding"]] = relationship(
        back_populates="branch",
        cascade="all, delete-orphan",
        order_by="DeepResearchFinding.relevance_score.desc()"
    )

    def __repr__(self) -> str:
        return f"<DeepResearchBranch(branch_id='{self.branch_id}', status='{self.status}', sources={self.sources_found})>"

    @property
    def is_completed(self) -> bool:
        """Check if branch research is completed."""
        return self.status == "completed"

    @property
    def is_failed(self) -> bool:
        """Check if branch research failed."""
        return self.status == "failed"

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate branch execution duration in seconds."""
        if self.started_at and self.completed_at:
            duration = self.completed_at - self.started_at
            return duration.total_seconds()
        return None

    @property
    def has_children(self) -> bool:
        """Check if this branch has child branches."""
        # This would require a query to find branches with this branch_id as parent
        # For now, return False - can be enhanced later
        return False

    def get_search_query_count(self) -> int:
        """Get the number of search queries executed for this branch."""
        if self.search_queries:
            return len(self.search_queries)
        return 0