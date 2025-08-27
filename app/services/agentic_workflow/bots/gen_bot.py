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
from openai.types.chat.chat_completion import ChatCompletion

from .base import BaseBotService
from .utils import get_parents_and_merge, init_base_chat, update_chat

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
        try:
            self.hggpt_prompt = PPT.load_prompt(self.agent_prompt_path)['HGGPT']
        except Exception as e:
            logger.error(f"Failed to load HGGPT prompt: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to load {self.bot_name} prompt")

    def _set_up(
        self,
    ):
        try:
            from services.agentic_workflow.tools import (
                get_query_processing_tool,
                FileProcessorTool, get_file_processor_tool,
            )

            from services import (
                get_google_genai_llm, get_xai_llm,
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

            self.xai_llm = get_xai_llm(
                model_name=settings.XAI_MODEL_NAME,
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

        except Exception as e:
            logger.error(f"Failed to initialize {self.bot_name}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to initialize {self.bot_name}")

    async def _get_response(
        self,
        inal_messages,
        user_id: str,
        session_id: str,
        agent_name: str,
    ) -> Any:
        try:
            async with TM.trace_span(
                span_name=agent_name,
                span_type=self.bot_name,
                custom_metadata={
                    "user_id": user_id,
                    "session_id": session_id,
                }
            ) as (trace_id, span_id, wrapper):
                response: ChatCompletion = await wrapper(self.xai_llm.arun, messages=inal_messages)

            return response
        except Exception as e:
            logger.error(f"Error during _get_response for session '{session_id}': {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Error during _get_response")

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
        selected_tool: str
    ) -> AsyncGenerator[str, None]:
        start_time_chat = timeit.default_timer()
        chat_id = None

        try:
            # Initialize base chat
            try:
                chat_id, session_title = await init_base_chat(
                    query_text=query_text, 
                    user_id=user_id, 
                    session_id=session_id,
                    memory_store=self.memory_store, 
                    llm=self.google_llm, 
                    bot_name=self.bot_name
                )
            except Exception as e:
                logger.error(f"HGGPT - Failed to initialize chat for session '{session_id}': {e}", exc_info=True)
                yield {'_type': 'error', 'text': 'Internal server error'}
                return

            try:
                if session_title:
                    yield {'_type': 'session_title', 'text': session_title}
                yield {'_type': 'chat_id', 'text': chat_id}

                yield {'_type': 'header_thinking', 'text': 'Đang phân tích yêu cầu...\n'}
            except Exception as e:
                logger.error(f"HGGPT - Error yielding initial data for session '{session_id}': {e}", exc_info=True)

            # Get chat history and prepare initial messages
            try:
                initial_messages, _, _ = await self.query_processor._get_chat_history_and_prompt(
                    user_id=user_id, 
                    session_id=session_id
                )
                message: ChatMessage = initial_messages[0]
                message.content = message.content + self.hggpt_prompt['instructions'].format(
                    TOOLS='\n'.join([f"- **{tool.name}**: {tool.description}" for tool in TOOLS])
                )
            except Exception as e:
                logger.error(f"HGGPT - Error preparing initial messages for session '{session_id}': {e}", exc_info=True)
                if chat_id:
                    await self._safe_update_chat_error(chat_id, str(e), start_time_chat)
                yield {'_type': 'error', 'text': 'Internal server error'}
                return

            try:
                his_sessions = await self.memory_store.get_user_sessions(user_id=user_id)
                yield {'_type': 'sys_resp_cnt', 'text': str(sum([len(chat) for chat in his_sessions]))}
            except Exception as e:
                logger.error(f"HGGPT - Error getting user sessions for session '{session_id}': {e}", exc_info=True)
                # Continue processing even if this fails

            # Handle selected tool execution
            if selected_tool and selected_tool in TOOL_FUNCTIONS:
                try:
                    response = ""
                    has_error = False
                    async for data in TOOL_FUNCTIONS[selected_tool](
                        query_text=query_text,
                        user_id=user_id,
                        session_id=session_id,
                        initial_messages=initial_messages,
                    ):
                        if data['_type'] == 'response':
                            response += data['text']
                        elif data['_type'] == 'error':
                            has_error = True
                        yield data

                    try:
                        await update_chat(
                            chat_id=chat_id,
                            response=response,
                            start_time=start_time_chat,
                            status=ChatStatus.FINISHED.value if not has_error else ChatStatus.ERROR.value,
                            memory_store=self.memory_store
                        )
                    except Exception as e:
                        logger.error(f"HGGPT - Error updating chat after tool execution for session '{session_id}': {e}", exc_info=True)
                        # Don't yield error as tool execution was completed

                    return

                except Exception as e:
                    logger.error(f"HGGPT - Error during tool execution '{selected_tool}' for session '{session_id}': {e}", exc_info=True)
                    if chat_id:
                        await self._safe_update_chat_error(chat_id, str(e), start_time_chat)
                    yield {'_type': 'error', 'text': 'Internal server error'}
                    return

            # Handle regular chat completion
            try:
                messages = initial_messages + [ChatMessage(role=MessageRole.USER, content=query_text)]
                response: ChatCompletion = await self._get_response(
                    inal_messages=messages,
                    user_id=user_id,
                    session_id=session_id, 
                    agent_name=self.bot_name
                )

                response_text = response.choices[0].message.content
                yield {'_type': 'response', 'text': response_text}
            except Exception as e:
                logger.error(f"HGGPT - Error during response generation for session '{session_id}': {e}", exc_info=True)
                if chat_id:
                    await self._safe_update_chat_error(chat_id, str(e), start_time_chat)
                yield {'_type': 'error', 'text': 'Internal server error'}
                return

            # Update chat with success
            try:
                await update_chat(
                    chat_id=chat_id,
                    response=response_text,
                    start_time=start_time_chat,
                    status=ChatStatus.FINISHED.value,
                    memory_store=self.memory_store
                )
            except Exception as e:
                logger.error(f"HGGPT - Error updating chat for session '{session_id}': {e}", exc_info=True)
                # Don't yield error here as the response was successful

        except Exception as e:
            logger.error(f"HGGPT - Unexpected error in process_chat_stream_request for session '{session_id}': {e}", exc_info=True)
            yield {'_type': 'error', 'text': 'Internal server error'}

    async def _safe_update_chat_error(self, chat_id: str, error_message: str, start_time: float):
        """Safely update chat with error status without raising exceptions"""
        try:
            await update_chat(
                chat_id=chat_id,
                response=error_message,
                start_time=start_time,
                status=ChatStatus.ERROR.value,
                memory_store=self.memory_store
            )
        except Exception as e:
            logger.error(f"HGGPT - Failed to update chat with error status for chat_id '{chat_id}': {e}", exc_info=True)