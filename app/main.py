import logging
logger = logging.getLogger(__name__)

import asyncio
from api.endpoints import app as api_app

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import get_api_settings
from api.endpoints import create_db_and_tables

from core.discord import client
from core.config import get_core_settings, setup_logging
from core.storages.client import TracerManager as TM
from core.storages.tracestores import PostgresTraceStore

from contextlib import asynccontextmanager

logger = logging.getLogger("main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    setup_logging()

    trace_store = PostgresTraceStore()
    TM.init_tracer(storage_writer=trace_store.upsert_span)

    yield

disable_docs = get_api_settings().ENV == "pro"
app = FastAPI(
    lifespan=lifespan,
    openapi_url=None      if disable_docs else "/openapi.json",
    docs_url=None         if disable_docs else "/docs",
    redoc_url=None        if disable_docs else "/redoc",
)
app.include_router(api_app)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["content-disposition"]
)

def main():
    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger.info("Starting HG Chatbot...")

    uvicorn.run(
        app=app,
        host="0.0.0.0",
        port=8000
    )

if __name__ == "__main__":
    main()



