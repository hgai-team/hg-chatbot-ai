from math import ceil
from uuid import uuid4, UUID
from sqlmodel import (
    select, update, delete, or_, asc, desc,
    func,
)

from fastapi import HTTPException, status

from api.schema import (
    FileInfo, DocumentType
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
    document_type: str,
    q: str,
    limit: int,
    page_index: int,
    file_ext: list[str],
    sort_field: str,
    sort_order: int
):
    if isinstance(bot_name, list):
        filters = [FileInfo.bot_name.in_(bot_name)]
    else:
        filters = [FileInfo.bot_name == bot_name]

    if document_type:
        try:
            dt = DocumentType(document_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid document_type '{document_type}'"
            )
        filters.append(FileInfo.document_type == dt)

    if q:
        filters.append(FileInfo.file_name.ilike(f"%{q}%"))

    if file_ext:
        ext_conds = []
        for ext in file_ext:
            e = ext.lower().strip()
            if not e.startswith("."):
                e = "." + e
            ext_conds.append(FileInfo.file_name.ilike(f"%{e}"))
        filters.append(or_(*ext_conds))

    async with PEM.get_session() as session:
        count_stmt = select(func.count()).select_from(FileInfo).where(*filters)
        total_items = (await session.exec(count_stmt)).one()

        if total_items == 0:
            return {
                "items": [],
                "total_items": 0,
                "total_pages": 0,
                "page_index": page_index,
            }

        total_pages = ceil(total_items / limit)
        if page_index < 1 or page_index > total_pages:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"page_index must be between 1 and {total_pages}"
            )

        stmt = select(FileInfo).where(*filters)

        if sort_field:
            if not hasattr(FileInfo, sort_field):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid sort_field '{sort_field}'"
                )
            col = getattr(FileInfo, sort_field)
            if sort_order == -1:
                stmt = stmt.order_by(desc(col))
            else:
                stmt = stmt.order_by(asc(col))

        offset = (page_index - 1) * limit
        stmt = stmt.offset(offset).limit(limit)

        result = await session.exec(stmt)
        items: List[FileInfo] = result.all()

    return {
        "items": items,
        "total_items": total_items,
        "total_pages": total_pages,
        "page_index": page_index,
    }

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
