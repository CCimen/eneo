"""
Copyright (c) 2025 Sundsvalls Kommun

This file is part of Eneo.
Licensed under the AGPL-3.0 License.
See LICENSE file in the project root for full license information.
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict


# Enums
class ResearchMode(str, Enum):
    """Research depth options."""
    quick = "quick"
    standard = "standard"
    deep = "deep"


class SessionStatus(str, Enum):
    """Research session status."""
    planning = "planning"
    pending_approval = "pending_approval"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class ExportFormat(str, Enum):
    """Available export formats from local-deep-research."""
    pdf = "pdf"
    markdown = "markdown"
    json = "json"
    txt = "txt"
    html = "html"


# Request Models
class CreateSessionRequest(BaseModel):
    """Request to create new research session."""
    query: str = Field(..., min_length=1, max_length=1000, description="Research query in natural language")
    mode: ResearchMode = Field(..., description="Research depth")
    assistant_id: UUID = Field(..., description="Assistant to use for research")
    space_id: Optional[UUID] = Field(None, description="Optional space context")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "Impact of AI adoption on municipal services",
                "mode": "deep",
                "assistant_id": "550e8400-e29b-41d4-a716-446655440000",
                "space_id": "550e8400-e29b-41d4-a716-446655440001"
            }
        }
    )


class ApprovePlanRequest(BaseModel):
    """Request to approve research plan."""
    approved: bool = Field(..., description="Whether to approve the plan")
    modifications: Optional[List[Dict[str, Any]]] = Field(None, description="Optional plan modifications")


class RegeneratePlanRequest(BaseModel):
    """Request to regenerate research plan with new query."""
    query: str = Field(..., description="New research query")


class ExportRequest(BaseModel):
    """Request to export research report."""
    format: ExportFormat = Field(..., description="Export format")
    include_citations: bool = Field(True, description="Include source citations")
    include_metadata: bool = Field(True, description="Include research metadata")


class UpdateConfigurationRequest(BaseModel):
    """Request to update research configuration."""
    max_breadth: Optional[int] = Field(None, ge=1, le=6, description="Parallel queries per level")
    max_depth: Optional[int] = Field(None, ge=1, le=3, description="Research tree depth")
    quick_timeout_seconds: Optional[int] = Field(None, ge=30, le=120, description="Quick mode timeout")
    standard_timeout_seconds: Optional[int] = Field(None, ge=60, le=300, description="Standard mode timeout")
    deep_timeout_seconds: Optional[int] = Field(None, ge=120, le=600, description="Deep mode timeout")
    sources_per_query: Optional[int] = Field(None, ge=1, le=20, description="Search results per query")
    enable_web_search: Optional[bool] = Field(None, description="Enable SearXNG integration")
    enable_academic_sources: Optional[bool] = Field(None, description="Include academic sources")


# Response Models
class ResearchSessionResponse(BaseModel):
    """Response for research session."""
    id: UUID
    query: str
    mode: ResearchMode
    status: SessionStatus
    assistant_id: UUID
    space_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    max_breadth: int
    max_depth: int
    timeout_minutes: int

    # Progress tracking fields
    progress_percentage: int = Field(0, description="Overall progress (0-100)")
    current_step: Optional[str] = Field(None, description="Current research step")
    sources_found: int = Field(0, description="Number of sources found")
    branches_complete: int = Field(0, description="Branches completed")
    total_branches: int = Field(0, description="Total branches planned")

    model_config = ConfigDict(from_attributes=True)


class ResearchBranch(BaseModel):
    """Research branch in plan."""
    id: str = Field(..., description="Branch identifier")
    parent: Optional[str] = Field(None, description="Parent branch ID")
    question: str = Field(..., description="Research question")
    type: str = Field(..., description="broad or deep")
    estimated_sources: int = Field(..., description="Expected sources")


class ResearchLevel(BaseModel):
    """Research level in plan."""
    level: int = Field(..., ge=1, le=3, description="Depth level")
    branches: List[ResearchBranch] = Field(..., description="Branches at this level")


class ResearchQuestions(BaseModel):
    """Structured research questions."""
    main_topic: str = Field(..., description="Primary research topic")
    levels: List[ResearchLevel] = Field(..., description="Research tree levels")


class ResearchPlanResponse(BaseModel):
    """Response for research plan."""
    id: UUID
    session_id: UUID
    questions: ResearchQuestions
    estimated_duration: int = Field(..., description="Expected runtime in seconds")
    estimated_sources: int = Field(..., description="Expected number of sources")
    approved: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Citation(BaseModel):
    """Source citation."""
    id: int
    title: str
    url: str
    author: Optional[str] = None
    publish_date: Optional[datetime] = None
    access_date: datetime
    domain: str


class ReportSubsection(BaseModel):
    """Report subsection."""
    title: str
    content: str
    citations: List[int] = Field(..., description="Citation reference numbers")


class ReportSection(BaseModel):
    """Report section."""
    title: str
    content: str
    subsections: List[ReportSubsection] = Field(default_factory=list)
    citations: List[int] = Field(..., description="Citation reference numbers")


class ReportMetadata(BaseModel):
    """Report metadata."""
    total_words: int
    research_duration: str = Field(..., description="Human readable duration")
    sources_by_type: Dict[str, int] = Field(..., description="Source type breakdown")


class ReportContent(BaseModel):
    """Structured report content."""
    sections: List[ReportSection]
    citations: List[Citation]
    metadata: ReportMetadata


class ResearchResultsResponse(BaseModel):
    """Response for research results."""
    id: UUID
    session_id: UUID
    executive_summary: str
    report_content: ReportContent
    total_sources: int
    total_findings: int
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    limitations: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResearchConfigurationResponse(BaseModel):
    """Response for research configuration."""
    id: UUID
    assistant_id: UUID
    max_breadth: int = Field(..., ge=1, le=6)
    max_depth: int = Field(..., ge=1, le=3)
    quick_timeout_seconds: int = Field(..., ge=30, le=120)
    standard_timeout_seconds: int = Field(..., ge=60, le=300)
    deep_timeout_seconds: int = Field(..., ge=120, le=600)
    sources_per_query: int = Field(..., ge=1, le=20)
    enable_web_search: bool
    enable_academic_sources: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SessionsListResponse(BaseModel):
    """Response for sessions list."""
    sessions: List[ResearchSessionResponse]
    pagination: Dict[str, Any] = Field(
        ...,
        description="Pagination info with page, limit, total, has_next"
    )


class ApprovalResponse(BaseModel):
    """Response for plan approval."""
    approved: bool
    message: str
    execution_started: bool


# Progress Update Models (WebSocket)
class ProgressUpdate(BaseModel):
    """WebSocket progress update."""
    session_id: UUID
    status: str = Field(..., description="planning, searching, synthesizing, complete")
    progress: int = Field(..., ge=0, le=100)
    current_step: str
    sources_found: int
    branches_complete: int
    total_branches: int
    timestamp: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": "550e8400-e29b-41d4-a716-446655440002",
                "status": "searching",
                "progress": 65,
                "current_step": "Searching branch_2_1: ROI studies",
                "sources_found": 18,
                "branches_complete": 4,
                "total_branches": 6,
                "timestamp": "2025-09-12T10:03:45Z"
            }
        }
    )