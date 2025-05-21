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

    async def validate_chat_request(
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

    async def process_chat_request(
        self,
        query_text: str,
        user_id: str,
        session_id: str,
        user_context: UserContext
    ) -> str:
        try:
            processed_info = await self.query_processor.analyze_query(query_text, user_id, session_id)
            retrieved_context = await self.context_retriever.retrieve_context(processed_info, user_id, session_id)

            inal_messages = self.prompt_formatter.format_chat_prompt(processed_info, retrieved_context)

            response_text = ""
            trace_name = f"{self.main_llm.__class__.__name__}_chat_completion"
            with self.instrumentor.observe(session_id=session_id, user_id=user_id, trace_name=trace_name):
                response_text = await self.main_llm.arun(messages=inal_messages)

            self.instrumentor.flush()

            if user_context.role != "admin":
                response_permission_editor_response = await self.evaluation_agent.validate(
                    query=f"""initial_response:\n{response_text}\n\nuser_context: {user_context.model_dump_json().lower()}""",
                    user_id=user_id,
                    session_id=session_id,
                    func=self.google_llm.arun, agent_name="response_permission_editor"
                )

                if response_permission_editor_response.get("status") == "edited":
                    response_text = response_permission_editor_response.get("filtered_response")

            chat_to_store = BaseChat(
                message=query_text,
                response=response_text,
                context={
                    "source_document_ids": [id_ for id_, _ in retrieved_context.source_documents.items()]
                },
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
            _ = await self._run_sync_in_thread(self.memory_store.add_chat, user_id, session_id, chat_to_store)

            return response_text

        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"An internal error occurred during chat processing. {e}")
