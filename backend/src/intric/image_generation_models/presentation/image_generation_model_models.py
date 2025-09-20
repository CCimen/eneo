from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from intric.image_generation_models.domain.image_generation_model import (
    ImageGenerationModel,
)


class ImageGenerationModelPublic(BaseModel):
    """Public representation of an image generation model (following completion model pattern)"""
    id: UUID
    name: str
    nickname: str
    family: str
    hosting: str
    org: Optional[str]
    stability: str
    open_source: bool
    description: Optional[str]
    deployment_name: Optional[str]
    litellm_model_name: Optional[str]  # Following LiteLLM pattern
    is_deprecated: bool
    is_org_enabled: bool
    is_org_default: bool
    is_locked: bool = False
    can_access: bool = True

    @classmethod
    def from_domain(cls, model: ImageGenerationModel) -> "ImageGenerationModelPublic":
        """Convert domain model to public model (following completion model pattern)"""
        return cls(
            id=model.id,
            name=model.name,
            nickname=model.nickname,
            family=model.family.value,
            hosting=model.hosting.value,
            org=model.org.value if model.org else None,
            stability=model.stability.value,
            open_source=model.open_source,
            description=model.description,
            deployment_name=model.deployment_name,
            litellm_model_name=model.litellm_model_name,  # Following LiteLLM pattern
            is_deprecated=model.is_deprecated,
            is_org_enabled=model.is_org_enabled,
            is_org_default=model.is_org_default,
            is_locked=False,  # Image generation models aren't locked
            can_access=True,  # Will be set by service layer
        )


class ImageGenerationModelSecurityStatus(ImageGenerationModelPublic):
    """Image generation model with security classification status (following completion model pattern)"""
    meets_security_classification: Optional[bool] = None

    @classmethod
    def from_domain(cls, model: ImageGenerationModel) -> "ImageGenerationModelSecurityStatus":
        """Convert domain model to security status model (following completion model pattern)"""
        base = ImageGenerationModelPublic.from_domain(model)
        return cls(**base.model_dump(), meets_security_classification=None)


class ImageGenerationModelUpdate(BaseModel):
    """Model for updating image generation model settings (following completion model pattern)"""
    is_org_enabled: bool
    is_org_default: Optional[bool] = None