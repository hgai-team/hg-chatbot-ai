import os

from typing import List, Dict, Any, Tuple

from fastapi import HTTPException

from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny

from core.embeddings import OpenAIEmbedding

from core.storages import (
    MongoDBDocumentStore,
    QdrantVectorStore
)

# from services.tools.bm25 import BM25Retriever

from core.base import Document

class SearchTool:
    def __init__(
        self,
        openai_embedding: OpenAIEmbedding,
        qdrant_vector_store: QdrantVectorStore,
        mongodb_doc_store: MongoDBDocumentStore,
        # bm25_retriever: BM25Retriever,
    ):
        from services import get_langfuse_instrumentor_cached
        self.instrumentor = get_langfuse_instrumentor_cached()

        self.openai_embedding = openai_embedding
        self.qdrant_vector_store = qdrant_vector_store
        self.mongodb_doc_store = mongodb_doc_store
        # self.bm25_retriever = bm25_retriever

    def _calculate_score(self, doc: Document, keywords_lower: List[str]):
        doc_dict: dict = doc.to_dict()
        doc_text = doc_dict.get('text')
        score = 0
        if doc_text and isinstance(doc_text, str):
            for keyword in keywords_lower:
                if keyword in doc_text:
                    score += 1
        if score > 0:
            return {'id': doc_dict.get('id_'), 'text': doc_text, 'score': score}
        return None

    def get_embed(
        self,
        query_text: str,
        user_id: str,
        session_id: str,
    ):
        try:
            with self.instrumentor.observe(session_id=session_id, user_id=user_id, trace_name="get_openai_embedding"):
                embedding = self.openai_embedding.embed_texts([query_text.lower()])[0]
            self.instrumentor.flush
            return embedding
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error embedding query: {str(e)}"
        )

    def find_similar_documents(
        self,
        embedding: List[float] = None,
        query_text: str = None,
        top_k: int = 20,
    ):
        if query_text:
            embedding=self.get_embed(query_text=query_text, user_id="demo", session_id="demo")
        results = self.qdrant_vector_store.query(
            embedding=embedding,
            top_k=top_k
        )
        return results


    async def find_documents_by_keywords(
        self,
        keywords: List[str],
        top_k: int = 20,
    ):
        import asyncio
        import concurrent.futures

        keywords = [keyword.lower() for keyword in keywords]
        query_string = " ".join(keywords)

        mongodb_scored_docs = []
        docs_mongo, scores_mongo = await self.mongodb_doc_store.query(query=query_string, top_k=top_k)
        mongodb_scored_docs = self.format_results(docs_mongo, scores_mongo)

        try:
            all_docs: List[Document] = self.mongodb_doc_store.get_all()
            if all_docs:
                loop = asyncio.get_running_loop()
                with concurrent.futures.ThreadPoolExecutor(min(16, os.cpu_count() + 4)) as executor:
                    tasks = [
                        loop.run_in_executor(
                            executor,
                            self._calculate_score,
                            doc,
                            keywords
                        )

                        for doc in all_docs
                    ]

                    scored_results_manual = await asyncio.gather(*tasks, return_exceptions=True)

                scored_docs_manual = []
                for result in scored_results_manual:
                    if isinstance(result, Exception):
                        print(f"Error during manual scoring task: {result}")
                    elif result is not None:
                        scored_docs_manual.append(result)

                scored_docs_manual.sort(key=lambda x: x['score'], reverse=True)
        except Exception as e:
            print(f"Error during manual scoring process: {e}")

        final_results = []
        seen_ids = set()

        if scored_docs_manual:
            for doc in scored_docs_manual:
                doc_id = doc.get("id")
                if doc_id not in seen_ids:
                    final_results.append(doc)
                    seen_ids.add(doc_id)

        if mongodb_scored_docs:
            for doc in mongodb_scored_docs:
                doc_id = doc.get("id")
                if doc_id not in seen_ids:
                    final_results.append(doc)
                    seen_ids.add(doc_id)

        return final_results[:top_k]

    def user_find_similar_documents(
        self,
        user_context: dict,
        embedding: List[float] = None,
        query_text: str = None,
        top_k: int = 20,
    ):
        if query_text:
            embedding=self.get_embed(query_text=query_text, user_id="demo", session_id="demo")

        should_conditions = [
            FieldCondition(key="general", match=MatchValue(value=True))
        ]

        projs = user_context.get("projects", [])
        if projs:
            should_conditions.append(
                FieldCondition(key="projects", match=MatchAny(any=projs))
            )
        nets = user_context.get("networks", [])
        if nets:
            should_conditions.append(
                FieldCondition(key="networks", match=MatchAny(any=nets))
            )
        deps = user_context.get("departments", [])
        if deps:
            should_conditions.append(
                FieldCondition(key="departments", match=MatchAny(any=deps))
            )

        try:
            results = self.qdrant_vector_store.query(
                embedding=embedding,
                top_k=top_k,
                qdrant_filters=Filter(
                    should=should_conditions
                )
            )
        except Exception as e:
            print(e)

        return results

    async def user_find_documents_by_keywords(
        self,
        keywords: List[str],
        user_context,
        top_k: int = 20,
    ):
        import asyncio
        import concurrent.futures

        keywords = [keyword.lower() for keyword in keywords]
        query_string = " ".join(keywords)

        docs_mongo = await self.mongodb_doc_store.user_query(
            query=query_string,
            top_k=top_k,
            user_context=user_context
        )

        try:
            all_docs: List[Document] = docs_mongo
            if all_docs:
                loop = asyncio.get_running_loop()
                with concurrent.futures.ThreadPoolExecutor(min(16, os.cpu_count() + 4)) as executor:
                    tasks = [
                        loop.run_in_executor(
                            executor,
                            self._calculate_score,
                            doc,
                            keywords
                        )

                        for doc in all_docs
                    ]

                    scored_results_manual = await asyncio.gather(*tasks, return_exceptions=True)

                scored_docs_manual = []
                for result in scored_results_manual:
                    if isinstance(result, Exception):
                        print(f"Error during manual scoring task: {result}")
                    elif result is not None:
                        scored_docs_manual.append(result)

                scored_docs_manual.sort(key=lambda x: x['score'], reverse=True)
        except Exception as e:
            print(f"Error during manual scoring process: {e}")

        return scored_docs_manual[:top_k]

    # async def find_documents_by_bm25(self, query: str, top_k: int = 20, with_score: bool = False):
    #     scores = await self.bm25_retriever.get_top_k(query=query, k=top_k)
    #     if not with_score:
    #         scores = [obj[0] for obj in scores if isinstance(obj[0], Document)]
    #     return scores

    def format_results(
        self,
        docs,
        scores
    ):
        def safe_get(obj, key):
            try:
                return getattr(obj, key)
            except AttributeError:
                try:
                    return obj.get(key)
                except (AttributeError, TypeError):
                    return None

        results = []
        for doc, score in zip(docs, scores):
            doc_dict = {
                "id": safe_get(doc, "id_"),
                "text": safe_get(doc, "text"),
                "score": score,
            }
            results.append(doc_dict)
        return results

    def retrieve_documents(
        self,
        ids
    ):
        """Retrieves documents from document store"""
        try:
            return self.mongodb_doc_store.get(ids)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error retrieving documents: {str(e)}"
            )
