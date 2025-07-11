import json
import random
import asyncio
from datetime import datetime
from uuid import uuid4

from services.agentic_workflow.bots.hr_bot import HrBotService
from core.storages import BaseChat
from core.parsers import simple_tokenize

async def yield_data(
    _type: str,
    text: str
):
    return f"""data: {
        json.dumps(
                {
                    'type' : _type,
                    'tokens' : await asyncio.to_thread(simple_tokenize, text)
                }
            )
        }
    """

async def hr_chat_stop(
    bot_service: HrBotService,
    chat_id: str,
):
    await bot_service.memory_store.update_chat_status(
        chat_id=chat_id
    )

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
