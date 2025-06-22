# Cần import thêm AsyncGenerator
from abc import ABC, abstractmethod
from typing import AsyncGenerator

class BaseBotService(ABC):
    @abstractmethod
    async def process_chat_request(
        self,
        query_text: str,
        user_id: str,
        session_id: str,
    ) -> str:
        ...

    @abstractmethod
    async def process_chat_stream_request(
        self,
        query_text: str,
        user_id: str,
        session_id: str,
    ) -> AsyncGenerator[str, None]:
        yield
