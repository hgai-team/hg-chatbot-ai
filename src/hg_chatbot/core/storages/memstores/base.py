from abc import ABC, abstractmethod
from typing import List, Optional, Union, Dict, Any
from datetime import datetime

class BaseChat:
    def __init__(
        self,
        message: str,
        response: str,
        context: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ):
        self.message = message
        self.response = response
        self.context = context or {}
        self.timestamp = timestamp or datetime.now()

class ChatHistory:
    """Represents a single chat message"""
    def __init__(
        self,
        session_id: str,
        user_id: str,
        history: Optional[list] = [],
        created_at: Optional[datetime] = None,
        last_updated: Optional[datetime] = None
    ):
        self.user_id = user_id
        self.session_id = session_id
        self.history = history
        self.created_at = created_at or datetime.now()
        self.last_updated = last_updated or datetime.now()


class BaseMemoryStore(ABC):
    """A memory store is responsible for storing and managing chat history"""

    @abstractmethod
    def __init__(self, *args, **kwargs):
        ...

    @abstractmethod
    def add_chat(
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
        ...

    @abstractmethod
    def get_user_sessions(
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
    def delete_session(
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
    def delete_user_history(
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
    def count_sessions(self) -> int:
        """Count total number of chat sessions"""
        ...
