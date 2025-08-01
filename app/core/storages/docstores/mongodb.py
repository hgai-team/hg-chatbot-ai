import json
import asyncio
from typing import List, Optional, Union, Dict, Any

from core.base import Document
from core.config import get_core_settings
from .base import BaseDocumentStore
from core.storages.client import MongoClientManager

class MongoDBDocumentStore(BaseDocumentStore):
    """MongoDB document store which supports full-text search queries"""

    def __init__(
        self,
        connection_string: Optional[str] = None,
        database_name: Optional[str] = None,
        collection_name: Optional[str] = None,
        **kwargs,
    ):
        try:
            from pymongo import MongoClient
            from pymongo.collection import Collection
            from pymongo.database import Database
        except ImportError:
            raise ImportError(
                "Please install pymongo: 'pip install pymongo'"
            )

        self.connection_string = connection_string
        self.database_name = database_name
        self.collection_name = collection_name

        MongoClientManager.init_async_client(
            uri=connection_string if connection_string else get_core_settings().MONGODB_CONNECTION_STRING
        )

        self.db: Database = MongoClientManager.get_async_database(
            db_name=database_name if database_name else get_core_settings().MONGODB_BASE_DATABASE_NAME
        )

        self.collection: Collection = MongoClientManager.get_async_collection(
            db_name=database_name if database_name else get_core_settings().MONGODB_BASE_DATABASE_NAME,
            collection_name=collection_name if collection_name else get_core_settings().MONGODB_BASE_DOC_COLLECTION_NAME
        )

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.init_indexes())
        except RuntimeError:
            asyncio.run(self.init_indexes())

    async def drop_index(self) -> None:
        async for idx in self.collection.list_indexes():
            name = idx["name"]
            if name != "_id_":
                await self.collection.drop_index(name)

    async def init_indexes(self) -> None:
        import pymongo

        existing = [idx["name"] async for idx in self.collection.list_indexes()]

        if "text_index" not in existing:
            await self.collection.create_index(
                [("text", pymongo.TEXT)],
                name="text_index"
            )

        if "doc_id_index" not in existing:
            await self.collection.create_index(
                [("id", pymongo.ASCENDING)],
                name="doc_id_index",
                unique=True
            )

        if "attributes_filename_idx" not in existing:
            await self.collection.create_index(
                [("attributes.file_name", pymongo.ASCENDING)],
                name="attributes_filename_idx"
            )

    async def add(
        self,
        docs: Union[Document, List[Document]],
        **kwargs,
    ):
        """Load documents into MongoDB storage."""
        from pymongo import ReplaceOne

        if not isinstance(docs, list):
            docs = [docs]

        doc_ids = [doc.doc_id for doc in docs]

        documents_to_insert = [
            ReplaceOne(
                {"id": doc_id},
                {
                    "id": doc_id,
                    "text": doc.text,
                    "attributes": doc.metadata,
                },
                upsert=True,
            )
            for doc_id, doc in zip(doc_ids, docs)
        ]

        if documents_to_insert:
            await self.collection.bulk_write(documents_to_insert, ordered=False)

    async def query(
        self, query: str, top_k: int = 20, doc_ids: Optional[list] = None, with_scores: bool = True
    ):
        """Search document store using text search query"""
        try:
            find_filter = {"$text": {"$search": query}}
            if doc_ids is not None:
                find_filter = {
                    "$and": [
                        {"id": {"$in": doc_ids}},
                        find_filter
                    ]
                }

            projection = {"score": {"$meta": "textScore"}}

            cursor = self.collection.find(
                find_filter,
                projection
            ).sort([("score", {"$meta": "textScore"})]).limit(top_k)

            docs = await cursor.to_list(length=top_k)
        except Exception as e:
            print(f"Error querying MongoDB: {e}")
            docs = []

        if with_scores:
            results, scores = [], []
            for doc in docs:
                results.append({
                    "id": doc["id"],
                    "text": doc["text"],
                    "attributes": doc["attributes"]
                })
                scores.append(doc["score"])
            return results, scores

        return [
            Document(
                id_=doc["id"],
                text=doc["text"] if doc["text"] else "<empty>",
                metadata=doc["attributes"],
            )
            for doc in docs
        ]

    async def find_docs_id_for_user(self, user_roles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Tìm kiếm id tài liệu dựa trên danh sách các vai trò (roles) của người dùng.
        Hàm này bảo toàn mối liên kết giữa dự án/network và bộ quyền cụ thể của nó.
        """

        or_conditions = []
        has_general_permission = False

        # Định nghĩa các loại quy tắc để dễ dàng lặp qua
        project_rules_keys = {
            "quy_định_chung_dự_án", "file_xlcv_chung_dự_án",
            "quy_định_riêng_dự_án_phòng_ban", "file_xlcv_riêng_dự_án_phòng_ban"
        }
        network_rules_keys = {
            "quy_định_riêng_dự_án_net", "file_xlcv_riêng_dự_án_net", "quy_định_network"
        }

        for role in user_roles:
            metadata = role.get("metadata_", {})
            if not metadata:
                continue

            # Xử lý quyền chung (chỉ cần kiểm tra một lần)
            if metadata.get("quy_định_chung"):
                has_general_permission = True

            # Xử lý các quy tắc gắn với dự án
            project_name = role.get("project")
            if project_name:
                for key in project_rules_keys:
                    if metadata.get(key):
                        or_conditions.extend([
                            {
                                "attributes.tên dự án": project_name,
                                f"attributes.{key}": True
                            },
                            {
                                "attributes.tên dự án": project_name,
                                "attributes.file_name": "Hệ thống nhân sự Vận hành.xlsx"
                            }
                        ])

            # Xử lý các quy tắc gắn với network
            role_networks = [net for net in [role.get("network_in_qlk"), role.get("network_in_ys")] if net]
            if role_networks:
                for key in network_rules_keys:
                    if metadata.get(key):
                        condition = {
                            f"attributes.{key}": True,
                            "attributes.tên network": {"$in": role_networks}
                        }
                        or_conditions.append(condition)

        # Thêm điều kiện chung vào cuối cùng nếu có
        if has_general_permission:
            # Để tránh trùng lặp, có thể kiểm tra nếu đã tồn tại
            general_condition = {"attributes.quy_định_chung": True}
            if general_condition not in or_conditions:
                or_conditions.append(general_condition)

        if not or_conditions:
            return []

        final_filter = {"$or": or_conditions}

        cursor = self.collection.find(final_filter)
        seen_ids = set()

        for doc in [doc async for doc in cursor]:
            if doc['id'] not in seen_ids:
                seen_ids.add(doc["id"])

        return list(seen_ids)

    async def get(self, ids: Union[List[str], str]) -> List[Document]:
        """Get document by id"""
        if not isinstance(ids, list):
            ids = [ids]

        if len(ids) == 0:
            return []

        try:
            cursor = self.collection.find({"id": {"$in": ids}})
            docs = await cursor.to_list(length=len(ids))
        except Exception as e:
            print(f"Error retrieving documents from MongoDB: {e}")
            docs = []

        return [
            Document(
                id_=doc["id"],
                text=doc["text"] if doc["text"] else "<empty>",
                metadata=doc["attributes"],
            )
            for doc in docs
        ]

    async def get_all(self) -> List[Document]:
        """Get all documents"""
        try:
            cursor = self.collection.find({})
            docs = await cursor.to_list(length=None)
        except Exception as e:
            print(f"Error retrieving all documents from MongoDB: {e}")
            docs = []

        return [
            Document(
                id_=doc["id"],
                text=doc["text"] if doc["text"] else "<empty>",
                metadata=doc["attributes"],
            )
            for doc in docs
        ]

    async def count(self) -> int:
        """Count number of documents"""
        try:
            return await self.collection.count_documents({})
        except Exception as e:
            print(f"Error counting documents in MongoDB: {e}")
            return 0

    async def delete(self, ids: Union[List[str], str]):
        """Delete document by id"""
        if not isinstance(ids, list):
            ids = [ids]

        if len(ids) == 0:
            return

        try:
            await self.collection.delete_many({"id": {"$in": ids}})
        except Exception as e:
            print(f"Error deleting documents from MongoDB: {e}")

    async def drop(self):
        """Drop the document store collection"""
        try:
            await self.collection.drop()
            await self.init_indexes()
        except Exception as e:
            print(f"Error dropping MongoDB collection: {e}")

    def __persist_flow__(self):
        """Return configuration for persistence"""
        return {
            "connection_string": self.connection_string,
            "database_name": self.database_name,
            "collection_name": self.collection_name,
        }
