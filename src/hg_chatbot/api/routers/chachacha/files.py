from fastapi import (
    APIRouter,
    UploadFile,
    HTTPException,
    File,
    Path,
    Depends,
)

from typing import Literal

from api.schema import FilesResponse, BotNames
from api.security import validate_auth

from services.tools import get_file_processor_tool

app = APIRouter(
    prefix="/files",
    tags=["Files"]
)

@app.delete(
    "/chachacha/{file_name}",
    dependencies=[Depends(validate_auth)],
    response_model=FilesResponse
)
async def delete_file(
    bot_name: BotNames,
    file_name: str = Path(...),
):
    file_processor = get_file_processor_tool(
        bot_name=bot_name
    )
    try:
        response = await file_processor.delete_file_data(
            file_name=file_name
        )
        return FilesResponse(**response)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
        


@app.post(
    "/chachacha/pdf-to-md",
    dependencies=[Depends(validate_auth)],
    response_model=FilesResponse
)
async def upload_and_convert_pdf_to_md(
    bot_name: BotNames,
    file: UploadFile = File(...),
):
    if not file.filename.endswith((".pdf")):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Please upload an PDF file."
        )

    file_processor = get_file_processor_tool(
        bot_name=bot_name
    )

    try:
        response = await file_processor.upload_and_convert_pdf_to_md(
            file=file
        )
        return FilesResponse(**response)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )