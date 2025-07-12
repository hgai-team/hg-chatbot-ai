import logging
logger = logging.getLogger(__name__)

import asyncio
from typing import List, Dict, Tuple, Callable
from llama_index.core.llms import ChatMessage, MessageRole
from fastapi import HTTPException

from core.config import CoreSettings
from core.storages import BaseMemoryStore, ChatHistory
from services.agentic_workflow.tools.evaluation_agent import EvaluationAgentTool
from services.agentic_workflow.tools.query_analyzer_agent import QueryAnalyzerAgentTool
from services.agentic_workflow.tools.prompt_processor import PromptProcessorTool as PPT

from services.agentic_workflow.schema.query_processor import QueryProcessed


class QueryProcessingTool:
    def __init__(
        self,
        query_analyzer: QueryAnalyzerAgentTool,
        eval_agent: EvaluationAgentTool,
        memory_store: BaseMemoryStore,
        settings: CoreSettings,
        llm_runner: Callable,
        llm_arunner: Callable,
        prompt_path: str,
        bot_name: str
    ):
        self.query_analyzer = query_analyzer
        self.eval_agent = eval_agent
        self.memory_store = memory_store
        self.settings = settings
        self.llm_runner = llm_runner
        self.llm_arunner = llm_arunner
        self.prompt_path = prompt_path
        self.bot_name = bot_name

    async def _get_chat_history_and_prompt(
        self,
        user_id: str,
        session_id: str
    ) -> Tuple[List[ChatMessage], ChatHistory, Dict]:

        try:
            loaded_data = PPT.load_prompt(self.prompt_path)
            if not isinstance(loaded_data, dict):
                raise TypeError("Prompt data is not a dictionary.")
            data = loaded_data

        except (FileNotFoundError, IOError) as e:
            logger.error(f"Prompt file not found or unreadable at {self.prompt_path}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Prompt file not found or unreadable")

        bot: dict = data.get(self.bot_name, {})
        initial_messages = [ChatMessage(role=MessageRole.SYSTEM, content=f"{bot.get('role', MessageRole.SYSTEM)}: {bot.get('description', 'Assistant')}")]

        try:
            chat_history = await self.memory_store.get_session_history(session_id)
        except Exception as e:
            logger.error(f"Failed to get session history for user '{user_id}', session '{session_id}': {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to get session history")

        if chat_history and chat_history.history:
            recent_chats = [item for item in chat_history.history if isinstance(item, dict)]
            for chat in recent_chats:
                user_msg = chat.get('message')
                assistant_msg = chat.get('response')
                if user_msg is not None:
                    initial_messages.append(ChatMessage(role=MessageRole.USER, content=str(user_msg)))
                    if assistant_msg is not None:
                        initial_messages.append(ChatMessage(role=MessageRole.ASSISTANT, content=str(assistant_msg)))

            message: ChatMessage = initial_messages[-1]
            if message.role == MessageRole.USER:
                initial_messages = initial_messages[:-1]

        return initial_messages, chat_history, data

    async def analyze_query(self, query_text: str, user_id: str, session_id: str) -> QueryProcessed:
        original_query = query_text.strip()
        if not original_query:
            original_query = self.settings.BASE_QUERY

        initial_messages, chat_history, prompt_data = await self._get_chat_history_and_prompt(user_id, session_id)

        system_prompt = initial_messages[0].content
        instructions = prompt_data.get(self.bot_name, {}).get('instructions', '')

        analysis_messages = list(initial_messages)
        analysis_messages.append(ChatMessage(role=MessageRole.USER, content=original_query))

        analysis_tasks = {
            "related_conv": asyncio.create_task(
                    self.eval_agent.intent_synthesis(
                    chat_messages=analysis_messages,
                    user_id=user_id, session_id=session_id, func=self.llm_arunner,
                    agent_name="intent_synthesizer"
                )
            ),
            "breakdown": asyncio.create_task(
                    self.query_analyzer.query_preprocess(
                    query=original_query,
                    user_id=user_id, session_id=session_id, func=self.llm_arunner,
                    agent_name="query_preprocessor"
                )
            )
        }
        results = await asyncio.gather(*analysis_tasks.values(), return_exceptions=True)
        task_names = list(analysis_tasks.keys())
        related_conv = results[task_names.index("related_conv")]
        breakdown_result = results[task_names.index("breakdown")]

        if isinstance(related_conv, Exception): related_conv = {"status": "error"}
        if isinstance(breakdown_result, Exception): breakdown_result = {"sub_queries": []}

        sub_queries = breakdown_result.get('sub_queries', [])
        all_queries_to_process = list(dict.fromkeys([original_query] + sub_queries))

        related_question = None
        if related_conv.get("status") == "valid" and chat_history:
            related_question = related_conv.get("question")
            if related_question and related_question != original_query and related_question not in all_queries_to_process:
                all_queries_to_process.append(related_question)

        if all_queries_to_process:
            try:
                keywords_result = await self.query_analyzer.extract_keyword(
                    queries=all_queries_to_process,
                    user_id=user_id,
                    session_id=session_id,
                    func=self.llm_arunner,
                    agent_name="keyword_extractor"
                )
                keywords_per_query = []
                if isinstance(keywords_result, list) and len(keywords_result) == len(all_queries_to_process):
                    for i, query in enumerate(all_queries_to_process):
                        k_data = keywords_result[i]
                        keywords_per_query.append({
                            "id": i, "query": query,
                            "keywords": k_data.get("keywords", []) if isinstance(k_data, dict) else []
                        })
                elif isinstance(keywords_result, dict) and len(all_queries_to_process) == 1:
                    keywords_per_query.append({
                        "id": 0, "query": original_query,
                        "keywords": keywords_result.get("keywords", [])
                    })
                else:
                    keywords_per_query = [{"id": i, "query": q, "keywords": []} for i, q in enumerate(all_queries_to_process)]
            except Exception:
                keywords_per_query = [{"id": i, "query": q, "keywords": []} for i, q in enumerate(all_queries_to_process)]


        history_messages_for_prompt = [msg for msg in initial_messages if msg.role in (MessageRole.USER, MessageRole.ASSISTANT)]

        return QueryProcessed(
            original_query=original_query,
            sub_queries=all_queries_to_process,
            keywords_per_query=keywords_per_query,
            history_messages=history_messages_for_prompt,
            system_prompt=system_prompt,
            instructions=instructions
        )
