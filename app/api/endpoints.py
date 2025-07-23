from fastapi import APIRouter, Depends
from sqlmodel import create_engine, Session, SQLModel

from api.routers import (
    bots_router,
    files_router,
    auth_router,
)

from api.security import validate_auth
from api.schema import UserInfo, FileInfo
from core.storages.client import PostgresEngineManager
from core.storages.tracestores import TraceSpan, SpanCreate

async def create_db_and_tables():
    async_engine = PostgresEngineManager.init_engine()
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

app = APIRouter(
    prefix="/api/v1",
)

@app.get(
    "/",
    dependencies=[Depends(validate_auth)],
)
def health_check():
    return {"status": 200}

app.include_router(bots_router)
app.include_router(files_router)
app.include_router(auth_router)


