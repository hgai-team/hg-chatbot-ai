import json
import random
from datetime import datetime
from uuid import uuid4

from services.agentic_workflow.bots.hr_bot import HrBotService
from core.storages import BaseChat
from core.parsers import tiktokenize

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
    obj: HrBotService,
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

async def hr_chat(
    bot_service: HrBotService,
    query_text: str,
    user_id: str,
    session_id: str
):
    response_text = await bot_service.process_chat_request(
        query_text=query_text.lower(),
        user_id=user_id,
        session_id=session_id,
    )
    return response_text


async def hr_chat_stream(
    bot_service: HrBotService,
    query_text: str,
    user_id: str,
    session_id: str
):
    yield await yield_data('header_thinking', "Đang xử lý...\n")

    async for data in bot_service.process_chat_stream_request(
        query_text=query_text.lower(),
        user_id=user_id,
        session_id=session_id,
    ):
        yield await yield_data(**data)

    yield await yield_data('end', 'Hoàn thành!\n')
