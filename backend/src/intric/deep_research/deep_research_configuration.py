"""
Copyright (c) 2025 Sundsvalls Kommun

This file is part of Eneo.
Licensed under the AGPL-3.0 License.
See LICENSE file in the project root for full license information.
"""

from uuid import UUID
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from intric.database.tables.base_class import BasePublic
from intric.database.tables.assistant_table import Assistants


class DeepResearchConfiguration(BasePublic):
    """
    Assistant-specific research settings configured by users.
    
    Controls research behavior including breadth, depth, timeouts,
    and search preferences for each assistant.
    """
    __tablename__ = "deep_research_configurations"

    # One configuration per assistant
    assistant_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey(Assistants.id, ondelete="CASCADE"),
        unique=True,
        comment="One configuration per assistant"
    )

    # Research scope settings
    max_breadth: Mapped[int] = mapped_column(
        default=3,
        comment="Parallel queries per level (1-6)"
    )
    max_depth: Mapped[int] = mapped_column(
        default=2,
        comment="Research tree depth (1-3)"
    )

    # Mode-specific timeouts (in seconds)
    quick_timeout_seconds: Mapped[int] = mapped_column(
        default=60,
        comment="Quick mode timeout"
    )
    standard_timeout_seconds: Mapped[int] = mapped_column(
        default=180,
        comment="Standard mode timeout"
    )
    deep_timeout_seconds: Mapped[int] = mapped_column(
        default=300,
        comment="Deep mode timeout"
    )

    # Search preferences
    sources_per_query: Mapped[int] = mapped_column(
        default=5,
        comment="Search results per query (1-20)"
    )
    enable_web_search: Mapped[bool] = mapped_column(
        default=True,
        comment="Enable SearXNG integration"
    )
    enable_academic_sources: Mapped[bool] = mapped_column(
        default=False,
        comment="Include academic search engines"
    )

    # Relationships (one-way only - don't modify existing core tables)
    assistant: Mapped["Assistants"] = relationship()

    def __repr__(self) -> str:
        return f"<DeepResearchConfiguration(assistant_id={self.assistant_id}, breadth={self.max_breadth}, depth={self.max_depth})>"

    def get_timeout_for_mode(self, mode: str) -> int:
        """Get timeout in seconds for the specified research mode."""
        timeouts = {
            "quick": self.quick_timeout_seconds,
            "standard": self.standard_timeout_seconds,
            "deep": self.deep_timeout_seconds
        }
        return timeouts.get(mode, self.standard_timeout_seconds)

    @property
    def is_valid_breadth(self) -> bool:
        """Validate breadth is within allowed range."""
        return 1 <= self.max_breadth <= 6

    @property
    def is_valid_depth(self) -> bool:
        """Validate depth is within allowed range."""
        return 1 <= self.max_depth <= 3

    @property
    def is_valid_sources_per_query(self) -> bool:
        """Validate sources per query is within allowed range."""
        return 1 <= self.sources_per_query <= 20