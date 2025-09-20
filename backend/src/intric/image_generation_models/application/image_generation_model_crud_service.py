from typing import TYPE_CHECKING, Optional

from intric.main.exceptions import UnauthorizedException
from intric.roles.permissions import Permission, validate_permissions

if TYPE_CHECKING:
    from uuid import UUID

    from intric.security_classifications.domain.repositories.security_classification_repo_impl import (  # noqa: E501
        SecurityClassificationRepoImpl,
    )
    from intric.image_generation_models.domain.image_generation_model_domain_repo import (
        ImageGenerationModelDomainRepository,
    )
    from intric.users.user import UserInDB


class ImageGenerationModelCRUDService:
    """CRUD service for image generation models (following completion model service pattern)"""

    def __init__(
        self,
        user: "UserInDB",
        image_generation_model_repo: "ImageGenerationModelDomainRepository",
        security_classification_repo: Optional["SecurityClassificationRepoImpl"] = None,
    ):
        self.image_generation_model_repo = image_generation_model_repo
        self.user = user
        self.security_classification_repo = security_classification_repo

    async def get_image_generation_models(self):
        """Get all image generation models (following completion model pattern)"""
        return await self.image_generation_model_repo.all()

    async def get_image_generation_model(self, model_id: "UUID"):
        """Get specific image generation model (following completion model pattern)"""
        image_generation_model = await self.image_generation_model_repo.one(model_id=model_id)

        if not image_generation_model.can_access:
            raise UnauthorizedException()

        return image_generation_model

    async def get_available_image_generation_models(self):
        """Get available image generation models (following completion model pattern)"""
        image_generation_models = await self.image_generation_model_repo.all()

        return [model for model in image_generation_models if model.can_access]

    async def get_default_image_generation_model(self):
        """Get default image generation model (following completion model pattern)"""
        image_generation_models = await self.get_available_image_generation_models()

        # First try to get the org default model
        for model in image_generation_models:
            if model.is_org_default:
                return model

        # If no default is set, return the first available model
        if image_generation_models:
            return image_generation_models[0]

        return None

    @validate_permissions(Permission.ADMIN)
    async def update_image_generation_model(
        self,
        model_id: "UUID",
        is_org_enabled: Optional[bool],
        is_org_default: Optional[bool],
        security_classification_id: Optional["UUID"] = None,
    ):
        """Update image generation model (following completion model pattern)"""
        image_generation_model = await self.image_generation_model_repo.one(model_id=model_id)

        if is_org_enabled is not None:
            image_generation_model.is_org_enabled = is_org_enabled

        if is_org_default is not None:
            image_generation_model.is_org_default = is_org_default

        if security_classification_id is not None:
            if security_classification_id is None:
                img_security_classification = None
            else:
                img_security_classification = await self.security_classification_repo.one(
                    id=security_classification_id
                )
            image_generation_model.security_classification = img_security_classification

        await self.image_generation_model_repo.update(image_generation_model)

        return image_generation_model