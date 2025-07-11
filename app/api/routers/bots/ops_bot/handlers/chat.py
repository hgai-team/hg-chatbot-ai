import json
import asyncio

from services.agentic_workflow.bots.ops_bot import OpsBotService
from core.parsers import simple_tokenize

from .master_data import get_user_info

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

async def ops_chat_stop(
    bot_service: OpsBotService,
    chat_id: str,
):
    await bot_service.memory_store.update_chat_status(
        chat_id=chat_id
    )

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

async def ops_chat_user_stream(
    chat_service: OpsBotService,
    query_text: str,
    user_id: str,
    session_id: str,
    email: str
):
    user_roles = await get_user_info(email=email)
    user_roles = [user_role.model_dump() for user_role in user_roles]

    yield await yield_data('header_thinking', "Đang xử lý...\n")

    async for data in chat_service.user_process_chat_request_stream(
        query_text=query_text.lower(),
        user_id=user_id,
        session_id=session_id,
        user_roles=user_roles
    ):
        yield await yield_data(**data)

    yield await yield_data('end', 'Hoàn thành!\n')
