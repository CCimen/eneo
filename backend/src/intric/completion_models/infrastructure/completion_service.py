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


def _load_image_generation_models():
    """Load image generation models and their configurations from ai_models.yml"""
    try:
        config_path = os.path.join(
            pathlib.Path(__file__).parent.parent.parent,
            "server", "dependencies", "ai_models.yml"
        )
        logger.debug(f"Loading models from config path: {config_path}")

        with open(config_path, "r") as file:
            data = yaml.safe_load(file)

        image_models = data.get("image_generation_models", [])
        logger.debug(f"Found {len(image_models)} image generation models in config")

        # Create lookup by litellm_model_name for easy access
        models_config = {}
        for model in image_models:
            if not model.get("is_deprecated", False):
                model_name = model.get("litellm_model_name")
                if model_name:
                    models_config[model_name] = model
                    logger.debug(f"Loaded model: {model_name} ({model.get('nickname', 'Unknown')})")
                else:
                    logger.warning(f"Model missing litellm_model_name: {model}")

        logger.debug(f"Successfully loaded {len(models_config)} active image generation models")
        return models_config

    except FileNotFoundError as e:
        logger.error(f"Config file not found: {config_path}")
        return {}
    except yaml.YAMLError as e:
        logger.error(f"YAML parsing error in config file: {e}")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error loading image models: {e}")
        return {}


def _get_default_image_model() -> str:
    """Get the default image generation model"""
    models_config = _load_image_generation_models()

    if models_config:
        # Return first available model
        return list(models_config.keys())[0]

    # Fallback to hardcoded Azure model
    logger.warning("No image models found in config, using fallback")
    return "azure/gpt-image-1"


def _get_model_params(model_name: str, **overrides):
    """Get generation parameters for a model, with optional overrides"""
    logger.debug(f"Getting parameters for model: {model_name}, overrides: {overrides}")

    models_config = _load_image_generation_models()
    model_config = models_config.get(model_name, {})

    if not model_config:
        logger.warning(f"Model '{model_name}' not found in config, using defaults")

    # Get default parameters from model config
    default_params = model_config.get("default_params", {
        "size": "1024x1024",
        "quality": "standard",
        "format": "png",
        "n": 1
    })
    logger.debug(f"Default params for {model_name}: {default_params}")

    # Override with provided parameters, only if they're not None
    params = default_params.copy()
    filtered_overrides = {k: v for k, v in overrides.items() if v is not None}
    params.update(filtered_overrides)

    # Validate parameters against model capabilities
    capabilities = model_config.get("capabilities", {})
    if capabilities:
        logger.debug(f"Validating params against capabilities: {capabilities}")

        # Validate size
        if "sizes" in capabilities and params["size"] not in capabilities["sizes"]:
            logger.warning(f"Size '{params['size']}' not supported by {model_name}, "
                          f"supported sizes: {capabilities['sizes']}")

        # Validate quality
        if "qualities" in capabilities and params["quality"] not in capabilities["qualities"]:
            logger.warning(f"Quality '{params['quality']}' not supported by {model_name}, "
                          f"supported qualities: {capabilities['qualities']}")

        # Validate number of images
        max_images = capabilities.get("max_images", 1)
        if params["n"] > max_images:
            logger.warning(f"Requested {params['n']} images but {model_name} "
                          f"supports max {max_images}, capping to {max_images}")
            params["n"] = max_images

    # Filter out unsupported parameters for specific models
    if model_name.startswith("gemini/"):
        # Gemini only supports: prompt, model, n, size (no quality, format)
        logger.debug("Filtering parameters for Gemini model")
        filtered_params = {
            "size": params["size"],
            "n": params["n"]
        }
        # Only include quality and format if they're not in overrides (i.e., defaults)
        # This way we don't pass unsupported params to LiteLLM
        logger.debug(f"Gemini filtered parameters: {filtered_params}")
        return filtered_params

    logger.debug(f"Final parameters: {params}")
    return params


async def generate_image(prompt: str, model: str = None, size: str = None, quality: str = None, **kwargs):
    """Generate image using LiteLLM - supports Azure, Gemini, and other providers

    Args:
        prompt: The text prompt for image generation
        model: LiteLLM model name (e.g., "azure/gpt-image-1", "gemini/gemini-2.5-flash-image-preview")
               If None, defaults to first available model from configuration
        size: Image size (e.g., "1024x1024"). Uses model default if not specified
        quality: Image quality (e.g., "standard", "hd"). Uses model default if not specified
        **kwargs: Additional parameters (n, format, etc.)
    """
    from intric.main.logging import get_logger
    import litellm
    import base64

    logger = get_logger(__name__)

    # Input validation and logging
    if not prompt or not prompt.strip():
        error_msg = "Image generation prompt cannot be empty"
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.debug(f"Starting image generation with prompt length: {len(prompt) if prompt else 0}")

    try:
        # Load model from configuration if not specified
        if model is None:
            model = _get_default_image_model()
            logger.debug(f"Using default model: {model}")

        if not model:
            error_msg = "No image generation model available"
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.debug(f"Selected model: {model}")

        # Get model parameters with overrides
        logger.debug(f"Resolving parameters for model: {model}")
        params = _get_model_params(
            model,
            size=size,
            quality=quality,
            **{k: v for k, v in kwargs.items() if v is not None}
        )

        # Prepare LiteLLM call - only include supported parameters
        litellm_params = {
            "model": model,
            "prompt": prompt,
        }

        # Add response_format only for non-Gemini models
        if not model.startswith("gemini/"):
            litellm_params["response_format"] = "b64_json"

        # Add parameters that are present in the filtered params
        if "size" in params:
            litellm_params["size"] = params["size"]
        if "quality" in params:
            litellm_params["quality"] = params["quality"]
        if "n" in params:
            litellm_params["n"] = params["n"]

        logger.debug(f"Calling LiteLLM image_generation with model: {model}")
        logger.debug(f"LiteLLM parameters being sent: {litellm_params}")

        # Call LiteLLM
        response = litellm.image_generation(**litellm_params)

        # Validate response
        if not hasattr(response, 'data') or not response.data:
            error_msg = f"Invalid response from LiteLLM: no data field. Response: {response}"
            logger.error(error_msg)
            raise ValueError("No image data received from model")

        if len(response.data) == 0:
            error_msg = "Empty image data array received from model"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Extract base64 data
        first_image = response.data[0]
        if not hasattr(first_image, 'b64_json') or not first_image.b64_json:
            error_msg = f"No b64_json data in response. First image object: {first_image}"
            logger.error(error_msg)
            raise ValueError("No base64 image data in response")

        base64_string = first_image.b64_json
        logger.debug(f"Received base64 data length: {len(base64_string)}")

        # Convert base64 to bytes
        try:
            image_bytes = base64.b64decode(base64_string)
        except Exception as decode_error:
            error_msg = f"Failed to decode base64 image data: {decode_error}"
            logger.error(error_msg)
            raise ValueError(f"Base64 decode error: {decode_error}")

        # Try to get actual image dimensions for debugging
        actual_dimensions = "unknown"
        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(image_bytes))
            actual_dimensions = f"{img.width}x{img.height}"
            logger.info(f"Actual image dimensions: {actual_dimensions}, Requested: {params.get('size', 'default')}")
        except Exception as e:
            logger.debug(f"Could not determine image dimensions: {e}")

        # Success logging
        quality_info = f", Quality: {params['quality']}" if 'quality' in params else ""
        size_info = f", Requested: {params['size']}" if 'size' in params else ""
        logger.debug(f"Image generation successful - Model: {model}, Size: {len(image_bytes)} bytes, Actual: {actual_dimensions}{size_info}")

        return image_bytes

    except litellm.AuthenticationError as e:
        error_msg = f"Authentication failed for model {model}: {e}"
        logger.error(error_msg)
        raise ValueError(f"Authentication error: Check API keys for {model}")

    except litellm.RateLimitError as e:
        error_msg = f"Rate limit exceeded for model {model}: {e}"
        logger.error(error_msg)
        raise ValueError(f"Rate limit exceeded for {model}. Please try again later.")

    except litellm.BadRequestError as e:
        error_msg = f"Bad request for model {model}: {e}"
        logger.error(error_msg)
        raise ValueError(f"Invalid request: {e}")

    except ValueError:
        # Re-raise ValueError as-is (these are our custom validation errors)
        raise

    except Exception as e:
        error_msg = f"Unexpected error during image generation with {model}: {type(e).__name__}: {e}"
        logger.error(error_msg)
        logger.debug("Full error details:", exc_info=True)
        raise ValueError(f"Image generation failed: {e}")


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
        # When user clicks image generation button, it should work regardless of global feature flag
        logger.info(f"[Completion Service] Image generation check: requested={use_image_generation}, stream={stream}")
        use_image_generation = use_image_generation and stream
        logger.info(f"[Completion Service] Final image generation decision: {use_image_generation}")
        logger.info(f"[Completion Service] Using model: {model.name}")

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
