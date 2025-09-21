"""
Copyright (c) 2025 Sundsvalls Kommun

This file is part of Eneo.
Licensed under the AGPL-3.0 License.
See LICENSE file in the project root for full license information.
"""

from typing import Optional
from uuid import UUID
from urllib.parse import urlparse
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from intric.database.tables.base_class import BasePublic


class SourceCitation(BasePublic):
    """
    References to original sources with metadata.
    
    Tracks where information came from with proper attribution,
    access timestamps, and availability status.
    """
    __tablename__ = "source_citations"

    # Parent finding
    finding_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("deep_research_findings.id", ondelete="CASCADE"),
        comment="Parent finding this citation supports"
    )

    # Source identification
    url: Mapped[str] = mapped_column(
        sa.Text,
        comment="Original source URL"
    )
    title: Mapped[str] = mapped_column(
        sa.String(500),
        comment="Page or article title"
    )
    author: Mapped[Optional[str]] = mapped_column(
        sa.String(200),
        nullable=True,
        comment="Author if available"
    )

    # Publication metadata
    publish_date: Mapped[Optional[sa.Date]] = mapped_column(
        sa.Date,
        nullable=True,
        comment="Publication date if available"
    )
    access_date: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True),
        comment="When source was accessed"
    )

    # Derived metadata
    domain: Mapped[str] = mapped_column(
        sa.String(100),
        comment="Extracted domain name"
    )
    citation_format: Mapped[str] = mapped_column(
        sa.Text,
        comment="Formatted citation string"
    )

    # Availability tracking
    is_accessible: Mapped[bool] = mapped_column(
        default=True,
        comment="Whether URL is still accessible"
    )

    # Relationships
    finding: Mapped["DeepResearchFinding"] = relationship(back_populates="citations")

    def __repr__(self) -> str:
        return f"<SourceCitation(title='{self.title[:50]}...', domain='{self.domain}')>"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Auto-extract domain from URL
        if self.url and not self.domain:
            self.domain = self._extract_domain(self.url)
        # Auto-generate citation format if not provided
        if not self.citation_format:
            self.citation_format = self._generate_citation_format()

    def _extract_domain(self, url: str) -> str:
        """Extract domain name from URL."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www. prefix if present
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except Exception:
            return "unknown"

    def _generate_citation_format(self) -> str:
        """Generate a formatted citation string."""
        parts = []
        
        # Author (if available)
        if self.author:
            parts.append(f"{self.author}.")
        
        # Title
        if self.title:
            parts.append(f'"{self.title}"')
        
        # Publication date (if available)
        if self.publish_date:
            parts.append(f"({self.publish_date.year})")
        
        # URL and access date
        if self.url:
            parts.append(f"Retrieved from {self.url}")
        
        if self.access_date:
            access_str = self.access_date.strftime("%Y-%m-%d")
            parts.append(f"(accessed {access_str})")
        
        return " ".join(parts)

    @property
    def is_recent(self) -> bool:
        """Check if source was published recently (within last 2 years)."""
        if not self.publish_date:
            return False
        
        from datetime import date, timedelta
        two_years_ago = date.today() - timedelta(days=730)
        return self.publish_date >= two_years_ago

    @property
    def is_academic(self) -> bool:
        """Check if source appears to be from an academic domain."""
        academic_domains = ['.edu', '.ac.', 'scholar.', 'researchgate.', 'academia.edu']
        return any(domain in self.domain for domain in academic_domains)

    @property
    def is_government(self) -> bool:
        """Check if source is from a government domain."""
        gov_domains = ['.gov', '.se', '.eu', 'europa.eu']
        return any(domain in self.domain for domain in gov_domains)