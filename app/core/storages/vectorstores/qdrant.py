from typing import Any, List, Optional, cast

from .base import LlamaIndexVectorStore

class QdrantVectorStore(LlamaIndexVectorStore):
    _li_class = None

    def _get_li_class(self):
        try:
            from llama_index.vector_stores.qdrant import (
                QdrantVectorStore as LIQdrantVectorStore,
            )
        except ImportError:
            raise ImportError(
                "Please install missing package: "
                "'pip install llama-index-vector-stores-qdrant'"
            )

        return LIQdrantVectorStore

    def __init__(
        self,
        collection_name,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        client_kwargs: Optional[dict] = None,
        **kwargs: Any,
    ):
        self._collection_name = collection_name
        self._url = url
        self._api_key = api_key
        self._client_kwargs = client_kwargs
        self._kwargs = kwargs

        super().__init__(
            collection_name=collection_name,
            url=url,
            api_key=api_key,
            client_kwargs=client_kwargs,
            **kwargs,
        )
        from llama_index.vector_stores.qdrant import (
            QdrantVectorStore as LIQdrantVectorStore,
        )

        self._client = cast(LIQdrantVectorStore, self._client)

    async def delete(self, ids: List[str], **kwargs):
        """Delete vector embeddings from vector stores

        Args:
            ids: List of ids of the embeddings to be deleted
            kwargs: meant for vectorstore-specific parameters
        """
        from qdrant_client import models

        self._client.client.delete(
            collection_name=self._collection_name,
            points_selector=models.PointIdsList(
                points=ids,
            ),
            **kwargs,
        )

    def drop(self):
        """Delete entire collection from vector stores"""
        self._client.client.delete_collection(self._collection_name)

    def count(self) -> int:
        return self._client.client.count(
            collection_name=self._collection_name, exact=True
        ).count

    def get_all_ids(self) -> List[str]:
        """
        Trả về danh sách tất cả point IDs (UUID) trong Qdrant collection.

        Sử dụng count() để biết tổng số điểm, rồi scroll một lần với limit=total
        để lấy hết mà không cần quản lý offset.
        """
        # 1. Lấy tổng số point
        total = self.count()

        # 2. Scroll một lần với limit=total, không lấy payload và vector
        records, _ = self._client.client.scroll(
            collection_name=self._collection_name,
            limit=total,
            with_payload=False,
            with_vectors=False,
        )

        # 3. Trả về list ID dưới dạng chuỗi
        return [str(r.id) for r in records]

    def __persist_flow__(self):
        return {
            "collection_name": self._collection_name,
            "url": self._url,
            "api_key": self._api_key,
            "client_kwargs": self._client_kwargs,
            **self._kwargs,
        }
