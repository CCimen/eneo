from openai import AsyncAzureOpenAI

from intric.ai_models.completion_models.completion_model import (
    CompletionModel,
    Context,
    ModelKwargs,
)
from intric.completion_models.infrastructure import get_response_open_ai
from intric.completion_models.infrastructure.adapters.openai_model_adapter import (
    OpenAIModelAdapter,
)
from intric.main.config import get_settings
from intric.main.exceptions import RetriableOpenAIError
from intric.main.logging import get_logger

logger = get_logger(__name__)


class AzureOpenAIModelAdapter(OpenAIModelAdapter):
    def __init__(
        self,
        model: CompletionModel,
    ):
        self.model = model
        settings = get_settings()
        # Use configured API version from environment (should be "preview" for Responses API support)
        api_version = settings.azure_api_version
        
        self.client: AsyncAzureOpenAI = AsyncAzureOpenAI(
            api_key=settings.azure_api_key,
            azure_endpoint=settings.azure_endpoint,
            api_version=api_version,
        )

    def _is_gpt5_model(self) -> bool:
        """Detect if this is a GPT-5 model that should use Responses API"""
        api_type = getattr(self.model, "api_type", None)
        model_name = self.model.name.lower()
        
        # Only route models explicitly marked for Responses API or with GPT-5 prefix
        # Removed o3/o4 to avoid routing non-GPT-5 models to Responses API
        return (api_type == "responses" or 
                model_name.startswith("gpt-5") or
                model_name.startswith("gpt5"))

    def _get_kwargs(self, kwargs):
        kwargs = super()._get_kwargs(kwargs)

        # For reasoning models hosted by Azure max_completion_tokens has to be provided.
        # https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/reasoning?tabs=python-secure#api--feature-support
        if self.model.reasoning:
            # Only set if not already provided, and use a conservative default
            if "max_completion_tokens" not in kwargs:
                # Use 8K default instead of 128K to avoid costs/errors
                kwargs["max_completion_tokens"] = 8192
                logger.debug(f"Set default max_completion_tokens=8192 for reasoning model {self.model.name}")

        # For GPT-5 models using Responses API, filter out unsupported parameters
        if self._is_gpt5_model():
            # Remove parameters not supported by GPT-5 reasoning models
            unsupported_params = ["temperature", "top_p", "presence_penalty", "frequency_penalty", 
                                 "logprobs", "top_logprobs", "logit_bias", "max_tokens"]
            
            filtered_kwargs = {k: v for k, v in kwargs.items() if k not in unsupported_params}
            
            # Log removed parameters for debugging
            removed_params = [k for k in kwargs.keys() if k in unsupported_params]
            if removed_params:
                logger.debug(f"Filtered unsupported GPT-5 parameters: {removed_params}")
            
            return filtered_kwargs

        return kwargs

    async def get_response(
        self,
        context: Context,
        model_kwargs: ModelKwargs | None = None,
    ):
        logger.debug(f"Azure adapter get_response called for model: {self.model.name}")
        query = self.create_query_from_context(context=context)
        
        # Route GPT-5 models to Responses API
        if self._is_gpt5_model():
            from intric.completion_models.infrastructure import get_response_gpt5_azure_responses
            
            logger.debug(f"Routing GPT-5 model {self.model.name} to Responses API")
            
            try:
                # Get GPT-5 specific parameters from model_kwargs (overrides) or model defaults
                kwargs_dict = model_kwargs.__dict__ if model_kwargs else {}
                reasoning_effort = kwargs_dict.get("reasoning_effort") or getattr(self.model, "reasoning_effort", "medium")
                verbosity = kwargs_dict.get("verbosity") or getattr(self.model, "verbosity", "medium")
                reasoning_summary = kwargs_dict.get("reasoning_summary")
                
                return await get_response_gpt5_azure_responses.get_response_gpt5_azure_responses(
                    client=self.client,
                    model_name=self.model.deployment_name,
                    messages=query,
                    model_kwargs=self._get_kwargs(model_kwargs),
                    reasoning_effort=reasoning_effort,
                    verbosity=verbosity,
                    reasoning_summary=reasoning_summary,
                )
            except Exception as e:
                # For GPT-5 models, don't fall back to Chat Completions as it will likely fail
                logger.error(f"Azure GPT-5 Responses API failed for {self.model.name}: {e}")
                logger.error("GPT-5 models require Responses API - check Azure API version and deployment configuration")
                raise
        
        # Use standard Chat Completions API for non-GPT-5 models or fallback
        logger.debug(f"Using Chat Completions API for model: {self.model.name}")
        return await get_response_open_ai.get_response(
            client=self.client,
            model_name=self.model.deployment_name,
            messages=query,
            model_kwargs=self._get_kwargs(model_kwargs),
        )

    def get_response_streaming(
        self,
        context: Context,
        model_kwargs: ModelKwargs | None = None,
    ):
        query = self.create_query_from_context(context=context)
        
        # Route GPT-5 models to Responses API
        if self._is_gpt5_model():
            from intric.completion_models.infrastructure import get_response_gpt5_azure_responses
            
            logger.debug(f"Routing GPT-5 model {self.model.name} to Responses API streaming")
            
            try:
                # Get GPT-5 specific parameters from model_kwargs (overrides) or model defaults
                kwargs_dict = model_kwargs.__dict__ if model_kwargs else {}
                reasoning_effort = kwargs_dict.get("reasoning_effort") or getattr(self.model, "reasoning_effort", "medium")
                verbosity = kwargs_dict.get("verbosity") or getattr(self.model, "verbosity", "medium")
                reasoning_summary = kwargs_dict.get("reasoning_summary")
                
                return get_response_gpt5_azure_responses.get_response_gpt5_azure_responses_streaming(
                    client=self.client,
                    model_name=self.model.deployment_name,
                    messages=query,
                    model_kwargs=self._get_kwargs(model_kwargs),
                    reasoning_effort=reasoning_effort,
                    verbosity=verbosity,
                    reasoning_summary=reasoning_summary,
                )
            except Exception as e:
                # For GPT-5 models, don't fall back to Chat Completions as it will likely fail
                logger.error(f"Azure GPT-5 Responses API streaming failed for {self.model.name}: {e}")
                logger.error("GPT-5 models require Responses API - check Azure API version and deployment configuration")
                raise
        
        # Use standard Chat Completions API for non-GPT-5 models or fallback
        logger.debug(f"Using Chat Completions API streaming for model: {self.model.name}")
        return get_response_open_ai.get_response_streaming(
            client=self.client,
            model_name=self.model.deployment_name,
            messages=query,
            model_kwargs=self._get_kwargs(model_kwargs),
        )
