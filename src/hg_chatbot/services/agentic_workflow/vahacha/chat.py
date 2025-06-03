import asyncio

from typing import Tuple
from datetime import datetime
from fastapi import HTTPException
from langfuse.llama_index import LlamaIndexInstrumentor

from api.schema import UserContext

from core.llms import OpenAILLM, GoogleGenAILLM
from core.storages import BaseMemoryStore, BaseChat


from services.agentic_workflow.tools import EvaluationAgent


from .query_processor import QueryProcessingService
from .context_retriever import ContextRetrievalService
from .prompt_formatter import PromptFormattingService

from uuid import uuid4

class ChatService:
    def __init__(
        self,
        query_processor: QueryProcessingService,
        context_retriever: ContextRetrievalService,
        prompt_formatter: PromptFormattingService,
        evaluation_agent: EvaluationAgent,
        google_llm: GoogleGenAILLM,
        main_llm: OpenAILLM,
        memory_store: BaseMemoryStore,
        instrumentor: LlamaIndexInstrumentor
    ):
        self.query_processor = query_processor
        self.context_retriever = context_retriever
        self.prompt_formatter = prompt_formatter
        self.evaluation_agent = evaluation_agent
        self.google_llm = google_llm
        self.main_llm = main_llm
        self.memory_store = memory_store
        self.instrumentor = instrumentor

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
            processed_info = await self.query_processor.analyze_query(
                query_text=query_text,
                user_id=user_id, 
                session_id=session_id
            )
            
            retrieved_context = await self.context_retriever.retrieve_context(
                processed_query_info=processed_info, 
                user_id=user_id, 
                session_id=session_id
            )

            inal_messages = self.prompt_formatter.format_chat_prompt(
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
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                chat_id=str(uuid4())
            )
            
            from services import get_google_genai_llm
            _ = await self._run_sync_in_thread(
                lambda: self.memory_store.add_chat(
                    user_id=user_id,
                    session_id=session_id,
                    chat=chat_to_store,
                    llm=get_google_genai_llm(model_name="models/gemini-2.0-flash")
                )
            )

            return response_text

        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"An internal error occurred during chat processing. {e}")
    
    async def process_chat_request_stream(
        self,
        query_text: str,
        user_id: str,
        session_id: str,
    ):
        try:
            yield {'_type': 'header_thinking', 'text': 'Đang phân tích yêu cầu...\n'}
            
            processed_info = await self.query_processor.analyze_query(
                query_text=query_text,
                user_id=user_id, 
                session_id=session_id
            )
            yield {'_type': 'thinking', 'text': 'Hoàn thành phân tích!\n'}
            
            yield {'_type': 'header_thinking', 'text': 'Đang tìm kiếm thông tin...\n'}
            
            retrieved_context = await self.context_retriever.retrieve_context(
                processed_query_info=processed_info, 
                user_id=user_id, 
                session_id=session_id
            )
            
            yield {'_type': 'thinking', 'text': 'Hoàn thành tìm kiếm thông tin!\n'}

            inal_messages = self.prompt_formatter.format_chat_prompt(
                processed_info=processed_info, 
                retrieved_context=retrieved_context
            )
            
            yield {'_type': 'header_thinking', 'text': 'Đang phản hồi yêu cầu...\n'}

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
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                chat_id=str(uuid4())
            )
            
            from services import get_google_genai_llm
            _ = await self._run_sync_in_thread(
                lambda: self.memory_store.add_chat(
                    user_id=user_id,
                    session_id=session_id,
                    chat=chat_to_store,
                    llm=get_google_genai_llm(model_name="models/gemini-2.0-flash")
                )
            )

            yield {'_type': 'response', 'text': response_text} 

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
                    self.evaluation_agent.validate(
                    query=f"""user_query:\n{query_text}\n\nuser_context:\n{user_context.model_dump_json().lower()}""",
                    user_id=user_id,
                    session_id=session_id,
                    func=self.google_llm.arun, agent_name="query_classifier"
                )
            ),
            "safety_guard": asyncio.create_task(
                    self.evaluation_agent.validate(
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
            processed_info = await self.query_processor.analyze_query(
                query_text=query_text,
                user_id=user_id,
                session_id=session_id
            )

            retrieved_context = await self.context_retriever.user_retrieve_context(
                processed_query_info=processed_info,
                user_id=user_id,
                session_id=user_id,
                user_context=user_context.model_dump(),
            )

            inal_messages = self.prompt_formatter.format_chat_prompt(
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
            response_permission_editor_response = await self.evaluation_agent.validate(
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
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                chat_id=str(uuid4())
            )
            
            __ = await self._run_sync_in_thread(
                lambda: self.memory_store.add_chat(
                    user_id=user_id,
                    session_id=session_id,
                    chat=chat_to_store,
                    llm=get_google_genai_llm(model_name="models/gemini-2.0-flash")
                )
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
            
            processed_info = await self.query_processor.analyze_query(
                query_text=query_text,
                user_id=user_id,
                session_id=session_id
            )
            
            yield {'_type': 'thinking', 'text': 'Hoàn thành phân tích!\n'}
            
            yield {'_type': 'header_thinking', 'text': 'Đang tìm kiếm thông tin...\n'}

            retrieved_context = await self.context_retriever.user_retrieve_context(
                processed_query_info=processed_info,
                user_id=user_id,
                session_id=user_id,
                user_context=user_context.model_dump(),
            )
            
            yield {'_type': 'thinking', 'text': 'Hoàn thành tìm kiếm thông tin!\n'}

            inal_messages = self.prompt_formatter.format_chat_prompt(
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
            response_permission_editor_response = await self.evaluation_agent.validate(
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
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                chat_id=str(uuid4())
            )
            
            _ = await self._run_sync_in_thread(
                lambda: self.memory_store.add_chat(
                    user_id=user_id,
                    session_id=session_id,
                    chat=chat_to_store,
                    llm=get_google_genai_llm(model_name="models/gemini-2.0-flash")
                )
            )

            yield {'_type': 'response', 'text': response_text} 

        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"An internal error occurred during chat processing. {e}")
