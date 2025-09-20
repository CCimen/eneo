from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from sqlalchemy.orm import selectinload

from intric.image_generation_models.domain.image_generation_model import (
    ImageGenerationModel,  # This is the domain model
)
from intric.database.tables.ai_models_table import (
    ImageGenerationModels,
    ImageGenerationModelSettings,
)
from intric.database.tables.security_classifications_table import (
    SecurityClassification as SecurityClassificationDBModel,
)
from intric.main.exceptions import NotFoundException

if TYPE_CHECKING:
    from uuid import UUID
    from intric.database.database import AsyncSession
    from intric.users.user import UserInDB


class ImageGenerationModelDomainRepository:
    """Domain repository for image generation models (following CompletionModelRepository pattern)"""

    def __init__(self, session: "AsyncSession", user: "UserInDB"):
        self.session = session
        self.user = user

    async def all(self, with_deprecated: bool = False):
        """Get all image generation models (following completion model pattern)"""
        stmt = (
            sa.select(ImageGenerationModels, ImageGenerationModelSettings)
            .outerjoin(
                ImageGenerationModelSettings,
                sa.and_(
                    ImageGenerationModelSettings.image_generation_model_id == ImageGenerationModels.id,
                    ImageGenerationModelSettings.tenant_id == self.user.tenant_id,
                ),
            )
            .options(
                selectinload(ImageGenerationModelSettings.security_classification),
                selectinload(ImageGenerationModelSettings.security_classification).options(
                    selectinload(SecurityClassificationDBModel.tenant)
                ),
            )
            .order_by(
                ImageGenerationModels.org,
                ImageGenerationModels.created_at,
                ImageGenerationModels.nickname,
            )
        )

        if not with_deprecated:
            stmt = stmt.where(ImageGenerationModels.is_deprecated == False)  # noqa

        result = await self.session.execute(stmt)
        image_generation_models = result.all()

        return [
            ImageGenerationModel.create_from_db(
                image_generation_model_db=image_generation_model,
                image_generation_model_settings=image_generation_model_settings,
                user=self.user,
            )
            for image_generation_model, image_generation_model_settings in image_generation_models
        ]

    async def one_or_none(self, model_id: "UUID") -> Optional["ImageGenerationModel"]:
        """Get one image generation model or none (following completion model pattern)"""
        stmt = (
            sa.select(ImageGenerationModels, ImageGenerationModelSettings)
            .outerjoin(
                ImageGenerationModelSettings,
                sa.and_(
                    ImageGenerationModelSettings.image_generation_model_id == ImageGenerationModels.id,
                    ImageGenerationModelSettings.tenant_id == self.user.tenant_id,
                ),
            )
            .options(
                selectinload(ImageGenerationModelSettings.security_classification),
                selectinload(ImageGenerationModelSettings.security_classification).options(
                    selectinload(SecurityClassificationDBModel.tenant)
                ),
            )
            .where(ImageGenerationModels.id == model_id)
        )

        result = await self.session.execute(stmt)
        one_or_none = result.one_or_none()

        if one_or_none is None:
            return

        image_generation_model, image_generation_model_settings = one_or_none

        return ImageGenerationModel.create_from_db(
            image_generation_model_db=image_generation_model,
            image_generation_model_settings=image_generation_model_settings,
            user=self.user,
        )

    async def one(self, model_id: "UUID") -> "ImageGenerationModel":
        """Get one image generation model (following completion model pattern)"""
        image_generation_model = await self.one_or_none(model_id=model_id)

        if image_generation_model is None:
            raise NotFoundException()

        return image_generation_model

    async def update(self, image_generation_model: "ImageGenerationModel"):
        """Update image generation model (following completion model pattern)"""
        stmt = sa.select(ImageGenerationModelSettings).where(
            ImageGenerationModelSettings.image_generation_model_id == image_generation_model.id,
            ImageGenerationModelSettings.tenant_id == self.user.tenant_id,
        )
        result = await self.session.execute(stmt)
        existing_settings = result.scalars().one_or_none()

        if existing_settings is None:
            stmt = sa.insert(ImageGenerationModelSettings).values(
                image_generation_model_id=image_generation_model.id,
                tenant_id=self.user.tenant_id,
                is_org_enabled=image_generation_model.is_org_enabled,
                is_org_default=image_generation_model.is_org_default,
                security_classification_id=(
                    image_generation_model.security_classification.id
                    if image_generation_model.security_classification
                    else None
                ),
            )
            await self.session.execute(stmt)

        else:
            stmt = (
                sa.update(ImageGenerationModelSettings)
                .values(
                    is_org_enabled=image_generation_model.is_org_enabled,
                    is_org_default=image_generation_model.is_org_default,
                    security_classification_id=(
                        image_generation_model.security_classification.id
                        if image_generation_model.security_classification
                        else None
                    ),
                )
                .where(
                    ImageGenerationModelSettings.image_generation_model_id == image_generation_model.id,
                    ImageGenerationModelSettings.tenant_id == self.user.tenant_id,
                )
            )
            await self.session.execute(stmt)

        if image_generation_model.is_org_default:
            # Set all other models to not default
            stmt = (
                sa.update(ImageGenerationModelSettings)
                .values(is_org_default=False)
                .where(
                    ImageGenerationModelSettings.image_generation_model_id != image_generation_model.id,
                    ImageGenerationModelSettings.tenant_id == self.user.tenant_id,
                )
            )
            await self.session.execute(stmt)