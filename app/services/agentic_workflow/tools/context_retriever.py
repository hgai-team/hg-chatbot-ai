import logging
logger = logging.getLogger(__name__)

import asyncio
from typing import List, Dict, Any, Set, Callable

from services.agentic_workflow.tools.search import SearchTool
from services.agentic_workflow.tools.evaluation_agent import EvaluationAgentTool
from services.agentic_workflow.schema import QueryProcessed, ContextRetrieved

class ContextRetrievalTool:
    def __init__(
        self,
        search: SearchTool,
        eval_agent: EvaluationAgentTool,
        llm_runner: Callable,
        llm_arunner: Callable
    ):
        self.search = search
        self.eval_agent = eval_agent
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
        idx: int,
        ids: list[str]
    ):
        vs_docs_formatted: List[Dict[str, Any]] = []
        fts_docs_formatted: List[Dict[str, Any]] = []

        try:
            search_tasks = {}
            search_tasks[f"embed_{idx}"] = asyncio.create_task(self._run_sync_in_thread(self.search.get_embed, query, user_id, session_id))
            search_tasks[f"fts_{idx}"] = asyncio.create_task(self.search.find_documents_by_keywords(keywords, ids))

            results = await asyncio.gather(*search_tasks.values(), return_exceptions=True)

            fts_res = results[1]
            if isinstance(fts_res, Exception):
                logger.warning(f"FTS search failed for query '{query}': {fts_res}")
                fts_docs_formatted = []
            else:
                fts_docs_formatted = fts_res if isinstance(fts_res, list) else []

            embed_res = results[0]
            if isinstance(embed_res, Exception):
                logger.warning(f"Embedding generation failed for query '{query}': {embed_res}")
                query_embedding = None
            else:
                query_embedding = embed_res

            if query_embedding:
                _, vs_scores, vs_ids = await self._run_sync_in_thread(self.search.find_similar_documents, query_embedding)
                if vs_ids:
                    vs_raw_docs = await self.search.retrieve_documents(vs_ids)
                    vs_docs_formatted = self.search.format_results(vs_raw_docs, vs_scores)
        except Exception as e:
            logger.error(f"An unexpected error occurred during search for query '{query}': {e}", exc_info=True)
            return []

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

        if "context_selector" in self.eval_agent.agent_prompt:
            relevant_ids = set()
            try:
                validation_result = await self.eval_agent.context_relevance(
                    query=query,
                    results=combined_results,
                    user_id=user_id,
                    session_id=session_id,
                    func=self.llm_arunner,
                    agent_name="context_selector",
                )

                if isinstance(validation_result, dict):
                    relevant_ids = set(validation_result.get('relevant_context_ids', []))
                else:
                    relevant_ids = set()
            except Exception:
                logger.error(f"Context relevance validation failed for query '{query}': {e}", exc_info=True)
                return []

            seen_ids: Set[str] = set()
            final_docs_for_query = []
            for doc in combined_results:
                doc_id = doc.get("id")
                if doc_id and doc_id in relevant_ids and doc_id not in seen_ids:
                    final_docs_for_query.append(doc)

            return final_docs_for_query

        return combined_results
    async def retrieve_context(
        self,
        processed_query_info: QueryProcessed,
        user_id: str,
        session_id: str
    ):
        all_relevant_docs_dict: Dict[str, Dict[str, Any]] = {}
        global_seen_ids = set()
        search_tasks = []
        query_map = {item.get("query"): item.get("keywords", []) for item in processed_query_info.keywords_per_query if item.get("query")}
        ids = await self.search.get_all_ids()

        for idx, (query, keywords) in enumerate(query_map.items()):
            task = asyncio.create_task(
                self._search_and_validate_for_query(
                    query, keywords, user_id, session_id, idx, ids
                )
            )
            search_tasks.append(task)

        results_from_tasks = await asyncio.gather(*search_tasks, return_exceptions=True)

        for result in results_from_tasks:
            if isinstance(result, list):
                for doc in result:
                    doc_id = doc.get("id")
                    if doc_id and doc_id not in all_relevant_docs_dict:
                        all_relevant_docs_dict[doc_id] = doc
                        global_seen_ids.add(doc_id)

        documents_as_markdown = (
            f"### Tài liệu {i}\n\n{doc.get('text', '')}"
            for i, doc in enumerate(all_relevant_docs_dict.values(), 1)
        )

        context_string = "\n\n---\n\n".join(documents_as_markdown)

        return ContextRetrieved(
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
                self.search.get_embed, query, user_id, session_id
            )
        )
        search_tasks[f"fts_{idx}"] = asyncio.create_task(
            self.search.user_find_documents_by_keywords(
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
                    self.search.user_find_similar_documents,
                    user_context,
                    query_embedding
                )

                if vs_ids:
                    vs_raw_docs = await self.search.retrieve_documents(vs_ids)
                    vs_docs_formatted = self.search.format_results(vs_raw_docs, vs_scores)
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
            validation_result = await self.eval_agent.context_relevance(
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
        processed_query_info: QueryProcessed,
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

        documents_as_markdown = (
            f"### Tài liệu {i}\n\n{doc.get('text', '')}"
            for i, doc in enumerate(all_relevant_docs_dict.values(), 1)
        )

        context_string = "\n\n---\n\n".join(documents_as_markdown)

        return ContextRetrieved(
            context_string=context_string,
            source_documents=all_relevant_docs_dict
        )
