from datetime import timezone, datetime
from zoneinfo import ZoneInfo

from uuid import UUID

from fastapi import (
    HTTPException,
    UploadFile,
    status,
    File,
)

from api.routers.bots.tools.files import (
    create_file_info,
    is_file_exists,
    get_file_info,
    get_files_info,
    delete_file_info,
    update_file_info
)

from api.schema import DocumentType, FileInfo

from services.agentic_workflow.bots.hr_bot import HrBotService

async def hr_get_files_metadata(
    bot_service: HrBotService,
    document_type: DocumentType
):
    files_info = await get_files_info(
        bot_name=bot_service.bot_name,
        document_type=document_type
    )

    for file_info in files_info:
        file_info.uploaded_at = file_info.uploaded_at.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Asia/Bangkok"))

    return files_info

async def hr_delete_file(
    bot_service: HrBotService,
    file_id: str,
):
    if not await is_file_exists(file_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found."
        )

    file_info: FileInfo = await get_file_info(file_id)

    response = await bot_service.file_processor.delete_file_data(
        file_name=file_info.file_name,
        document_type=file_info.document_type
    )

    await delete_file_info(file_id)

    return response

async def hr_get_file(
    bot_service: HrBotService,
    file_id: UUID,
):
    if not await is_file_exists(file_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found."
        )

    file_info: FileInfo = await get_file_info(file_id)

    response = await bot_service.file_processor.get_file_data(
        file_name=file_info.file_name,
        document_type=file_info.document_type
    )

    await update_file_info(
        file_id=file_info.id,
        last_accessed_at=datetime.now(timezone.utc),
    )

    return response

async def hr_ocr_pdf_to_md(
    bot_service: HrBotService,
    email: str,
    file: UploadFile,
    document_type: DocumentType = DocumentType.CHATBOT
):
    size_bytes = file.size or 0
    file_size = round(size_bytes / (1024 * 1024), 2)

    file_name = file.filename

    response = await bot_service.file_processor.ocr_pdf_to_md(
        file=file,
        document_type=document_type
    )

    await create_file_info(
        email=email,
        bot_name=bot_service.bot_name,
        document_type=document_type,
        file_name=file_name,
        file_size=file_size
    )

    return response
