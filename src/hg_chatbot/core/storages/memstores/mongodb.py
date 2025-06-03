from typing import List, Optional, Dict, Any
from datetime import datetime
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from .base import BaseMemoryStore, BaseChat, ChatHistory
from core.config import get_core_settings

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
        self.client = MongoClient(connection_string if connection_string else get_core_settings().MONGODB_CONNECTION_STRING)
        self.db: Database = self.client[database_name if database_name else get_core_settings().MONGODB_BASE_DATABASE_NAME]
        self.collection: Collection = self.db[collection_name if collection_name else get_core_settings().MONGODB_BASE_CHAT_HISTORY_COLLECTION_NAME]

        self.collection.create_index([("user_id", 1)])
        self.collection.create_index([("session_id", 1)])
        
    def add_rating(
        self,
        chat_id: str,
        rating_type: str
    ):
        self.collection.update_one(
            {"history.chat_id": chat_id}, 
            {
                "$set": {"history.$.rating": rating_type} 
            }
        )

    def add_chat(
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

        chat_history = self.collection.find_one({"session_id": session_id})

        current_time = datetime.now()

        if chat_history:
            self.collection.update_one(
                {"session_id": session_id},
                {
                    "$push": {
                        "history": {
                            "message": chat.message,
                            "response": chat.response,
                            "context": chat.context,
                            "timestamp": chat.timestamp,
                            "chat_id": chat.chat_id,
                            "rating": chat.rating
                        }
                    },
                    "$set": {"last_updated": current_time}
                }
            )
        else:
            from services.tools.prompt import prepare_chat_messages

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
                        "rating": chat.rating
                    }
                ],
                "created_at": current_time,
                "last_updated": current_time,
                "session_title": kwargs.get('llm').run(
                    messages=prepare_chat_messages(
                        system_prompt="""
                            Chat Thread Title Expert: Bạn là chuyên gia chuyên tạo tiêu đề cho luồng chat. Nhiệm vụ của bạn là dựa vào câu hỏi gốc để sinh ra một tiêu đề ngắn gọn, súc tích, phản ánh đúng chủ đề của luồng.
                            1. Nhận tham số:
                                - question: nội dung câu hỏi gốc.
                            2. Phân tích và tổng hợp thông tin để tạo tiêu đề ngắn gọn, dễ hiểu và hấp dẫn, khái quát nội dung luồng chat.
                            3. Đầu ra phải là một đoạn text ngắn gọn dài từ 15 đến 30 ký tự.
                        """,
                        prompt=f"""
                            #Input:
                                question: 
                                {chat.message}
                            #Output:
                        """
                    )
                )
            }
            self.collection.insert_one(new_chat_history)

    def get_session_history(
        self,
        user_id: str,
        session_id: str,
        **kwargs,
    ) -> ChatHistory:
        """Get chat history for a user in a specific session

        Args:
            user_id: ID of the user
            session_id: ID of the chat session
        """
        result = self.collection.find_one({"user_id": user_id, "session_id": session_id})
        if result:
            return ChatHistory(
                session_id=result["session_id"],
                user_id=result["user_id"],
                history=result["history"],
                created_at=result.get("created_at"),
                last_updated=result.get("last_updated"),
                session_title=result.get("session_title"),
            )
        return ChatHistory(session_id=session_id, user_id=user_id)

    def get_user_sessions(
        self,
        user_id: str,
        **kwargs,
    ) -> List[str]:
        """Get all chat history for a user

        Args:
            user_id: ID of the user
        """
        results = self.collection.find({"user_id": user_id}, {"history": 1})
        return [doc["history"] for doc in results]

    def delete_session(
        self,
        session_id: str,
        **kwargs,
    ):
        """Delete a chat session and all its messages

        Args:
            session_id: ID of the chat session to delete
        """
        self.collection.delete_one({"session_id": session_id})

    def delete_user_history(
        self,
        user_id: str,
        **kwargs,
    ):
        """Delete all chat history for a user

        Args:
            user_id: ID of the user
        """
        self.collection.delete_many({"user_id": user_id})

    def count_sessions(self) -> int:
        """Count total number of chat sessions"""
        return self.collection.count_documents({})

    def drop(self):
        """Drop the document store collection"""
        try:
            self.collection.drop()
            self.collection.create_index([("user_id", 1)])
            self.collection.create_index([("session_id", 1)])
        except Exception as e:
            print(f"Error dropping MongoDB collection: {e}")
