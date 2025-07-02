import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Awaitable, Tuple
import uuid

from core.storages.tracestores.base import SpanCreate, LLMTracer 

logger = logging.getLogger(__name__)

class TracerManager:
    """
    Singleton manager cho việc khởi tạo và sử dụng LLMTracer.

    Pattern này tương tự như quản lý DB Engine, đảm bảo chỉ có một instance
    của tracer được tạo và worker của nó được quản lý tập trung.
    """
    _tracer_instance: Optional[LLMTracer] = None

    @classmethod
    def init_tracer(
        cls,
        *,
        storage_writer: Callable[[List[SpanCreate]], Awaitable[None]],
        **kwargs
    ) -> LLMTracer:
        """
        Khởi tạo instance duy nhất của tracer.

        Hàm này phải được gọi một lần khi ứng dụng khởi động.
        Việc gọi lại sẽ không có tác dụng.

        Args:
            storage_writer: Hàm async chịu trách nhiệm ghi dữ liệu trace.
            **kwargs: Các tham số khác cho constructor của LLMTracer.

        Returns:
            Instance của LLMTracer.
        """
        if cls._tracer_instance is None:
            logger.info("Initializing LLMTracer singleton instance...")
            cls._tracer_instance = LLMTracer(
                storage_writer=storage_writer, **kwargs
            )
            logger.info("LLMTracer singleton initialized.")
        return cls._tracer_instance

    @classmethod
    def get_tracer(cls) -> LLMTracer:
        """
        Lấy về instance tracer đã được khởi tạo.

        Raises:
            RuntimeError: Nếu tracer chưa được khởi tạo bằng `init_tracer`.

        Returns:
            Instance của LLMTracer.
        """
        if cls._tracer_instance is None:
            raise RuntimeError(
                "TracerManager has not been initialized. "
                "Call TracerManager.init_tracer() at application startup."
            )
        return cls._tracer_instance

    @classmethod
    @asynccontextmanager
    async def trace_span(
        cls,
        *,
        span_name: str,
        span_type: str = "DEFAULT",
        trace_id: Optional[uuid.UUID] = None,
        parent_span_id: Optional[uuid.UUID] = None,
        custom_metadata: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Tuple[uuid.UUID, uuid.UUID, Callable[..., Awaitable[Any]]], None]:
        """
        Context manager để tạo một span mới thông qua tracer được quản lý.

        Đây là phương thức chính để sử dụng tracer từ bất cứ đâu trong code.
        """
        tracer = cls.get_tracer()
        async with tracer.trace_span(
            span_name=span_name,
            span_type=span_type,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            custom_metadata=custom_metadata,
        ) as (tid, sid, wrapper):
            yield tid, sid, wrapper

    @classmethod
    async def shutdown_tracer(cls, timeout_sec: float = 10.0) -> None:
        """
        Dọn dẹp và shutdown tracer.

        Hàm này nên được gọi khi ứng dụng tắt để đảm bảo tất cả
        các trace đang chờ được xử lý.
        """
        if cls._tracer_instance:
            logger.info("Shutting down the LLMTracer instance...")
            await cls._tracer_instance.shutdown(timeout_sec=timeout_sec)
            cls._tracer_instance = None
            logger.info("LLMTracer instance shut down and disposed.")