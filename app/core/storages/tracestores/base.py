from sqlmodel import Field, SQLModel, JSON, Column
from pydantic import BaseModel, ConfigDict

from contextlib import asynccontextmanager
from typing import Any, Awaitable, Callable, Dict, List, Optional, AsyncIterator

from sqlalchemy import TIMESTAMP

from tenacity import (
    RetryError,
    before_sleep_log,
    retry,
    stop_after_attempt,
    wait_exponential,
)

from core.sqldb.traces import SpanCreate

import asyncio
import datetime
import json
import logging
import threading
import time
import traceback
import uuid
import re

logger = logging.getLogger(__name__)

def _prepare_for_json(data: Any) -> Any:
    """Chuẩn bị dữ liệu để có thể serialize thành JSON một cách an toàn.

    Hàm này không trả về chuỗi JSON, mà là các kiểu Python gốc (dict, list,
    str...). Nó xử lý các đối tượng phức tạp như Pydantic models, datetime,
    và UUID.

    Args:
        data: Dữ liệu đầu vào cần được chuẩn bị.

    Returns:
        Dữ liệu đã được chuyển đổi thành các kiểu tương thích với JSON.
    """
    if hasattr(data, 'model_dump'):
        return data.model_dump()
    elif isinstance(data, (datetime.datetime, datetime.date)):
        return data.isoformat()
    elif isinstance(data, uuid.UUID):
        return str(data)
    elif isinstance(data, (list, tuple, set)):
        return [_prepare_for_json(item) for item in data]
    elif isinstance(data, dict):
        return {key: _prepare_for_json(value) for key, value in data.items()}

    # Trả về các kiểu dữ liệu gốc khác (str, int, float, bool, None)
    return data


def _parse_llm_output(output: Any) -> Any:
    """Phân tích output từ LLM.

    Nếu output là một chuỗi chứa khối mã JSON, hàm sẽ cố gắng trích xuất
    và phân tích (parse) nó.

    Args:
        output: Dữ liệu đầu ra từ LLM.

    Returns:
        Một đối tượng Python (thường là dict) nếu phân tích thành công,
        hoặc dữ liệu gốc nếu không thể phân tích.
    """
    if not isinstance(output, str):
        return output

    match = re.search(r'```json\s*(\{.*?\})\s*```', output, re.DOTALL)
    if match:
        json_string = match.group(1)
        try:
            return json.loads(json_string)
        except json.JSONDecodeError:
            return json_string

    try:
        if output.strip().startswith('{') and output.strip().endswith('}'):
            return json.loads(output)
    except json.JSONDecodeError:
        pass

    return output

class LLMTracer:
    """
    Tracer chuyên nghiệp, tích hợp với các Pydantic/SQLModel của ứng dụng.
    """

    def __init__(
        self,
        *,
        storage_writer: Callable[[List[SpanCreate]], Awaitable[None]],
        queue_max_size: int = 2000,
        batch_size: int = 20,
        batch_timeout_sec: float = 2.0,
        retry_attempts: int = 5,
        retry_max_wait_sec: int = 10,
    ):
        """
        Khởi tạo Tracer.

        Args:
            storage_writer: Hàm async nhận một List[SpanCreate] để lưu trữ.
            ... (các tham số khác)
        """
        self._trace_queue = asyncio.Queue(maxsize=queue_max_size)
        self._batch_size = batch_size
        self._batch_timeout = batch_timeout_sec

        self._worker_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._lock = threading.Lock()

        self.retrying_storage_writer = retry(
            stop=stop_after_attempt(retry_attempts),
            wait=wait_exponential(multiplier=1, min=2, max=retry_max_wait_sec),
            before_sleep=before_sleep_log(logger, logging.WARNING),
        )(storage_writer)

    async def _ensure_started(self):
        """
        Kiểm tra và khởi động worker nếu nó chưa chạy.
        Hàm này an toàn để gọi nhiều lần.
        """
        # Lock để đảm bảo chỉ có một thread có thể start worker tại một thời điểm
        with self._lock:
            if not self._worker_task or self._worker_task.done():
                logger.info("Tracer worker is not running. Starting it now...")
                self.start()

    def start(self):
        """Khởi động worker xử lý hàng đợi nền."""
        # start() không cần lock vì _ensure_started đã có lock
        if self._worker_task and not self._worker_task.done():
            logger.warning("Tracer worker is already running.")
            return
        self._stop_event.clear()
        self._worker_task = asyncio.create_task(self._queue_worker())
        logger.info("Tracer worker started.")

    async def shutdown(self, timeout_sec: float = 10.0):
        """Dừng worker và xử lý các trace còn lại trong hàng đợi."""
        with self._lock:
            if not self._worker_task or self._worker_task.done():
                return

            logger.info("Shutting down tracer. Processing remaining traces...")
            self._stop_event.set()
            try:
                self._trace_queue.put_nowait(None)
            except asyncio.QueueFull:
                pass

            try:
                await asyncio.wait_for(self._worker_task, timeout=timeout_sec)
                logger.info("Tracer worker shut down gracefully.")
            except asyncio.TimeoutError:
                logger.error("Tracer worker shutdown timed out.")
                self._worker_task.cancel()

    async def _queue_worker(self):
        """Worker chạy nền, lấy trace từ queue, tạo batch và gửi đi."""
        while not (self._stop_event.is_set() and self._trace_queue.empty()):
            batch = []
            try:
                first_item = await asyncio.wait_for(
                    self._trace_queue.get(), timeout=self._batch_timeout
                )
                if first_item is None:
                    break
                batch.append(first_item)

                while len(batch) < self._batch_size:
                    batch.append(self._trace_queue.get_nowait())

            except (asyncio.TimeoutError, asyncio.QueueEmpty):
                pass

            if batch:
                try:
                    logger.info("Sending a batch of %s spans.", len(batch))
                    await self.retrying_storage_writer(batch)
                except RetryError as e:
                    logger.critical(
                        "Failed to write span batch after multiple retries: %s", e
                    )
                except Exception:
                    logger.error(
                        "An unexpected error occurred in storage writer.",
                        exc_info=True
                    )

    @asynccontextmanager
    async def trace_span(
        self,
        *,
        span_name: str,
        span_type: str = "DEFAULT",
        trace_id: Optional[uuid.UUID] = None,
        parent_span_id: Optional[uuid.UUID] = None,
        custom_metadata: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[
        tuple[uuid.UUID, uuid.UUID, Callable[..., Awaitable[Any]]]
    ]:
        """
        Tạo một 'span' để theo dõi một đơn vị công việc.

        Yields:
            Tuple chứa (trace_id, span_id, wrapper_function).
        """
        await self._ensure_started()

        current_trace_id = trace_id or uuid.uuid4()
        current_span_id = uuid.uuid4()
        start_time = datetime.datetime.now(datetime.timezone.utc)

        span_to_create = SpanCreate(
            id=current_span_id,
            trace_id=current_trace_id,
            parent_id=parent_span_id,
            name=span_name,
            span_type=span_type,
            start_time=start_time,
            metadata_=custom_metadata or {},
        )

        async def wrapper(
            func: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any
        ) -> Any:

            model_name = None
            if hasattr(func, '__self__'):
                instance_obj = func.__self__
                model_name = getattr(instance_obj, 'model_name', None)
                if not model_name:
                    model_name = getattr(instance_obj, 'model', None)
            if model_name:
                span_to_create.metadata_['model_name'] = model_name

            input_payload = {"args": _prepare_for_json(args), "kwargs": _prepare_for_json(kwargs)}
            span_to_create.metadata_.update({"input": input_payload})

            try:
                result = await func(*args, **kwargs)
                span_to_create.status = "OK"
                span_to_create.metadata_.update(
                    {"output": _prepare_for_json(_parse_llm_output(result))}
                )
                return result
            except Exception as e:
                span_to_create.status = "ERROR"
                span_to_create.metadata_.update(
                    {
                        "error_message": str(e),
                        "error_traceback": traceback.format_exc(),
                    }
                )
                raise
            finally:
                span_to_create.end_time = datetime.datetime.now(
                    datetime.timezone.utc
                )
                duration_ms = (
                    span_to_create.end_time - span_to_create.start_time
                ).total_seconds() * 1000
                span_to_create.metadata_["latency_ms"] = round(duration_ms, 2)

                try:
                    self._trace_queue.put_nowait(span_to_create)
                except asyncio.QueueFull:
                    logger.warning(
                        "Tracer queue is full. Dropping span '%s'.", span_name
                    )

        yield current_trace_id, current_span_id, wrapper
