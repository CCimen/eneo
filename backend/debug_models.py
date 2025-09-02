#!/usr/bin/env python3
"""
Debug script to check model access and settings.
"""

import asyncio
import os
import sys
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from intric.database.database import sessionmanager
from intric.database.tables.ai_models_table import CompletionModels, CompletionModelSettings
from intric.database.tables.tenant_table import Tenants
from intric.main.config import get_settings
from intric.main.logging import get_logger

logger = get_logger(__name__)


async def debug_models():
    """Debug model access and settings."""
    
    # Check GPT-5 models in database
    print("=== GPT-5 Models in Database ===")
    stmt = sa.select(CompletionModels).where(CompletionModels.name.like('gpt-5%'))
    
    async with sessionmanager.session() as session:
        result = await session.execute(stmt)
        gpt5_models = result.scalars().all()
        
        for model in gpt5_models:
            print(f"Model: {model.name}")
            print(f"  ID: {model.id}")
            print(f"  Family: {model.family}")
            print(f"  Default Enabled: {getattr(model, 'default_enabled', 'NOT SET')}")
            print(f"  API Type: {getattr(model, 'api_type', 'NOT SET')}")
            print()
        
        # Check if any tenants have settings for GPT-5 models
        print("=== GPT-5 Model Settings by Tenant ===")
        stmt = (
            sa.select(Tenants.name, Tenants.id, CompletionModels.name, CompletionModelSettings.is_org_enabled)
            .join(CompletionModelSettings, CompletionModelSettings.tenant_id == Tenants.id)
            .join(CompletionModels, CompletionModels.id == CompletionModelSettings.completion_model_id)
            .where(CompletionModels.name.like('gpt-5%'))
        )
        result = await session.execute(stmt)
        settings = result.all()
        
        if settings:
            for tenant_name, tenant_id, model_name, is_enabled in settings:
                print(f"Tenant: {tenant_name} ({tenant_id})")
                print(f"  Model: {model_name} - Enabled: {is_enabled}")
        else:
            print("No GPT-5 model settings found for any tenant")
        
        print()
        
        # Check all tenants
        print("=== All Tenants ===")
        stmt = sa.select(Tenants)
        result = await session.execute(stmt)
        tenants = result.scalars().all()
        
        for tenant in tenants:
            print(f"Tenant: {tenant.name} ({tenant.id})")
        

async def main():
    # Initialize database connection
    settings = get_settings()
    database_url = settings.database_url
    sessionmanager.init(database_url)
    
    try:
        await debug_models()
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())