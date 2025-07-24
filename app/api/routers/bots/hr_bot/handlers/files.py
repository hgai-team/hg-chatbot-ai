import asyncio

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
    update_file_info,

    get_files_metadata,
    get_file,
    delete_file
)

from api.schema import DocumentType, FileInfo

from services.agentic_workflow.bots.hr_bot import HrBotService

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
