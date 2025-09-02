"""
Azure GPT-5 Responses API Implementation
Handles communication with Azure OpenAI's GPT-5 models using the Responses API for full feature support
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


async def get_response_gpt5_azure_responses(
    client: AsyncAzureOpenAI,
    model_name: str,
    messages: list,
    model_kwargs: dict,
    reasoning_effort: str = "medium",
    verbosity: str = "medium",
    reasoning_summary: str = None,
    extra_headers: dict = None,
):
    """
    Get response from Azure GPT-5 using Responses API
    
    Supports full GPT-5 feature set:
    - reasoning.effort (minimal, low, medium, high)
    - text.verbosity (low, medium, high)
    - reasoning.summary (auto, concise, detailed)
    
    Requires API version "preview" for Responses API support.
    """
    logger.debug(f"Azure GPT-5 Responses API call for model: {model_name}")
    logger.debug(f"Parameters - reasoning_effort: {reasoning_effort}, verbosity: {verbosity}, reasoning_summary: {reasoning_summary}")
    
    extra_headers = extra_headers or openai.NOT_GIVEN
    
    # Convert Chat Completions messages to Responses API input format
    input_messages = []
    for i, msg in enumerate(messages):
        logger.debug(f"Processing message {i}: role={msg['role']}, content_type={type(msg['content'])}")
        
        # Responses API expects content to be an array of content objects
        if isinstance(msg["content"], str):
            # Map role to appropriate content type
            if msg["role"] == "user":
                content_type = "input_text"
            elif msg["role"] == "assistant":
                content_type = "output_text"
            else:
                content_type = "input_text"  # Default fallback
                
            content = [{"type": content_type, "text": msg["content"]}]
            logger.debug(f"Message {i}: converted string to {content_type}")
        elif isinstance(msg["content"], list):
            # Handle content that's already in array format
            content = []
            for content_item in msg["content"]:
                if isinstance(content_item, dict):
                    if "type" in content_item:
                        # Already has type, validate it
                        if content_item["type"] == "text":
                            # Fix invalid 'text' type
                            fixed_type = "input_text" if msg["role"] == "user" else "output_text"
                            content.append({"type": fixed_type, "text": content_item.get("text", "")})
                            logger.debug(f"Message {i}: fixed type 'text' -> '{fixed_type}'")
                        else:
                            content.append(content_item)
                    else:
                        # No type specified, add appropriate type
                        content_type = "input_text" if msg["role"] == "user" else "output_text"
                        content.append({"type": content_type, "text": content_item.get("text", str(content_item))})
                        logger.debug(f"Message {i}: added missing type '{content_type}'")
                else:
                    # Convert non-dict content to proper format
                    content_type = "input_text" if msg["role"] == "user" else "output_text"
                    content.append({"type": content_type, "text": str(content_item)})
                    logger.debug(f"Message {i}: converted non-dict to '{content_type}'")
        else:
            # Handle other content types
            content_type = "input_text" if msg["role"] == "user" else "output_text"
            content = [{"type": content_type, "text": str(msg["content"])}]
            logger.debug(f"Message {i}: converted other type to '{content_type}'")
        
        input_messages.append({
            "role": msg["role"],
            "content": content
        })
        
        logger.debug(f"Message {i} final content: {content}")
    
    logger.debug(f"Converted {len(messages)} messages to Responses API format")
    logger.debug(f"Full input_messages structure: {input_messages}")
    
    # Build Responses API parameters
    # Always use the full conversation format as per Azure documentation
    responses_kwargs = {
        "model": model_name,
        "input": input_messages,
        "reasoning": {
            "effort": reasoning_effort
        },
        "text": {
            "verbosity": verbosity
        }
    }
    
    logger.debug(f"Responses API request structure:")
    logger.debug(f"  Model: {model_name}")
    logger.debug(f"  Input messages count: {len(input_messages)}")
    logger.debug(f"  Reasoning effort: {reasoning_effort}")
    logger.debug(f"  Text verbosity: {verbosity}")
    
    # Log full request for debugging (be careful with sensitive data)
    logger.debug(f"Full Responses API request: {responses_kwargs}")
    
    # Add reasoning summary if requested
    # Note: Some GPT-5 model versions only support "detailed" summary
    # Fallback to "detailed" if other options are not supported
    if reasoning_summary and reasoning_summary != "disabled":
        # For now, map all non-disabled values to "detailed" as it's the only supported option
        # for gpt-5-2025-08-07 model according to Azure
        if reasoning_summary in ["auto", "concise"]:
            logger.warning(f"Model {model_name} may not support '{reasoning_summary}' summary, using 'detailed' instead")
            responses_kwargs["reasoning"]["summary"] = "detailed"
        else:
            responses_kwargs["reasoning"]["summary"] = reasoning_summary
        logger.debug(f"Reasoning summary enabled: {responses_kwargs['reasoning'].get('summary', reasoning_summary)}")
    
    # Add max_output_tokens (Responses API uses this instead of max_completion_tokens)
    if "max_completion_tokens" in model_kwargs:
        responses_kwargs["max_output_tokens"] = model_kwargs["max_completion_tokens"]
        logger.debug(f"Set max_output_tokens: {model_kwargs['max_completion_tokens']}")
    
    # Remove Chat Completions specific parameters that don't apply to Responses API
    # Also remove unsupported parameters for GPT-5 reasoning models
    azure_kwargs = dict(model_kwargs)
    removed_params = []
    unsupported_params = ["reasoning_effort", "verbosity", "max_completion_tokens", 
                         "temperature", "top_p", "presence_penalty", "frequency_penalty", 
                         "logprobs", "top_logprobs", "logit_bias", "max_tokens", "reasoning_summary"]
    # Note: reasoning_summary is handled separately above and must be filtered out to avoid duplication
    
    for param in unsupported_params:
        if azure_kwargs.pop(param, None) is not None:
            removed_params.append(param)
    
    if removed_params:
        logger.debug(f"Removed Chat Completions parameters: {removed_params}")
    
    # Merge any remaining valid parameters
    responses_kwargs.update(azure_kwargs)
    
    try:
        logger.debug("Calling Azure Responses API...")
        response = await client.responses.create(
            extra_headers=extra_headers,
            **responses_kwargs,
        )
        
        logger.debug(f"Azure GPT-5 Responses API completed successfully (ID: {response.id})")
        
        # Extract text content from Responses API output
        completion_text = ""
        reasoning_tokens = 0
        reasoning_summary_text = None
        
        logger.debug(f"Processing {len(response.output)} output items")
        
        for output_item in response.output:
            logger.debug(f"Processing output item type: {output_item.type}")
            
            if output_item.type == "message":
                for content in output_item.content:
                    if content.type == "output_text":
                        completion_text += content.text
                        logger.debug(f"Added {len(content.text)} characters to completion")
            
            elif output_item.type == "reasoning":
                # Extract reasoning summary if available
                if hasattr(output_item, 'summary') and output_item.summary:
                    reasoning_summary_text = "\n".join(output_item.summary)
                    logger.info(f"Extracted reasoning summary: {len(reasoning_summary_text)} characters")
        
        # Get token usage information
        if hasattr(response, 'usage') and response.usage:
            if hasattr(response.usage, 'output_tokens_details'):
                reasoning_tokens = getattr(response.usage.output_tokens_details, 'reasoning_tokens', 0)
                logger.debug(f"Token usage - reasoning: {reasoning_tokens}, total: {response.usage.total_tokens}")
            else:
                logger.warning("No output_tokens_details found in usage")
        else:
            logger.warning("No usage information in response")
        
        completion = Completion(
            reasoning_token_count=reasoning_tokens,
            text=completion_text.strip(),
        )
        
        # Add reasoning summary to completion if available (store in extended_logging for now)
        if reasoning_summary_text:
            completion.extended_logging = {
                "reasoning_summary": reasoning_summary_text,
                "api_type": "responses"
            }
        
        return completion
        
    except openai.BadRequestError as exc:
        logger.error(f"Bad request to Azure GPT-5 Responses API: {str(exc)}")
        raise BadRequestException(f"Invalid request to Azure GPT-5 Responses API: {str(exc)}") from exc
    
    except openai.RateLimitError as exc:
        logger.warning(f"Rate limit error from Azure GPT-5 Responses API: {str(exc)}")
        raise RetriableOpenAIError("Rate limit exceeded on Azure GPT-5 Responses API") from exc
    
    except openai.APIStatusError as exc:
        if exc.status_code >= 500:
            logger.warning(f"Server error from Azure GPT-5 Responses API: {str(exc)}")
            raise RetriableOpenAIError(f"Server error on Azure GPT-5 Responses API: {exc.status_code}") from exc
        else:
            logger.error(f"API status error from Azure GPT-5 Responses API: {str(exc)}")
            raise OpenAIException(f"API error: {str(exc)}") from exc
    
    except openai.APITimeoutError as exc:
        logger.warning(f"Timeout from Azure GPT-5 Responses API: {str(exc)}")
        raise RetriableOpenAIError("Timeout on Azure GPT-5 Responses API") from exc
    
    except Exception as exc:
        logger.exception("Unexpected error calling Azure GPT-5 Responses API")
        raise OpenAIException(f"Unexpected error: {str(exc)}") from exc


async def get_response_gpt5_azure_responses_streaming(
    client: AsyncAzureOpenAI,
    model_name: str,
    messages: list,
    model_kwargs: dict,
    reasoning_effort: str = "medium",
    verbosity: str = "medium",
    reasoning_summary: str = None,
    tools: list[dict] = None,
    extra_headers: dict = None,
):
    """
    Get streaming response from Azure GPT-5 using Responses API
    
    Supports full GPT-5 feature set with streaming:
    - reasoning.effort (minimal, low, medium, high)
    - text.verbosity (low, medium, high) 
    - reasoning.summary (auto, concise, detailed)
    """
    logger.debug(f"Azure GPT-5 Responses API streaming call for model: {model_name}")
    logger.debug(f"Parameters - reasoning_effort: {reasoning_effort}, verbosity: {verbosity}, reasoning_summary: {reasoning_summary}")
    
    tools = tools or openai.NOT_GIVEN
    extra_headers = extra_headers or openai.NOT_GIVEN
    
    # Convert Chat Completions messages to Responses API input format
    input_messages = []
    for i, msg in enumerate(messages):
        logger.debug(f"Streaming - Processing message {i}: role={msg['role']}, content_type={type(msg['content'])}")
        
        # Responses API expects content to be an array of content objects
        if isinstance(msg["content"], str):
            # Map role to appropriate content type
            if msg["role"] == "user":
                content_type = "input_text"
            elif msg["role"] == "assistant":
                content_type = "output_text"
            else:
                content_type = "input_text"  # Default fallback
                
            content = [{"type": content_type, "text": msg["content"]}]
            logger.debug(f"Streaming - Message {i}: converted string to {content_type}")
        elif isinstance(msg["content"], list):
            # Handle content that's already in array format
            content = []
            for content_item in msg["content"]:
                if isinstance(content_item, dict):
                    if "type" in content_item:
                        # Already has type, validate it
                        if content_item["type"] == "text":
                            # Fix invalid 'text' type
                            fixed_type = "input_text" if msg["role"] == "user" else "output_text"
                            content.append({"type": fixed_type, "text": content_item.get("text", "")})
                            logger.debug(f"Streaming - Message {i}: fixed type 'text' -> '{fixed_type}'")
                        else:
                            content.append(content_item)
                    else:
                        # No type specified, add appropriate type
                        content_type = "input_text" if msg["role"] == "user" else "output_text"
                        content.append({"type": content_type, "text": content_item.get("text", str(content_item))})
                        logger.debug(f"Streaming - Message {i}: added missing type '{content_type}'")
                else:
                    # Convert non-dict content to proper format
                    content_type = "input_text" if msg["role"] == "user" else "output_text"
                    content.append({"type": content_type, "text": str(content_item)})
                    logger.debug(f"Streaming - Message {i}: converted non-dict to '{content_type}'")
        else:
            # Handle other content types
            content_type = "input_text" if msg["role"] == "user" else "output_text"
            content = [{"type": content_type, "text": str(msg["content"])}]
            logger.debug(f"Streaming - Message {i}: converted other type to '{content_type}'")
        
        input_messages.append({
            "role": msg["role"],
            "content": content
        })
        
        logger.debug(f"Streaming - Message {i} final content: {content}")
    
    logger.debug(f"Streaming - Converted {len(messages)} messages to Responses API format")
    logger.debug(f"Streaming - Full input_messages structure: {input_messages}")
    
    # Build Responses API parameters for streaming
    # Always use the full conversation format as per Azure documentation
    responses_kwargs = {
        "model": model_name,
        "input": input_messages,
        "stream": True,
        "reasoning": {
            "effort": reasoning_effort
        },
        "text": {
            "verbosity": verbosity
        }
    }
    
    logger.debug(f"Streaming Responses API request structure:")
    logger.debug(f"  Model: {model_name}")
    logger.debug(f"  Input messages count: {len(input_messages)}")
    logger.debug(f"  Reasoning effort: {reasoning_effort}")
    logger.debug(f"  Text verbosity: {verbosity}")
    
    # Log full request for debugging (be careful with sensitive data)
    logger.debug(f"Full streaming Responses API request: {responses_kwargs}")
    
    # Add reasoning summary if requested
    # Note: Some GPT-5 model versions only support "detailed" summary
    # Fallback to "detailed" if other options are not supported
    if reasoning_summary and reasoning_summary != "disabled":
        # For now, map all non-disabled values to "detailed" as it's the only supported option
        # for gpt-5-2025-08-07 model according to Azure
        if reasoning_summary in ["auto", "concise"]:
            logger.warning(f"Model {model_name} may not support '{reasoning_summary}' summary, using 'detailed' instead")
            responses_kwargs["reasoning"]["summary"] = "detailed"
        else:
            responses_kwargs["reasoning"]["summary"] = reasoning_summary
        logger.debug(f"Reasoning summary enabled for streaming: {responses_kwargs['reasoning'].get('summary', reasoning_summary)}")
    
    # Add max_output_tokens if specified
    if "max_completion_tokens" in model_kwargs:
        responses_kwargs["max_output_tokens"] = model_kwargs["max_completion_tokens"]
        logger.debug(f"Set max_output_tokens for streaming: {model_kwargs['max_completion_tokens']}")
    
    # Add tools if provided
    if tools and tools != openai.NOT_GIVEN:
        responses_kwargs["tools"] = tools
        logger.debug(f"Added {len(tools)} tools to streaming request")
    
    # Remove Chat Completions specific parameters and unsupported GPT-5 parameters
    azure_kwargs = dict(model_kwargs)
    removed_params = []
    unsupported_params = ["reasoning_effort", "verbosity", "max_completion_tokens", 
                         "temperature", "top_p", "presence_penalty", "frequency_penalty", 
                         "logprobs", "top_logprobs", "logit_bias", "max_tokens", "reasoning_summary"]
    # Note: reasoning_summary is handled separately above and must be filtered out to avoid duplication
    
    for param in unsupported_params:
        if azure_kwargs.pop(param, None) is not None:
            removed_params.append(param)
    
    if removed_params:
        logger.debug(f"Removed Chat Completions parameters from streaming: {removed_params}")
    
    # Merge any remaining valid parameters
    responses_kwargs.update(azure_kwargs)
    
    try:
        logger.debug("Starting Azure Responses API streaming...")
        stream = await client.responses.create(
            extra_headers=extra_headers,
            **responses_kwargs,
        )
        
        reasoning_tokens = 0
        
        async for event in stream:
            logger.debug(f"Received streaming event type: {event.type}")
            
            if event.type == 'response.output_text.delta':
                # Text content streaming
                yield Completion(
                    text=event.delta,
                    tool_call=None,
                )
            
            elif event.type == 'response.function_call.delta':
                # Function call streaming (if tools are used)
                if hasattr(event, 'function_call'):
                    tool_call = FunctionCall(
                        name=event.function_call.name,
                        arguments=event.function_call.arguments,
                    )
                    yield Completion(
                        text="",
                        tool_call=tool_call,
                    )
            
            elif event.type == 'response.done':
                # Stream completion - extract final usage information
                if hasattr(event, 'response') and hasattr(event.response, 'usage'):
                    if hasattr(event.response.usage, 'output_tokens_details'):
                        reasoning_tokens = getattr(event.response.usage.output_tokens_details, 'reasoning_tokens', 0)
                        logger.debug(f"Streaming completed - reasoning tokens: {reasoning_tokens}")
                
                # Yield final completion with token counts
                yield Completion(
                    reasoning_token_count=reasoning_tokens,
                    text="",
                    tool_call=None,
                )
            
            elif event.type == 'response.reasoning.done':
                # Reasoning phase completed
                logger.debug("Reasoning phase completed in streaming")
            
            elif event.type == 'error':
                # Handle streaming errors
                logger.error(f"Streaming error: {event.error}")
                raise OpenAIException(f"Streaming error: {event.error}")
        
        logger.info("Azure GPT-5 Responses API streaming completed successfully")

    except openai.BadRequestError as exc:
        logger.error(f"Bad request in Azure GPT-5 Responses API streaming: {str(exc)}")
        raise BadRequestException(f"Invalid request to Azure GPT-5 Responses API: {str(exc)}") from exc
    
    except openai.RateLimitError as exc:
        logger.warning(f"Rate limit error in Azure GPT-5 Responses API streaming: {str(exc)}")
        raise RetriableOpenAIError("Rate limit exceeded on Azure GPT-5 Responses API") from exc
    
    except Exception as exc:
        logger.exception("Unexpected error in Azure GPT-5 Responses API streaming")
        raise OpenAIException(f"Unexpected error in streaming: {str(exc)}") from exc