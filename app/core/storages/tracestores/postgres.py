import logging
logger = logging.getLogger(__name__)

import asyncio

from typing import List, Optional, Dict, Any

from .base import SpanCreate, TraceSpan


from core.storages.client import (
    PostgresEngineManager as PEM,
)
class PostgresTraceStore():
    def __init__(
        self,
        **kwargs,
    ):
        PEM.init_engine()
    async def upsert_span(
        self,
        spans: List[SpanCreate]
    ):
        async with PEM.get_session() as session:
            db_spans = [TraceSpan.model_validate(span) for span in spans]
            session.add_all(db_spans)
