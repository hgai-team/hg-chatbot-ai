import asyncio
from typing import Dict, Any, List, Union, Callable

from core.parsers import json_parser
from core.storages.client import TracerManager as TM
from llama_index.core.llms import ChatResponse
from services.agentic_workflow.tools.prompt_processor import PromptProcessorTool as PPT

class QueryAnalyzerAgentTool:
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
            "description": "Analyzer Agent",
            "instructions": "",
            "input": ""
        })

    async def _run_agent(
        self,
        input_data: Union[str, List[str]],
        user_id: str,
        session_id: str,
        func: Callable,
        agent_name: str,
        fallback: Callable[[Union[str, List[str]]], Any]
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
                    **{**agent_config, **{"input": input_data}}
                )

                messages = PPT.prepare_chat_messages(prompt=prompt)

                response: ChatResponse = await wrapper(func, messages=messages)
                final_result = json_parser(response.message.content)

            return final_result
        except Exception:
            return fallback(input_data)


    async def extract_keyword(
        self,
        queries: Union[str, List[str]],
        user_id: str,
        session_id: str,
        func: Callable,
        agent_name: str
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        def fallback(qs):
            if isinstance(qs, list):
                return [{"query": q, "keywords": []} for q in qs]
            return {"query": qs, "keywords": []}

        return await self._run_agent(
            input_data=queries,
            user_id=user_id,
            session_id=session_id,
            func=func,
            agent_name=agent_name,
            fallback=fallback
        )

    async def query_preprocess(
        self,
        query: str,
        user_id: str,
        session_id: str,
        func: Callable,
        agent_name: str
    ) -> Dict[str, Any]:
        def fallback(q):
            return {"query": q, "sub_queries": []}

        return await self._run_agent(
            input_data=query,
            user_id=user_id,
            session_id=session_id,
            func=func,
            agent_name=agent_name,
            fallback=fallback
        )
