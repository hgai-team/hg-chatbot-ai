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

    async def _restore_relations(
        self,
        all_docs: List[Document]
    ) -> List[TextNode]:
        node_map: Dict[str, TextNode] = {}
        for doc in all_docs:
            node = TextNode(
                text=doc.text,
                id_=doc.id_,
                metadata=doc.metadata,
            )
            node_map[node.id_] = node

        for node in node_map.values():
            raw_rels = node.metadata.get("relationships", {})
            for rel_name, rel_val in raw_rels.items():
                rel_enum = NodeRelationship[rel_name.upper()]
                if isinstance(rel_val, list):
                    node.relationships[rel_enum] = [
                        RelatedNodeInfo(**info) for info in rel_val
                    ]
                else:
                    node.relationships[rel_enum] = RelatedNodeInfo(**rel_val)

        return list(node_map.values())

    async def _get_parents_and_merge(
        self,
        retrieved_docs: List[Document],
        all_docs: List[Document]
    ) -> list[dict]:
        try:
            retrieved_nodes = await self._restore_relations(retrieved_docs)
            all_nodes = await self._restore_relations(all_docs)
            class InMemoryDocstore:
                def __init__(self, nodes: List[TextNode]):
                    self._map = {n.id_: n for n in nodes}

                def get_document(self, doc_id: str) -> TextNode:
                    return self._map.get(doc_id)

                def get_documents(self, doc_ids: List[str]) -> List[TextNode]:
                    return [self._map[i] for i in doc_ids if i in self._map]

            docstore = InMemoryDocstore(all_nodes)
            storage_context = SimpleNamespace(docstore=docstore)

            merger = AutoMergingRetriever(
                None,
                storage_context=storage_context,
                verbose=False
            )

            scored = [NodeWithScore(node=n, score=1.0) for n in retrieved_nodes]

            merged, changed = merger._get_parents_and_merge(scored)
            while changed:
                merged, changed = merger._get_parents_and_merge(merged)

            seen_ids = set()
            docs = []
            for nws in merged:
                doc: TextNode = nws.node
                if doc.id_ not in seen_ids:
                    seen_ids.add(doc.id_)
                    docs.append({
                        'id': doc.id_,
                        'text': doc.get_content(),
                        'metadata': doc.metadata
                    })

            return docs

        except Exception as e:
            logger.error(f"Error during _get_parents_and_merge: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Error during _get_parents_and_merge")

    async def _init_base_chat(
        self,
        query_text: str,
        user_id: str,
        session_id: str,
    ):
        chat_id = str(uuid4())
        session_title = "New Chat"

        chat_to_store = BaseChat(
            message=query_text,
            chat_id=chat_id
        )

        try:
            session_title = await self.memory_store.add_chat(
                user_id=user_id,
                session_id=session_id,
                chat=chat_to_store,
                llm=self.google_llm,
                bot_name=self.bot_name
            )
        except Exception as e:
            logger.error(f"ChaChaCha - Failed to store chat history in _init_base_chat for session '{session_id}': {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Error during _init_base_chat")

        return chat_id, session_title

    async def _update_chat(
        self,
        chat_id: str,
        response: str,
        retrieved_context: ContextRetrieved,
        start_time: float,
        status: int,
    ):
        await self.memory_store.update_chat(
            chat_id=chat_id,
            response=response,
            context={
                "source_document_ids": [id_ for id_, _ in retrieved_context.source_documents.items()]
            },
            metadata={
                'time_taken': timeit.default_timer() - start_time
            },
            status=status
        )

    async def _get_response(
        self,
        inal_messages,
        user_id: str,
        session_id: str,
        agent_name: str,
    ) -> Any:
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

    async def process_chat_request(
        self,
        query_text: str,
        user_id: str,
        session_id: str,
    ) -> str:
        start_time = timeit.default_timer()

        chat_id, session_title = await self._init_base_chat(
            query_text=query_text,
            user_id=user_id,
            session_id=session_id
        )
        # analyze query
        try:
            processed_info = await self.query_processor.analyze_query(
                query_text=query_text,
                user_id=user_id,
                session_id=session_id
            )
        except Exception as e:
            logger.error(f"ChaChaCha - Error during query analysis for session '{session_id}': {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Error during query analysis")

        # retrieve context
        try:
            retrieved_context = await self.context_retriever.retrieve_context(
                processed_query_info=processed_info,
                user_id=user_id,
                session_id=session_id
            )
        except Exception as e:
            logger.error(f"ChaChaCha - Error during context retrieval for session '{session_id}': {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Error during context retrieval")

        # merge context
        ids = list(retrieved_context.source_documents.keys())
        retrieved_docs = await self.file_processor.mongodb_doc_store.get(ids)
        all_docs = await self.file_processor.mongodb_doc_store.get_all()
        docs = await self._get_parents_and_merge(retrieved_docs, all_docs)

        reranked_res = await MSMarcoReranker.rerank(query_text, docs)
        reranked_docs = [res[0] for res in reranked_res]

        documents_as_markdown = []
        for i, doc in enumerate(reranked_docs, 1):
            doc_str = f"### Tài liệu {i}\n\n{doc['text']}"
            documents_as_markdown.append(doc_str)

        retrieved_context.context_string = "\n\n---\n\n".join(documents_as_markdown)

        # init prompt
        inal_messages = PPT.format_chat_prompt(
            processed_info=processed_info,
            retrieved_context=retrieved_context
        )

        # check has stopped
        ses_his = await self.memory_store.get_session_history(session_id=session_id)
        if ses_his.history[-1]['status'] == ChatStatus.STOPPED.value:
            await self.memory_store.add_metadata(
                chat_id=chat_id,
                metadata={
                    'time_taken': timeit.default_timer() - start_time
                }
            )
        else:
            # if sill pending
            try:
                response_text = await self._get_response(
                    inal_messages=inal_messages,
                    session_id=session_id,
                    user_id=user_id,
                    agent_name=self.bot_name
                )

            except Exception as e:
                await self._update_chat(
                    chat_id=chat_id,
                    response=str(e),
                    retrieved_context=retrieved_context,
                    start_time=start_time,
                    status=ChatStatus.ERROR.value
                )

                logger.error(f"ChaChaCha - Error during response for session '{session_id}': {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Error during response")

            try:
                await self._update_chat(
                    chat_id=chat_id,
                    response=response_text,
                    retrieved_context=retrieved_context,
                    start_time=start_time,
                    status=ChatStatus.FINISHED.value
                )
            except Exception as e:
                logger.error(f"ChaChaCha - Error during update_chat for session '{session_id}': {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Error during update_chat")

            return response_text

    async def process_chat_stream_request(
        self,
        query_text: str,
        user_id: str,
        session_id: str,
    ):
        start_time = timeit.default_timer()

        chat_id, session_title = await self._init_base_chat(
                query_text=query_text,
                user_id=user_id,
                session_id=session_id
            )

        try:
            if session_title:
                yield {'_type': 'session_title', 'text': session_title}
            yield {'_type': 'chat_id', 'text': chat_id}

            yield {'_type': 'header_thinking', 'text': 'Đang phân tích yêu cầu...\n'}

            try:
                processed_info = await self.query_processor.analyze_query(
                    query_text=query_text,
                    user_id=user_id,
                    session_id=session_id
                )
            except Exception as e:
                logger.error(f"ChaChaCha - Error during query analysis for session '{session_id}': {e}", exc_info=True)
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
                logger.error(f"ChaChaCha - Error during context retrieval for session '{session_id}': {e}", exc_info=True)
                raise HTTPException(status_code=500, detail="Error during context retrieval")

            ids = list(retrieved_context.source_documents.keys())
            retrieved_docs = await self.file_processor.mongodb_doc_store.get(ids)
            all_docs = await self.file_processor.mongodb_doc_store.get_all()
            docs = await self._get_parents_and_merge(retrieved_docs, all_docs)

            reranked_res = await MSMarcoReranker.rerank(query_text, docs)
            reranked_docs = [res[0] for res in reranked_res]

            documents_as_markdown = []
            for i, doc in enumerate(reranked_docs, 1):
                doc_str = f"### Tài liệu {i}\n\n{doc['text']}"
                documents_as_markdown.append(doc_str)

            retrieved_context.context_string = "\n\n---\n\n".join(documents_as_markdown)

            yield {'_type': 'thinking', 'text': 'Hoàn thành tìm kiếm thông tin!\n'}

            inal_messages = PPT.format_chat_prompt(
                processed_info=processed_info,
                retrieved_context=retrieved_context
            )

            ses_his = await self.memory_store.get_session_history(session_id=session_id)
            if ses_his.history[-1]['status'] == ChatStatus.STOPPED.value:
                await self.memory_store.add_metadata(
                    chat_id=chat_id,
                    metadata={
                        'time_taken': timeit.default_timer() - start_time
                    }
                )
            else:
                yield {'_type': 'header_thinking', 'text': 'Đang phản hồi yêu cầu...\n'}

                his_sessions = await self.memory_store.get_user_sessions(
                    user_id=user_id,
                )
                yield {'_type': 'sys_resp_cnt', 'text': str(sum([len(chat) for chat in his_sessions]))}

                try:
                    response_text = await self._get_response(
                        inal_messages=inal_messages,
                        session_id=session_id,
                        user_id=user_id,
                        agent_name=self.bot_name
                    )

                except Exception as e:
                    await self._update_chat(
                        chat_id=chat_id,
                        response=str(e),
                        retrieved_context=retrieved_context,
                        start_time=start_time,
                        status=ChatStatus.ERROR.value
                    )

                    logger.error(f"ChaChaCha - Error during response for session '{session_id}': {e}", exc_info=True)
                    raise HTTPException(status_code=500, detail="Error during response")

                yield {'_type': 'response', 'text': response_text}

                try:
                    await self._update_chat(
                        chat_id=chat_id,
                        response=response_text,
                        retrieved_context=retrieved_context,
                        start_time=start_time,
                        status=ChatStatus.FINISHED.value
                    )
                except Exception as e:
                    logger.error(f"ChaChaCha - Error during update_chat for session '{session_id}': {e}", exc_info=True)
                    raise HTTPException(status_code=500, detail="Error during update_chat")

        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            logger.error(f"ChaChaCha - An internal error occurred during chat processing: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"ChaChaCha - An internal error occurred during chat processing. {e}")
