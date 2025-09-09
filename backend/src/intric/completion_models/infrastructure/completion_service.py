from __future__ import annotations

import json
from typing import TYPE_CHECKING, AsyncGenerator

from intric.ai_models.completion_models.completion_model import (
    Completion,
    CompletionModel,
    CompletionModelResponse,
    ModelKwargs,
    ResponseType,
)
from intric.ai_models.model_enums import ModelFamily
from intric.completion_models.infrastructure.adapters import (
    AzureOpenAIModelAdapter,
    ClaudeModelAdapter,
    LiteLLMModelAdapter,
    MistralModelAdapter,
    OpenAIModelAdapter,
    OVHCloudModelAdapter,
    VLMMModelAdapter,
)
from intric.completion_models.infrastructure.context_builder import ContextBuilder
from intric.files.file_models import File
from intric.info_blobs.info_blob import InfoBlobChunkInDBWithScore
from intric.main.config import SETTINGS
from intric.main.logging import get_logger
from intric.sessions.session import SessionInDB
import litellm
import os
import pathlib
import yaml

if TYPE_CHECKING:
    from intric.completion_models.infrastructure.adapters.base_adapter import (
        CompletionModelAdapter,
    )
    from intric.completion_models.infrastructure.web_search import WebSearchResult
    from intric.main.container.container import Container

logger = get_logger(__name__)


def _get_default_image_model() -> str:
    """Load default image generation model from ai_models.yml configuration"""
    try:
        # Load from the same ai_models.yml file used by the rest of the system
        config_path = os.path.join(
            pathlib.Path(__file__).parent.parent.parent, 
            "server", "dependencies", "ai_models.yml"
        )
        with open(config_path, "r") as file:
            data = yaml.safe_load(file)
            
        # Get first available image generation model
        image_models = data.get("image_generation_models", [])
        if image_models:
            default_model = image_models[0]  # Use first model as default
            return default_model["litellm_model_name"]
            
    except Exception as e:
        logger.warning(f"[Image Tool] Could not load from ai_models.yml: {e}")
        
    # Fallback to hardcoded Azure model
    return "azure/gpt-image-1"


async def generate_image(prompt: str, model: str = None):
    """Generate image using LiteLLM - supports Azure, Gemini, OpenAI (replaces FluxAdapter)
    
    Args:
        prompt: The text prompt for image generation
        model: LiteLLM model name (e.g., "azure/gpt-image-1", "gemini/gemini-2.0-flash-exp-image-generation")
               If None, defaults to Azure deployment
    """
    from intric.main.logging import get_logger
    import litellm
    import base64
    
    logger = get_logger(__name__)
    logger.info(f"[Image Tool] Generate image called with prompt: {prompt[:50]}...")
    
    try:
        # Load model from configuration if not specified
        if model is None:
            model = _get_default_image_model()  # Load from ai_models.yml
        
        # Support switching to Gemini via environment variable for testing
        if model == "gemini" or model == "gemini/gemini-2.0-flash-exp-image-generation":
            model = "gemini/gemini-2.0-flash-exp-image-generation"
        
        logger.info(f"[Image Tool] Using model: {model}")
        
        # Use LiteLLM directly for different providers
        if model.startswith("gemini/"):
            # Gemini uses completion API with modalities (per litellm_docs_gemini.md)
            logger.info(f"[Image Tool] Using Gemini completion API")
            response = await litellm.acompletion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                modalities=["image", "text"]
            )
            # Extract base64 from Gemini response
            image_data_url = response.choices[0].message.images[0]["image_url"]["url"]
            # Remove data:image/png;base64, prefix and decode
            base64_string = image_data_url.split(",")[1] if "," in image_data_url else image_data_url
        else:
            # Azure/OpenAI use image_generation API
            logger.info(f"[Image Tool] Using standard image_generation API") 
            response = litellm.image_generation(
                model=model,
                prompt=prompt,
                size="1024x1024",
                quality="medium",  # Azure format
                output_format="png",
                n=1
            )
            # Extract base64 from standard response
            base64_string = response.data[0].b64_json
        
        # Convert base64 to bytes (same format as original FluxAdapter)
        image_bytes = base64.b64decode(base64_string)
        
        logger.info(f"[Image Tool] Image generation successful! Size: {len(image_bytes)} bytes")
        
        return image_bytes
        
    except Exception as e:
        logger.error(f"[Image Tool] Image generation failed: {e}")
        raise


class CompletionService:
    def __init__(
        self,
        context_builder: ContextBuilder,
    ):
        self._adapters = {
            ModelFamily.OPEN_AI: OpenAIModelAdapter,
            ModelFamily.VLLM: VLMMModelAdapter,
            ModelFamily.CLAUDE: ClaudeModelAdapter,
            ModelFamily.AZURE: AzureOpenAIModelAdapter,
            ModelFamily.OVHCLOUD: OVHCloudModelAdapter,
            ModelFamily.MISTRAL: MistralModelAdapter,
        }
        self.context_builder = context_builder

    def _get_adapter(self, model: CompletionModel) -> "CompletionModelAdapter":
        # Check for LiteLLM model first
        if model.litellm_model_name:
            return LiteLLMModelAdapter(model)
        
        # Fall back to existing family-based selection
        adapter_class = self._adapters.get(model.family.value)
        if not adapter_class:
            raise ValueError(f"No adapter found for modelfamily {model.family.value}")

        return adapter_class(model)

    @staticmethod
    def is_valid_arguments(arguments: str):
        try:
            # Attempt to parse the string
            parsed = json.loads(arguments)
            # Check if the parsed object is a dictionary
            return isinstance(parsed, dict)
        except (json.JSONDecodeError, TypeError):
            # If there is a JSON decode error or TypeError, return False
            return False

    async def _handle_tool_call(self, completion: AsyncGenerator[Completion]):
        name = None
        arguments = ""
        function_called = False

        async for chunk in completion:
            logger.debug(chunk)

            if chunk.tool_call:
                if chunk.tool_call.name:
                    name = chunk.tool_call.name

                if chunk.tool_call.arguments:
                    arguments += chunk.tool_call.arguments

                if not name or not arguments or not self.is_valid_arguments(arguments):
                    # Keep collecting the tool call
                    continue
                elif not function_called:
                    call_args = json.loads(arguments)

                    if name == "generate_image":
                        yield Completion(response_type=ResponseType.INTRIC_EVENT)

                        chunk.image_data = await generate_image(**call_args)
                        chunk.response_type = ResponseType.FILES

                        yield chunk

                    function_called = True

            elif chunk.text:
                chunk.response_type = ResponseType.TEXT

                yield chunk

    async def get_response(
        self,
        model: CompletionModel,
        text_input: str,
        model_kwargs: ModelKwargs | None = None,
        files: list[File] = [],
        prompt: str = "",
        prompt_files: list[File] = [],
        transcription_inputs: list[str] = [],
        info_blob_chunks: list[InfoBlobChunkInDBWithScore] = [],
        web_search_results: list["WebSearchResult"] = [],
        session: SessionInDB | None = None,
        stream: bool = False,
        extended_logging: bool = False,
        version: int = 1,
        use_image_generation: bool = False,
    ):
        model_adapter = self._get_adapter(model)

        # Make sure everything fits in the context of the model
        max_tokens = model_adapter.get_token_limit_of_model()

        # Image generation only works on streaming for now
        # And only if feature flag is turned on
        use_image_generation = use_image_generation and stream and SETTINGS.using_image_generation

        context = self.context_builder.build_context(
            input_str=text_input,
            max_tokens=max_tokens,
            files=files,
            prompt=prompt,
            session=session,
            info_blob_chunks=info_blob_chunks,
            prompt_files=prompt_files,
            transcription_inputs=transcription_inputs,
            version=version,
            use_image_generation=use_image_generation,
            web_search_results=web_search_results,
        )

        if extended_logging:
            logging_details = model_adapter.get_logging_details(
                context=context, model_kwargs=model_kwargs
            )
        else:
            logging_details = None

        if not stream:
            completion = await model_adapter.get_response(
                context=context,
                model_kwargs=model_kwargs,
            )
        else:
            # Will be an async generator - not awaitable
            completion = model_adapter.get_response_streaming(
                context=context,
                model_kwargs=model_kwargs,
            )

            completion = self._handle_tool_call(completion)

        return CompletionModelResponse(
            completion=completion,
            model=model_adapter.model,
            extended_logging=logging_details,
            total_token_count=context.token_count,
        )


class CompletionServiceFactory:
    def __init__(self, container: Container):
        self.container = container
