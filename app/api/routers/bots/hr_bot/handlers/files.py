from datetime import timezone
from zoneinfo import ZoneInfo

from fastapi import (
    UploadFile,
    File,
)

from typing import Literal

from services.agentic_workflow.bots.hr_bot import HrBotService

async def hr_get_files_metadata(
    bot_service: HrBotService,
):
    docs = await bot_service.file_processor.mongodb_doc_store.get_all()
    docs_metadata = []
    seen_file = set()
    for doc in docs:
        metadata = doc.metadata
        if metadata['file_name'] not in seen_file:
            docs_metadata.append(
                {
                    'file_name': metadata['file_name'],
                    'uploaded_at': metadata['uploaded_at'].replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Asia/Bangkok")),
                }
            )
            seen_file.add(metadata['file_name'])

    return sorted(docs_metadata, key=lambda doc: doc['uploaded_at'], reverse=True)

async def hr_delete_file(
    bot_service: HrBotService,
    file_name: str,
):

    response = await bot_service.file_processor.delete_file_data(
        file_name=file_name
    )
    return response


async def hr_ocr_pdf_to_md(
    bot_service: HrBotService,
    file: UploadFile,
):
    response = await bot_service.file_processor.ocr_pdf_to_md(
        file=file,
    )

    return response
