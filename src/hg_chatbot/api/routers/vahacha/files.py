from fastapi import (
    APIRouter,
    UploadFile,
    HTTPException,
    File,
    Path,
    Depends,
    Form
)

from typing import Literal

from api.schema import FilesResponse, BotNames
from api.security import get_api_key

from services.tools import get_file_processor_tool

app = APIRouter(
    prefix="/files",
    tags=["Files"]
)

# @app.get(
#     "/{file_name}",
#     dependencies=[Depends(get_api_key)],
#     response_model=FilesResponse
# )
# async def get_file_info(file_name: str = Path(...)):
#     try:
#         pass
#         # return FilesResponse(**response)
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=str(e)
#         )

@app.delete(
    "/{file_name}",
    dependencies=[Depends(get_api_key)],
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
    "/excel",
    dependencies=[Depends(get_api_key)],
    response_model=FilesResponse
)
async def upload_excel_file(
    bot_name: BotNames,
    file: UploadFile = File(...),
    use_type: bool = Literal[True, False]
):
    if not file.filename.endswith((".xlsx", ".xls", ".xlsm")):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Please upload an Excel file."
        )

    file_processor = get_file_processor_tool(
        bot_name=bot_name
    )

    try:
        response = await file_processor.upload_excel_data(
            file=file,
            use_type=use_type
        )
        
        return FilesResponse(**response)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.post(
    "/pdf",
    dependencies=[Depends(get_api_key)],
    response_model=FilesResponse
)
async def upload_pdf_file(
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
        response = await file_processor.upload_pdf_data(
            file=file
        )
        return FilesResponse(**response)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.post(
    "/docx",
    dependencies=[Depends(get_api_key)],
    response_model=FilesResponse
)
async def upload_docx_file(
    bot_name: BotNames,
    file: UploadFile = File(...),
):

    if not file.filename.endswith((".docx")):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Please upload an Docx file."
        )

    file_processor = get_file_processor_tool(
        bot_name=bot_name
    )

    try:
        response = await file_processor.upload_docx_file(
            file=file
        )

        return FilesResponse(**response)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
