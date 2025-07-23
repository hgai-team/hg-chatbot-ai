from uuid import uuid4, UUID
from sqlmodel import select, update, delete

from api.schema import (
    FileInfo
)
from core.storages.client import PostgresEngineManager as PEM

from typing import List, Any

async def create_file_info(
    email: str,
    bot_name: str,
    document_type: str,
    file_name: str,
    file_size: int,
):
    input_ = FileInfo(
        email=email,
        bot_name=bot_name,
        document_type=document_type,
        file_name=file_name,
        file_size=file_size
    )

    async with PEM.get_session() as session:
        session.add(input_)

async def is_file_exists(
    file_id: UUID,
):
    async with PEM.get_session() as session:
        result = await session.exec(
            select(FileInfo).where(
                FileInfo.id == file_id
            )
        )
        return result.first() is not None

async def get_file_info(
    file_id: UUID
):
    async with PEM.get_session() as session:
        result = await session.exec(
            select(FileInfo).where(
                FileInfo.id==file_id
            )
        )
        return result.first()

async def get_files_info(
    bot_name: str,
    document_type: str
):
    if document_type:
        stmt = select(FileInfo).where(
            FileInfo.bot_name == bot_name,
            FileInfo.document_type == document_type
        )
    else:
        stmt = select(FileInfo).where(
            FileInfo.bot_name == bot_name,
        )

    async with PEM.get_session() as session:
        result = await session.exec(stmt)
        return result.all()

async def delete_file_info(
    file_id: UUID
):
    async with PEM.get_session() as session:
        await session.exec(
            delete(FileInfo).where(
                FileInfo.id == file_id
            )
        )
        await session.commit()

async def update_file_info(
    file_id: UUID,
    **kwargs: Any,
):
    if not kwargs:
        raise ValueError("You must pass at least 1 field to update")

    async with PEM.get_session() as session:
        await session.exec(
            update(FileInfo)
            .where(FileInfo.id == file_id)
            .values(**kwargs)
            .execution_options(synchronize_session="fetch")
        )
