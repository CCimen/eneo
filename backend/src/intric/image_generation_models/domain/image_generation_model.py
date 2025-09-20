import json
from typing import TYPE_CHECKING, Optional

from intric.ai_models.ai_model import AIModel
from intric.ai_models.model_enums import (
    ModelFamily,
    ModelHostingLocation,
    ModelOrg,
    ModelStability,
)
from intric.security_classifications.domain.entities.security_classification import (
    SecurityClassification,
)

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

    from intric.database.tables.ai_models_table import (
        ImageGenerationModels as ImageGenerationModelsDB,
    )
    from intric.database.tables.ai_models_table import (
        ImageGenerationModelSettings,
    )
    from intric.users.user import UserInDB


class ImageGenerationModel(AIModel):
    """Domain model for image generation models (following completion model pattern)"""

    def __init__(
        self,
        user: "UserInDB",
        id: "UUID",
        created_at: "datetime",
        updated_at: "datetime",
        nickname: str,
        name: str,
        family: ModelFamily,
        hosting: ModelHostingLocation,
        org: Optional[ModelOrg],
        stability: ModelStability,
        open_source: bool,
        description: Optional[str],
        deployment_name: Optional[str],
        is_deprecated: bool,
        is_org_enabled: bool,
        is_org_default: bool,
        litellm_model_name: Optional[str] = None,  # Following LiteLLM pattern
        security_classification: Optional["SecurityClassification"] = None,
    ):
        super().__init__(
            user=user,
            id=id,
            created_at=created_at,
            updated_at=updated_at,
            nickname=nickname,
            name=name,
            family=family,
            hosting=hosting,
            org=org,
            stability=stability,
            open_source=open_source,
            description=description,
            hf_link=None,  # Not applicable for image generation models
            is_deprecated=is_deprecated,
            is_org_enabled=is_org_enabled,
            security_classification=security_classification,
        )

        self.deployment_name = deployment_name
        self.is_org_default = is_org_default
        self.litellm_model_name = litellm_model_name  # Following LiteLLM pattern

    @classmethod
    def create_from_db(
        cls,
        image_generation_model_db: "ImageGenerationModelsDB",
        image_generation_model_settings: Optional["ImageGenerationModelSettings"],
        user: "UserInDB",
    ):
        """Create domain model from database (following completion model pattern)"""
        if image_generation_model_settings is None:
            is_org_enabled = False
            is_org_default = False
            updated_at = image_generation_model_db.updated_at
            security_classification = None
        else:
            is_org_enabled = image_generation_model_settings.is_org_enabled
            is_org_default = image_generation_model_settings.is_org_default
            updated_at = image_generation_model_settings.updated_at
            security_classification = (
                image_generation_model_settings.security_classification
            )

        org = (
            None
            if image_generation_model_db.org is None
            else ModelOrg(image_generation_model_db.org)
        )

        return cls(
            user=user,
            id=image_generation_model_db.id,
            created_at=image_generation_model_db.created_at,
            updated_at=updated_at,
            nickname=image_generation_model_db.nickname,
            name=image_generation_model_db.name,
            family=ModelFamily(image_generation_model_db.family),
            hosting=ModelHostingLocation(image_generation_model_db.hosting),
            org=org,
            stability=ModelStability(image_generation_model_db.stability),
            open_source=image_generation_model_db.open_source,
            description=image_generation_model_db.description,
            deployment_name=image_generation_model_db.deployment_name,
            is_deprecated=image_generation_model_db.is_deprecated,
            is_org_enabled=is_org_enabled,
            is_org_default=is_org_default,
            litellm_model_name=image_generation_model_db.litellm_model_name,  # Following LiteLLM pattern
            security_classification=SecurityClassification.to_domain(
                db_security_classification=security_classification
            ),
        )


# Pydantic models for YAML initialization (following completion model pattern)
from pydantic import BaseModel
from intric.ai_models.model_enums import ModelFamily, ModelHostingLocation, ModelStability
from intric.main.models import partial_model, InDB
from uuid import UUID


class ImageGenerationModelBase(BaseModel):
    """Base model for image generation models (following CompletionModelBase pattern)"""
    name: str
    nickname: str
    family: ModelFamily
    stability: ModelStability
    hosting: ModelHostingLocation
    is_deprecated: bool
    open_source: bool
    description: Optional[str] = None
    deployment_name: Optional[str] = None
    org: Optional[str] = None
    litellm_model_name: Optional[str] = None  # Following LiteLLM pattern


class ImageGenerationModelCreate(ImageGenerationModelBase):
    """Model for creating new image generation models (following CompletionModelCreate pattern)"""
    pass


class ImageGenerationModelDB(ImageGenerationModelBase, InDB):
    """Image generation model with database fields (following CompletionModel pattern)"""
    pass


@partial_model
class ImageGenerationModelUpdate(ImageGenerationModelBase):
    """Model for updating existing image generation models (following CompletionModelUpdate pattern)"""
    id: UUID