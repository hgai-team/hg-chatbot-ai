import asyncio

from datetime import timezone, datetime
from zoneinfo import ZoneInfo

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
from services.agentic_workflow.tools.files_processor import FileProcessorTool

from typing import List, Any

# File Info
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

# File
async def get_files_metadata(
    bot_name: str,
    document_type: DocumentType,
    q: str,
    limit: int,
    page_index: int,
    file_ext: list[str],
    sort_field: str,
    sort_order: int
):
    resp = await get_files_info(
        bot_name=bot_name,
        document_type=document_type,
        q=q,
        limit=limit,
        page_index=page_index,
        file_ext=file_ext,
        sort_field=sort_field,
        sort_order=sort_order
    )

    for file_info in resp['items']:
        file_info.uploaded_at = file_info.uploaded_at.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Asia/Bangkok"))

    return resp

async def get_file(
    file_processor: FileProcessorTool,
    file_id: UUID,
):
    if not await is_file_exists(file_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found."
        )

    file_info: FileInfo = await get_file_info(file_id)

    response = await file_processor.get_file_data(
        file_name=file_info.file_name,
        document_type=file_info.document_type
    )

    await update_file_info(
        file_id=file_info.id,
        last_accessed_at=datetime.now(timezone.utc),
    )

    return response

async def delete_file(
    file_processor: FileProcessorTool,
    file_ids: list[UUID],
):
    tasks_info = [get_file_info(file_id) for file_id in file_ids]
    file_infos = await asyncio.gather(*tasks_info, return_exceptions=True)

    user_info_files: list[str] = []
    file_ids_to_delete: list[UUID] = []
    file_names_to_delete: list[str] = []
    delete_tasks = []

    for fi in file_infos:
        if isinstance(fi, Exception):
            continue

        if fi.document_type == DocumentType.USER_INFO:
            user_info_files.append(fi.file_name)
        else:
            file_ids_to_delete.append(fi.id)
            file_names_to_delete.append(fi.file_name)
            delete_tasks.append(
                file_processor.delete_file_data(
                    file_name=fi.file_name,
                    document_type=fi.document_type
                )
            )

    results = await asyncio.gather(*delete_tasks, return_exceptions=True)

    deleted_success_ids: list[UUID] = []
    deleted_failed_ids:  list[UUID] = []
    delete_failed_names: list[str] = []

    for idx, res in enumerate(results):
        fid = file_ids_to_delete[idx]
        fname = file_names_to_delete[idx]

        if isinstance(res, Exception):
            deleted_failed_ids.append(fid)
            delete_failed_names.append(fname)
        else:
            deleted_success_ids.append(fid)

    delete_file_info_tasks = [delete_file_info(file_id) for file_id in deleted_success_ids]
    _ = await asyncio.gather(*delete_file_info_tasks, return_exceptions=True)

    return {
        "not_allowed_to_delete": user_info_files,
        "delete_failed_names": delete_failed_names
    }
