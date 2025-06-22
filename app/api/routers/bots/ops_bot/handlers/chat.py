import json
import random
from datetime import datetime
from uuid import uuid4

from services.agentic_workflow.bots.ops_bot import OpsBotService
from core.storages import BaseChat
from api.schema import (
    UserContext
)
from services import get_settings_cached

async def tiktokenize(text: str) -> list[str]:
    import tiktoken

    encoding = tiktoken.get_encoding("o200k_base")

    token_ids = encoding.encode(text)

    tokens: list[str] = []
    for tid in token_ids:
        try:
            token_str = encoding.decode_single_token_str(tid)
        except AttributeError:
            token_str = encoding.decode([tid])
        tokens.append(token_str)

    return tokens


async def yield_data(
    _type: str,
    text: str
):
    return f"""data: {
        json.dumps(
                {
                    'type' : _type,
                    'tokens' : await tiktokenize(text)
                }
            )
        }
    """

async def store_chat(
    obj: OpsBotService,
    user_id: str,
    session_id: str,
    query_text: str,
    response_text: str,
    source_document_ids: list[str] = []
):
    chat_id = str(uuid4())
    chat_to_store = BaseChat(
        message=query_text,
        response=response_text,
        context={
            "source_document_ids": source_document_ids
        },
        timestamp=datetime.now(),
        chat_id=chat_id
    )

    from services import get_google_genai_llm
    session_title = await obj.memory_store.add_chat(
        user_id=user_id,
        session_id=session_id,
        chat=chat_to_store,
        llm=get_google_genai_llm(model_name="models/gemini-2.0-flash")
    )

    return session_title, chat_id

async def ops_chat(
    chat_service: OpsBotService,
    query_text: str,
    user_id: str,
    session_id: str
):
    response_text = await chat_service.process_chat_request(
        query_text=query_text.lower(),
        user_id=user_id,
        session_id=session_id,
    )
    return response_text


async def ops_chat_stream(
    chat_service: OpsBotService,
    query_text: str,
    user_id: str,
    session_id: str
):
    yield await yield_data('header_thinking', "Đang xử lý...\n")

    async for data in chat_service.process_chat_stream_request(
        query_text=query_text.lower(),
        user_id=user_id,
        session_id=session_id,
    ):
        yield await yield_data(**data)

    yield await yield_data('end', 'Hoàn thành!\n')

async def ops_chat_user(
    chat_service: OpsBotService,
    query_text: str,
    user_id: str,
    session_id: str,
    user_context: UserContext
):
    with open(get_settings_cached().OPS_AGENT_THINKING_PROMPT_PATH, 'r') as f:
        agent_thinking_data = json.load(f)

    validate_response = await chat_service.user_validate_chat_request(
        query_text=query_text.lower(),
        user_id=user_id,
        session_id=session_id,
        user_context=user_context
    )

    if validate_response.get("status") == "invalid":
        await store_chat(
            obj=chat_service,
            user_id=user_id,
            session_id=session_id,
            query_text=query_text.lower(),
            response_text=validate_response.get("response", "Invalid query.")
        )
        return validate_response.get("response", "Invalid query.")

    if validate_response.get("user_information"):
        response_text = await chat_service.eval_agent.validate(
            query=f"""user_query:\n{query_text.lower()}\n\nuser_context:\n{user_context.model_dump_json().lower()}""",
            user_id=user_id,
            session_id=session_id,
            func=chat_service.google_llm.arun, agent_name="user_information_answerer"
        )

        await store_chat(
            obj=chat_service,
            user_id=user_id,
            session_id=session_id,
            query_text=query_text.lower(),
            response_text=response_text.get("answer")
        )
        return response_text.get("answer")

    if validate_response.get("chatbot_information"):
        await store_chat(
            obj=chat_service,
            user_id=user_id,
            session_id=session_id,
            query_text=query_text.lower(),
            response_text="\n".join(agent_thinking_data['chatbot_information'])
        )
        return "\n".join(agent_thinking_data['chatbot_information'])

    response_text = await chat_service.user_process_chat_request(
        query_text=query_text.lower(),
        user_id=user_id,
        session_id=session_id,
        user_context=user_context
    )

    return response_text

async def ops_chat_user_stream(
    chat_service: OpsBotService,
    query_text: str,
    user_id: str,
    session_id: str,
    user_context: UserContext
):
    with open(get_settings_cached().OPS_AGENT_THINKING_PROMPT_PATH, 'r') as f:
        agent_thinking_data = json.load(f)

    yield await yield_data('header_thinking', "Đang xử lý...\n")

    validate_response = await chat_service.user_validate_chat_request(
        query_text=query_text.lower(),
        user_id=user_id,
        session_id=session_id,
        user_context=user_context
    )

    yield await yield_data('header_thinking', "Đang kiểm tra tính an toàn của query\n")

    if validate_response.get("status") == "invalid":
        yield await yield_data('response', f"""{validate_response.get("response", "Invalid query.")}\n""")
        yield await yield_data('end', 'Hoàn thành!\n')
        session_title, chat_id = await store_chat(
            obj=chat_service,
            user_id=user_id,
            session_id=session_id,
            query_text=query_text.lower(),
            response_text=validate_response.get("response", "Invalid query.")
        )
        if session_title:
            yield await yield_data('session_title', session_title)
        yield await yield_data('chat_id', chat_id)
        return

    yield await yield_data('thinking', f"""{agent_thinking_data.get("safety_guards")[random.randint(0, len(agent_thinking_data.get("safety_guards")) - 1)]}\n""")

    if validate_response.get("user_information"):
        yield await yield_data('header_thinking', f"""Đang phản hồi...\n""")

        response_text = await chat_service.eval_agent.validate(
            query=f"""user_query:\n{query_text.lower()}\n\nuser_context:\n{user_context.model_dump_json().lower()}""",
            user_id=user_id,
            session_id=session_id,
            func=chat_service.google_llm.arun, agent_name="user_information_answerer"
        )

        yield await yield_data('response', response_text.get("answer"))
        yield await yield_data('end', 'Hoàn thành!\n')
        session_title, chat_id = await store_chat(
            obj=chat_service,
            user_id=user_id,
            session_id=session_id,
            query_text=query_text.lower(),
            response_text=response_text.get("answer")
        )
        if session_title:
            yield await yield_data('session_title', session_title)
        yield await yield_data('chat_id', chat_id)
        return

    if validate_response.get("chatbot_information"):
        yield await yield_data('header_thinking', f"""Đang phản hồi...\n""")

        for text in agent_thinking_data['chatbot_information']:
            yield await yield_data('response', text)
        yield await yield_data('end', 'Hoàn thành!\n')
        session_title, chat_id = await store_chat(
            obj=chat_service,
            user_id=user_id,
            session_id=session_id,
            query_text=query_text.lower(),
            response_text="\n".join(agent_thinking_data['chatbot_information'])
        )
        if session_title:
            yield await yield_data('session_title', session_title)
        yield await yield_data('chat_id', chat_id)
        return

    async for data in chat_service.user_process_chat_request_stream(
        query_text=query_text.lower(),
        user_id=user_id,
        session_id=session_id,
        user_context=user_context
    ):
        yield await yield_data(**data)

    yield await yield_data('end', 'Hoàn thành!\n')
