from google import genai
from google.genai import types

from llama_index.core.llms import ChatMessage, MessageRole, ChatResponse

from core.storages.client import TracerManager as TM
from core.parsers import json_parser

from services.agentic_workflow.tools import PromptProcessorTool as PPT
from services import get_settings_cached, get_google_genai_llm

async def _analyze(
    video_analyzer: dict,
    video_url: str,
    user_request: str,
    start_time: str,
    end_time: str,
    fps: int,
):
    client = genai.Client(
        api_key=get_settings_cached().GOOGLEAI_API_KEY,
    )

    response = client.models.generate_content(
        model=get_settings_cached().GOOGLEAI_MODEL_THINKING,
        config=types.GenerateContentConfig(
            system_instruction="\n".join(video_analyzer.values()),
        ),
        contents=types.Content(
            parts=[
                types.Part(
                    file_data=types.FileData(file_uri=video_url),
                    video_metadata=types.VideoMetadata(
                        start_time=start_time,
                        end_time=end_time,
                        fps=fps,
                    )
                ),
                types.Part(text=user_request)
            ]
        )
    )

    return response

async def video_analyze(
    query_text: str,
    user_id: str,
    session_id: str,
    start_time: str,
    end_time: str,
    fps: int,
    initial_messages: list[ChatMessage],
    *args, **kwargs
):
    google_llm = get_google_genai_llm(
        model_name=get_settings_cached().GOOGLEAI_MODEL_THINKING,
    )

    agents = PPT.load_prompt(get_settings_cached().HGGPT_AGENT_PROMPT_PATH)
    video_analyzer: dict = agents['video_analyzer']
    vidmind: dict = agents['VidMind']

    messages = [
        ChatMessage(role=MessageRole.SYSTEM, content="\n".join(vidmind.values()))
    ] + initial_messages[1:] + [
        ChatMessage(role=MessageRole.USER, content=query_text)
    ]

    async with TM.trace_span(
        span_name="VidMind",
        span_type="LLM_AGENT_CALL",
        custom_metadata={
            "user_id": user_id,
            "session_id": session_id,
            "agent_name": "VidMind",
        }
    ) as (_, _, wrapper):
        response: ChatResponse = await wrapper(google_llm.arun, messages=messages)

    json_resp = json_parser(response.message.content)
    if "status" in json_resp:
        if json_resp['status'] == 'READY_FOR_ANALYSIS':
            yield {'_type': 'response', 'text': f"{json_resp['response']}\n"}

            async with TM.trace_span(
                span_name="video_analyzer",
                span_type="LLM_AGENT_CALL",
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
                    start_time=start_time,
                    end_time=end_time,
                    fps=fps
                )

            yield {'_type': 'response', 'text': response.text}
            return

    yield {'_type': 'response', 'text': response.message.content}



