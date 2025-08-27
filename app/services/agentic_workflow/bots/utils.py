import logging
logger = logging.getLogger(__name__)

import timeit

from fastapi import HTTPException
from types import SimpleNamespace
from typing import List, Dict, Any

from uuid import uuid4

from llama_index.core.schema import TextNode, RelatedNodeInfo, NodeRelationship
from llama_index.core.retrievers import AutoMergingRetriever
from llama_index.core.schema import NodeWithScore

from services import MongoDBMemoryStore
from services.agentic_workflow.schema import ContextRetrieved

from core.base import Document
from core.storages import BaseChat, ChatStatus

async def restore_relations(
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

async def get_parents_and_merge(
    retrieved_docs: List[Document],
    all_docs: List[Document]
) -> list[dict]:
    try:
        retrieved_nodes = await restore_relations(retrieved_docs)
        all_nodes = await restore_relations(all_docs)
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
    
async def init_base_chat(
    query_text: str,
    user_id: str,
    session_id: str,
    memory_store: MongoDBMemoryStore,
    bot_name: str
):
    chat_id = str(uuid4())

    chat_to_store = BaseChat(
        message=query_text,
        chat_id=chat_id
    )

    try:
        is_new_session = await memory_store.add_chat(
            user_id=user_id,
            session_id=session_id,
            chat=chat_to_store
        )
    except Exception as e:
        logger.error(f"{bot_name} - Failed to store chat history in init_base_chat for session '{session_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error during init_base_chat")

    return chat_id, is_new_session

async def update_chat(
    chat_id: str,
    response: str,
    start_time: float,
    status: int,
    memory_store: MongoDBMemoryStore,
    retrieved_context: ContextRetrieved = None,
):
    await memory_store.update_chat(
        chat_id=chat_id,
        response=response,
        context={
            "source_document_ids": [id_ for id_, _ in retrieved_context.source_documents.items()]
        } if retrieved_context else {},
        metadata={
            'time_taken': timeit.default_timer() - start_time
        },
        status=status
    )