from uuid import uuid4
from sqlmodel import select, update, delete

from core.storages.client import PostgresEngineManager as PEM
from core.storages.tracestores import TraceSpan


async def hr_get_all_traces():
    async with PEM.get_session() as session:
        result = await session.exec(select(TraceSpan))
        return result.all()

