# Copyright (c) 2025 Sundsvalls Kommun
#
# Licensed under the MIT License.

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from intric.main.config import get_settings
from intric.main.models import ModelId
from intric.questions.question import UseTools


class ImageGenerationParams(BaseModel):
    """Parameters for image generation"""
    model: Optional[str] = Field(None, description="Image generation model to use")
    size: Optional[str] = Field(None, description="Image size (e.g., '1024x1024')")
    quality: Optional[str] = Field(None, description="Image quality (e.g., 'standard', 'hd')")
    n: Optional[int] = Field(None, description="Number of images to generate", ge=1, le=4)


class ConversationRequest(BaseModel):
    """
    A unified model for asking questions to either assistants or group chats.

    Either session_id, assistant_id, or group_chat_id must be provided.
    If session_id is provided, the conversation will continue with the existing session.

    For group chats:
    - If tools.assistants contains an assistant, that specific assistant will be targeted
      (requires the group chat to have allow_mentions=True).
    - If no assistant is targeted, the most appropriate assistant will be selected.
    """

    question: str
    session_id: Optional[UUID] = None
    assistant_id: Optional[UUID] = None
    group_chat_id: Optional[UUID] = None
    files: list[ModelId] = Field(max_length=get_settings().max_in_question, default=[])
    stream: bool = False
    tools: Optional[UseTools] = None
    use_web_search: bool = False

    # Image generation configuration
    image_generation: bool = False  # Backward compatibility flag
    image_generation_params: Optional[ImageGenerationParams] = Field(
        None,
        description="Advanced image generation parameters. If provided, image_generation is automatically set to True."
    )

    @model_validator(mode="after")
    def validate_request(self) -> "ConversationRequest":
        """Validate the conversation request"""
        # Validate that at least one ID is provided
        if (
            self.session_id is None
            and self.assistant_id is None
            and self.group_chat_id is None
        ):
            raise ValueError(
                "Either session_id, assistant_id, or group_chat_id must be provided"
            )

        # Auto-enable image generation if parameters are provided
        if self.image_generation_params is not None:
            self.image_generation = True

        return self
