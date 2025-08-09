import logging
import requests
import asyncio

from google import genai
from google.genai import types

from llama_index.core.llms import ChatMessage, MessageRole, ChatResponse

from core.storages.client import TracerManager as TM
from core.parsers import json_parser

from services.agentic_workflow.tools import PromptProcessorTool as PPT
from services import get_settings_cached, get_google_genai_llm

logger = logging.getLogger(__name__)

async def count_video_tokens(
    video_url: str,
    start_offset: str,
    end_offset: str,
    fps: int,
):
    try:
        if start_offset is not None and end_offset is not None:
            total_tokens = (int(end_offset[:-1]) - int(start_offset[:-1])) * int(fps) * 300
        else:
            downstream = "http://crawl-comment:5000/api/video/check"
            params = {"url": video_url}
            resp = await asyncio.to_thread(requests.post, downstream, params=params, timeout=5)
            js_resp = resp.json()
            if js_resp["exists"]:
                total_tokens = js_resp["video_info"]["duration_seconds"] * int(fps) * 300
            else:
                total_tokens = 0

        return total_tokens
    except (requests.RequestException, ValueError, KeyError, TypeError) as e:
        logger.error(f"Error counting video tokens: {e}")
        raise

async def _analyze(
    video_analyzer: dict,
    video_url: str,
    user_request: str,
    start_offset: str,
    end_offset: str,
    fps: int,
):
    try:
        client = genai.Client(
            api_key=get_settings_cached().GOOGLEAI_API_KEY,
        )

        response = await asyncio.to_thread(
            client.models.generate_content,
            model=get_settings_cached().GOOGLEAI_MODEL_THINKING,
            config=types.GenerateContentConfig(
                system_instruction="\n".join(video_analyzer.values()),
            ),
            contents=types.Content(
                parts=[
                    types.Part(
                        file_data=types.FileData(file_uri=video_url),
                        video_metadata=types.VideoMetadata(
                            start_offset=start_offset,
                            end_offset=end_offset,
                            fps=fps,
                        )
                    ),
                    types.Part(text=user_request)
                ]
            )
        )

        return response
    except Exception as e:
        logger.error(f"Error in video analysis: {e}")
        raise

async def video_analyze(
    query_text: str,
    user_id: str,
    session_id: str,
    initial_messages: list[ChatMessage],
    *args, **kwargs
):
    try:
        google_llm = get_google_genai_llm(
            model_name=get_settings_cached().GOOGLEAI_MODEL_THINKING,
        )
    except Exception as e:
        logger.error(f"Error initializing Google LLM: {e}")
        yield {'_type': 'error', 'text': "Internal server error"}
        return

    try:
        agents = PPT.load_prompt(get_settings_cached().HGGPT_AGENT_PROMPT_PATH)
        video_analyzer: dict = agents['video_analyzer']
        vidmind: dict = agents['VidMind']
    except (KeyError, Exception) as e:
        logger.error(f"Error loading agent prompts: {e}")
        yield {'_type': 'error', 'text': "Internal server error"}
        return

    try:
        messages = [
            ChatMessage(role=MessageRole.SYSTEM, content="\n".join(vidmind.values()))
        ] + initial_messages[1:] + [
            ChatMessage(role=MessageRole.USER, content=query_text)
        ]
    except Exception as e:
        logger.error(f"Error creating messages: {e}")
        yield {'_type': 'error', 'text': "Internal server error"}
        return

    async with TM.trace_span(
        span_name="VidMind",
        span_type="HGGPT",
        custom_metadata={
            "user_id": user_id,
            "session_id": session_id,
            "agent_name": "VidMind",
        }
    ) as (_, _, wrapper):
        try:
            response: ChatResponse = await wrapper(google_llm.arun, messages=messages)
        except Exception as e:
            logger.error(f"Error calling VidMind: {e}")
            yield {'_type': 'error', 'text': "Internal server error"}
            return

    try:
        json_resp = json_parser(response.message.content)
    except Exception as e:
        logger.error(f"Error parsing JSON response: {e}")
        # Fallback to plain text response if JSON parsing fails
        yield {'_type': 'response', 'text': response.message.content}
        return

    try:
        if "status" in json_resp:
            if json_resp['status'] == 'READY_FOR_ANALYSIS':
                try:
                    total_tokens = await count_video_tokens(
                        video_url=json_resp['video_url'],
                        start_offset=json_resp['analysis_params']['start_offset'],
                        end_offset=json_resp['analysis_params']['end_offset'],
                        fps=json_resp['analysis_params']['fps']
                    )
                except (KeyError, Exception) as e:
                    logger.error(f"Error counting video tokens: {e}")
                    yield {'_type': 'error', 'text': "Internal server error"}
                    return

                if total_tokens > 0 and total_tokens < 512000:
                    yield {'_type': 'response', 'text': f"{json_resp['response']}\n\n"}

                    try:
                        async with TM.trace_span(
                            span_name="video_analyzer",
                            span_type="HGGPT",
                            custom_metadata={
                                "user_id": user_id,
                                "session_id": session_id,
                                "agent_name": "video_analyzer",
                            }
                        ) as (_, _, wrapper):
                            response = await wrapper(
                                _analyze,
                                video_analyzer=video_analyzer,
                                video_url=json_resp['video_url'],
                                user_request=json_resp['user_request'],
                                start_offset=json_resp['analysis_params']['start_offset'],
                                end_offset=json_resp['analysis_params']['end_offset'],
                                fps=json_resp['analysis_params']['fps']
                            )

                        # Check if response has text attribute
                        if hasattr(response, 'text'):
                            yield {'_type': 'response', 'text': response.text}
                        else:
                            logger.error("Response object missing 'text' attribute")
                            yield {'_type': 'error', 'text': "Internal server error"}

                    except Exception as e:
                        logger.error(f"Error in video analysis: {e}")
                        yield {'_type': 'error', 'text': "Internal server error"}
                else:
                    logger.error(f"Invalid token count: {total_tokens}")
                    yield {'_type': 'error', 'text': "Internal server error"}
            else:
                yield {'_type': 'response', 'text': response.message.content}
        else:
            # No status field in response - return raw response
            yield {'_type': 'response', 'text': response.message.content}

    except KeyError as e:
        logger.error(f"Missing required field in JSON response: {e}")
        yield {'_type': 'error', 'text': "Internal server error"}
        return
    except Exception as e:
        logger.error(f"Unexpected error processing response: {e}")
        yield {'_type': 'error', 'text': "Internal server error"}
        return
