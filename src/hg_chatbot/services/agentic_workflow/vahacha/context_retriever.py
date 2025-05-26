import asyncio
from typing import List, Dict, Any, Set, Callable

from services.tools import SearchTool
from services.agentic_workflow.tools import EvaluationAgent
from .schema import ProcessedQueryInfo, RetrievedContext

class ContextRetrievalService:
    def __init__(
        self,
        search_tool: SearchTool,
        evaluation_agent: EvaluationAgent,
        llm_runner: Callable,
        llm_arunner: Callable
    ):
        self.search_tool = search_tool
        self.evaluation_agent = evaluation_agent
        self.llm_runner = llm_runner
        self.llm_arunner = llm_arunner

    async def _run_sync_in_thread(self, func, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)

    async def _search_and_validate_for_query(
        self,
        query: str,
        keywords: List[str],
        user_id: str,
        session_id: str,
        idx: int
    ):
        vs_docs_formatted: List[Dict[str, Any]] = []
        fts_docs_formatted: List[Dict[str, Any]] = []
        search_tasks = {}
        search_tasks[f"embed_{idx}"] = asyncio.create_task(self._run_sync_in_thread(self.search_tool.get_embed, query, user_id, session_id))
        search_tasks[f"fts_{idx}"] = asyncio.create_task(self.search_tool.find_documents_by_keywords(keywords))

        try:
            fts_res = await search_tasks[f"fts_{idx}"]
            if isinstance(fts_res, list): fts_docs_formatted = fts_res
            embed_res = await search_tasks[f"embed_{idx}"]
            query_embedding = embed_res if not isinstance(embed_res, Exception) else None

            if query_embedding:
                _, vs_scores, vs_ids = await self._run_sync_in_thread(self.search_tool.find_similar_documents, query_embedding)
                if vs_ids:
                    vs_raw_docs = await self._run_sync_in_thread(self.search_tool.retrieve_documents, vs_ids)
                    vs_docs_formatted = self.search_tool.format_results(vs_raw_docs, vs_scores)
        except Exception:
            vs_docs_formatted = []
            fts_docs_formatted = []

        combined_results: List[Dict[str, Any]] = []

        seen_ids: Set[str] = set()
        for doc in fts_docs_formatted:
            doc_id = doc.get("id")
            if doc_id and doc_id not in seen_ids:
                seen_ids.add(doc_id)
                combined_results.append(doc)

        for doc in vs_docs_formatted:
            doc_id = doc.get("id")
            if doc_id and doc_id not in seen_ids:
                seen_ids.add(doc_id)
                combined_results.append(doc)

        relevant_ids = set()
        try:
            validation_result = await self.evaluation_agent.context_relevance(
                query=query,
                results=combined_results,
                user_id=user_id,
                session_id=session_id,
                func=self.llm_arunner,
                agent_name="context_selector",
            )

            if isinstance(validation_result, dict):
                relevant_ids = set(validation_result.get('relevant_context_ids', []))
        except Exception:
            return []

        seen_ids: Set[str] = set()
        final_docs_for_query = []
        for doc in combined_results:
            doc_id = doc.get("id")
            if doc_id and doc_id in relevant_ids and doc_id not in seen_ids:
                final_docs_for_query.append(doc)

        return final_docs_for_query

    async def retrieve_context(
        self,
        processed_query_info: ProcessedQueryInfo,
        user_id: str,
        session_id: str
    ):
        all_relevant_docs_dict: Dict[str, Dict[str, Any]] = {}
        global_seen_ids = set()
        search_tasks = []
        query_map = {item.get("query"): item.get("keywords", []) for item in processed_query_info.keywords_per_query if item.get("query")}

        for idx, (query, keywords) in enumerate(query_map.items()):
            task = asyncio.create_task(self._search_and_validate_for_query(
                query, keywords, user_id, session_id, idx
            ))
            search_tasks.append(task)

        results_from_tasks = await asyncio.gather(*search_tasks, return_exceptions=True)

        for result in results_from_tasks:
            if isinstance(result, list):
                for doc in result:
                    doc_id = doc.get("id")
                    if doc_id and doc_id not in all_relevant_docs_dict:
                        all_relevant_docs_dict[doc_id] = doc
                        global_seen_ids.add(doc_id)

        context_string = "\n\n".join(doc.get("text", "") for _, doc in all_relevant_docs_dict.items()).strip()

        return RetrievedContext(
            context_string=context_string,
            source_documents=all_relevant_docs_dict
        )

    async def _user_search_and_validate_for_query(
        self,
        query: str,
        keywords: List[str],
        user_id: str,
        session_id: str,
        user_context: dict,
        idx: int
    ):
        vs_docs_formatted: List[Dict[str, Any]] = []
        fts_docs_formatted: List[Dict[str, Any]] = []

        search_tasks = {}
        search_tasks[f"embed_{idx}"] = asyncio.create_task(
            self._run_sync_in_thread(
                self.search_tool.get_embed, query, user_id, session_id
            )
        )
        search_tasks[f"fts_{idx}"] = asyncio.create_task(
            self.search_tool.user_find_documents_by_keywords(
                keywords=keywords,
                user_context=user_context
            )
        )

        try:
            fts_res = await search_tasks[f"fts_{idx}"]
            if isinstance(fts_res, list): fts_docs_formatted = fts_res
            embed_res = await search_tasks[f"embed_{idx}"]
            query_embedding = embed_res if not isinstance(embed_res, Exception) else None

            if query_embedding:
                _, vs_scores, vs_ids = await self._run_sync_in_thread(
                    self.search_tool.user_find_similar_documents,
                    user_context,
                    query_embedding
                )

                if vs_ids:
                    vs_raw_docs = await self._run_sync_in_thread(
                        self.search_tool.retrieve_documents,
                        vs_ids
                    )
                    vs_docs_formatted = self.search_tool.format_results(vs_raw_docs, vs_scores)
        except Exception:
            vs_docs_formatted = []
            fts_docs_formatted = []

        combined_results: List[Dict[str, Any]] = []

        seen_ids: Set[str] = set()
        for doc in fts_docs_formatted:
            doc_id = doc.get("id")
            if doc_id and doc_id not in seen_ids:
                seen_ids.add(doc_id)
                combined_results.append(doc)

        for doc in vs_docs_formatted:
            doc_id = doc.get("id")
            if doc_id and doc_id not in seen_ids:
                seen_ids.add(doc_id)
                combined_results.append(doc)

        relevant_ids = set()
        try:
            validation_result = await self.evaluation_agent.context_relevance(
                query=query,
                results=combined_results,
                user_id=user_id,
                session_id=session_id,
                func=self.llm_arunner,
                agent_name="context_selector",
            )

            if isinstance(validation_result, dict):
                relevant_ids = set(validation_result.get('relevant_context_ids', []))
        except Exception:
            return []

        seen_ids: Set[str] = set()
        final_docs_for_query = []
        for doc in combined_results:
            doc_id = doc.get("id")
            if doc_id and doc_id in relevant_ids and doc_id not in seen_ids:
                final_docs_for_query.append(doc)

        return final_docs_for_query

    async def user_retrieve_context(
        self,
        processed_query_info: ProcessedQueryInfo,
        user_id: str,
        session_id: str,
        user_context: dict
    ):
        all_relevant_docs_dict: Dict[str, Dict[str, Any]] = {}
        global_seen_ids = set()
        search_tasks = []
        query_map = {item.get("query"): item.get("keywords", []) for item in processed_query_info.keywords_per_query if item.get("query")}

        for idx, (query, keywords) in enumerate(query_map.items()):
            task = asyncio.create_task(self._user_search_and_validate_for_query(
                query, keywords, user_id, session_id, user_context, idx
            ))
            search_tasks.append(task)

        results_from_tasks = await asyncio.gather(*search_tasks, return_exceptions=True)

        for result in results_from_tasks:
            if isinstance(result, list):
                for doc in result:
                    doc_id = doc.get("id")
                    if doc_id and doc_id not in all_relevant_docs_dict:
                        all_relevant_docs_dict[doc_id] = doc
                        global_seen_ids.add(doc_id)

        context_string = "\n\n".join(doc.get("text", "") for _, doc in all_relevant_docs_dict.items()).strip()

        return RetrievedContext(
            context_string=context_string,
            source_documents=all_relevant_docs_dict
        )
