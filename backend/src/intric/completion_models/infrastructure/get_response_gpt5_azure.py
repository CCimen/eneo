"""
Azure GPT-5 Chat Completions API Implementation (Fallback)
Handles communication with Azure OpenAI's GPT-5 models using Chat Completions API
This serves as a fallback when Responses API is not available.
"""
import openai
from openai import AsyncAzureOpenAI
from tenacity import (
    retry,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from intric.ai_models.completion_models.completion_model import Completion, FunctionCall
from intric.main.exceptions import BadRequestException, OpenAIException, RetriableOpenAIError
from intric.main.logging import get_logger

logger = get_logger(__name__)


async def get_response_gpt5_azure(
    client: AsyncAzureOpenAI,
    model_name: str,
    messages: list,
    model_kwargs: dict,
    reasoning_effort: str = "medium",
    verbosity: str = "medium",
    extra_headers: dict = None,
):
    """
    Get response from Azure GPT-5 using Chat Completions API
    
    Azure Chat Completions API for GPT-5 supports:
    - max_completion_tokens (required for reasoning models)
    - reasoning_effort (minimal, low, medium, high)
    
    Does NOT support:
    - verbosity (only available in Responses API)
    
    Requires API version 2025-03-01-preview or later.
    """
    extra_headers = extra_headers or openai.NOT_GIVEN
    
    # Azure Chat Completions API supports max_completion_tokens and reasoning_effort
    # but does NOT support verbosity (that's Responses API only)
    azure_kwargs = dict(model_kwargs)
    
    # Add supported GPT-5 parameters for Chat Completions API
    if reasoning_effort:
        azure_kwargs["reasoning_effort"] = reasoning_effort
    
    # Remove verbosity as it's not supported in Chat Completions API
    azure_kwargs.pop("verbosity", None)
    
    try:
        response = await client.chat.completions.create(
            model=model_name,
            messages=messages,
            extra_headers=extra_headers,
            **azure_kwargs,
        )
        choices = response.choices
        
        completion_str = choices[0].message.content.strip()
        
        # Get reasoning tokens if available (Azure Chat Completions may not include these)
        reasoning_tokens = 0
        try:
            if hasattr(response, 'usage') and response.usage and hasattr(response.usage, 'completion_tokens_details'):
                reasoning_tokens = getattr(response.usage.completion_tokens_details, 'reasoning_tokens', 0)
        except AttributeError:
            reasoning_tokens = 0
        
        completion = Completion(
            reasoning_token_count=reasoning_tokens,
            text=completion_str,
        )
        
        return completion
        
    except openai.BadRequestError as exc:
        # 4xx errors should not trigger fallback
        raise BadRequestException(f"Invalid request to Azure GPT-5: {str(exc)}") from exc
    except openai.RateLimitError as exc:
        # Rate limit errors are retriable
        logger.warning(f"Rate limit error from Azure GPT-5: {str(exc)}")
        raise RetriableOpenAIError("Rate limit exceeded on Azure GPT-5") from exc
    except openai.APIStatusError as exc:
        if exc.status_code >= 500:
            # 5xx errors are retriable
            logger.warning(f"Server error from Azure GPT-5: {str(exc)}")
            raise RetriableOpenAIError(f"Server error on Azure GPT-5: {exc.status_code}") from exc
        else:
            # Other status errors should not trigger fallback
            raise OpenAIException(f"API error: {str(exc)}") from exc
    except openai.APITimeoutError as exc:
        # Timeout errors are retriable
        logger.warning(f"Timeout from Azure GPT-5: {str(exc)}")
        raise RetriableOpenAIError("Timeout on Azure GPT-5") from exc
    except Exception as exc:
        logger.exception("Unexpected error calling Azure GPT-5:")
        raise OpenAIException(f"Unexpected error: {str(exc)}") from exc


async def get_response_gpt5_azure_streaming(
    client: AsyncAzureOpenAI,
    model_name: str,
    messages: list,
    model_kwargs: dict,
    reasoning_effort: str = "medium",
    verbosity: str = "medium",
    tools: list[dict] = None,
    extra_headers: dict = None,
):
    """
    Get streaming response from Azure GPT-5 using Chat Completions API
    
    Azure Chat Completions API for GPT-5 supports:
    - max_completion_tokens (required for reasoning models)
    - reasoning_effort (minimal, low, medium, high)
    
    Does NOT support:
    - verbosity (only available in Responses API)
    
    Requires API version 2025-03-01-preview or later.
    """
    tools = tools or openai.NOT_GIVEN
    extra_headers = extra_headers or openai.NOT_GIVEN
    
    # Azure Chat Completions API supports max_completion_tokens and reasoning_effort
    # but does NOT support verbosity (that's Responses API only)
    azure_kwargs = dict(model_kwargs)
    
    # Add supported GPT-5 parameters for Chat Completions API
    if reasoning_effort:
        azure_kwargs["reasoning_effort"] = reasoning_effort
    
    # Remove verbosity as it's not supported in Chat Completions API
    azure_kwargs.pop("verbosity", None)
    
    try:
        stream = await client.chat.completions.create(
            model=model_name,
            messages=messages,
            stream=True,
            stream_options={"include_usage": True},
            tools=tools,
            extra_headers=extra_headers,
            **azure_kwargs,
        )

        async for chunk in stream:
            if len(chunk.choices) > 0:
                delta = chunk.choices[0].delta

                if delta.tool_calls:
                    _tool_call = delta.tool_calls[0]
                    tool_call = FunctionCall(
                        name=_tool_call.function.name,
                        arguments=_tool_call.function.arguments,
                    )
                else:
                    tool_call = None

                if delta.content:
                    yield Completion(
                        text=delta.content,
                        tool_call=tool_call,
                    )

            # Handle usage information if available (Azure Chat Completions may not include reasoning tokens)
            if hasattr(chunk, 'usage') and chunk.usage:
                try:
                    if hasattr(chunk.usage, 'completion_tokens_details'):
                        reasoning_tokens = getattr(chunk.usage.completion_tokens_details, 'reasoning_tokens', 0)
                    else:
                        reasoning_tokens = 0
                except AttributeError:
                    reasoning_tokens = 0
                
                yield Completion(
                    reasoning_token_count=reasoning_tokens,
                    text="",
                    tool_call=None,
                )

    except openai.BadRequestError as exc:
        logger.exception(f"Unexpected error in Azure GPT-5 streaming: {exc}")
        raise BadRequestException(f"Invalid request to Azure GPT-5: {str(exc)}") from exc
    except openai.RateLimitError as exc:
        logger.warning(f"Rate limit error from Azure GPT-5 streaming: {str(exc)}")
        raise RetriableOpenAIError("Rate limit exceeded on Azure GPT-5") from exc
    except Exception as exc:
        logger.exception(f"Unexpected error in Azure GPT-5 streaming: {exc}")
        raise OpenAIException(f"Unexpected error in streaming: {str(exc)}") from exc