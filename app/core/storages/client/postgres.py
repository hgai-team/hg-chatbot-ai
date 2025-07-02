import logging

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import sessionmaker

from api.config import get_api_settings
from core.config import get_sql_db_path

logger = logging.getLogger(__name__)

class PostgresEngineManager:
    """
    Singleton manager for AsyncEngine and AsyncSession creation.
    """
    _engine: Optional[AsyncEngine] = None
    _SessionLocal: Optional[sessionmaker] = None

    @classmethod
    def init_engine(cls, uri: Optional[str] = None) -> AsyncEngine:
        if cls._engine is None:
            db_uri = uri or get_sql_db_path()
            echo = True
            if get_api_settings().ENV == 'pro':
                echo = False
            cls._engine = create_async_engine(
                db_uri,
                echo=echo,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10,
            )
        return cls._engine

    @classmethod
    def init_sessionmaker(cls) -> sessionmaker:
        if cls._SessionLocal is None:
            engine = cls.init_engine()
            cls._SessionLocal = sessionmaker(
                bind=engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
        return cls._SessionLocal

    @classmethod
    @asynccontextmanager
    async def get_session(cls) -> AsyncGenerator[AsyncSession, None]:
        SessionLocal = cls.init_sessionmaker()
        async with SessionLocal() as session:
            try:
                yield session
                await session.commit()
            except:
                await session.rollback()
                raise

    @classmethod
    async def dispose_engine(cls) -> None:
        if cls._engine:
            await cls._engine.dispose()
            cls._engine = None
            cls._SessionLocal = None
