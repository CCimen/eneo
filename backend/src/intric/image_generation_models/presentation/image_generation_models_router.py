from uuid import UUID

from fastapi import APIRouter, Depends

from intric.main.container.container import Container
from intric.main.models import PaginatedResponse
from intric.server.dependencies.container import get_container
from intric.server.protocol import responses
from intric.image_generation_models.presentation.image_generation_model_models import (
    ImageGenerationModelPublic,
    ImageGenerationModelUpdate,
)

router = APIRouter()


@router.get(
    "/",
    response_model=PaginatedResponse[ImageGenerationModelPublic],
)
async def get_image_generation_models(
    container: Container = Depends(get_container(with_user=True)),
):
    """Get all image generation models (following completion model router pattern)"""
    service = container.image_generation_model_crud_service()

    models = await service.get_image_generation_models()

    return PaginatedResponse(
        items=[ImageGenerationModelPublic.from_domain(model) for model in models]
    )


@router.post(
    "/{id}/",
    response_model=ImageGenerationModelPublic,
    responses=responses.get_responses([404]),
)
async def update_image_generation_model(
    id: UUID,
    update_flags: ImageGenerationModelUpdate,
    container: Container = Depends(get_container(with_user=True)),
):
    """Update image generation model settings (following completion model router pattern)"""
    service = container.image_generation_model_crud_service()

    image_generation_model = await service.update_image_generation_model(
        model_id=id,
        is_org_enabled=update_flags.is_org_enabled,
        is_org_default=update_flags.is_org_default,
    )

    return ImageGenerationModelPublic.from_domain(image_generation_model)