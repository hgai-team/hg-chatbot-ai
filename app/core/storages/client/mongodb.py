import logging
logger = logging.getLogger(__name__)

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection
from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorDatabase,
    AsyncIOMotorCollection,
)
from core.config import get_core_settings

class MongoClientManager:

    _client: MongoClient | None = None

    @classmethod
    def init_client(cls, uri: str | None = None):
        if cls._client is None:
            uri = uri or get_core_settings().MONGODB_CONNECTION_STRING
            cls._client = MongoClient(uri)
        return cls._client

    @classmethod
    def get_database(cls, db_name: str | None = None) -> Database:
        client = cls.init_client()
        db_name = db_name or get_core_settings().MONGODB_BASE_DATABASE_NAME
        return client[db_name]

    @classmethod
    def get_collection(
        cls,
        db_name: str | None = None,
        collection_name: str | None = None
    ) -> Collection:
        db = cls.get_database(db_name)
        col_name = collection_name or get_core_settings().MONGODB_BASE_DOC_COLLECTION_NAME
        return db[col_name]
    
    _async_client: AsyncIOMotorClient | None = None

    @classmethod
    def init_async_client(cls, uri: str | None = None) -> AsyncIOMotorClient:
        if cls._async_client is None:
            uri = uri or get_core_settings().MONGODB_CONNECTION_STRING
            cls._async_client = AsyncIOMotorClient(uri)
        return cls._async_client

    @classmethod
    def get_async_database(
        cls,
        db_name: str | None = None
    ) -> AsyncIOMotorDatabase:
        client = cls.init_async_client()
        db_name = db_name or get_core_settings().MONGODB_BASE_DATABASE_NAME
        return client[db_name]

    @classmethod
    def get_async_collection(
        cls,
        db_name: str | None = None,
        collection_name: str | None = None
    ) -> AsyncIOMotorCollection:
        db = cls.get_async_database(db_name)
        col_name = collection_name or get_core_settings().MONGODB_BASE_CHAT_HISTORY_COLLECTION_NAME
        return db[col_name]
