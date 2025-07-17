import logging
logger = logging.getLogger(__name__)

import asyncio
import requests
from requests.exceptions import HTTPError, Timeout, RequestException

from fastapi import HTTPException, status
from typing import List, Dict, Any

from llama_index.core.llms import ChatMessage, MessageRole, ChatResponse
from openai.types.chat.chat_completion import ChatCompletion

from core.storages.client import TracerManager as TM
from core.parsers import json_parser

from services.agentic_workflow.tools import PromptProcessorTool as PPT
from services import get_settings_cached, get_google_genai_llm, GoogleGenAILLM, get_xai_llm, XAILLM


def _extract_video_id(url: str):
    if "youtube.com/watch?v=" in url:
        return url.split("v=")[1].split("&")[0]
    elif "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    else:
        return url

async def _create_messages(
    agent: dict,
    input_: Any
):
    messages = [
        ChatMessage(
            role=MessageRole.SYSTEM,
            content=(
                f"{agent['role']}: {agent['description']}\n\n"
                f"## Hướng dẫn:\n{agent['instructions']}\n\n"
            )
        ),
        ChatMessage(role=MessageRole.USER, content=f"## Đầu vào:\n{input_}\n\n## Phản hồi:\n"),
    ]

    return messages

async def _chat(
    user_id: str,
    session_id: str,
    model: GoogleGenAILLM,
    messages: List[ChatMessage],
    agent_name: str
):
    try:
        async with TM.trace_span(
            span_name=agent_name,
            span_type="LLM_AGENT_CALL",
            custom_metadata={
                "user_id": user_id,
                "session_id": session_id,
                "agent_name": agent_name,
            }
        ) as (_, _, wrapper):
            response: ChatResponse = await wrapper(model.arun, messages=messages)

        return response.message.content
    except Exception as e:
        logger.exception("Chat call failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Lỗi khi xử lý phân tích comment'
        )

async def _process_batch(
    user_id: str,
    session_id: str,
    model: GoogleGenAILLM,
    batch_json: dict,
    batch_idx: int,
    agent: dict,
    agent_name: str
):

    logger.info(f"[Batch {batch_idx}] Đang được xử lý")
    messages = await _create_messages(agent=agent, input_=batch_json)
    response  = await _chat(user_id=user_id, session_id=session_id, model=model, messages=messages, agent_name=agent_name)
    return response

async def _analyze(
    user_id: str,
    session_id: str,
    video_url: str,
    user_request: str,
    comment_analyzer: dict,
    analysis_aggregator_expert: dict
):
    yield {'_type': 'header_thinking', 'text': "Đang thu thập comment"}

    try:
        comments = await crawl_comment(video_url)
    except HTTPException:
        raise

    model = get_google_genai_llm(model_name='gemini-2.0-flash')

    yield {'_type': 'header_thinking', 'text': "Đang phân tích"}
    try:
        text_comments = []
        id_comments = []
        for comment in comments:
            text_comments.append(comment['text'])
            id_comments.append(comment['comment_id'])

        total_comments = len(text_comments)
        batch_size = 256

        all_batches = []
        for idx in range(0, total_comments, batch_size):
            input_ = {
                'user_request': user_request
            }
            batch_text = text_comments[idx:idx + batch_size]
            batch_id   = id_comments[idx:idx + batch_size]
            batch_json = {str(cid): text for cid, text in zip(batch_id, batch_text)}
            input_['comments'] = batch_json
            all_batches.append(input_)


        batch_response = []
        tasks = []
        for i in range(0, len(all_batches)):
            tasks.append(
                _process_batch(
                    user_id=user_id,
                    session_id=session_id,
                    model=model,
                    batch_json=all_batches[i],
                    batch_idx=i,
                    agent=comment_analyzer,
                    agent_name="comment_analyzer"
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"[Batch] Lỗi khi xử lý batch: {result}")
                continue
            batch_response.append(result)

        if not batch_response:
            logger.error(f"Sau khi chạy tất cả batch, `batch_response` rỗng! all_batches: {all_batches}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail='Lỗi khi xử lý phân tích comment'
            )

        if len(batch_response) > 1:
            messages = await _create_messages(
                agent=analysis_aggregator_expert,
                input_=batch_response
            )
            response = await _chat(user_id=user_id, session_id=session_id, model=model, messages=messages, agent_name="analysis_aggregator_expert")
        else:
            response = batch_response[0]

        yield {'_type': 'response', 'text': response}

    except Exception as e:
        logger.error(f"Lỗi khi xử lý phân tích comment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Lỗi khi xử lý phân tích comment'
        )

async def crawl_comment(
    video_url: str,
):
    video_id = _extract_video_id(video_url)
    downstream = "http://crawl-comment:5000/api/comments"
    params = {"video_id": video_id, "max_results": 1000}

    try:
        resp = requests.get(downstream, params=params, timeout=3600)
        resp.raise_for_status()
    except Timeout:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Request to downstream comments API timed out"
        )
    except HTTPError as e:
        raise HTTPException(
            status_code=resp.status_code,
            detail=f"Downstream error: {resp.text}"
        )
    except RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to connect to downstream comments API: {e}"
        )

    try:
        return resp.json()['comments']
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Downstream comments API returned invalid JSON"
        )

async def comment_analyze(
    query_text: str,
    user_id: str,
    session_id: str,
    initial_messages: List[ChatMessage],
    *args, **kwargs
):
    xai_llm: XAILLM = get_xai_llm(
        model_name=get_settings_cached().XAI_MODEL_NAME,
    )

    agents = PPT.load_prompt(get_settings_cached().HGGPT_AGENT_PROMPT_PATH)

    comment_id: dict = agents['CommentIQ']
    comment_analyzer: dict = agents['comment_analyzer']
    analysis_aggregator_expert: dict = agents['analysis_aggregator_expert']

    messages = [
        ChatMessage(role=MessageRole.SYSTEM, content="\n".join(comment_id.values()))
    ] + initial_messages[1:] + [
        ChatMessage(role=MessageRole.USER, content=query_text)
    ]

    async with TM.trace_span(
        span_name="CommentIQ",
        span_type="LLM_AGENT_CALL",
        custom_metadata={
            "user_id": user_id,
            "session_id": session_id,
            "agent_name": "CommentIQ",
        }
    ) as (_, _, wrapper):
        response: ChatCompletion = await wrapper(xai_llm.arun, messages=messages)

    json_resp = json_parser(response.choices[0].message.content)
    if "status" in json_resp:
        if json_resp['status'] == 'READY_FOR_ANALYSIS':
            yield {'_type': 'response', 'text': f"{json_resp['response']}\n"}

            async for data in _analyze(
                user_id=user_id,
                session_id=session_id,
                video_url=json_resp['video_url'],
                user_request=json_resp['user_request'],
                comment_analyzer=comment_analyzer,
                analysis_aggregator_expert=analysis_aggregator_expert,
            ):
                yield data
        else:
            yield {'_type': 'response', 'text': response.choices[0].message.content}
