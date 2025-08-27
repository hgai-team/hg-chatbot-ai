import logging
logger = logging.getLogger(__name__)

import timeit
import asyncio
from types import SimpleNamespace
from typing import List, Dict, Any, Callable

from uuid import uuid4
from datetime import datetime
from fastapi import HTTPException

from llama_index.core.schema import TextNode, RelatedNodeInfo, NodeRelationship
from llama_index.core.retrievers import AutoMergingRetriever
from llama_index.core.schema import NodeWithScore
from llama_index.core.llms import ChatResponse

from .base import BaseBotService
from .utils import get_parents_and_merge, init_base_chat, update_chat

from core.base import Document
from core.storages import BaseChat, ChatStatus
from core.rerank import MSMarcoReranker

from services.agentic_workflow.tools import PromptProcessorTool as PPT
from services.agentic_workflow.schema import ContextRetrieved
from core.storages.client import TracerManager as TM

from services import get_settings_cached


class HrBotService(BaseBotService):
    def __init__(
        self,
    ):
        self.bot_name = 'ChaChaCha'
        self._set_up()

    def _set_up(
        self,
    ):
        try:
            from services.agentic_workflow.tools import (
                get_query_processing_tool,
                get_context_retrieval_tool,
                get_evaluation_agent_tool,
                FileProcessorTool, get_file_processor_tool,
            )

            from services import (
                get_settings_cached,
                get_google_genai_llm,
                get_openai_llm,
                MongoDBMemoryStore, get_mongodb_memory_store,
                get_langfuse_instrumentor_cached
            )

            settings = get_settings_cached()

            database_name = f"{self.bot_name}{settings.MONGODB_BASE_DATABASE_NAME}"
            collection_name = f"{self.bot_name}{settings.MONGODB_BASE_CHAT_HISTORY_COLLECTION_NAME}"

            self.file_processor: FileProcessorTool = get_file_processor_tool(bot_name=self.bot_name)

            self.agent_prompt_path = settings.HR_AGENT_PROMPT_PATH

            self.query_processor = get_query_processing_tool(
                database_name=database_name,
                collection_name=collection_name,
                agent_prompt_path=self.agent_prompt_path,
                bot_name=self.bot_name
            )
            
            self.context_retriever = get_context_retrieval_tool(
                bot_name=self.bot_name,
                agent_prompt_path=self.agent_prompt_path
            )
            
            self.eval_agent = get_evaluation_agent_tool(
                agent_prompt_path=self.agent_prompt_path
            )
            
            self.google_llm = get_google_genai_llm(
                model_name=get_settings_cached().GOOGLEAI_MODEL,
            )
            
            self.main_llm = get_google_genai_llm(
                model_name=get_settings_cached().GOOGLEAI_MODEL_THINKING,
            )
            
            self.memory_store: MongoDBMemoryStore = get_mongodb_memory_store(
                database_name=database_name,
                collection_name=collection_name
            )
            
            self.instrumentor = get_langfuse_instrumentor_cached()

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
            ) as (_, _, wrapper):
                response: ChatResponse = await wrapper(self.main_llm.arun, messages=inal_messages)

            return response.message.content
        except Exception as e:
            logger.error(f"Error during _get_response for session '{session_id}': {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Error during _get_response")

    async def process_chat_request(
        self,
        query_text: str,
        user_id: str,
        session_id: str,
    ) -> str:
        start_time = timeit.default_timer()
        chat_id = None
        retrieved_context = None

        try:
            # Initialize base chat
            try:
                chat_id, is_new_session = await init_base_chat(
                    query_text=query_text, 
                    user_id=user_id, 
                    session_id=session_id,  
                    memory_store=self.memory_store, 
                    bot_name=self.bot_name
                )
            except Exception as e:
                logger.error(f"ChaChaCha - Failed to initialize chat for session '{session_id}': {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Failed to initialize chat")

            # Analyze query
            try:
                processed_info = await self.query_processor.analyze_query(
                    query_text=query_text,
                    user_id=user_id,
                    session_id=session_id
                )
            except Exception as e:
                logger.error(f"ChaChaCha - Error during query analysis for session '{session_id}': {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Error during query analysis")

            # Retrieve context
            try:
                retrieved_context = await self.context_retriever.retrieve_context(
                    processed_query_info=processed_info,
                    user_id=user_id,
                    session_id=session_id
                )
            except Exception as e:
                logger.error(f"ChaChaCha - Error during context retrieval for session '{session_id}': {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Error during context retrieval")

            # Merge context and process documents
            try:
                ids = list(retrieved_context.source_documents.keys())
                retrieved_docs = await self.file_processor.mongodb_doc_store.get(ids)
                all_docs = await self.file_processor.mongodb_doc_store.get_all()
                docs = await get_parents_and_merge(retrieved_docs, all_docs)

                reranked_res = await MSMarcoReranker.rerank(query_text, docs)
                reranked_docs = [res["doc"] for res in reranked_res]

                documents_as_markdown = []
                for i, doc in enumerate(reranked_docs, 1):
                    doc_str = f"### Tài liệu {i}\n\n{doc['text']}"
                    documents_as_markdown.append(doc_str)

                retrieved_context.context_string = "\n\n---\n\n".join(documents_as_markdown)
            except Exception as e:
                logger.error(f"ChaChaCha - Error processing documents for session '{session_id}': {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Error processing documents")

            # Format chat prompt
            try:
                inal_messages = PPT.format_chat_prompt(
                    processed_info=processed_info,
                    retrieved_context=retrieved_context
                )
            except Exception as e:
                logger.error(f"ChaChaCha - Error formatting chat prompt for session '{session_id}': {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Error formatting chat prompt")

            # Check session status
            try:
                ses_his = await self.memory_store.get_session_history(session_id=session_id)
                if ses_his.history[-1]['status'] == ChatStatus.STOPPED.value:
                    await self.memory_store.add_metadata(
                        chat_id=chat_id,
                        metadata={
                            'time_taken': timeit.default_timer() - start_time
                        }
                    )
                    return "Session stopped"
            except Exception as e:
                logger.error(f"ChaChaCha - Error checking session status for session '{session_id}': {e}", exc_info=True)
                # Continue processing even if this fails

            # Generate response
            try:
                response_text = await self._get_response(
                    inal_messages=inal_messages,
                    session_id=session_id,
                    user_id=user_id,
                    agent_name=self.bot_name
                )
            except Exception as e:
                await self._safe_update_chat_error(chat_id, str(e), retrieved_context, start_time)
                logger.error(f"ChaChaCha - Error during response for session '{session_id}': {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Error during response")

            # Update chat with success
            try:
                await update_chat(
                    chat_id=chat_id,
                    response=response_text,
                    retrieved_context=retrieved_context,
                    start_time=start_time,
                    status=ChatStatus.FINISHED.value,
                    memory_store=self.memory_store
                )
            except Exception as e:
                logger.error(f"ChaChaCha - Error during update_chat for session '{session_id}': {e}", exc_info=True)
                # Don't raise exception here as response was successful

            return response_text

        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            logger.error(f"ChaChaCha - Unexpected error in process_chat_request for session '{session_id}': {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="An internal error occurred during chat processing")

    async def process_chat_stream_request(
        self,
        query_text: str,
        user_id: str,
        session_id: str,
    ):
        start_time = timeit.default_timer()
        chat_id = None
        retrieved_context = None

        try:
            # Initialize base chat
            try:
                chat_id, is_new_session = await init_base_chat(
                    query_text=query_text, 
                    user_id=user_id, 
                    session_id=session_id,  
                    memory_store=self.memory_store, 
                    bot_name=self.bot_name
                )
            except Exception as e:
                logger.error(f"ChaChaCha - Failed to initialize chat for session '{session_id}': {e}", exc_info=True)
                yield {'_type': 'error', 'text': 'Internal server error'}
                return

            try:
                yield {'_type': 'chat_id', 'text': chat_id}

                yield {'_type': 'header_thinking', 'text': 'Đang phân tích yêu cầu...\n'}
            except Exception as e:
                logger.error(f"ChaChaCha - Error yielding initial data for session '{session_id}': {e}", exc_info=True)

            # Query processing
            try:
                processed_info = await self.query_processor.analyze_query(
                    query_text=query_text,
                    user_id=user_id,
                    session_id=session_id
                )
                yield {'_type': 'thinking', 'text': 'Hoàn thành phân tích!\n'}
            except Exception as e:
                logger.error(f"ChaChaCha - Error during query analysis for session '{session_id}': {e}", exc_info=True)
                if chat_id:
                    await self._safe_update_chat_error(chat_id, str(e), retrieved_context, start_time)
                yield {'_type': 'error', 'text': 'Internal server error'}
                return

            try:
                yield {'_type': 'header_thinking', 'text': 'Đang tìm kiếm thông tin...\n'}
            except Exception as e:
                logger.error(f"ChaChaCha - Error yielding thinking header for session '{session_id}': {e}", exc_info=True)

            # Context retrieval
            try:
                retrieved_context = await self.context_retriever.retrieve_context(
                    processed_query_info=processed_info,
                    user_id=user_id,
                    session_id=session_id
                )
            except Exception as e:
                logger.error(f"ChaChaCha - Error during context retrieval for session '{session_id}': {e}", exc_info=True)
                if chat_id:
                    await self._safe_update_chat_error(chat_id, str(e), retrieved_context, start_time)
                yield {'_type': 'error', 'text': 'Internal server error'}
                return

            # Document processing and reranking
            try:
                ids = list(retrieved_context.source_documents.keys())
                retrieved_docs = await self.file_processor.mongodb_doc_store.get(ids)
                all_docs = await self.file_processor.mongodb_doc_store.get_all()
                docs = await get_parents_and_merge(retrieved_docs, all_docs)

                reranked_res = await MSMarcoReranker.rerank(query_text, docs)
                reranked_docs = [res["doc"] for res in reranked_res]

                documents_as_markdown = []
                for i, doc in enumerate(reranked_docs, 1):
                    doc_str = f"### Tài liệu {i}\n\n{doc['text']}"
                    documents_as_markdown.append(doc_str)

                retrieved_context.context_string = "\n\n---\n\n".join(documents_as_markdown)

                yield {'_type': 'thinking', 'text': 'Hoàn thành tìm kiếm thông tin!\n'}
            except Exception as e:
                logger.error(f"ChaChaCha - Error processing documents for session '{session_id}': {e}", exc_info=True)
                if chat_id:
                    await self._safe_update_chat_error(chat_id, str(e), retrieved_context, start_time)
                yield {'_type': 'error', 'text': 'Internal server error'}
                return

            # Format chat prompt
            try:
                inal_messages = PPT.format_chat_prompt(
                    processed_info=processed_info,
                    retrieved_context=retrieved_context
                )
            except Exception as e:
                logger.error(f"ChaChaCha - Error formatting chat prompt for session '{session_id}': {e}", exc_info=True)
                if chat_id:
                    await self._safe_update_chat_error(chat_id, str(e), retrieved_context, start_time)
                yield {'_type': 'error', 'text': 'Internal server error'}
                return

            # Check session status
            try:
                ses_his = await self.memory_store.get_session_history(session_id=session_id)
                if ses_his.history[-1]['status'] == ChatStatus.STOPPED.value:
                    await self.memory_store.add_metadata(
                        chat_id=chat_id,
                        metadata={
                            'time_taken': timeit.default_timer() - start_time
                        }
                    )
                    return
            except Exception as e:
                logger.error(f"ChaChaCha - Error checking session status for session '{session_id}': {e}", exc_info=True)
                # Continue processing even if this fails

            try:
                yield {'_type': 'header_thinking', 'text': 'Đang phản hồi yêu cầu...\n'}

                his_sessions = await self.memory_store.get_user_sessions(user_id=user_id)
                yield {'_type': 'sys_resp_cnt', 'text': str(sum([len(chat) for chat in his_sessions]))}
            except Exception as e:
                logger.error(f"ChaChaCha - Error getting user sessions for session '{session_id}': {e}", exc_info=True)
                # Continue processing even if this fails

            # Generate response
            try:
                response_text = await self._get_response(
                    inal_messages=inal_messages,
                    session_id=session_id,
                    user_id=user_id,
                    agent_name=self.bot_name
                )
                if is_new_session:
                    session_title = await self.memory_store.create_session_title(
                        user_id=user_id, session_id=session_id,
                        bot_name=self.bot_name, llm=self.google_llm, message=query_text, response=response_text
                    )
                    yield {'_type': 'session_title', 'text': session_title}

                yield {'_type': 'response', 'text': response_text}
            except Exception as e:
                logger.error(f"ChaChaCha - Error during response generation for session '{session_id}': {e}", exc_info=True)
                if chat_id:
                    await self._safe_update_chat_error(chat_id, str(e), retrieved_context, start_time)
                yield {'_type': 'error', 'text': 'Internal server error'}
                return

            # Update chat with success
            try:
                await update_chat(
                    chat_id=chat_id,
                    response=response_text,
                    retrieved_context=retrieved_context,
                    start_time=start_time,
                    status=ChatStatus.FINISHED.value,
                    memory_store=self.memory_store
                )
            except Exception as e:
                logger.error(f"ChaChaCha - Error during update_chat for session '{session_id}': {e}", exc_info=True)
                # Don't yield error here as the response was successful

        except Exception as e:
            logger.error(f"ChaChaCha - Unexpected error in process_chat_stream_request for session '{session_id}': {e}", exc_info=True)
            yield {'_type': 'error', 'text': 'Internal server error'}

    async def _safe_update_chat_error(self, chat_id: str, error_message: str, retrieved_context, start_time: float):
        """Safely update chat with error status without raising exceptions"""
        try:
            await update_chat(
                chat_id=chat_id,
                response=error_message,
                retrieved_context=retrieved_context,
                start_time=start_time,
                status=ChatStatus.ERROR.value,
                memory_store=self.memory_store
            )
        except Exception as e:
            logger.error(f"ChaChaCha - Failed to update chat with error status for chat_id '{chat_id}': {e}", exc_info=True)