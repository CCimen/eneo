"""
Copyright (c) 2025 Sundsvalls Kommun

This file is part of Eneo.
Licensed under the AGPL-3.0 License.
See LICENSE file in the project root for full license information.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession

from intric.main.logging import get_logger
from intric.database.database import get_session_with_transaction
from intric.users.user import UserInDB
from intric.authentication.auth_dependencies import get_current_active_user

from ..deep_research_service import DeepResearchService
from .deep_research_models import (
    CreateSessionRequest,
    ResearchSessionResponse,
    SessionsListResponse,
    ResearchPlanResponse,
    ApprovePlanRequest,
    RegeneratePlanRequest,
    ApprovalResponse,
    ResearchResultsResponse,
    ExportRequest,
    ResearchConfigurationResponse,
    UpdateConfigurationRequest,
    SessionStatus,
    ExportFormat
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/research", tags=["Deep Research"])


@router.post("/sessions", response_model=ResearchSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_research_session(
    request: CreateSessionRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session_with_transaction)
):
    """
    Create a new deep research session.
    
    The system will generate a research plan for user approval before execution.
    """
    logger.info(
        f"API: Creating research session for user {current_user.id}, "
        f"query='{request.query[:50]}...', mode={request.mode}, assistant={request.assistant_id}"
    )
    
    service = DeepResearchService(session)
    
    try:
        research_session = await service.create_research_session(
            query=request.query,
            mode=request.mode.value,
            assistant_id=request.assistant_id,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            space_id=request.space_id
        )
        
        logger.info(f"API: Research session created successfully: {research_session.id}")
        return ResearchSessionResponse.model_validate(research_session)
        
    except ValueError as e:
        logger.warning(f"API: Invalid request from user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except RuntimeError as e:
        logger.error(f"API: Runtime error creating session for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"API: Unexpected error creating research session for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the research session"
        )


@router.get("/sessions", response_model=SessionsListResponse)
async def list_research_sessions(
    page: int = 1,
    limit: int = 20,
    status_filter: Optional[SessionStatus] = None,
    space_id: Optional[UUID] = None,
    current_user: UserInDB = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session_with_transaction)
):
    """Get paginated list of research sessions for current user."""
    if page < 1:
        raise HTTPException(status_code=400, detail="Page must be >= 1")
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="Limit must be between 1 and 100")
    
    service = DeepResearchService(session)
    offset = (page - 1) * limit
    
    sessions = await service.list_research_sessions(
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        space_id=space_id,
        status=status_filter.value if status_filter else None,
        limit=limit,
        offset=offset
    )
    
    # Simple pagination info (could be enhanced with total count)
    pagination = {
        "page": page,
        "limit": limit,
        "total": len(sessions),  # This is just current page count
        "has_next": len(sessions) == limit  # Approximate
    }
    
    return SessionsListResponse(
        sessions=[ResearchSessionResponse.model_validate(s) for s in sessions],
        pagination=pagination
    )


@router.get("/sessions/{session_id}", response_model=ResearchSessionResponse)
async def get_research_session(
    session_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session_with_transaction)
):
    """Get research session details."""
    service = DeepResearchService(session)
    
    research_session = await service.get_research_session(
        session_id=session_id,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id
    )
    
    if not research_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research session not found"
        )
    
    return ResearchSessionResponse.model_validate(research_session)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_research_session(
    session_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session_with_transaction)
):
    """Cancel an active research session."""
    service = DeepResearchService(session)
    
    cancelled = await service.cancel_research_session(
        session_id=session_id,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id
    )
    
    if not cancelled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research session not found or cannot be cancelled"
        )


@router.get("/sessions/{session_id}/plan", response_model=ResearchPlanResponse)
async def get_research_plan(
    session_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session_with_transaction)
):
    """Get research plan for approval."""
    service = DeepResearchService(session)
    
    research_session = await service.get_research_session(
        session_id=session_id,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id
    )
    
    if not research_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research session not found"
        )
    
    if not research_session.plan:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Research plan not ready yet"
        )
    
    return ResearchPlanResponse.model_validate(research_session.plan)


@router.post("/sessions/{session_id}/approve", response_model=ApprovalResponse)
async def approve_research_plan(
    session_id: UUID,
    request: ApprovePlanRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session_with_transaction)
):
    """Approve research plan and start execution."""
    service = DeepResearchService(session)
    
    execution_started = await service.approve_research_plan(
        session_id=session_id,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        approved=request.approved
    )
    
    if execution_started:
        return ApprovalResponse(
            approved=True,
            message="Research plan approved. Execution started.",
            execution_started=True
        )
    elif request.approved:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research session or plan not found"
        )
    else:
        return ApprovalResponse(
            approved=False,
            message="Research plan rejected. Back to planning.",
            execution_started=False
        )


@router.put("/sessions/{session_id}/regenerate-plan", response_model=ResearchPlanResponse)
async def regenerate_research_plan(
    session_id: UUID,
    request: RegeneratePlanRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session_with_transaction)
):
    """Regenerate research plan with updated query."""
    service = DeepResearchService(session)

    # Update session query and regenerate plan
    new_plan = await service.regenerate_plan(
        session_id=session_id,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        new_query=request.query
    )

    if new_plan:
        return ResearchPlanResponse(**new_plan)
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research session not found"
        )


@router.get("/sessions/{session_id}/results", response_model=ResearchResultsResponse)
async def get_research_results(
    session_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session_with_transaction)
):
    """Get completed research results."""
    service = DeepResearchService(session)
    
    research_session = await service.get_research_session(
        session_id=session_id,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id
    )
    
    if not research_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research session not found"
        )
    
    if not research_session.result:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Research not completed yet"
        )
    
    return ResearchResultsResponse.model_validate(research_session.result)


@router.post("/sessions/{session_id}/export")
async def export_research_report(
    session_id: UUID,
    request: ExportRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session_with_transaction)
):
    """Export research report in specified format."""
    service = DeepResearchService(session)
    
    exported_data = await service.export_research_report(
        session_id=session_id,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        format_type=request.format.value,
        include_citations=request.include_citations,
        include_metadata=request.include_metadata
    )
    
    if not exported_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research session not found or results not available"
        )
    
    # Set appropriate content type and filename
    content_types = {
        ExportFormat.pdf: "application/pdf",
        ExportFormat.markdown: "text/markdown",
        ExportFormat.json: "application/json",
        ExportFormat.txt: "text/plain",
        ExportFormat.html: "text/html"
    }
    
    extensions = {
        ExportFormat.pdf: "pdf",
        ExportFormat.markdown: "md",
        ExportFormat.json: "json",
        ExportFormat.txt: "txt",
        ExportFormat.html: "html"
    }
    
    content_type = content_types.get(request.format, "application/octet-stream")
    extension = extensions.get(request.format, "bin")
    filename = f"research_report_{session_id}.{extension}"
    
    return Response(
        content=exported_data,
        media_type=content_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/configurations/{assistant_id}", response_model=ResearchConfigurationResponse)
async def get_research_configuration(
    assistant_id: UUID,
    current_user: UserInDB = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session_with_transaction)
):
    """Get research configuration for assistant."""
    service = DeepResearchService(session)
    
    # TODO: Add authorization check that user can access this assistant
    
    config = await service.get_or_create_configuration(assistant_id)
    return ResearchConfigurationResponse.model_validate(config)


@router.put("/configurations/{assistant_id}", response_model=ResearchConfigurationResponse)
async def update_research_configuration(
    assistant_id: UUID,
    request: UpdateConfigurationRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session_with_transaction)
):
    """Update research configuration for assistant."""
    service = DeepResearchService(session)
    
    # TODO: Add authorization check that user can modify this assistant
    
    # Convert request to dict, excluding None values
    config_data = request.model_dump(exclude_none=True)
    
    config = await service.update_configuration(assistant_id, config_data)
    return ResearchConfigurationResponse.model_validate(config)