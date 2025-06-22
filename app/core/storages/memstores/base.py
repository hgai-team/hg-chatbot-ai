from abc import ABC, abstractmethod
from typing import List, Optional, Union, Dict, Any
from datetime import datetime
from uuid import uuid4

class BaseChat:
    def __init__(
        self,
        message: str,
        response: str,
        chat_id: str,
        context: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
        rating_type: Optional[str] = None,
        rating_text: Optional[str] = None,
        **kwargs
    ):
        self.message = message
        self.response = response
        self.context = context or {}
        self.timestamp = timestamp or datetime.now()
        self.chat_id = chat_id
        self.rating_type = rating_type
        self.rating_text = rating_text

class ChatHistory:
    """Represents a single chat message"""
    def __init__(
        self,
        session_id: str,
        user_id: str = None,
        history: Optional[list] = [],
        created_at: Optional[datetime] = None,
        last_updated: Optional[datetime] = None,
        session_title: Optional[str] = None,
        **kwargs
    ):
        self.user_id = user_id
        self.session_id = session_id
        self.history = history
        self.created_at = created_at or datetime.now()
        self.last_updated = last_updated or datetime.now()
        self.session_title = session_title

class BaseMemoryStore(ABC):
    """A memory store is responsible for storing and managing chat history"""

    @abstractmethod
    async def __init__(self, *args, **kwargs):
        ...

    @abstractmethod
    async def add_chat(
        self,
        message: BaseChat,
        **kwargs,
    ):
        """Add a chat message to the store

        Args:
            message: ChatMessage object containing the chat interaction
        """
        ...

    @abstractmethod
    async def get_session_history(
        self,
        session_id: str,
        **kwargs,
    ) -> ChatHistory:
        """Get chat history for a user in a specific session

        Args:
            user_id: ID of the user
            session_id: ID of the chat session
        """
        ...

    @abstractmethod
    async def get_user_sessions(
        self,
        user_id: str,
        **kwargs,
    ) -> List[str]:
        """Get all session IDs for a user

        Args:
            user_id: ID of the user
        """
        ...

    @abstractmethod
    async def delete_session(
        self,
        session_id: str,
        **kwargs,
    ):
        """Delete a chat session and all its messages

        Args:
            session_id: ID of the chat session to delete
        """
        ...

    @abstractmethod
    async def delete_user_history(
        self,
        user_id: str,
        **kwargs,
    ):
        """Delete all chat history for a user

        Args:
            user_id: ID of the user
        """
        ...

    @abstractmethod
    async def count_sessions(self) -> int:
        """Count total number of chat sessions"""
        ...
