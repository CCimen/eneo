from typing import TYPE_CHECKING, Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from intric.image_generation_models.domain.image_generation_model import (
    ImageGenerationModelDB,
    ImageGenerationModelCreate,
    ImageGenerationModelUpdate,
)
from intric.database.database import AsyncSession
from intric.database.repositories.base import BaseRepositoryDelegate
from intric.database.tables.ai_models_table import (
    ImageGenerationModels,
    ImageGenerationModelSettings,
)
from intric.main.exceptions import UniqueException
from intric.main.models import IdAndName

if TYPE_CHECKING:
    pass


class ImageGenerationModelRepository:
    """Repository for image generation models (following CompletionModelsRepository pattern)"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.delegate = BaseRepositoryDelegate(
            session, ImageGenerationModels, ImageGenerationModelDB
        )

    async def _get_model_settings(self, id: UUID, tenant_id: UUID):
        query = sa.select(ImageGenerationModelSettings).where(
            ImageGenerationModelSettings.tenant_id == tenant_id,
            ImageGenerationModelSettings.image_generation_model_id == id,
        )
        return await self.session.scalar(query)

    async def _get_models_settings_mapper(self, tenant_id: UUID):
        query = sa.select(ImageGenerationModelSettings).where(
            ImageGenerationModelSettings.tenant_id == tenant_id
        )
        settings = await self.session.scalars(query)
        return {s.image_generation_model_id: s.is_org_enabled for s in settings}

    async def get_model(self, id: UUID, tenant_id: UUID) -> ImageGenerationModelDB:
        model = await self.delegate.get(id)

        settings = await self._get_model_settings(id, tenant_id)
        if settings:
            model.is_org_enabled = settings.is_org_enabled
        return model

    async def get_model_by_name(self, name: str) -> ImageGenerationModelDB:
        return await self.delegate.get_by(conditions={ImageGenerationModels.name: name})

    async def create_model(self, model: ImageGenerationModelCreate) -> ImageGenerationModelDB:
        return await self.delegate.add(model)

    async def enable_image_generation_model(
        self,
        is_org_enabled: bool,
        image_generation_model_id: UUID,
        tenant_id: UUID,
        is_org_default: Optional[bool] = None,
    ):
        query = sa.select(ImageGenerationModelSettings).where(
            ImageGenerationModelSettings.tenant_id == tenant_id,
            ImageGenerationModelSettings.image_generation_model_id == image_generation_model_id,
        )
        settings = await self.session.scalar(query)

        try:
            if settings:
                query = (
                    sa.update(ImageGenerationModelSettings)
                    .values(
                        is_org_enabled=is_org_enabled,
                        is_org_default=is_org_default if is_org_default is not None else settings.is_org_default
                    )
                    .where(
                        ImageGenerationModelSettings.tenant_id == tenant_id,
                        ImageGenerationModelSettings.image_generation_model_id == image_generation_model_id,
                    )
                    .returning(ImageGenerationModelSettings)
                )
                return await self.session.scalar(query)
            query = (
                sa.insert(ImageGenerationModelSettings)
                .values(
                    is_org_enabled=is_org_enabled,
                    is_org_default=is_org_default or False,
                    image_generation_model_id=image_generation_model_id,
                    tenant_id=tenant_id,
                )
                .returning(ImageGenerationModelSettings)
            )
            return await self.session.scalar(query)
        except IntegrityError as e:
            raise UniqueException("Default image generation model already exists.") from e

    async def update_model(self, model: ImageGenerationModelUpdate) -> ImageGenerationModelDB:
        return await self.delegate.update(model)

    async def delete_model(self, id: UUID) -> ImageGenerationModelDB:
        stmt = (
            sa.delete(ImageGenerationModels)
            .where(ImageGenerationModels.id == id)
            .returning(ImageGenerationModels)
        )

        await self.delegate.get_record_from_query(stmt)

    async def get_models(
        self,
        tenant_id: UUID = None,
        is_deprecated: bool = False,
        id_list: list[UUID] = None,
    ) -> list[ImageGenerationModelDB]:
        query = (
            sa.select(ImageGenerationModels)
            .where(ImageGenerationModels.is_deprecated == is_deprecated)
            .order_by(ImageGenerationModels.created_at)
        )

        if id_list is not None:
            query = query.where(ImageGenerationModels.id.in_(id_list))

        models = await self.delegate.get_models_from_query(query)

        if tenant_id is not None:
            settings_mapper = await self._get_models_settings_mapper(tenant_id)

            for model in models:
                model.is_org_enabled = settings_mapper.get(model.id, False)

        return models

    async def get_ids_and_names(self) -> list[(UUID, str)]:
        stmt = sa.select(ImageGenerationModels)

        models = await self.delegate.get_records_from_query(stmt)

        return [IdAndName(id=model.id, name=model.name) for model in models.all()]