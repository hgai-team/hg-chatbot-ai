import logging
logger = logging.getLogger(__name__)

import asyncio

from datetime import datetime
from fastapi import HTTPException
from uuid import uuid4

from api.schema import UserContext
from core.storages import BaseChat

from .base import BaseBotService
from services.agentic_workflow.tools import PromptProcessorTool as PPT

from services import get_settings_cached
class OpsBotService(BaseBotService):
    def __init__(
        self,
    ):
        self.bot_name = 'VaHaCha'
        self._set_up()

    def _set_up(
        self,
    ):
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

        self.agent_prompt_path = settings.OPS_AGENT_PROMPT_PATH

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

        self.main_llm = get_openai_llm()
        self.memory_store: MongoDBMemoryStore = get_mongodb_memory_store(
            database_name=database_name,
            collection_name=collection_name
        )
        self.instrumentor = get_langfuse_instrumentor_cached()

    async def _run_sync_in_thread(self, func, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)

    async def process_chat_request(
        self,
        query_text: str,
        user_id: str,
        session_id: str,
    ) -> str:
        try:
            try:
                processed_info = await self.query_processor.analyze_query(
                    query_text=query_text,
                    user_id=user_id,
                    session_id=session_id
                )
            except Exception as e:
                logger.error(f"VaHaCha - Error during query analysis for session '{session_id}': {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Error during query analysis")

            try:
                retrieved_context = await self.context_retriever.retrieve_context(
                    processed_query_info=processed_info,
                    user_id=user_id,
                    session_id=session_id
                )
            except Exception as e:
                logger.error(f"VaHaCha - Error during context retrieval for session '{session_id}': {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Error during context retrieval")

            inal_messages = PPT.format_chat_prompt(
                processed_info=processed_info,
                retrieved_context=retrieved_context
            )

            response_text = ""
            trace_name = f"{self.main_llm.__class__.__name__}_chat_completion"
            with self.instrumentor.observe(session_id=session_id, user_id=user_id, trace_name=trace_name):
                response_text = await self.main_llm.arun(messages=inal_messages)
            self.instrumentor.flush()

            chat_to_store = BaseChat(
                message=query_text,
                response=response_text,
                context={
                    "source_document_ids": [id_ for id_, _ in retrieved_context.source_documents.items()]
                },
                timestamp=datetime.now(),
                chat_id=str(uuid4())
            )

            try:
                from services import get_google_genai_llm
                session_title = await self.memory_store.add_chat(
                    user_id=user_id,
                    session_id=session_id,
                    chat=chat_to_store,
                    llm=get_google_genai_llm(model_name=get_settings_cached().GOOGLEAI_MODEL)
                )

            except Exception as e:
                logger.error(f"VaHaCha - Failed to store chat history for session '{session_id}': {e}", exc_info=True)
                session_title = "New Chat"

            return response_text

        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"An internal error occurred during chat processing. {e}")

    async def process_chat_stream_request(
        self,
        query_text: str,
        user_id: str,
        session_id: str,
    ):
        try:
            yield {'_type': 'header_thinking', 'text': 'Đang phân tích yêu cầu...\n'}

            try:
                processed_info = await self.query_processor.analyze_query(
                    query_text=query_text,
                    user_id=user_id,
                    session_id=session_id
                )
            except Exception as e:
                logger.error(f"VaHaCha - Error during query analysis for session '{session_id}': {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Error during query analysis")

            yield {'_type': 'thinking', 'text': 'Hoàn thành phân tích!\n'}

            yield {'_type': 'header_thinking', 'text': 'Đang tìm kiếm thông tin...\n'}

            try:
                retrieved_context = await self.context_retriever.retrieve_context(
                    processed_query_info=processed_info,
                    user_id=user_id,
                    session_id=session_id
                )
            except Exception as e:
                logger.error(f"VaHaCha - Error during context retrieval for session '{session_id}': {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Error during context retrieval")

            yield {'_type': 'thinking', 'text': 'Hoàn thành tìm kiếm thông tin!\n'}

            inal_messages = PPT.format_chat_prompt(
                processed_info=processed_info,
                retrieved_context=retrieved_context
            )

            yield {'_type': 'header_thinking', 'text': 'Đang phản hồi yêu cầu...\n'}

            response_text = ""
            trace_name = f"{self.main_llm.__class__.__name__}_chat_completion"
            with self.instrumentor.observe(session_id=session_id, user_id=user_id, trace_name=trace_name):
                response_text = await self.main_llm.arun(messages=inal_messages)
            self.instrumentor.flush()

            chat_id = str(uuid4())
            chat_to_store = BaseChat(
                message=query_text,
                response=response_text,
                context={
                    "source_document_ids": [id_ for id_, _ in retrieved_context.source_documents.items()]
                },
                timestamp=datetime.now(),
                chat_id=chat_id
            )

            try:
                from services import get_google_genai_llm
                session_title = await self.memory_store.add_chat(
                    user_id=user_id,
                    session_id=session_id,
                    chat=chat_to_store,
                    llm=get_google_genai_llm(model_name=get_settings_cached().GOOGLEAI_MODEL)
                )

            except Exception as e:
                logger.error(f"VaHaCha - Failed to store chat history for session '{session_id}': {e}", exc_info=True)
                session_title = "New Chat"

            yield {'_type': 'response', 'text': response_text}

            if session_title:
                yield {'_type': 'session_title', 'text': session_title}
            yield {'_type': 'chat_id', 'text': chat_id}

        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"An internal error occurred during chat processing. {e}")

    async def user_validate_chat_request(
        self,
        query_text: str,
        user_id: str,
        session_id: str,
        user_context: UserContext
    ):
        analysis_tasks = {
            "query_classifier": asyncio.create_task(
                    self.eval_agent.validate(
                    query=f"""user_query:\n{query_text}\n\nuser_context:\n{user_context.model_dump_json().lower()}""",
                    user_id=user_id,
                    session_id=session_id,
                    func=self.google_llm.arun, agent_name="query_classifier"
                )
            ),
            "safety_guard": asyncio.create_task(
                    self.eval_agent.validate(
                    query=query_text, user_id=user_id, session_id=session_id,
                    func=self.google_llm.arun, agent_name="safety_guard"
                )
            ),
        }
        results = await asyncio.gather(*analysis_tasks.values(), return_exceptions=True)
        task_names = list(analysis_tasks.keys())
        safety_guard_response = results[task_names.index("safety_guard")]
        query_classifier_response = results[task_names.index("query_classifier")]

        if safety_guard_response.get("status") == "invalid":
            return safety_guard_response

        return query_classifier_response

    async def user_process_chat_request(
        self,
        query_text: str,
        user_id: str,
        session_id: str,
        user_context: UserContext
    ) -> str:
        try:
            try:
                processed_info = await self.query_processor.analyze_query(
                    query_text=query_text,
                    user_id=user_id,
                    session_id=session_id
                )
            except Exception as e:
                logger.error(f"VaHaCha - Error during query analysis for session '{session_id}': {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Error during query analysis")

            try:
                retrieved_context = await self.context_retriever.user_retrieve_context(
                    processed_query_info=processed_info,
                    user_id=user_id,
                    session_id=user_id,
                    user_context=user_context.model_dump(),
                )
            except Exception as e:
                logger.error(f"VaHaCha - Error during context retrieval for session '{session_id}': {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Error during context retrieval")

            inal_messages = PPT.format_chat_prompt(
                processed_info=processed_info,
                retrieved_context=retrieved_context
            )

            response_text = ""
            trace_name = f"{self.main_llm.__class__.__name__}_chat_completion"
            with self.instrumentor.observe(session_id=session_id, user_id=user_id, trace_name=trace_name):
                response_text = await self.main_llm.arun(messages=inal_messages)

            self.instrumentor.flush()

            from services import (
                get_google_genai_llm,
                get_settings_cached
            )
            google_llm = get_google_genai_llm(
                model_name=get_settings_cached().GOOGLEAI_MODEL_EDITOR
            )
            response_permission_editor_response = await self.eval_agent.validate(
                query=f"""question:\n{query_text}\n\question_context:\n{response_text}\n\nuser_context:\n{user_context.model_dump_json(exclude='role').lower()}""",
                user_id=user_id,
                session_id=session_id,
                func=google_llm.arun, agent_name="response_permission_editor"
            )
            response_text = response_permission_editor_response.get("answer")

            chat_to_store = BaseChat(
                message=query_text,
                response=response_text,
                context={
                    "source_document_ids": [id_ for id_, _ in retrieved_context.source_documents.items()]
                },
                timestamp=datetime.now(),
                chat_id=str(uuid4())
            )

            _ = await self.memory_store.add_chat(
                user_id=user_id,
                session_id=session_id,
                chat=chat_to_store,
                llm=get_google_genai_llm(model_name=get_settings_cached().GOOGLEAI_MODEL)
            )

            return response_text

        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"An internal error occurred during chat processing. {e}")

    async def user_process_chat_request_stream(
        self,
        query_text: str,
        user_id: str,
        session_id: str,
        user_context: UserContext
    ):
        try:
            yield {'_type': 'header_thinking', 'text': 'Đang phân tích yêu cầu...\n'}

            try:
                processed_info = await self.query_processor.analyze_query(
                    query_text=query_text,
                    user_id=user_id,
                    session_id=session_id
                )
            except Exception as e:
                logger.error(f"VaHaCha - Error during query analysis for session '{session_id}': {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Error during query analysis")

            yield {'_type': 'thinking', 'text': 'Hoàn thành phân tích!\n'}

            yield {'_type': 'header_thinking', 'text': 'Đang tìm kiếm thông tin...\n'}

            try:
                retrieved_context = await self.context_retriever.user_retrieve_context(
                    processed_query_info=processed_info,
                    user_id=user_id,
                    session_id=user_id,
                    user_context=user_context.model_dump(),
                )
            except Exception as e:
                logger.error(f"VaHaCha - Error during context retrieval for session '{session_id}': {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Error during context retrieval")

            yield {'_type': 'thinking', 'text': 'Hoàn thành tìm kiếm thông tin!\n'}

            inal_messages = PPT.format_chat_prompt(
                processed_info=processed_info,
                retrieved_context=retrieved_context
            )

            yield {'_type': 'header_thinking', 'text': 'Đang phản hồi yêu cầu...\n'}

            response_text = ""
            trace_name = f"{self.main_llm.__class__.__name__}_chat_completion"
            with self.instrumentor.observe(session_id=session_id, user_id=user_id, trace_name=trace_name):
                response_text = await self.main_llm.arun(messages=inal_messages)
            self.instrumentor.flush()

            yield {'_type': 'header_thinking', 'text': 'Đang phân tích phản hổi...\n'}

            from services import (
                get_google_genai_llm,
                get_settings_cached
            )
            google_llm = get_google_genai_llm(
                model_name=get_settings_cached().GOOGLEAI_MODEL_EDITOR
            )
            response_permission_editor_response = await self.eval_agent.validate(
                query=f"""question:\n{query_text}\n\question_context:\n{response_text}\n\nuser_context:\n{user_context.model_dump_json(exclude='role').lower()}""",
                user_id=user_id,
                session_id=session_id,
                func=google_llm.arun, agent_name="response_permission_editor"
            )
            response_text = response_permission_editor_response.get("answer")

            chat_id = str(uuid4())
            chat_to_store = BaseChat(
                message=query_text,
                response=response_text,
                context={
                    "source_document_ids": [id_ for id_, _ in retrieved_context.source_documents.items()]
                },
                timestamp=datetime.now(),
                chat_id=chat_id
            )

            session_title = await self.memory_store.add_chat(
                user_id=user_id,
                session_id=session_id,
                chat=chat_to_store,
                llm=get_google_genai_llm(model_name=get_settings_cached().GOOGLEAI_MODEL)
            )


            yield {'_type': 'response', 'text': response_text}

            if session_title:
                yield {'_type': 'session_title', 'text': session_title}
            yield {'_type': 'chat_id', 'text': chat_id}

        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"An internal error occurred during chat processing. {e}")
