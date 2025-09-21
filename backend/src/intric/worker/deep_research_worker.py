"""
Copyright (c) 2025 Sundsvalls Kommun

This file is part of Eneo.
Licensed under the AGPL-3.0 License.
See LICENSE file in the project root for full license information.
"""

import asyncio
import json
from typing import Dict, Any
from uuid import UUID
from datetime import datetime, timezone

from intric.main.logging import get_logger
from intric.main.config import SETTINGS
from intric.database.database import sessionmanager

from intric.deep_research.deep_research_service import DeepResearchService
from intric.deep_research.deep_research_session import DeepResearchSession
from intric.deep_research.deep_research_result import DeepResearchResult
from intric.deep_research.deep_research_branch import DeepResearchBranch
from intric.deep_research.deep_research_finding import DeepResearchFinding
from intric.deep_research.source_citation import SourceCitation

logger = get_logger(__name__)


async def generate_research_plan(session_id: UUID) -> bool:
    """
    Generate research plan using local-deep-research library.

    Args:
        session_id: Research session ID

    Returns:
        True if successful, False otherwise
    """
    logger.info(f"Worker: Starting plan generation for session {session_id}")

    try:
        # Configure library to use OpenAI before any imports
        import os
        os.environ['LDR_LLM_PROVIDER'] = 'openai'
        os.environ['LDR_LLM_MODEL'] = 'gpt-4o-mini'  # TODO: Make this configurable based on assistant settings
        if SETTINGS.openai_api_key:
            os.environ['OPENAI_API_KEY'] = SETTINGS.openai_api_key

        async with sessionmanager.session() as session:
            service = DeepResearchService(session)
            
            # Publish initial status
            await _publish_progress_update(session_id, {
                "status": "planning",
                "progress": 0,
                "current_step": "Generating research plan...",
                "sources_found": 0,
                "branches_complete": 0,
                "total_branches": 0
            })
            
            success = await service.generate_research_plan_impl(session_id)
            
            if success:
                logger.info(f"Worker: Plan generation successful for session {session_id}")
                # Publish success update
                await _publish_progress_update(session_id, {
                    "status": "pending_approval",
                    "progress": 100,
                    "current_step": "Research plan generated - awaiting approval",
                    "sources_found": 0,
                    "branches_complete": 0,
                    "total_branches": 0
                })
            else:
                logger.error(f"Worker: Plan generation failed for session {session_id}")
                # Publish failure update
                await _publish_progress_update(session_id, {
                    "status": "failed",
                    "progress": 0,
                    "current_step": "Failed to generate research plan",
                    "sources_found": 0,
                    "branches_complete": 0,
                    "total_branches": 0
                })
            
            return success
            
    except Exception as e:
        logger.error(f"Worker: Unexpected error in plan generation for session {session_id}: {e}", exc_info=True)
        
        # Publish failure update
        await _publish_progress_update(session_id, {
            "status": "failed",
            "progress": 0,
            "current_step": f"Plan generation error: {str(e)[:100]}",
            "sources_found": 0,
            "branches_complete": 0,
            "total_branches": 0
        })
        
        return False


async def execute_research(session_id: UUID) -> bool:
    """
    Execute research using local-deep-research library.

    This is the main research execution function that:
    1. Gets the approved research plan
    2. Executes research using local-deep-research
    3. Stores findings and citations
    4. Generates final report
    5. Publishes progress updates via WebSocket

    Args:
        session_id: Research session ID

    Returns:
        True if successful, False otherwise
    """
    logger.info(f"Starting research execution for session {session_id}")

    async with sessionmanager.session() as session:
        try:
            # Configure library to use OpenAI before importing
            import os
            os.environ['LDR_LLM_PROVIDER'] = 'openai'
            os.environ['LDR_LLM_MODEL'] = 'gpt-4o-mini'  # TODO: Make this configurable based on assistant settings
            if SETTINGS.openai_api_key:
                os.environ['OPENAI_API_KEY'] = SETTINGS.openai_api_key

            # Import local-deep-research library
            import local_deep_research
            from functools import partial

            service = DeepResearchService(session)

            # Get research session with plan
            research_session = await session.get(DeepResearchSession, session_id)
            if not research_session or not research_session.plan:
                logger.error(f"Session or plan not found: {session_id}")
                return False

            # Publish initial progress
            await _publish_progress_update(session_id, {
                "status": "searching",
                "progress": 0,
                "current_step": "Starting research execution",
                "sources_found": 0,
                "branches_complete": 0,
                "total_branches": research_session.plan.total_branches if hasattr(research_session.plan, 'total_branches') else 1
            })

            # Create progress callback wrapper
            def library_progress_callback(message: str, percentage: int = None, metadata: dict = None):
                """Callback for library progress updates."""
                if percentage is None:
                    percentage = 0

                asyncio.create_task(_publish_progress_update(session_id, {
                    "status": "searching",
                    "progress": percentage,
                    "current_step": message,
                    "sources_found": metadata.get('sources_found', 0) if metadata else 0,
                    "branches_complete": metadata.get('branches_complete', 0) if metadata else 0,
                    "total_branches": metadata.get('total_branches', 1) if metadata else 1
                }))

            # Run research using the correct library functions
            loop = asyncio.get_event_loop()

            if research_session.mode == "quick":
                research_result = await loop.run_in_executor(
                    None,
                    partial(
                        local_deep_research.quick_summary,
                        research_session.query,
                        search_tool="auto",
                        iterations=1,
                        questions_per_iteration=research_session.max_breadth or 1,
                        max_results=20,
                        max_filtered_results=5,
                        progress_callback=library_progress_callback
                    )
                )
            else:
                iterations = 2 if research_session.mode == "standard" else 3
                questions_per_iteration = research_session.max_breadth or 3

                research_result = await loop.run_in_executor(
                    None,
                    partial(
                        local_deep_research.generate_report,
                        research_session.query,
                        search_tool="auto",
                        iterations=iterations,
                        questions_per_iteration=questions_per_iteration,
                        searches_per_section=2,
                        max_results=50,
                        max_filtered_results=5,
                        progress_callback=library_progress_callback
                    )
                )
            
            # Store final results
            await _store_research_results(session, session_id, research_result)
            
            # Update session status
            research_session.status = "completed"
            research_session.completed_at = datetime.now(timezone.utc)
            await session.commit()
            
            # Final progress update
            await _publish_progress_update(session_id, {
                "status": "complete",
                "progress": 100,
                "current_step": "Research completed",
                "sources_found": research_result.get("total_sources", 0),
                "branches_complete": research_session.plan.total_branches,
                "total_branches": research_session.plan.total_branches
            })
            
            logger.info(f"Research execution completed for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Research execution failed for session {session_id}: {e}")
            
            # Update session to failed state
            research_session = await session.get(DeepResearchSession, session_id)
            if research_session:
                research_session.status = "failed"
                research_session.completed_at = datetime.now(timezone.utc)
                await session.commit()
            
            # Publish failure update
            await _publish_progress_update(session_id, {
                "status": "failed",
                "progress": 0,
                "current_step": f"Research failed: {str(e)}",
                "sources_found": 0,
                "branches_complete": 0,
                "total_branches": 0
            })
            
            return False


async def _publish_progress_update(session_id: UUID, update: Dict[str, Any]):
    """Publish progress update via WebSocket."""
    try:
        # For now, just log the progress update
        # TODO: Implement WebSocket publishing once WebSocket manager is available
        logger.info(f"Progress update for session {session_id}: {update}")
        
    except Exception as e:
        logger.warning(f"Failed to publish progress update: {e}")


async def _store_branch_progress(
    session,
    session_id: UUID,
    update: Dict[str, Any]
):
    """Store branch progress in database."""
    try:
        branch_id = update.get("current_branch_id")
        if not branch_id:
            return
        
        # Find or create branch record
        branch = await session.query(DeepResearchBranch).filter(
            DeepResearchBranch.session_id == session_id,
            DeepResearchBranch.branch_id == branch_id
        ).first()
        
        if not branch:
            # Create new branch record
            branch = DeepResearchBranch(
                session_id=session_id,
                branch_id=branch_id,
                question=update.get("current_step", ""),
                level=update.get("level", 1),
                branch_type=update.get("branch_type", "broad"),
                status="searching" if update.get("progress", 0) < 100 else "completed",
                progress=update.get("progress", 0),
                sources_found=update.get("sources_found", 0)
            )
            session.add(branch)
        else:
            # Update existing branch
            branch.status = "searching" if update.get("progress", 0) < 100 else "completed"
            branch.progress = update.get("progress", 0)
            branch.sources_found = update.get("sources_found", 0)
            
            if branch.status == "completed" and not branch.completed_at:
                branch.completed_at = datetime.now(timezone.utc)
        
        await session.commit()
        
    except Exception as e:
        logger.warning(f"Failed to store branch progress: {e}")


async def _store_research_results(
    session,
    session_id: UUID,
    research_result: Dict[str, Any]
):
    """Store final research results in database."""
    try:
        # Create result record
        result = DeepResearchResult(
            session_id=session_id,
            executive_summary=research_result.get("executive_summary", ""),
            report_content=research_result.get("report_content", {}),
            total_sources=research_result.get("total_sources", 0),
            total_findings=research_result.get("total_findings", 0),
            confidence_score=research_result.get("confidence_score", 0.0),
            limitations=research_result.get("limitations"),
            export_formats={
                "pdf": True,
                "markdown": True,
                "json": True,
                "txt": True,
                "html": True
            }
        )
        
        session.add(result)
        
        # Store findings and citations
        for finding_data in research_result.get("findings", []):
            finding = DeepResearchFinding(
                branch_id=finding_data.get("branch_id"),  # This would need proper mapping
                content=finding_data.get("content", ""),
                relevance_score=finding_data.get("relevance_score", 0.0),
                content_type=finding_data.get("content_type", "article"),
                language=finding_data.get("language", "en"),
                word_count=len(finding_data.get("content", "").split())
            )
            
            session.add(finding)
            await session.flush()  # Get finding ID
            
            # Store citations for this finding
            for citation_data in finding_data.get("citations", []):
                citation = SourceCitation(
                    finding_id=finding.id,
                    url=citation_data.get("url", ""),
                    title=citation_data.get("title", ""),
                    author=citation_data.get("author"),
                    access_date=datetime.now(timezone.utc),
                    domain=citation_data.get("domain", ""),
                    citation_format=citation_data.get("citation_format", "")
                )
                session.add(citation)
        
        await session.commit()
        logger.info(f"Stored research results for session {session_id}")
        
    except Exception as e:
        logger.error(f"Failed to store research results: {e}")
        raise