# Cần import thêm AsyncGenerator
from abc import ABC, abstractmethod
from typing import AsyncGenerator

class BaseManager(ABC):
    @abstractmethod
    async def chat(
        self,
        *args,
        **kwargs
    ) -> str:
        ...

    @abstractmethod
    async def chat_stream(
        self,
        *args,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        ...

    @abstractmethod
    async def get_session(
        self,
        *args,
        **kwargs
    ) -> str:
        ...

    @abstractmethod
    async def add_rating(
        self,
        *args,
        **kwargs
    ) -> str:
        ...

    @abstractmethod
    async def get_logs(
        self,
        *args,
        **kwargs
    ) -> str:
        ...


