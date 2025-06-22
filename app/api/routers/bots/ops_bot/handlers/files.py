from datetime import timezone
from zoneinfo import ZoneInfo

from fastapi import (
    UploadFile,
    File,
)

from typing import Literal

from services.agentic_workflow.bots.ops_bot import OpsBotService

async def ops_get_files_metadata(
    ops_bot_service: OpsBotService,
):
    docs = await ops_bot_service.file_processor.mongodb_doc_store.get_all()
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

async def ops_delete_file(
    file_service: OpsBotService,
    file_name: str,
):

    response = await file_service.file_processor.delete_file_data(
        file_name=file_name
    )
    return response


async def ops_upload_excel(
    file_service: OpsBotService,
    file: UploadFile = File(...),
    use_type: bool = Literal[True, False],
    use_pandas: bool = Literal[True, False]
):
    response = await file_service.file_processor.upload_excel_data(
        file=file,
        use_type=use_type,
        use_pandas=use_pandas
    )

    return response
