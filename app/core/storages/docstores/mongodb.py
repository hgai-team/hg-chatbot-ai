import json
import asyncio
from typing import List, Optional, Union

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
            if doc_ids:
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

    async def user_query(
        self,
        query: str,
        top_k: int = 20,
        doc_ids: Optional[list] = None,
        user_context: Optional[dict] = None,
    ):
        """Search document store using text search query + context filters."""
        try:
            base_filters = [
                {"$text": {"$search": query}}
            ]
            if doc_ids:
                base_filters.append({"id": {"$in": doc_ids}})

            context_or = []
            if user_context:
                projs = user_context.get("projects", [])
                nets = user_context.get("networks", [])
                deps = user_context.get("departments", [])

                context_or.append({
                    "$and": [
                        {"attributes.projects": {"$in": projs}},
                        {"attributes.networks": {"$size": 0}},
                        {"attributes.departments": {"$size": 0}}
                    ],
                })

                context_or.append({
                    "$and": [
                        {"attributes.projects": {"$in": projs}},
                        {"attributes.networks": {"$in": nets}},
                        {"attributes.departments": {"$size": 0}}
                    ],
                })

                context_or.append({
                    "$and": [
                        {"attributes.projects": {"$in": projs}},
                        {"attributes.networks": {"$in": nets}},
                        {"attributes.departments": {"$in": deps}}
                    ],
                })

                context_or.append({
                    "$and": [
                        {"attributes.projects": {"$size": 0}},
                        {"attributes.networks": {"$in": nets}},
                        {"attributes.departments": {"$in": deps}}
                    ],
                })

                context_or.append({
                    "$and": [
                        {"attributes.projects": {"$size": 0}},
                        {"attributes.networks": {"$in": nets}},
                        {"attributes.departments": {"$size": 0}}
                    ],
                })

                context_or.append({
                    "$and": [
                        {"attributes.projects": {"$size": 0}},
                        {"attributes.networks": {"$size": 0}},
                        {"attributes.departments": {"$in": deps}}
                    ],
                })

            context_or.append({
                "$and": [
                    {"attributes.general": True},
                    {"attributes.projects": {"$size": 0}},
                    {"attributes.networks": {"$size": 0}},
                    {"attributes.departments": {"$size": 0}}
                ]
            })

            if context_or:
                find_filter = {
                    "$and": [
                        {"$and": base_filters},
                        {"$or": context_or}
                    ]
                }
            else:
                find_filter = {"$and": base_filters}

            cursor = (
                self.collection
                    .find(find_filter, {"score": {"$meta": "textScore"}})
                    .sort([("score", {"$meta": "textScore"})])
                    .limit(top_k)
            )

            docs = await cursor.to_list(length=top_k)

        except Exception as e:
            print(f"Error querying MongoDB: {e}")
            docs = []

        return [
            Document(
                id_=doc["id"],
                text=doc.get("text", "<empty>"),
                metadata=doc.get("attributes", {}),
            )
            for doc in docs
        ]

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
