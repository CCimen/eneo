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

from intric.database.tables.base_class import BasePublic
from intric.database.tables.tenant_table import Tenants
from intric.database.tables.users_table import Users
from intric.database.tables.spaces_table import Spaces
from intric.database.tables.assistant_table import Assistants


class DeepResearchSession(BasePublic):
    """
    Represents a single deep research request from start to completion.
    
    Tracks the lifecycle from initial query submission through plan generation,
    approval, execution, and final results.
    """
    __tablename__ = "deep_research_sessions"

    # Core research parameters
    query: Mapped[str] = mapped_column(sa.Text, comment="Original research query from user")
    mode: Mapped[str] = mapped_column(
        sa.String(20), 
        comment="Research depth: quick, standard, deep"
    )
    status: Mapped[str] = mapped_column(
        sa.String(20),
        default="planning",
        comment="Current state: planning, pending_approval, running, completed, failed, cancelled"
    )

    # Multi-tenant and user context
    tenant_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey(Tenants.id, ondelete="CASCADE"), 
        index=True,
        comment="Tenant isolation"
    )
    user_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey(Users.id, ondelete="CASCADE"),
        comment="User who initiated research"
    )
    space_id: Mapped[Optional[UUID]] = mapped_column(
        sa.ForeignKey(Spaces.id, ondelete="CASCADE"),
        nullable=True,
        comment="Optional space context"
    )
    assistant_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey(Assistants.id, ondelete="CASCADE"),
        comment="Assistant used for research"
    )

    # Execution tracking
    started_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
        comment="When research execution began"
    )
    completed_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
        comment="When research finished"
    )

    # Progress tracking fields
    progress_percentage: Mapped[int] = mapped_column(
        default=0,
        comment="Overall progress percentage (0-100)"
    )
    current_step: Mapped[Optional[str]] = mapped_column(
        sa.String(500),
        nullable=True,
        comment="Current research step description"
    )
    sources_found: Mapped[int] = mapped_column(
        default=0,
        comment="Number of sources discovered so far"
    )
    branches_complete: Mapped[int] = mapped_column(
        default=0,
        comment="Number of research branches completed"
    )
    total_branches: Mapped[int] = mapped_column(
        default=0,
        comment="Total number of research branches planned"
    )

    # Research configuration from assistant settings
    max_breadth: Mapped[int] = mapped_column(
        default=3,
        comment="Parallel queries per level (1-6)"
    )
    max_depth: Mapped[int] = mapped_column(
        default=2,
        comment="Research tree depth (1-3)"
    )
    timeout_minutes: Mapped[int] = mapped_column(
        default=3,
        comment="Research timeout based on mode"
    )

    # Relationships (one-way only - don't modify existing core tables)
    tenant: Mapped["Tenants"] = relationship()
    user: Mapped["Users"] = relationship()
    space: Mapped[Optional["Spaces"]] = relationship()
    assistant: Mapped["Assistants"] = relationship()

    # One-to-one relationships
    plan: Mapped[Optional["DeepResearchPlan"]] = relationship(
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan"
    )
    result: Mapped[Optional["DeepResearchResult"]] = relationship(
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan"
    )

    # One-to-many relationships
    branches: Mapped[list["DeepResearchBranch"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="DeepResearchBranch.created_at"
    )

    def __repr__(self) -> str:
        return f"<DeepResearchSession(id={self.id}, query='{self.query[:50]}...', status='{self.status}')>"

    @property
    def is_active(self) -> bool:
        """Check if research is currently running."""
        return self.status in ("planning", "pending_approval", "running")

    @property
    def is_completed(self) -> bool:
        """Check if research has finished successfully."""
        return self.status == "completed"

    @property
    def duration_minutes(self) -> Optional[float]:
        """Calculate research duration in minutes if completed."""
        if self.started_at and self.completed_at:
            duration = self.completed_at - self.started_at
            return duration.total_seconds() / 60
        return None