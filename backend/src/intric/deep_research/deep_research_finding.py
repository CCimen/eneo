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


class DeepResearchFinding(BasePublic):
    """
    Individual pieces of information discovered during research.
    
    Represents content extracted from sources with relevance scoring
    and metadata about the information quality and type.
    """
    __tablename__ = "deep_research_findings"

    # Parent branch
    branch_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("deep_research_branches.id", ondelete="CASCADE"),
        comment="Source branch that found this information"
    )

    # Content data
    content: Mapped[str] = mapped_column(
        sa.Text,
        comment="Extracted content or summary"
    )
    
    # Quality metrics
    relevance_score: Mapped[float] = mapped_column(
        sa.Float,
        comment="AI-assessed relevance (0.0-1.0)"
    )
    
    # Content classification
    content_type: Mapped[str] = mapped_column(
        sa.String(50),
        comment="Source type: article, academic, news, documentation"
    )
    language: Mapped[str] = mapped_column(
        sa.String(5),
        default="en",
        comment="Content language (ISO 639-1)"
    )
    word_count: Mapped[int] = mapped_column(
        comment="Length metric for content"
    )

    # Relationships
    branch: Mapped["DeepResearchBranch"] = relationship(back_populates="findings")
    citations: Mapped[list["SourceCitation"]] = relationship(
        back_populates="finding",
        cascade="all, delete-orphan",
        order_by="SourceCitation.created_at"
    )

    def __repr__(self) -> str:
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<DeepResearchFinding(relevance={self.relevance_score:.2f}, type='{self.content_type}', content='{content_preview}')>"

    @property
    def is_high_relevance(self) -> bool:
        """Check if finding has high relevance score (>= 0.7)."""
        return self.relevance_score >= 0.7

    @property
    def is_substantial(self) -> bool:
        """Check if finding has substantial content (>= 100 words)."""
        return self.word_count >= 100

    def get_primary_citation(self) -> Optional["SourceCitation"]:
        """Get the primary (first) citation for this finding."""
        return self.citations[0] if self.citations else None

    def get_citation_count(self) -> int:
        """Get the number of citations supporting this finding."""
        return len(self.citations)

    @classmethod
    def content_type_options(cls) -> list[str]:
        """Get valid content type options."""
        return ["article", "academic", "news", "documentation", "other"]