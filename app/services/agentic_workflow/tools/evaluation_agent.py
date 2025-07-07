import asyncio
from typing import Dict, Any, List, Callable
from llama_index.core.llms import ChatMessage, ChatResponse

from core.parsers import json_parser
from core.storages.client import TracerManager as TM
from services.agentic_workflow.tools.prompt_processor import PromptProcessorTool as PPT

class EvaluationAgentTool:
    def __init__(
        self,
        agent_prompt_path: str,
        prompt_template_path: str,
    ):
        from services import get_langfuse_instrumentor_cached
        self.instrumentor = get_langfuse_instrumentor_cached()

        self.agent_prompt = PPT.load_prompt(agent_prompt_path)
        if not isinstance(self.agent_prompt, dict):
            self.agent_prompt = {}

        self.prompt_template = PPT.load_prompt(prompt_template_path)
        if not isinstance(self.prompt_template, dict):
            self.prompt_template = {}

    def _get_agent_config(self, agent_name: str) -> Dict:
        return self.agent_prompt.get(agent_name, {
            "role": "system",
            "description": "Evaluation Agent",
            "instructions": "",
            "input": ""
        })

    async def _run_agent(
        self,
        input_str: str,
        user_id: str,
        session_id: str,
        func: Callable,
        agent_name: str,
        fallback: Callable[[], Any]
    ) -> Any:
        agent_config = self._get_agent_config(agent_name)

        try:
            async with TM.trace_span(
                span_name=f"{func.__name__}_{agent_name}",
                span_type="LLM_AGENT_CALL",
                custom_metadata={
                    "user_id": user_id,
                    "session_id": session_id,
                    "agent_name": agent_name,
                }
            ) as (trace_id, span_id, wrapper):

                prompt = PPT.apply_chat_template(
                    template=self.prompt_template,
                    **{**agent_config, **{"input": input_str}}
                )
                messages = PPT.prepare_chat_messages(prompt=prompt)

                response: ChatResponse = await wrapper(func, messages=messages)
                final_result = json_parser(response.message.content)

            return final_result
        except Exception:
            return fallback()

    async def context_relevance(
        self,
        query: str,
        results: List[Dict[str, Any]],
        user_id: str,
        session_id: str,
        func: Callable,
        agent_name: str,
    ) -> Dict[str, Any]:
        default_response = {"relevant_context_ids": []}

        context_for_prompt = [
            {"id": doc["id"], "content": doc["text"]}
            for doc in results
            if doc.get("id") and doc.get("text")
        ]
        if not context_for_prompt:
            return default_response

        input_str = (
            f"user_query:\n{query}\n\n"
            f"retrieved_contexts:\n{context_for_prompt}"
        )

        return await self._run_agent(
            input_str=input_str,
            user_id=user_id,
            session_id=session_id,
            func=func,
            agent_name=agent_name,
            fallback=lambda: default_response
        )

    async def validate(
        self,
        query: str,
        user_id: str,
        session_id: str,
        func: Callable,
        agent_name: str
    ) -> Dict[str, Any]:
        def fallback():
            return {
                "query": query,
                "status": "invalid",
                "response": "Error during validation"
            }

        return await self._run_agent(
            input_str=query,
            user_id=user_id,
            session_id=session_id,
            func=func,
            agent_name=agent_name,
            fallback=fallback
        )

    async def intent_synthesis(
        self,
        chat_messages: List[ChatMessage],
        user_id: str,
        session_id: str,
        func: Callable,
        agent_name: str
    ) -> Dict[str, Any]:
        formatted_history = "\n".join(
            f"{msg.role}: {msg.content}" for msg in chat_messages
        )

        return await self._run_agent(
            input_str=formatted_history,
            user_id=user_id,
            session_id=session_id,
            func=func,
            agent_name=agent_name,
            fallback=lambda: {"status": "error", "question": None}
        )
