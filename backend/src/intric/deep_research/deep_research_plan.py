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


class DeepResearchPlan(BasePublic):
    """
    Generated research plan awaiting user approval.
    
    Contains structured research questions organized in a tree pattern
    with breadth (parallel queries) and depth (follow-up questions).
    """
    __tablename__ = "deep_research_plans"

    # One plan per session
    session_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("deep_research_sessions.id", ondelete="CASCADE"),
        unique=True,
        comment="One plan per research session"
    )

    # Research plan structure
    questions: Mapped[dict] = mapped_column(
        JSON,
        comment="Structured research questions tree"
    )

    # Plan metadata
    estimated_duration: Mapped[int] = mapped_column(
        comment="Expected runtime in seconds"
    )
    estimated_sources: Mapped[int] = mapped_column(
        comment="Expected number of sources"
    )

    # Approval workflow
    approved: Mapped[bool] = mapped_column(
        default=False,
        comment="User approval status"
    )
    approved_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
        comment="Approval timestamp"
    )

    # Relationships
    session: Mapped["DeepResearchSession"] = relationship(back_populates="plan")

    def __repr__(self) -> str:
        status = "approved" if self.approved else "pending"
        return f"<DeepResearchPlan(session_id={self.session_id}, status={status}, sources={self.estimated_sources})>"

    @property
    def total_branches(self) -> int:
        """Count total number of research branches in the plan."""
        if not self.questions or "levels" not in self.questions:
            return 0
        
        total = 0
        for level in self.questions["levels"]:
            total += len(level.get("branches", []))
        return total

    @property
    def max_level(self) -> int:
        """Get the maximum depth level in the plan."""
        if not self.questions or "levels" not in self.questions:
            return 0
        
        return max(level.get("level", 0) for level in self.questions["levels"])

    def get_branches_for_level(self, level: int) -> list[dict]:
        """Get all branches for a specific depth level."""
        if not self.questions or "levels" not in self.questions:
            return []
        
        for level_data in self.questions["levels"]:
            if level_data.get("level") == level:
                return level_data.get("branches", [])
        return []

    def get_branch_by_id(self, branch_id: str) -> Optional[dict]:
        """Find a specific branch by its ID across all levels."""
        if not self.questions or "levels" not in self.questions:
            return None
        
        for level in self.questions["levels"]:
            for branch in level.get("branches", []):
                if branch.get("id") == branch_id:
                    return branch
        return None