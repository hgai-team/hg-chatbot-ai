import uuid
import pandas as pd

from datetime import timezone
from zoneinfo import ZoneInfo
from uuid import UUID


from fastapi import (
    HTTPException,
    UploadFile,
    status,
    File,
)

from typing import Literal
from io import BytesIO

from .user_info import (
    create_user_info,
)

from api.routers.bots.tools.files import (
    create_file_info,
    is_file_exists,
    get_file_info,
    get_files_info,
    delete_file_info,
)

from api.schema import DocumentType, FileInfo, UserInfo

from services.agentic_workflow.bots.ops_bot import OpsBotService

async def ops_get_files_metadata(
    bot_service: OpsBotService,
    document_type: DocumentType = DocumentType.CHATBOT
):
    files_info = await get_files_info(
        bot_name=bot_service.bot_name,
        document_type=document_type
    )

    for file_info in files_info:
        file_info.uploaded_at = file_info.uploaded_at.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Asia/Bangkok"))

    return files_info

async def ops_delete_file(
    bot_service: OpsBotService,
    file_id: UUID,
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

async def ops_upload_excel(
    bot_service: OpsBotService,
    email: str,
    file: UploadFile = File(...),
    use_pandas: bool = Literal[True, False],
    document_type: DocumentType = DocumentType.CHATBOT
):
    size_bytes = file.size or 0
    file_size = round(size_bytes / (1024 * 1024), 2)

    file_name = file.filename

    response = await bot_service.file_processor.upload_excel_data(
        file=file,
        use_pandas=use_pandas,
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

async def ops_upload_excel_user_infos(
    bot_service: OpsBotService,
    email: str,
    file: UploadFile = File(...),
    document_type: DocumentType = DocumentType.USER_INFO
):
    size_bytes = file.size or 0
    file_size = round(size_bytes / (1024 * 1024), 2)

    file_name = file.filename

    contents = await file.read()

    with BytesIO(contents) as buffer:
        df = pd.read_excel(buffer)

    df.columns = [col.lower() for col in df.columns.tolist()]

    users = []

    df = df.where(pd.notna(df), None)
    for _, row in df.iterrows():
        if row.get("mail nhân sự") and isinstance(row.get("mail nhân sự"), str):
            def get_lower_str_or_none(value):
                if isinstance(value, str):
                    stripped_value = value.strip()
                    if stripped_value == '':
                        return None
                    return stripped_value.lower()
                return None

            def get_bool_from_excel(value):
                if value is None or value == '':
                    return False
                try:
                    num_value = float(value)
                    return num_value == 1.0
                except (ValueError, TypeError):
                    return False

            user_data = {}
            user_data["id"] = uuid.uuid4()

            user_data["name"] = get_lower_str_or_none(row.get("tên nhân sự"))
            user_data["email"] = get_lower_str_or_none(row.get("mail nhân sự"))
            user_data["managed_by"] = get_lower_str_or_none(row.get("quản lý"))
            user_data["network_in_qlk"] = get_lower_str_or_none(row.get("tên net trên tool qlk"))
            user_data["network_in_ys"] = get_lower_str_or_none(row.get("tên net (theo youtube studio)"))
            user_data["project"] = get_lower_str_or_none(row.get("tên dự án"))
            user_data["department"] = get_lower_str_or_none(row.get("phòng ban"))

            user_data["metadata_"] = {
                'tên dự án': get_lower_str_or_none(row.get("tên dự án")),
                'quy_định_chung': get_bool_from_excel(row.get("quy_định_chung")),
                'quy_định_chung_dự_án': get_bool_from_excel(row.get("quy_định_chung_dự_án")),
                'file_xlcv_chung_dự_án': get_bool_from_excel(row.get("file_xlcv_chung_dự_án")),
                'quy_định_riêng_dự_án_phòng_ban': get_bool_from_excel(row.get("quy_định_riêng_dự_án_phòng_ban")),
                'file_xlcv_riêng_dự_án_phòng_ban': get_bool_from_excel(row.get("file_xlcv_riêng_dự_án_phòng_ban")),
                'quy_định_riêng_dự_án_net': get_bool_from_excel(row.get("quy_định_riêng_dự_án_net")),
                'file_xlcv_riêng_dự_án_net': get_bool_from_excel(row.get("file_xlcv_riêng_dự_án_net")),
                'quy_định_network': get_bool_from_excel(row.get("quy_định_network")),
            }

            users.append(UserInfo.model_validate(user_data))

    if users:
        await create_user_info(input_=users)
        await create_file_info(
            email=email,
            bot_name=bot_service.bot_name,
            document_type=document_type,
            file_name=file_name,
            file_size=file_size
        )

    return {'status': 200}
