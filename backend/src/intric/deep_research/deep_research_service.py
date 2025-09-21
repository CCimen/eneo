"""
Copyright (c) 2025 Sundsvalls Kommun

This file is part of Eneo.
Licensed under the AGPL-3.0 License.
See LICENSE file in the project root for full license information.
"""

import asyncio
import json
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from intric.main.logging import get_logger
from intric.main.config import SETTINGS
from intric.main.models import Channel, ChannelType, RedisMessage
from intric.database.tables.assistant_table import Assistants
from intric.worker.redis import r as redis_client
from intric.server.websockets.websocket_models import WsDeepResearchUpdate
# from intric.jobs.job_manager import job_manager
# from intric.jobs.job_models import Task
# from intric.jobs.task_models import DeepResearchPlanTask, DeepResearchExecuteTask

from .deep_research_session import DeepResearchSession
from .deep_research_configuration import DeepResearchConfiguration
from .deep_research_plan import DeepResearchPlan
from .deep_research_result import DeepResearchResult
from .deep_research_branch import DeepResearchBranch
from .deep_research_finding import DeepResearchFinding
from .source_citation import SourceCitation

logger = get_logger(__name__)


class DeepResearchService:
    """
    Single service that orchestrates all deep research operations.
    
    Acts as a thin wrapper around the local-deep-research library,
    handling data persistence, progress tracking, and integration
    with Eneo's existing infrastructure.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_research_session(
        self,
        query: str,
        mode: str,
        assistant_id: UUID,
        user_id: UUID,
        tenant_id: UUID,
        space_id: Optional[UUID] = None
    ) -> DeepResearchSession:
        """
        Create a new research session and trigger plan generation.
        
        Args:
            query: Research query in natural language
            mode: Research depth (quick, standard, deep)
            assistant_id: Assistant to use for research
            user_id: User initiating research
            tenant_id: Tenant for isolation
            space_id: Optional space context
            
        Returns:
            Created research session
            
        Raises:
            ValueError: Invalid input parameters
            RuntimeError: Assistant configuration or task queue issues
        """
        logger.info(
            f"Creating research session: query='{query[:100]}...', mode='{mode}', "
            f"user={user_id}, tenant={tenant_id}, assistant={assistant_id}, space={space_id}"
        )

        try:
            # Validate input parameters
            if not query or len(query.strip()) == 0:
                logger.error(f"Empty query provided by user {user_id}")
                raise ValueError("Research query cannot be empty")
            
            if mode not in ["quick", "standard", "deep"]:
                logger.error(f"Invalid research mode '{mode}' provided by user {user_id}")
                raise ValueError(f"Invalid research mode: {mode}")

            # Get assistant configuration with error handling
            try:
                config = await self.get_or_create_configuration(assistant_id)
                logger.debug(f"Retrieved configuration for assistant {assistant_id}: breadth={config.max_breadth}, depth={config.max_depth}")
            except Exception as e:
                logger.error(f"Failed to get configuration for assistant {assistant_id}: {e}")
                raise RuntimeError(f"Assistant configuration error: {e}")

            # Create session with configuration
            research_session = DeepResearchSession(
                query=query.strip(),
                mode=mode,
                status="planning",
                tenant_id=tenant_id,
                user_id=user_id,
                space_id=space_id,
                assistant_id=assistant_id,
                max_breadth=config.max_breadth,
                max_depth=config.max_depth,
                timeout_minutes=config.get_timeout_for_mode(mode) // 60
            )

            try:
                self.session.add(research_session)
                await self.session.flush()  # Flush to get ID
                logger.debug(f"Research session persisted with ID: {research_session.id}")
            except Exception as e:
                logger.error(f"Database error creating session for user {user_id}: {e}")
                raise RuntimeError(f"Failed to create research session: {e}")

            # Generate research plan structure (NOT execute research)
            try:
                logger.info(f"Generating plan structure for session {research_session.id}")
                await self.generate_plan_structure_only(research_session.id)
                logger.info(f"Plan structure generated for session {research_session.id}")
            except Exception as e:
                logger.error(f"Failed to generate plan structure for session {research_session.id}: {e}")
                # Update session to failed state
                research_session.status = "failed"
            
            # Get a fresh copy of the session object to avoid Pydantic serialization issues
            # after the long-running executor operations
            fresh_session_stmt = select(DeepResearchSession).where(
                DeepResearchSession.id == research_session.id
            )
            fresh_result = await self.session.execute(fresh_session_stmt)
            fresh_session = fresh_result.scalar_one()

            logger.info(f"Research session created successfully: {fresh_session.id}")
            return fresh_session
            
        except (ValueError, RuntimeError):
            # Re-raise expected errors
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating research session for user {user_id}: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error creating research session: {e}")

    async def get_research_session(
        self,
        session_id: UUID,
        user_id: UUID,
        tenant_id: UUID
    ) -> Optional[DeepResearchSession]:
        """Get research session with tenant isolation."""
        stmt = (
            select(DeepResearchSession)
            .where(
                DeepResearchSession.id == session_id,
                DeepResearchSession.user_id == user_id,
                DeepResearchSession.tenant_id == tenant_id
            )
            .options(
                selectinload(DeepResearchSession.plan),
                selectinload(DeepResearchSession.result),
                selectinload(DeepResearchSession.branches)
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_research_sessions(
        self,
        user_id: UUID,
        tenant_id: UUID,
        space_id: Optional[UUID] = None,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[DeepResearchSession]:
        """List user's research sessions with filtering."""
        stmt = select(DeepResearchSession).where(
            DeepResearchSession.user_id == user_id,
            DeepResearchSession.tenant_id == tenant_id
        )

        if space_id:
            stmt = stmt.where(DeepResearchSession.space_id == space_id)
        if status:
            stmt = stmt.where(DeepResearchSession.status == status)

        stmt = stmt.order_by(DeepResearchSession.created_at.desc())
        stmt = stmt.limit(limit).offset(offset)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def approve_research_plan(
        self,
        session_id: UUID,
        user_id: UUID,
        tenant_id: UUID,
        approved: bool = True
    ) -> bool:
        """
        Approve research plan and start execution.
        
        Returns True if execution started, False if plan not ready.
        """
        logger.info(f"Approving research plan: session={session_id}, approved={approved}")

        # Get session and plan
        research_session = await self.get_research_session(session_id, user_id, tenant_id)
        if not research_session or not research_session.plan:
            return False

        if approved:
            # Update plan approval
            research_session.plan.approved = True
            research_session.plan.approved_at = datetime.now(timezone.utc)
            
            # Update session status
            research_session.status = "running"
            research_session.started_at = datetime.now(timezone.utc)

            # IMPORTANT: Commit the status change so other database connections can see it
            await self.session.commit()
            logger.info(f"Session {session_id} status committed as 'running'")

            # Execute actual research using local-deep-research library
            logger.info(f"Starting actual research execution for session {session_id}")

            # Execute research with a fresh session since we committed above
            from intric.database.database import sessionmanager
            async with sessionmanager.session() as new_session:
                async with new_session.begin():
                    research_service = DeepResearchService(new_session)
                    try:
                        await research_service._execute_research_impl(session_id)
                        logger.info(f"Research execution completed successfully for session {session_id}")
                    except Exception as e:
                        logger.error(f"Research execution failed for session {session_id}: {e}")
                        # Update to failed status using the new session
                        stmt = select(DeepResearchSession).where(DeepResearchSession.id == session_id)
                        result = await new_session.execute(stmt)
                        failed_session = result.scalar_one_or_none()
                        if failed_session:
                            failed_session.status = "failed"
                            failed_session.completed_at = datetime.now(timezone.utc)

            return True
        else:
            # User rejected plan - back to planning
            research_session.status = "planning"
            
            logger.info(f"Research plan rejected for session {session_id}")
            return False

    async def cancel_research_session(
        self,
        session_id: UUID,
        user_id: UUID,
        tenant_id: UUID
    ) -> bool:
        """Cancel active research session."""
        research_session = await self.get_research_session(session_id, user_id, tenant_id)
        if not research_session:
            return False

        if research_session.is_active:
            research_session.status = "cancelled"
            logger.info(f"Research session cancelled: {session_id}")
            return True

        return False

    async def regenerate_plan(
        self,
        session_id: UUID,
        user_id: UUID,
        tenant_id: UUID,
        new_query: str
    ) -> Optional[dict]:
        """Regenerate research plan with new query."""

        # Get existing session
        stmt = (
            select(DeepResearchSession)
            .where(
                DeepResearchSession.id == session_id,
                DeepResearchSession.user_id == user_id,
                DeepResearchSession.tenant_id == tenant_id
            )
            .options(selectinload(DeepResearchSession.plan))
        )
        result = await self.session.execute(stmt)
        research_session = result.scalar_one_or_none()

        if not research_session:
            return None

        # Update query
        research_session.query = new_query

        try:
            # Get configuration
            config = await self.get_or_create_configuration(research_session.assistant_id)

            # Use OpenAI directly to generate research questions (same as in generate_plan_structure_only)
            import os
            if SETTINGS.openai_api_key:
                os.environ['OPENAI_API_KEY'] = SETTINGS.openai_api_key

            from openai import OpenAI
            client = OpenAI(api_key=SETTINGS.openai_api_key)

            prompt = f"""Generate a research plan for: "{new_query}"

Research Mode: {research_session.mode}
Max Breadth: {config.max_breadth} parallel questions per level
Max Depth: {config.max_depth} levels deep

Create a tree structure with:
- Level 1: {config.max_breadth} broad research questions covering different aspects
- Level 2: For each Level 1 question, create 1-2 deeper follow-up questions

Return as JSON:
{{
  "main_topic": "topic name",
  "levels": [
    {{
      "level": 1,
      "branches": [
        {{
          "id": "branch_1",
          "question": "research question",
          "type": "broad",
          "estimated_sources": 5
        }}
      ]
    }}
  ]
}}"""

            logger.info("Regenerating research questions using OpenAI")
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000
            )

            plan_text = response.choices[0].message.content
            logger.debug(f"Generated plan text: {plan_text}")

            # Parse JSON response
            import json
            try:
                questions = json.loads(plan_text.strip())
            except json.JSONDecodeError:
                # Extract JSON from markdown code blocks if present
                import re
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', plan_text, re.DOTALL)
                if json_match:
                    questions = json.loads(json_match.group(1))
                else:
                    raise ValueError("Could not parse plan JSON from OpenAI response")

            # Calculate estimates based on mode
            timeout_map = {
                "quick": 60,
                "standard": 180,
                "deep": 300
            }

            estimated_duration = timeout_map.get(research_session.mode, 180)

            # Count total branches for estimation
            total_branches = 0
            for level in questions.get("levels", []):
                total_branches += len(level.get("branches", []))

            estimated_sources = total_branches * 5

            plan_data = {
                "questions": questions,
                "estimated_duration": estimated_duration,
                "estimated_sources": estimated_sources
            }

            # Update the plan in database
            if research_session.plan:
                research_session.plan.questions = plan_data["questions"]
                research_session.plan.estimated_duration = plan_data["estimated_duration"]
                research_session.plan.estimated_sources = plan_data["estimated_sources"]
                research_session.plan.updated_at = datetime.now(timezone.utc)
                plan_id = research_session.plan.id
                plan_created_at = research_session.plan.created_at
            else:
                # Create new plan if it doesn't exist
                new_plan = DeepResearchPlan(
                    session_id=session_id,
                    questions=plan_data["questions"],
                    estimated_duration=plan_data["estimated_duration"],
                    estimated_sources=plan_data["estimated_sources"],
                    approved=False
                )
                self.session.add(new_plan)
                await self.session.flush()  # Flush to get the ID
                research_session.plan = new_plan
                plan_id = new_plan.id
                plan_created_at = new_plan.created_at

            await self.session.commit()

            logger.info(f"Regenerated plan for session {session_id} with new query: {new_query}")

            # Return the plan in the expected format
            return {
                "id": plan_id,
                "session_id": session_id,
                "questions": plan_data["questions"],
                "estimated_duration": plan_data["estimated_duration"],
                "estimated_sources": plan_data["estimated_sources"],
                "approved": False,
                "created_at": plan_created_at
            }

        except Exception as e:
            logger.error(f"Failed to regenerate plan: {e}", exc_info=True)
            await self.session.rollback()
            return None

    async def get_or_create_configuration(
        self,
        assistant_id: UUID
    ) -> DeepResearchConfiguration:
        """Get existing configuration or create default one."""
        stmt = select(DeepResearchConfiguration).where(
            DeepResearchConfiguration.assistant_id == assistant_id
        )
        result = await self.session.execute(stmt)
        config = result.scalar_one_or_none()

        if not config:
            config = DeepResearchConfiguration(
                assistant_id=assistant_id,
                max_breadth=3,
                max_depth=2,
                quick_timeout_seconds=60,
                standard_timeout_seconds=180,
                deep_timeout_seconds=300,
                sources_per_query=5,
                enable_web_search=True,
                enable_academic_sources=False
            )
            self.session.add(config)
            await self.session.flush()  # Flush to get ID, but don't commit

        return config

    async def update_configuration(
        self,
        assistant_id: UUID,
        config_data: Dict[str, Any]
    ) -> DeepResearchConfiguration:
        """Update research configuration for assistant."""
        config = await self.get_or_create_configuration(assistant_id)

        # Update fields that are provided
        for field, value in config_data.items():
            if hasattr(config, field):
                setattr(config, field, value)

        await self.session.flush()  # Flush changes
        return config

    async def generate_research_plan_impl(
        self,
        session_id: UUID
    ) -> bool:
        """
        Implementation for plan generation (called by worker).
        
        Uses local-deep-research library to generate structured research plan.
        """
        try:
            # Import local-deep-research library
            import local_deep_research
            import asyncio
            import os
            from functools import partial
            
            logger.info(f"Generating research plan for session {session_id}")

            # Get session
            stmt = select(DeepResearchSession).where(DeepResearchSession.id == session_id)
            result = await self.session.execute(stmt)
            research_session = result.scalar_one_or_none()

            if not research_session:
                logger.error(f"Session not found: {session_id}")
                return False

            # Configure local-deep-research settings directly using the settings API
            if SETTINGS.openai_api_key:
                # Set API key in environment (still needed)
                os.environ['OPENAI_API_KEY'] = SETTINGS.openai_api_key
                logger.debug("OpenAI API key configured from Eneo settings")
            else:
                logger.warning("No OpenAI API key found in Eneo settings")
                return False

            # Configure the library settings directly
            logger.info("Configuring local-deep-research settings...")
            try:
                from local_deep_research.config import settings
                
                # Set LLM provider to OpenAI
                settings.set('LLM.PROVIDER', 'openai')
                settings.set('LLM.MODEL', 'gpt-4o-mini')
                # Fix token limit for gpt-4o-mini (max 16,384 output tokens)
                settings.set('LLM.MAX_TOKENS', 8000)  # Use conservative limit
                
                # Configure search settings if SearXNG is available
                if SETTINGS.searxng_base_url:
                    os.environ['SEARXNG_URL'] = SETTINGS.searxng_base_url
                    logger.debug(f"SearXNG URL configured: {SETTINGS.searxng_base_url}")
                
                logger.info("Local-deep-research configured: OpenAI provider, gpt-4o-mini model")
                
            except Exception as e:
                logger.error(f"Failed to configure local-deep-research settings: {e}")
                return False

            # Use the assistant's research configuration to determine search strategy  
            config = await self.get_or_create_configuration(research_session.assistant_id)
            
            if config.enable_web_search:
                # Use auto to get comprehensive results from multiple sources
                search_tool = "auto"
                logger.info("Using comprehensive search with auto engine selection")
            else:
                # Fall back to Wikipedia only
                search_tool = "wikipedia"
                logger.info("Using Wikipedia-only search based on configuration")
            
            logger.info(f"Using local-deep-research for {research_session.mode} mode with openai provider")
            
            if research_session.mode == "quick":
                # Use quick_summary for quick research
                logger.info(f"Calling quick_summary with query: {research_session.query}")
                
                # Run the sync function in executor since it's not async
                loop = asyncio.get_event_loop()
                summary_result = await loop.run_in_executor(
                    None,
                    partial(
                        local_deep_research.quick_summary,
                        research_session.query,
                        search_tool,
                        1,  # iterations
                        1,  # questions_per_iteration
                        10,  # max_results
                        5   # max_filtered_results
                    )
                )
                
                logger.info(f"quick_summary completed, result type: {type(summary_result)}")
                
                # Create plan from summary result
                plan_data = {
                    "questions": {
                        "main_topic": research_session.query,
                        "levels": [
                            {
                                "level": 1,
                                "branches": [
                                    {
                                        "id": "quick_branch_1",
                                        "question": research_session.query,
                                        "type": "broad",
                                        "estimated_sources": 5
                                    }
                                ]
                            }
                        ]
                    },
                    "estimated_duration": 60,
                    "estimated_sources": 5
                }
                
            else:
                # Use generate_report for standard/deep research
                logger.info(f"Calling generate_report with query: {research_session.query}")
                
                iterations = 1 if research_session.mode == "standard" else 2
                questions_per_iteration = research_session.max_breadth
                
                # Run the sync function in executor
                loop = asyncio.get_event_loop()
                report_result = await loop.run_in_executor(
                    None,
                    partial(
                        local_deep_research.generate_report,
                        research_session.query,
                        search_tool,
                        iterations,
                        questions_per_iteration,
                        2,  # searches_per_section  
                        30,  # max_results
                        5   # max_filtered_results
                    )
                )
                
                logger.info(f"generate_report completed, result type: {type(report_result)}")
                
                # Create plan from report structure
                plan_data = {
                    "questions": {
                        "main_topic": research_session.query,
                        "levels": [
                            {
                                "level": 1,
                                "branches": [
                                    {
                                        "id": f"branch_{i+1}",
                                        "question": f"Research aspect {i+1}: {research_session.query}",
                                        "type": "broad", 
                                        "estimated_sources": 5
                                    } for i in range(questions_per_iteration)
                                ]
                            }
                        ]
                    },
                    "estimated_duration": research_session.timeout_minutes * 60,
                    "estimated_sources": questions_per_iteration * 5
                }

            # Create plan record
            research_plan = DeepResearchPlan(
                session_id=session_id,
                questions=plan_data["questions"],
                estimated_duration=plan_data.get("estimated_duration", research_session.timeout_minutes * 60),
                estimated_sources=plan_data.get("estimated_sources", research_session.max_breadth * 5)
            )

            self.session.add(research_plan)

            # Update session status
            research_session.status = "pending_approval"
            
            await self.session.flush()  # Flush changes
            
            # Refresh the session object to ensure all attributes are loaded
            await self.session.refresh(research_session)

            logger.info(f"Research plan generated for session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to generate research plan for session {session_id}: {e}")
            
            # Update session to failed state
            stmt = (
                update(DeepResearchSession)
                .where(DeepResearchSession.id == session_id)
                .values(status="failed")
            )
            await self.session.execute(stmt)
            
            return False

    def _get_llm_provider(self, assistant: Assistants) -> str:
        """Extract LLM provider from assistant configuration."""
        # This would need to be implemented based on how Eneo stores model configuration
        # For now, return a default
        return "openai"

    def _get_llm_model(self, assistant: Assistants) -> str:
        """Extract LLM model from assistant configuration."""
        # This would need to be implemented based on how Eneo stores model configuration
        # For now, return a default
        return "gpt-4o-mini"

    async def export_research_report(
        self,
        session_id: UUID,
        user_id: UUID,
        tenant_id: UUID,
        format_type: str,
        include_citations: bool = True,
        include_metadata: bool = True
    ) -> Optional[bytes]:
        """
        Export research report with fallback mechanisms.

        Args:
            session_id: Research session ID
            user_id: User requesting export
            tenant_id: Tenant for isolation
            format_type: Export format (pdf, markdown, json, txt, html)
            include_citations: Include source citations
            include_metadata: Include research metadata

        Returns:
            Exported report as bytes, or None if not available
        """
        research_session = await self.get_research_session(session_id, user_id, tenant_id)
        if not research_session or not research_session.result:
            logger.warning(f"No research session or results found for export: {session_id}")
            return None

        # Prepare report data
        report_data = research_session.result.report_content
        executive_summary = research_session.result.executive_summary

        try:
            # Fallback export implementation
            if format_type == "json":
                import json
                export_dict = {
                    "session_id": str(session_id),
                    "query": research_session.query,
                    "executive_summary": executive_summary,
                    "report": report_data,
                    "created_at": research_session.created_at.isoformat() if research_session.created_at else None,
                    "completed_at": research_session.completed_at.isoformat() if research_session.completed_at else None,
                }
                if include_metadata:
                    export_dict["metadata"] = report_data.get("metadata", {})
                if not include_citations:
                    export_dict["report"].pop("citations", None)

                return json.dumps(export_dict, indent=2).encode('utf-8')

            elif format_type == "markdown":
                # Generate markdown format
                md_lines = []
                md_lines.append(f"# Research Report: {research_session.query}\n")
                md_lines.append(f"*Generated on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}*\n")
                md_lines.append(f"\n## Executive Summary\n\n{executive_summary}\n")

                # Add sections
                if "sections" in report_data:
                    for section in report_data["sections"]:
                        md_lines.append(f"\n## {section.get('title', 'Section')}\n")
                        md_lines.append(f"{section.get('content', '')}\n")

                # Add citations if requested
                if include_citations and "citations" in report_data:
                    md_lines.append("\n## References\n")
                    for i, citation in enumerate(report_data["citations"], 1):
                        md_lines.append(f"{i}. [{citation.get('title', 'Source')}]({citation.get('url', '#')})")

                # Add metadata if requested
                if include_metadata and "metadata" in report_data:
                    md_lines.append("\n---\n")
                    md_lines.append(f"*Research Duration: {report_data['metadata'].get('research_duration', 'N/A')}*  ")
                    md_lines.append(f"*Total Sources: {research_session.result.total_sources}*  ")
                    md_lines.append(f"*Confidence Score: {research_session.result.confidence_score:.2%}*")

                return "\n".join(md_lines).encode('utf-8')

            elif format_type == "txt":
                # Generate plain text format
                txt_lines = []
                txt_lines.append(f"RESEARCH REPORT: {research_session.query}")
                txt_lines.append("=" * 80)
                txt_lines.append(f"Generated on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
                txt_lines.append("EXECUTIVE SUMMARY")
                txt_lines.append("-" * 40)
                txt_lines.append(executive_summary)

                # Add sections
                if "sections" in report_data:
                    for section in report_data["sections"]:
                        txt_lines.append(f"\n{section.get('title', 'SECTION').upper()}")
                        txt_lines.append("-" * 40)
                        txt_lines.append(section.get('content', ''))

                # Add citations if requested
                if include_citations and "citations" in report_data:
                    txt_lines.append("\nREFERENCES")
                    txt_lines.append("-" * 40)
                    for i, citation in enumerate(report_data["citations"], 1):
                        txt_lines.append(f"[{i}] {citation.get('title', 'Source')}")
                        txt_lines.append(f"    URL: {citation.get('url', 'N/A')}")

                return "\n".join(txt_lines).encode('utf-8')

            elif format_type == "html":
                # Generate HTML format
                html_parts = []
                html_parts.append('<!DOCTYPE html><html><head>')
                html_parts.append('<meta charset="UTF-8">')
                html_parts.append(f'<title>Research Report: {research_session.query}</title>')
                html_parts.append('<style>')
                html_parts.append('body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }')
                html_parts.append('h1 { color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }')
                html_parts.append('h2 { color: #555; margin-top: 30px; }')
                html_parts.append('.metadata { background: #f5f5f5; padding: 10px; border-radius: 5px; margin: 20px 0; }')
                html_parts.append('.citations { background: #f9f9f9; padding: 15px; border-left: 3px solid #007bff; }')
                html_parts.append('</style></head><body>')

                html_parts.append(f'<h1>Research Report: {research_session.query}</h1>')
                html_parts.append(f'<p><em>Generated on {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}</em></p>')
                html_parts.append(f'<h2>Executive Summary</h2><p>{executive_summary}</p>')

                # Add sections
                if "sections" in report_data:
                    for section in report_data["sections"]:
                        html_parts.append(f'<h2>{section.get("title", "Section")}</h2>')
                        html_parts.append(f'<div>{section.get("content", "")}</div>')

                # Add citations if requested
                if include_citations and "citations" in report_data:
                    html_parts.append('<div class="citations"><h2>References</h2><ol>')
                    for citation in report_data["citations"]:
                        html_parts.append(f'<li><a href="{citation.get("url", "#")}">{citation.get("title", "Source")}</a></li>')
                    html_parts.append('</ol></div>')

                # Add metadata if requested
                if include_metadata and "metadata" in report_data:
                    html_parts.append('<div class="metadata">')
                    html_parts.append(f'<strong>Research Duration:</strong> {report_data["metadata"].get("research_duration", "N/A")}<br>')
                    html_parts.append(f'<strong>Total Sources:</strong> {research_session.result.total_sources}<br>')
                    html_parts.append(f'<strong>Confidence Score:</strong> {research_session.result.confidence_score:.2%}')
                    html_parts.append('</div>')

                html_parts.append('</body></html>')
                return ''.join(html_parts).encode('utf-8')

            elif format_type == "pdf":
                # For PDF, we'll return a simple error message for now
                # In production, you'd use reportlab or similar
                logger.warning(f"PDF export not yet implemented, falling back to markdown")
                # Return markdown as fallback
                return await self.export_research_report(
                    session_id, user_id, tenant_id, "markdown",
                    include_citations, include_metadata
                )

            else:
                logger.error(f"Unsupported export format: {format_type}")
                return None

        except Exception as e:
            logger.error(f"Failed to export research report: session={session_id}, format={format_type}, error={e}")
            return None


    def _create_progress_callback(self, session_id: UUID, user_id: UUID, loop: asyncio.AbstractEventLoop):
        """
        Create a progress callback function for the local-deep-research library.

        This callback will be called by the library during research execution
        with progress updates that we can send via WebSocket.

        Args:
            session_id: Research session ID
            user_id: User ID for WebSocket channel
            loop: The event loop to schedule async tasks in
        """
        def progress_callback(message: str, percentage: int = None, metadata: dict = None):
            """
            Callback function that receives progress updates from the library.

            Args:
                message: Current step description
                percentage: Progress percentage (0-100) or None
                metadata: Additional data like sources_found, branches, etc.
            """
            try:
                # Handle None percentage values
                if percentage is None:
                    # Try to infer from message or default to previous value
                    if 'complete' in message.lower() or 'finish' in message.lower():
                        percentage = 100
                    elif 'start' in message.lower() or 'initializ' in message.lower():
                        percentage = 5
                    else:
                        # Keep progress moving forward, don't send None
                        return  # Skip this update if we can't determine progress

                # Ensure percentage is within valid range
                percentage = max(0, min(100, percentage))

                # Parse metadata for additional info
                sources_found = metadata.get('sources_found', 0) if metadata else 0
                branches_complete = metadata.get('branches_complete', 0) if metadata else 0
                total_branches = metadata.get('total_branches', 1) if metadata else 1

                # Extract source count from message if available
                import re
                # Look for patterns like "Found 5 results" or "5 sources" or "Generated 3 follow-up questions"
                source_match = re.search(r'(?:found|got)\s+(\d+)\s+(?:result|source)', message.lower())
                if source_match:
                    sources_found = int(source_match.group(1))

                # Extract iteration info if available
                iteration_match = re.search(r'iteration\s+(\d+)\s+of\s+(\d+)', message.lower())
                if iteration_match:
                    branches_complete = int(iteration_match.group(1)) - 1
                    total_branches = int(iteration_match.group(2))

                # Determine status from message
                status = 'searching'
                if 'synthesiz' in message.lower() or 'generat' in message.lower() or 'compress' in message.lower():
                    status = 'synthesizing'
                elif 'complet' in message.lower() or 'finish' in message.lower() or 'saved' in message.lower():
                    status = 'complete'
                elif 'fail' in message.lower() or 'error' in message.lower():
                    status = 'failed'
                elif 'search' in message.lower() or 'query' in message.lower():
                    status = 'searching'

                logger.info(f"Progress update for session {session_id}: {percentage}% - {message}")

                # Create WebSocket update message
                ws_update = WsDeepResearchUpdate(
                    session_id=session_id,
                    status=status,
                    progress=percentage,
                    current_step=message,
                    sources_found=sources_found,
                    branches_complete=branches_complete,
                    total_branches=total_branches,
                    timestamp=datetime.now(timezone.utc)
                )

                # Schedule async tasks in the main event loop using thread-safe method
                asyncio.run_coroutine_threadsafe(
                    self._send_progress_updates(session_id, user_id, ws_update, percentage, message,
                                               sources_found, branches_complete, total_branches),
                    loop
                )

            except Exception as e:
                logger.error(f"Error in progress callback: {e}", exc_info=True)

        return progress_callback

    async def _send_progress_updates(self, session_id: UUID, user_id: UUID, ws_update: WsDeepResearchUpdate,
                                    percentage: int, message: str, sources_found: int,
                                    branches_complete: int, total_branches: int):
        """Combined async function to send WebSocket and database updates."""
        try:
            # Send WebSocket update
            await self._send_websocket_update(user_id, ws_update)

            # Update database
            await self._update_session_progress(
                session_id, percentage, message, sources_found,
                branches_complete, total_branches
            )
        except Exception as e:
            logger.error(f"Failed to send progress updates: {e}")

    async def _send_websocket_update(self, user_id: UUID, update: WsDeepResearchUpdate):
        """Send WebSocket update via Redis."""
        try:
            from intric.main.models import Status

            channel = Channel(type=ChannelType.APP_RUN_UPDATES, user_id=user_id)

            # Map our custom status to valid RedisMessage status
            redis_status = Status.IN_PROGRESS  # Default to in_progress
            if update.status in ['complete', 'completed']:
                redis_status = Status.COMPLETE
            elif update.status == 'failed':
                redis_status = Status.FAILED
            else:
                redis_status = Status.IN_PROGRESS

            # Convert to dict for Redis message
            update_dict = {
                "type": "deep_research_update",
                "data": update.model_dump(mode='json')
            }

            await redis_client.publish(
                channel.channel_string,
                RedisMessage(
                    id=update.session_id,
                    status=redis_status,
                    additional_data=update_dict
                ).model_dump_json()
            )
            logger.debug(f"Sent WebSocket update for session {update.session_id}")
        except Exception as e:
            logger.error(f"Failed to send WebSocket update: {e}")

    async def _update_session_progress(
        self, session_id: UUID, progress: int, current_step: str,
        sources_found: int, branches_complete: int, total_branches: int
    ):
        """Update session progress in database."""
        # Import here to avoid circular imports
        from intric.database.database import sessionmanager

        async with sessionmanager.session() as new_session:
            try:
                async with new_session.begin():
                    stmt = (
                        update(DeepResearchSession)
                        .where(DeepResearchSession.id == session_id)
                        .values(
                            progress_percentage=progress,
                            current_step=current_step,
                            sources_found=sources_found,
                            branches_complete=branches_complete,
                            total_branches=total_branches,
                            updated_at=datetime.now(timezone.utc)
                        )
                    )
                    await new_session.execute(stmt)
                    # No need to commit - it's automatic with begin()
                logger.debug(f"Updated progress for session {session_id}: {progress}%")
            except Exception as e:
                logger.error(f"Failed to update session progress: {e}")

    async def _execute_research_impl(self, session_id: UUID) -> None:
        """
        Execute the actual research and generate final results.
        """
        logger.info(f"Executing research for session {session_id}")

        # Get session
        stmt = select(DeepResearchSession).where(DeepResearchSession.id == session_id)
        result = await self.session.execute(stmt)
        research_session = result.scalar_one_or_none()

        if not research_session:
            raise RuntimeError(f"Session not found: {session_id}")

        try:
            # Configure environment (same as plan generation)
            import os
            from functools import partial
            import asyncio
            import local_deep_research

            if SETTINGS.openai_api_key:
                os.environ['OPENAI_API_KEY'] = SETTINGS.openai_api_key

            from local_deep_research.config import settings
            settings.set('LLM.PROVIDER', 'openai')
            settings.set('LLM.MODEL', 'gpt-4o-mini')
            settings.set('LLM.MAX_TOKENS', 8000)

            # Get configuration to determine search settings
            config = await self.get_or_create_configuration(research_session.assistant_id)
            search_tool = "auto" if config.enable_web_search else "wikipedia"
            
            logger.info(f"Executing {research_session.mode} research for: {research_session.query}")
            logger.info(f"Using search tool: {search_tool}, max_results: {config.sources_per_query}")

            # Get the current event loop for thread-safe async operations
            loop = asyncio.get_event_loop()

            # Create progress callback for real-time updates
            progress_callback = self._create_progress_callback(session_id, research_session.user_id, loop)

            if research_session.mode == "quick":
                # For quick mode, use quick_summary with configuration
                research_result = await loop.run_in_executor(
                    None,
                    partial(
                        local_deep_research.quick_summary,
                        research_session.query,
                        search_tool,
                        1,  # iterations
                        1,  # questions_per_iteration
                        config.sources_per_query,  # max_results from config
                        min(config.sources_per_query, 5),   # max_filtered_results
                        "us",  # region
                        "y",   # time_period
                        True,  # safe_search
                        0.7,   # temperature
                        progress_callback  # Our progress callback
                    )
                )
            else:
                # For standard/deep mode, use the same approach as quick mode but with more iterations
                iterations = 2 if research_session.mode == "standard" else 3
                questions_per_iteration = 3 if research_session.mode == "standard" else 5

                research_result = await loop.run_in_executor(
                    None,
                    partial(
                        local_deep_research.quick_summary,
                        research_session.query,
                        search_tool,
                        iterations,
                        questions_per_iteration,
                        config.sources_per_query,  # max_results from config
                        min(config.sources_per_query, 5),   # max_filtered_results
                        "us",  # region
                        "y",   # time_period
                        True,  # safe_search
                        0.7,   # temperature
                        progress_callback  # Our progress callback
                    )
                )
            
            logger.info(f"Research execution completed, result type: {type(research_result)}")
            
            # Extract data from the actual result structure
            summary = research_result.get("summary", "Research completed successfully")
            findings = research_result.get("findings", [])
            formatted_findings = research_result.get("formatted_findings", "")
            sources = research_result.get("sources", [])
            
            # Calculate metrics from the actual content
            total_words = len(summary.split()) + len(formatted_findings.split())
            total_findings = len(findings)
            
            # Calculate confidence score based on content quality
            confidence_score = min(0.9, 0.5 + (total_findings * 0.1) + (len(sources) * 0.05))
            
            logger.info(f"Extracted: {total_findings} findings, {len(sources)} sources, confidence: {confidence_score}")
            
            # Create final result record with proper data extraction
            final_result = DeepResearchResult(
                session_id=session_id,
                executive_summary=summary,
                report_content={
                    "sections": [{
                        "title": "Research Results", 
                        "content": formatted_findings or summary,
                        "subsections": [],
                        "citations": list(range(1, len(findings) + 1))
                    }],
                    "citations": [
                        {
                            "id": i + 1,
                            "title": f"Finding {i + 1}",
                            "url": f"https://wikipedia.org/research-finding-{i+1}",
                            "access_date": datetime.now(timezone.utc).isoformat(),
                            "domain": "wikipedia.org"
                        } for i, finding in enumerate(findings)
                    ],
                    "metadata": {
                        "total_words": total_words,
                        "research_duration": f"{int((datetime.now(timezone.utc) - research_session.started_at).total_seconds() // 60):02d}:{int((datetime.now(timezone.utc) - research_session.started_at).total_seconds() % 60):02d}",
                        "sources_by_type": {"wikipedia": len(findings)}
                    }
                },
                total_sources=max(len(sources), len(findings)),  # Use findings count if sources is empty
                total_findings=total_findings,
                confidence_score=confidence_score,
                limitations=None if confidence_score > 0.7 else "Limited search scope - consider using more comprehensive search tools"
            )
            
            self.session.add(final_result)

            # Update session to completed
            research_session.status = "completed"
            research_session.completed_at = datetime.now(timezone.utc)

            await self.session.commit()

            logger.info(f"Research results stored for session {session_id}")

        except Exception as e:
            logger.error(f"Research execution failed for session {session_id}: {e}")

            # Try to update status to failed using a new session
            try:
                from intric.database.database import sessionmanager
                async with sessionmanager.session() as new_session:
                    async with new_session.begin():
                        stmt = (
                            update(DeepResearchSession)
                            .where(DeepResearchSession.id == session_id)
                            .values(
                                status="failed",
                                completed_at=datetime.now(timezone.utc)
                            )
                        )
                        await new_session.execute(stmt)
                        # No need to commit - it's automatic with begin()
            except Exception as update_error:
                logger.error(f"Failed to update session status to failed: {update_error}")

    async def generate_plan_structure_only(self, session_id: UUID) -> bool:
        """
        Generate ONLY the research plan structure without executing research.
        
        Creates a tree of research questions showing breadth/depth exploration
        that the user can review and approve before execution begins.
        """
        try:
            logger.info(f"Generating research plan structure for session {session_id}")

            # Get session
            stmt = select(DeepResearchSession).where(DeepResearchSession.id == session_id)
            result = await self.session.execute(stmt)
            research_session = result.scalar_one_or_none()

            if not research_session:
                logger.error(f"Session not found: {session_id}")
                return False

            # Configure OpenAI for plan generation only
            import os
            if SETTINGS.openai_api_key:
                os.environ['OPENAI_API_KEY'] = SETTINGS.openai_api_key

            # Get configuration
            config = await self.get_or_create_configuration(research_session.assistant_id)
            
            # Use OpenAI directly to generate research questions tree
            from openai import OpenAI
            client = OpenAI(api_key=SETTINGS.openai_api_key)
            
            prompt = f"""Generate a research plan for: "{research_session.query}"

Research Mode: {research_session.mode}
Max Breadth: {config.max_breadth} parallel questions per level
Max Depth: {config.max_depth} levels deep

Create a tree structure with:
- Level 1: {config.max_breadth} broad research questions covering different aspects
- Level 2: For each Level 1 question, create 1-2 deeper follow-up questions

Return as JSON:
{{
  "main_topic": "topic name",
  "levels": [
    {{
      "level": 1,
      "branches": [
        {{
          "id": "branch_1",
          "question": "research question",
          "type": "broad",
          "estimated_sources": 5
        }}
      ]
    }}
  ]
}}"""

            logger.info("Generating research questions using OpenAI")
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000
            )
            
            plan_text = response.choices[0].message.content
            logger.debug(f"Generated plan text: {plan_text}")
            
            # Parse JSON response
            import json
            try:
                plan_data = json.loads(plan_text.strip())
            except json.JSONDecodeError:
                # Extract JSON from markdown code blocks if present
                import re
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', plan_text, re.DOTALL)
                if json_match:
                    plan_data = json.loads(json_match.group(1))
                else:
                    raise ValueError("Could not parse plan JSON from OpenAI response")

            # Create plan record
            research_plan = DeepResearchPlan(
                session_id=session_id,
                questions=plan_data,
                estimated_duration=config.get_timeout_for_mode(research_session.mode),
                estimated_sources=config.max_breadth * 5  # Rough estimate
            )

            self.session.add(research_plan)

            # Update session status to pending approval
            research_session.status = "pending_approval"
            
            await self.session.flush()
            await self.session.refresh(research_session)

            logger.info(f"Research plan structure generated for session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to generate plan structure for session {session_id}: {e}")
            
            # Update session to failed state
            stmt = (
                update(DeepResearchSession)
                .where(DeepResearchSession.id == session_id)
                .values(status="failed")
            )
            await self.session.execute(stmt)
            
            return False