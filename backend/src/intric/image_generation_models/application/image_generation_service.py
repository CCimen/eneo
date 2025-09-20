from typing import TYPE_CHECKING, Optional
from uuid import UUID

from intric.completion_models.infrastructure.completion_service import generate_image
from intric.main.logging import get_logger

if TYPE_CHECKING:
    from intric.image_generation_models.domain.image_generation_model import ImageGenerationModel
    from intric.image_generation_models.domain.image_generation_model_domain_repo import ImageGenerationModelDomainRepository

logger = get_logger(__name__)


class ImageGenerationService:
    """Service for handling image generation requests"""

    def __init__(self, image_generation_repo: "ImageGenerationModelDomainRepository"):
        self.image_generation_repo = image_generation_repo

    async def get_enabled_models(self) -> list["ImageGenerationModel"]:
        """Get enabled image generation models for the current tenant"""
        all_models = await self.image_generation_repo.all()
        # Filter for enabled models
        return [model for model in all_models if model.is_org_enabled]

    async def get_default_model(self) -> Optional["ImageGenerationModel"]:
        """Get the default image generation model"""
        enabled_models = await self.get_enabled_models()
        if enabled_models:
            # Return the first enabled model as default
            return enabled_models[0]
        return None

    async def generate_image(
        self,
        prompt: str,
        model_id: Optional[UUID] = None,
        size: Optional[str] = None,
        quality: Optional[str] = None,
        **kwargs
    ) -> bytes:
        """
        Generate an image using the specified or default model

        Args:
            prompt: Text description for image generation
            model_id: Specific model ID to use (optional)
            size: Image size (optional)
            quality: Image quality (optional)
            **kwargs: Additional parameters

        Returns:
            Image bytes
        """
        logger.info(f"[Image Generation Service] Starting image generation")
        logger.debug(f"[Image Generation Service] Prompt: '{prompt[:100]}...', model_id: {model_id}")

        # Get the model to use
        if model_id:
            # Use specific model
            model = await self.image_generation_repo.one(model_id)
            if not model.is_org_enabled:
                raise ValueError(f"Image generation model {model_id} is not enabled")
        else:
            # Use default model
            model = await self.get_default_model()
            if not model:
                raise ValueError("No image generation models enabled")

        logger.info(f"[Image Generation Service] Using model: {model.name} ({model.litellm_model_name})")

        # Call the LiteLLM generate_image function directly
        try:
            image_bytes = await generate_image(
                prompt=prompt,
                model=model.litellm_model_name,
                size=size,
                quality=quality,
                **kwargs
            )

            logger.info(f"[Image Generation Service] Image generation successful! Size: {len(image_bytes)} bytes")
            return image_bytes

        except Exception as e:
            logger.error(f"[Image Generation Service] Image generation failed: {e}")
            raise