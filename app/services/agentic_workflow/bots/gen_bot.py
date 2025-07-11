import logging
logger = logging.getLogger(__name__)

import json
import timeit
import asyncio
from typing import List, Dict, Any, Callable, AsyncGenerator

from uuid import uuid4
from datetime import datetime
from fastapi import HTTPException

from llama_index.core.llms import ChatMessage, MessageRole, ChatResponse

from .base import BaseBotService

from services.agentic_workflow.tools import PromptProcessorTool as PPT
from services import get_settings_cached

from core.storages import BaseChat, ChatStatus
from core.storages.client import TracerManager as TM
from core.mcp.tools import TOOLS, TOOL_FUNCTIONS
from core.parsers import json_parser

class GenBotService(BaseBotService):
    def __init__(
        self,
    ):
        self.bot_name = 'HGGPT'
        self._set_up()
        self.hggpt_prompt = PPT.load_prompt(self.agent_prompt_path)['HGGPT']

    def _set_up(
        self,
    ):
        from services.agentic_workflow.tools import (
            get_query_processing_tool,
            FileProcessorTool, get_file_processor_tool,
        )

        from services import (
            get_google_genai_llm,
            MongoDBMemoryStore, get_mongodb_memory_store,
        )

        settings = get_settings_cached()

        database_name = f"{self.bot_name}{settings.MONGODB_BASE_DATABASE_NAME}"
        collection_name = f"{self.bot_name}{settings.MONGODB_BASE_CHAT_HISTORY_COLLECTION_NAME}"

        self.file_processor: FileProcessorTool = get_file_processor_tool(bot_name=self.bot_name)

        self.agent_prompt_path = settings.HGGPT_AGENT_PROMPT_PATH

        self.query_processor = get_query_processing_tool(
            database_name=database_name,
            collection_name=collection_name,
            agent_prompt_path=self.agent_prompt_path,
            bot_name=self.bot_name

        )

        self.google_llm = get_google_genai_llm(
            model_name=settings.GOOGLEAI_MODEL,
        )

        self.main_llm = get_google_genai_llm(
            model_name=settings.GOOGLEAI_MODEL_THINKING,
        )

        self.memory_store: MongoDBMemoryStore = get_mongodb_memory_store(
            database_name=database_name,
            collection_name=collection_name
        )

    async def _init_base_chat(
        self,
        query_text: str,
        user_id: str,
        session_id: str,
    ):
        chat_id = str(uuid4())
        session_title = "New Chat"

        chat_to_store = BaseChat(
            message=query_text,
            chat_id=chat_id
        )

        try:
            session_title = await self.memory_store.add_chat(
                user_id=user_id,
                session_id=session_id,
                chat=chat_to_store,
                llm=self.google_llm
            )
        except Exception as e:
            logger.error(f"ChaChaCha - Failed to store chat history in _init_base_chat for session '{session_id}': {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Error during _init_base_chat")

        return chat_id, session_title

    async def _update_chat(
        self,
        chat_id: str,
        response: str,
        start_time: float,
        status: int,
    ):
        await self.memory_store.update_chat(
            chat_id=chat_id,
            response=response,
            metadata={
                'time_taken': timeit.default_timer() - start_time
            },
            status=status
        )

    async def _get_response(
        self,
        inal_messages,
        user_id: str,
        session_id: str,
        agent_name: str,
    ) -> Any:
        async with TM.trace_span(
            span_name=f"{self.main_llm.__class__.__name__}_chat_completion",
            span_type="LLM_AGENT_CALL",
            custom_metadata={
                "user_id": user_id,
                "session_id": session_id,
                "agent_name": agent_name,
            }
        ) as (trace_id, span_id, wrapper):
            response: ChatResponse = await wrapper(self.main_llm.arun, messages=inal_messages)

        return response.message.content

    async def _choose_tool(
        self,
        query_text: str,
        initial_messages: list[ChatMessage]
    ):
        prompt_templates = PPT.load_prompt(get_settings_cached().BASE_PROMPT_PATH)
        agent = prompt_templates['tool_selector_expert']

        tools_schema_string = json.dumps( [tool.to_json_schema() for tool in TOOLS], indent=2, ensure_ascii=False)

        messages = [
            ChatMessage(
                role=MessageRole.SYSTEM,
                content=(
                    f"{agent['role']}: {agent['description']}\n\n"
                    f"## Hướng dẫn:\n{agent['instructions']}\n\n"
                    "## Danh sách công cụ có sẵn (Tool Schemas):\n"
                    f"Dưới đây là danh sách các công cụ bạn có thể sử dụng, được định dạng dưới dạng JSON. "
                    f"Bạn phải tuân thủ nghiêm ngặt schema này, đặc biệt là tên công cụ (`name`) và tên các tham số trong `properties` để tạo output.\n\n"
                    f"```json\n"
                    f"{tools_schema_string}\n"
                    f"```\n\n"
                )
            )
        ] + initial_messages[1:] + [
            ChatMessage(role=MessageRole.USER, content=f"## Đầu vào:\n{query_text}\n\n## Phản hồi:\n"),
        ]

        response: ChatResponse = await self.google_llm.arun(
            messages=messages,
        )

        json_resp = json_parser(response.message.content)

        if all(key in json_resp for key in ['status', 'response', 'raw_analysis']):
            return response.message.content
        return json_resp

    async def process_chat_request(
        self,
        query_text: str,
        user_id: str,
        session_id: str,
    ) -> str:
        pass

    async def process_chat_stream_request(
        self,
        query_text: str,
        user_id: str,
        session_id: str,
    ) -> AsyncGenerator[str, None]:
        start_time = timeit.default_timer()

        chat_id, session_title = await self._init_base_chat(
            query_text=query_text,
            user_id=user_id,
            session_id=session_id
        )
        try:
            if session_title:
                yield {'_type': 'session_title', 'text': session_title}
            yield {'_type': 'chat_id', 'text': chat_id}

            yield {'_type': 'header_thinking', 'text': 'Đang phân tích yêu cầu...\n'}

            initial_messages, _, _ = await self.query_processor._get_chat_history_and_prompt(user_id=user_id, session_id=session_id)
            message: ChatMessage = initial_messages[0]
            message.content = message.content + self.hggpt_prompt['instruction'].format(
                TOOLS='\n'.join([f"- **{tool.name}**: {tool.description}" for tool in TOOLS])
            )

            choosed_tool = await self._choose_tool(query_text=query_text, initial_messages=initial_messages)

            his_sessions = await self.memory_store.get_user_sessions(
                    user_id=user_id,
                )
            yield {'_type': 'sys_resp_cnt', 'text': str(sum([len(chat) for chat in his_sessions]))}

            if isinstance(choosed_tool, str):
                await self._update_chat(
                    chat_id=chat_id,
                    response=choosed_tool,
                    start_time=start_time,
                    status=ChatStatus.FINISHED.value
                )
                yield {'_type': 'response', 'text': choosed_tool}
                return

            if isinstance(choosed_tool, dict):
                if choosed_tool['tool_name'] and choosed_tool['tool_name'] in TOOL_FUNCTIONS:
                    response = None
                    async for data in TOOL_FUNCTIONS[choosed_tool['tool_name']](**choosed_tool['tool_input']):
                        if data['_type'] == 'response':
                            response = data['text']
                        yield data

                    await self._update_chat(
                        chat_id=chat_id,
                        response=response,
                        start_time=start_time,
                        status=ChatStatus.FINISHED.value
                    )
                    return

            response: ChatResponse = await self.google_llm.arun(
                messages=initial_messages + [ChatMessage(role=MessageRole.USER, content=query_text)]
            )

            await self._update_chat(
                chat_id=chat_id,
                response=response.message.content,
                start_time=start_time,
                status=ChatStatus.FINISHED.value
            )

            yield {'_type': 'response', 'text': response.message.content}

        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            logger.error(f"HGGPT - An internal error occurred during chat processing: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"HGGPT - Internal error")
