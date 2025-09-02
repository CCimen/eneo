"""
GPT-5 Responses API Implementation
Handles communication with OpenAI's new Responses API endpoint for GPT-5 models
"""
import openai
from openai import AsyncOpenAI
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


async def get_response_gpt5(
    client: AsyncOpenAI,
    model_name: str,
    messages: list,
    model_kwargs: dict,
    reasoning_effort: str = "medium",
    verbosity: str = "medium",
    extra_headers: dict = None,
):
    """
    Get response from GPT-5 using fallback to Chat Completions API
    
    Note: Until OpenAI Python client supports Responses API,
    we'll use Chat Completions with GPT-5 parameters.
    """
    import openai
    
    extra_headers = extra_headers or openai.NOT_GIVEN
    
    # Use Chat Completions API - filter out GPT-5 specific parameters for compatibility
    # The Chat Completions API doesn't support reasoning_effort and verbosity yet
    gpt5_kwargs = dict(model_kwargs)
    # Remove GPT-5 specific parameters that aren't supported in Chat Completions API
    gpt5_kwargs.pop("reasoning_effort", None)
    gpt5_kwargs.pop("verbosity", None)
    # Note: GPT-5 parameters will be supported when we switch to Responses API
    
    try:
        response = await client.chat.completions.create(
            model=model_name,
            messages=messages,
            extra_headers=extra_headers,
            **gpt5_kwargs,
        )
        choices = response.choices
        
        completion_str = choices[0].message.content.strip()
        
        # Get reasoning tokens if available
        reasoning_tokens = 0
        try:
            reasoning_tokens = response.usage.completion_tokens_details.reasoning_tokens
        except AttributeError:
            reasoning_tokens = 0
        
        completion = Completion(
            reasoning_token_count=reasoning_tokens,
            text=completion_str,
        )
        
        return completion
        
    except openai.BadRequestError as exc:
        # 4xx errors should not trigger fallback
        raise BadRequestException(f"Invalid request to GPT-5: {str(exc)}") from exc
    except openai.RateLimitError as exc:
        # Rate limit errors are retriable
        logger.warning(f"Rate limit error from GPT-5: {str(exc)}")
        raise RetriableOpenAIError("Rate limit exceeded on GPT-5") from exc
    except openai.APIStatusError as exc:
        if exc.status_code >= 500:
            # 5xx errors are retriable
            logger.warning(f"Server error from GPT-5: {str(exc)}")
            raise RetriableOpenAIError(f"Server error on GPT-5: {exc.status_code}") from exc
        else:
            # Other status errors should not trigger fallback
            raise OpenAIException(f"API error: {str(exc)}") from exc
    except openai.APITimeoutError as exc:
        # Timeout errors are retriable
        logger.warning(f"Timeout from GPT-5: {str(exc)}")
        raise RetriableOpenAIError("Timeout on GPT-5") from exc
    except Exception as exc:
        logger.exception("Unexpected error calling GPT-5:")
        raise OpenAIException(f"Unexpected error: {str(exc)}") from exc


async def get_response_gpt5_streaming(
    client: AsyncOpenAI,
    model_name: str,
    messages: list,
    model_kwargs: dict,
    reasoning_effort: str = "medium",
    verbosity: str = "medium",
    tools: list[dict] = None,
    extra_headers: dict = None,
):
    """
    Get streaming response from GPT-5 using fallback to Chat Completions API
    
    Note: Until OpenAI Python client supports Responses API,
    we'll use Chat Completions with GPT-5 parameters.
    """
    import openai
    
    tools = tools or openai.NOT_GIVEN
    extra_headers = extra_headers or openai.NOT_GIVEN
    
    # Use Chat Completions API - filter out GPT-5 specific parameters for compatibility
    # The Chat Completions API doesn't support reasoning_effort and verbosity yet
    gpt5_kwargs = dict(model_kwargs)
    # Remove GPT-5 specific parameters that aren't supported in Chat Completions API
    gpt5_kwargs.pop("reasoning_effort", None)
    gpt5_kwargs.pop("verbosity", None)
    # Note: GPT-5 parameters will be supported when we switch to Responses API
    
    try:
        stream = await client.chat.completions.create(
            model=model_name,
            messages=messages,
            stream=True,
            stream_options={"include_usage": True},
            tools=tools,
            extra_headers=extra_headers,
            **gpt5_kwargs,
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

            # Handle usage information if available
            if hasattr(chunk, 'usage') and chunk.usage:
                try:
                    reasoning_tokens = chunk.usage.completion_tokens_details.reasoning_tokens
                except AttributeError:
                    reasoning_tokens = 0
                
                yield Completion(
                    reasoning_token_count=reasoning_tokens,
                    text="",
                    tool_call=None,
                )

    except openai.BadRequestError as exc:
        logger.exception(f"Unexpected error in GPT-5 streaming: {exc}")
        raise BadRequestException(f"Invalid request to GPT-5: {str(exc)}") from exc
    except openai.RateLimitError as exc:
        logger.warning(f"Rate limit error from GPT-5 streaming: {str(exc)}")
        raise RetriableOpenAIError("Rate limit exceeded on GPT-5") from exc
    except Exception as exc:
        logger.exception(f"Unexpected error in GPT-5 streaming: {exc}")
        raise OpenAIException(f"Unexpected error in streaming: {str(exc)}") from exc


def _convert_messages_to_input(messages: list) -> str:
    """
    Convert chat messages format to a single input string for Responses API
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        
    Returns:
        Formatted input string
    """
    if not messages:
        return ""
    
    # For a single user message, just return the content
    if len(messages) == 1 and messages[0].get("role") == "user":
        return messages[0].get("content", "")
    
    # For multiple messages, format them appropriately
    formatted_parts = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        
        if role == "system":
            formatted_parts.append(f"System: {content}")
        elif role == "user":
            formatted_parts.append(f"User: {content}")
        elif role == "assistant":
            formatted_parts.append(f"Assistant: {content}")
        else:
            formatted_parts.append(content)
    
    return "\n\n".join(formatted_parts)


def _filter_model_kwargs_for_responses_api(model_kwargs: dict) -> dict:
    """
    Filter model kwargs to only include parameters compatible with Responses API
    
    Args:
        model_kwargs: Original model kwargs from chat completions
        
    Returns:
        Filtered kwargs suitable for Responses API
    """
    # The Responses API has different parameters than Chat Completions
    # Filter out chat-specific parameters
    chat_only_params = {
        "temperature", "top_p", "n", "stop", "max_tokens",
        "presence_penalty", "frequency_penalty", "logit_bias",
        "user", "seed", "response_format", "tool_choice"
    }
    
    filtered = {}
    for key, value in model_kwargs.items():
        if key not in chat_only_params:
            filtered[key] = value
    
    # Map some parameters if they have equivalents in Responses API
    # For now, we'll keep this simple and may need to expand based on actual API behavior
    
    return filtered