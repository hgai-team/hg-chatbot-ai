import json
import timeit
import asyncio

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from api.schema import ChatRequest, ChatResponse, BotNames
from api.security import validate_auth
from api.routers.vahacha.tokenizer import tiktokenize

from services import get_settings_cached
from services.agentic_workflow.vahacha.chat import ChatService

app = APIRouter(
    prefix="/chatbots",
    tags=["ChatBots"]
)

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
    obj: ChatService,
    user_id: str,
    session_id: str,
    query_text: str,
    response_text: str,
    source_document_ids: list[str] = []
):
    from datetime import datetime
    from core.storages import BaseChat
    from uuid import uuid4
    chat_to_store = BaseChat(
        message=query_text,
        response=response_text,
        context={
            "source_document_ids": source_document_ids
        },
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        chat_id=str(uuid4())
    )
    _ = await obj._run_sync_in_thread(obj.memory_store.add_chat, user_id, session_id, chat_to_store)

@app.get(
    "/vahacha/get-vh-info",
    dependencies=[Depends(validate_auth)]
)
async def get_vh_info(
    bot_name: BotNames
):
    from services.tools import get_search_tool
    from core.base import Document

    search_tool = get_search_tool(bot_name=bot_name)

    collection = search_tool.mongodb_doc_store.collection

    find_filter = {
        "$and": [
            {"attributes.file_name": "Hệ thống nhân sự Vận hành.xlsx"},
        ]
    }
    cursor = (collection.find(find_filter))

    docs = list(cursor)

    return [
        Document(
            id_=doc["id"],
            text=doc.get("text", "<empty>"),
            metadata=doc.get("attributes", {}),
        )
        for doc in docs
    ]


@app.post(
    "/vahacha/agentic-workflow/admin",
    response_model=ChatResponse,
    dependencies=[Depends(validate_auth)]
)
async def chat_admin(
    request: ChatRequest,
):
    from services.agentic_workflow.vahacha import get_chat_service

    chat_service = get_chat_service(
        bot_name=request.bot_name,
        agent_prompt_path=get_settings_cached().VAHACHA_AGENT_PROMPT_PATH
    )

    try:
        start_time = timeit.default_timer()

        response_text = await chat_service.process_chat_request(
            query_text=request.query_text.lower(),
            user_id=request.user_id,
            session_id=request.session_id,
        )
        end_time = timeit.default_timer()

        return ChatResponse(results=response_text, status=200, time_taken=end_time - start_time)

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.post(
    "/vahacha/agentic-workflow/admin/stream",
    dependencies=[Depends(validate_auth)]
)
async def chat_admin_stream(
    request: ChatRequest,
):
    async def stream_generator():
        from services.agentic_workflow.vahacha import get_chat_service

        yield await yield_data('header_thinking', "Đang xử lý...\n")

        chat_service = get_chat_service(
            bot_name=request.bot_name,
            agent_prompt_path=get_settings_cached().VAHACHA_AGENT_PROMPT_PATH
        )

        async for data in chat_service.process_chat_request_stream(
            query_text=request.query_text.lower(),
            user_id=request.user_id,
            session_id=request.session_id,
        ):
            yield await yield_data(**data)

        yield await yield_data('end', 'Hoàn thành!\n')

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream"
    )

@app.post(
    "/vahacha/agentic-workflow/user",
    response_model=ChatResponse,
    dependencies=[Depends(validate_auth)]
)
async def chat_user(
    request: ChatRequest,
):
    from services.agentic_workflow.vahacha import (
        get_chat_service,
        get_evaluation_agent,
        get_google_genai_llm
    )
    agent_thinking_prompt_path = get_settings_cached().VAHACHA_AGENT_THINKING_PROMPT_PATH
    with open(agent_thinking_prompt_path, 'r') as f:
        agent_thinking_data = json.load(f)

    agent_prompt_path = get_settings_cached().VAHACHA_AGENT_PROMPT_PATH

    chat_service = get_chat_service(
        bot_name=request.bot_name,
        agent_prompt_path=agent_prompt_path
    )

    evaluation_agent = get_evaluation_agent(
        agent_prompt_path=agent_prompt_path
    )

    google_llm = get_google_genai_llm(
        model_name=get_settings_cached().GOOGLEAI_MODEL
    )

    try:
        start_time = timeit.default_timer()
        validate_response = await chat_service.user_validate_chat_request(
            query_text=request.query_text.lower(),
            user_id=request.user_id,
            session_id=request.session_id,
            user_context=request.user_context
        )

        if validate_response.get("status") == "invalid":
            end_time = timeit.default_timer()
            await store_chat(
                obj=chat_service,
                user_id=request.user_id,
                session_id=request.session_id,
                query_text=request.query_text.lower(),
                response_text=validate_response.get("response", "Invalid query.")
            )
            return ChatResponse(results=validate_response.get("response", "Invalid query."), status=200, time_taken=end_time - start_time)

        if validate_response.get("user_information"):
            response_text = await evaluation_agent.validate(
                query=f"""user_query:\n{request.query_text.lower()}\n\nuser_context:\n{request.user_context.model_dump_json().lower()}""",
                user_id=request.user_id,
                session_id=request.session_id,
                func=google_llm.arun, agent_name="user_information_answerer"
            )
            end_time = timeit.default_timer()
            await store_chat(
                obj=chat_service,
                user_id=request.user_id,
                session_id=request.session_id,
                query_text=request.query_text.lower(),
                response_text=response_text.get("answer")
            )
            return ChatResponse(results=response_text.get("answer"), status=200, time_taken=end_time - start_time)

        if validate_response.get("chatbot_information"):
            end_time = timeit.default_timer()
            await store_chat(
                obj=chat_service,
                user_id=request.user_id,
                session_id=request.session_id,
                query_text=request.query_text.lower(),
                response_text="\n".join(agent_thinking_data['chatbot_information'])
            )
            return ChatResponse(results="\n".join(agent_thinking_data['chatbot_information']), status=200, time_taken=end_time - start_time)

        response_text = await chat_service.user_process_chat_request(
            query_text=request.query_text.lower(),
            user_id=request.user_id,
            session_id=request.session_id,
            user_context=request.user_context
        )
        end_time = timeit.default_timer()
        return ChatResponse(results=response_text, status=200, time_taken=end_time - start_time)

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.post(
    "/vahacha/agentic-workflow/user/stream",
    dependencies=[Depends(validate_auth)]
)
async def chat_user_stream(
    request: ChatRequest,
):
    async def stream_generator():
        import random
        from services.agentic_workflow.vahacha import (
            get_chat_service,
            get_evaluation_agent,
            get_google_genai_llm
        )

        agent_thinking_prompt_path = get_settings_cached().VAHACHA_AGENT_THINKING_PROMPT_PATH
        with open(agent_thinking_prompt_path, 'r') as f:
            agent_thinking_data = json.load(f)

        agent_prompt_path = get_settings_cached().VAHACHA_AGENT_PROMPT_PATH

        chat_service = get_chat_service(
            bot_name=request.bot_name,
            agent_prompt_path=agent_prompt_path
        )

        evaluation_agent = get_evaluation_agent(
            agent_prompt_path=agent_prompt_path
        )

        google_llm = get_google_genai_llm(
            model_name=get_settings_cached().GOOGLEAI_MODEL
        )

        yield await yield_data('header_thinking', "Đang xử lý...\n")

        validate_response = await chat_service.user_validate_chat_request(
            query_text=request.query_text.lower(),
            user_id=request.user_id,
            session_id=request.session_id,
            user_context=request.user_context
        )

        yield await yield_data('header_thinking', "Đang kiểm tra tính an toàn của query\n")

        if validate_response.get("status") == "invalid":
            yield await yield_data('response', f"""{validate_response.get("response", "Invalid query.")}\n""")
            yield await yield_data('end', 'Hoàn thành!\n')
            await store_chat(
                obj=chat_service,
                user_id=request.user_id,
                session_id=request.session_id,
                query_text=request.query_text.lower(),
                response_text=validate_response.get("response", "Invalid query.")
            )
            return

        yield await yield_data('thinking', f"""{agent_thinking_data.get("safety_guards")[random.randint(0, len(agent_thinking_data.get("safety_guards")) - 1)]}\n""")

        if validate_response.get("user_information"):
            yield await yield_data('header_thinking', f"""Đang phản hồi...\n""")

            response_text = await evaluation_agent.validate(
                query=f"""user_query:\n{request.query_text.lower()}\n\nuser_context:\n{request.user_context.model_dump_json().lower()}""",
                user_id=request.user_id,
                session_id=request.session_id,
                func=google_llm.arun, agent_name="user_information_answerer"
            )

            yield await yield_data('response', response_text.get("answer"))
            yield await yield_data('end', 'Hoàn thành!\n')
            await store_chat(
                obj=chat_service,
                user_id=request.user_id,
                session_id=request.session_id,
                query_text=request.query_text.lower(),
                response_text=response_text.get("answer")
            )
            return

        if validate_response.get("chatbot_information"):
            yield await yield_data('header_thinking', f"""Đang phản hồi...\n""")

            for text in agent_thinking_data['chatbot_information']:
                yield await yield_data('response', text)
            yield await yield_data('end', 'Hoàn thành!\n')
            await store_chat(
                obj=chat_service,
                user_id=request.user_id,
                session_id=request.session_id,
                query_text=request.query_text.lower(),
                response_text="\n".join(agent_thinking_data['chatbot_information'])
            )
            return

        async for data in chat_service.user_process_chat_request_stream(
            query_text=request.query_text.lower(),
            user_id=request.user_id,
            session_id=request.session_id,
            user_context=request.user_context
        ):
            yield await yield_data(**data)

        yield await yield_data('end', 'Hoàn thành!\n')


    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream"
    )
