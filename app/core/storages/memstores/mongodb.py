import logging
logger = logging.getLogger(__name__)

import asyncio

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pymongo.collection import Collection
from pymongo.database import Database
from llama_index.core.llms import ChatResponse

from .base import BaseMemoryStore, BaseChat, ChatHistory, ChatStatus
from core.config import get_core_settings
from core.storages.client import MongoClientManager

class MongoDBMemoryStore(BaseMemoryStore):
    """MongoDB implementation of memory store for chat history"""

    def __init__(
        self,
        connection_string: Optional[str] = None,
        database_name: Optional[str] = None,
        collection_name: Optional[str] = None,
        **kwargs,
    ):
        """Initialize MongoDB memory store

        Args:
            connection_string: MongoDB connection string
            database_name: Name of the database to use
            collection_name: Name of the collection to use
        """
        MongoClientManager.init_async_client(
            uri=connection_string if connection_string else get_core_settings().MONGODB_CONNECTION_STRING
        )

        self.db: Database = MongoClientManager.get_async_database(
            db_name=database_name if database_name else get_core_settings().MONGODB_BASE_DATABASE_NAME
        )

        self.collection: Collection = MongoClientManager.get_async_collection(
            db_name=database_name if database_name else get_core_settings().MONGODB_BASE_DATABASE_NAME,
            collection_name=collection_name if collection_name else get_core_settings().MONGODB_BASE_CHAT_HISTORY_COLLECTION_NAME
        )

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.init_indexes())
        except RuntimeError:
            asyncio.run(self.init_indexes())

    async def init_indexes(self):
        await self.collection.create_index("user_id")
        await self.collection.create_index("session_id")

    async def add_metadata(
        self,
        chat_id: str,
        metadata: dict
    ):
        update_fields = {
            f"history.$.metadata.{k}": v
            for k, v in metadata.items()
        }

        await self.collection.update_one(
            {"history.chat_id": chat_id},
            {"$set": update_fields}
        )

    async def add_rating(
        self,
        chat_id: str,
        rating_type: str,
        rating_text: str
    ):
        await self.collection.update_one(
            {"history.chat_id": chat_id},
            {
                "$set": {
                    "history.$.rating_type": rating_type,
                    "history.$.rating_text": rating_text
                },
            }
        )

    async def add_chat(
        self,
        user_id: str,
        session_id: str,
        chat: BaseChat,
        **kwargs,
    ):
        """Add a chat message to the MongoDB store

        Args:
            user_id: ID of the user
            session_id: ID of the chat session
            chat: BaseChat object containing the message and response
        """

        chat_history = await self.collection.find_one({"session_id": session_id})

        current_time = datetime.now()

        if chat_history:
            await self.collection.update_one(
                {"session_id": session_id},
                {
                    "$push": {
                        "history": {
                            "message": chat.message,
                            "response": chat.response,
                            "context": chat.context,
                            "timestamp": chat.timestamp,
                            "chat_id": chat.chat_id,
                            "rating_type": chat.rating_type,
                            "rating_text": chat.rating_text,
                            "metadata": chat.metadata,
                            "status": chat.status.value
                        }
                    },
                    "$set": {"last_updated": current_time}
                }
            )
            return None
        else:
            from services.agentic_workflow.tools.prompt_processor import PromptProcessorTool as PPT

            response: ChatResponse = await kwargs.get('llm').arun(
                messages=PPT.prepare_chat_messages(
                    system_prompt=(
                        "Chat Thread Title Expert: Bạn là chuyên gia chuyên tạo tiêu đề cho luồng chat. "
                        "Nhiệm vụ của bạn là dựa vào câu hỏi gốc để sinh ra một tiêu đề ngắn gọn, súc tích, phản ánh đúng chủ đề của luồng.\n"
                        "1. Nhận tham số:\n"
                        "    - question: nội dung câu hỏi gốc.\n"
                        "2. Phân tích và tổng hợp thông tin để tạo tiêu đề ngắn gọn, dễ hiểu và hấp dẫn, khái quát nội dung luồng chat.\n"
                        "3. Đầu ra phải là một đoạn text ngắn gọn dài từ 15 đến 30 ký tự."
                    ),
                    prompt=f"""
                        #Input:
                            question:
                            {chat.message}
                        #Output:
                    """
                )
            )

            new_chat_history = {
                "session_id": session_id,
                "user_id": user_id,
                "history": [
                    {
                        "message": chat.message,
                        "response": chat.response,
                        "context": chat.context,
                        "timestamp": chat.timestamp,
                        "chat_id": chat.chat_id,
                        "rating_type": chat.rating_type,
                        "rating_text": chat.rating_text,
                        "metadata": chat.metadata,
                        "status": chat.status.value
                    }
                ],
                "created_at": current_time,
                "last_updated": current_time,
                "session_title": response.message.content
            }
            await self.collection.insert_one(new_chat_history)
            return new_chat_history["session_title"]

    async def update_chat(
        self,
        chat_id: str,
        response: str,
        context: dict,
        metadata: dict,
        status: int
    ):
        update_fields = {
            f"history.$.metadata.{k}": v
            for k, v in metadata.items()
        }

        await self.collection.update_one(
            {"history.chat_id": chat_id},
            {"$set": {
                    **update_fields,
                    "history.$.response": response,
                    "history.$.context": context,
                    "history.$.status": status,
                }
            }
        )

    async def update_chat_status(
        self,
        chat_id: str,
        status: int = ChatStatus.STOPPED.value
    ):
        await self.collection.update_one(
            {"history.chat_id": chat_id},
            {"$set": {
                    "history.$.status": status,
                }
            }
        )

    async def get_session_history(
        self,
        session_id: str,
        **kwargs,
    ) -> ChatHistory:
        """Get chat history for a specific session

        Args:
            session_id: ID of the chat session
        """
        result = await self.collection.find_one({"session_id": session_id})
        if result:
            return ChatHistory(
                session_id=result["session_id"],
                user_id=result["user_id"],
                history=result["history"],
                created_at=result.get("created_at"),
                last_updated=result.get("last_updated"),
                session_title=result.get("session_title"),
            )
        return ChatHistory(session_id=session_id)

    async def get_user_sessions(
        self,
        user_id: str,
        **kwargs,
    ) -> List[str]:
        """Get all chat history for a user

        Args:
            user_id: ID of the user
        """
        results = self.collection.find({"user_id": user_id}, {"history": 1})
        return [doc["history"] async for doc in results]

    async def delete_session(
        self,
        session_id: str,
        **kwargs,
    ):
        """Delete a chat session and all its messages

        Args:
            session_id: ID of the chat session to delete
        """
        await self.collection.delete_one({"session_id": session_id})

    async def delete_user_history(
        self,
        user_id: str,
        **kwargs,
    ):
        """Delete all chat history for a user

        Args:
            user_id: ID of the user
        """
        await self.collection.delete_many({"user_id": user_id})

    async def count_sessions(self) -> int:
        """Count total number of chat sessions"""
        return await self.collection.count_documents({})

    async def drop(self):
        """Drop the document store collection"""
        try:
            await self.collection.drop()
            await self.init_indexes()
        except Exception as e:
            print(f"Error dropping MongoDB collection: {e}")

    async def get_logs(
        self,
        rating_type: Optional[list[str]] = None,
        st: Optional[str] = None,
        et: Optional[str] = None,
        **kwargs,
    ) -> List[ChatHistory]:
        """
            Get session histories with optional filters:
            - rating_type: only include chats whose rating_type == this value
            - st, et: only include chats whose timestamp is between these dates (format DD/MM/YYYY)
            - so: sort order for timestamps, 1=asc, -1=desc
            Returns a list of ChatHistory, each with its `history` list filtered & sorted.
        """
        query: Dict[str, Any] = {}
        if rating_type:
            query["history.rating_type"] = {"$in": rating_type}
        if st and et:
            start_dt = datetime.strptime(st, "%d/%m/%Y")
            end_dt = datetime.strptime(et, "%d/%m/%Y") + timedelta(days=1)
            query["history.timestamp"] = {"$gte": start_dt, "$lte": end_dt}

        cursor = self.collection.find(query).sort("created_at", -1)
        results: List[ChatHistory] = []

        async for doc in cursor:
            raw_history = doc.get("history", [])

            filtered: List[Dict[str, Any]] = []
            for h in raw_history:
                if rating_type and h.get("rating_type") not in rating_type:
                    continue
                if st and et:
                    ts = h.get("timestamp")
                    if not (start_dt <= ts <= end_dt):
                        continue
                filtered.append(h)

            if filtered:
                results.append(
                    ChatHistory(
                        session_id=doc["session_id"],
                        user_id=doc.get("user_id"),
                        history=filtered,
                        created_at=doc.get("created_at"),
                        last_updated=doc.get("last_updated"),
                        session_title=doc.get("session_title"),
                    )
                )

        return results
