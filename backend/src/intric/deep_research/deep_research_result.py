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


class DeepResearchResult(BasePublic):
    """
    Final synthesized research report.
    
    Contains the complete research output with structured sections,
    citations, metadata, and export configuration.
    """
    __tablename__ = "deep_research_results"

    # One result per session
    session_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("deep_research_sessions.id", ondelete="CASCADE"),
        unique=True,
        comment="One result per research session"
    )

    # Report content
    executive_summary: Mapped[str] = mapped_column(
        sa.Text,
        comment="High-level findings summary"
    )
    report_content: Mapped[dict] = mapped_column(
        JSON,
        comment="Structured report with sections and citations"
    )

    # Research metrics
    total_sources: Mapped[int] = mapped_column(
        comment="Number of sources used"
    )
    total_findings: Mapped[int] = mapped_column(
        comment="Number of findings discovered"
    )
    confidence_score: Mapped[float] = mapped_column(
        sa.Float,
        comment="Overall confidence in results (0.0-1.0)"
    )

    # Quality indicators
    limitations: Mapped[Optional[str]] = mapped_column(
        sa.Text,
        nullable=True,
        comment="Known limitations or gaps in research"
    )

    # Export metadata
    export_formats: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Available export options and metadata"
    )

    # Relationships
    session: Mapped["DeepResearchSession"] = relationship(back_populates="result")

    def __repr__(self) -> str:
        return f"<DeepResearchResult(session_id={self.session_id}, sources={self.total_sources}, confidence={self.confidence_score:.2f})>"

    @property
    def is_high_confidence(self) -> bool:
        """Check if research has high confidence score (>= 0.8)."""
        return self.confidence_score >= 0.8

    @property
    def is_comprehensive(self) -> bool:
        """Check if research found substantial sources (>= 10)."""
        return self.total_sources >= 10

    @property
    def has_limitations(self) -> bool:
        """Check if research has documented limitations."""
        return self.limitations is not None and len(self.limitations.strip()) > 0

    def get_section_count(self) -> int:
        """Get the number of main sections in the report."""
        if not self.report_content or "sections" not in self.report_content:
            return 0
        return len(self.report_content["sections"])

    def get_citation_count(self) -> int:
        """Get the total number of citations in the report."""
        if not self.report_content or "citations" not in self.report_content:
            return 0
        return len(self.report_content["citations"])

    def get_word_count(self) -> int:
        """Get the total word count of the report."""
        if not self.report_content or "metadata" not in self.report_content:
            return 0
        return self.report_content["metadata"].get("total_words", 0)

    def get_research_duration(self) -> str:
        """Get human-readable research duration."""
        if not self.report_content or "metadata" not in self.report_content:
            return "Unknown"
        return self.report_content["metadata"].get("research_duration", "Unknown")

    def get_sources_by_type(self) -> dict:
        """Get breakdown of sources by type."""
        if not self.report_content or "metadata" not in self.report_content:
            return {}
        return self.report_content["metadata"].get("sources_by_type", {})

    def is_export_format_available(self, format_name: str) -> bool:
        """Check if a specific export format is available."""
        if not self.export_formats:
            return format_name in ["pdf", "markdown", "json", "txt", "html"]  # Default formats
        return format_name in self.export_formats