import logging
logger = logging.getLogger(__name__)

import os
import io
import requests
import timeit
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import (
    APIRouter, HTTPException, UploadFile, status,
    Depends, Path, File, Query, Body, Form
)
from fastapi.responses import StreamingResponse
from typing import Optional, Any, List, Dict, Literal

from pydantic import EmailStr

from api.security.api_credentials import validate_auth
from api.schema import (
    BaseResponse,
    ChatRequest, ChatResponse, UserContext,
    FileResponse, DocumentType, UserInfo,
    SessionResponse, SessionRatingResponse,
    AgentRequest, AgentResponse, AgentResult,
    LogResponse, LogResult
)
from api.config import get_bot_manager
from api.routers.bots.base import BaseManager

app = APIRouter(
    prefix="/bots",
)

# Chat API Endpoints
@app.post(
    "/{bot_name}/chat/stop",
    dependencies=[Depends(validate_auth)],
    response_model=BaseResponse,
    tags=['Chat']
)
async def chat_stop(
    chat_id: str,
    bot_name: str = Path(...),
):
    try:
        bot_manager: BaseManager = get_bot_manager(bot_name)

        await bot_manager.chat_stop(
            chat_id=chat_id,
        )

        return BaseResponse(
            status=200,
            data=None
        )

    except HTTPException:
        raise
    except AttributeError as e:
        logger.error(f"Attribute error in chat_stop for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Bot '{bot_name}' does not support chat_stop feature"
        )
    except Exception as e:
        logger.error(f"An unhandled error occurred in chat_stop for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.post(
    "/{bot_name}/chat",
    dependencies=[Depends(validate_auth)],
    response_model=ChatResponse,
    tags=['Chat']
)
async def chat(
    chat_request: ChatRequest,
    bot_name: str = Path(...),
):
    try:
        bot_manager: BaseManager = get_bot_manager(bot_name)

        st = timeit.default_timer()
        response = await bot_manager.chat(
            chat_request=chat_request,
        )
        et = timeit.default_timer()

        return ChatResponse(
            status=200,
            data={
                "response": response,
                "time_taken": et - st
            }
        )

    except HTTPException:
        raise
    except AttributeError as e:
        logger.error(f"Attribute error in chat for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Bot '{bot_name}' does not support chat feature"
        )
    except Exception as e:
        logger.error(f"An unhandled error occurred in chat for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.post(
    "/{bot_name}/chat/stream",
    dependencies=[Depends(validate_auth)],
    response_model=ChatResponse,
    tags=['Chat']
)
async def chat_stream(
    chat_request: ChatRequest,
    bot_name: str = Path(...),
):
    try:
        bot_manager: BaseManager = get_bot_manager(bot_name)

        return StreamingResponse(
            bot_manager.chat_stream(
                chat_request=chat_request,
            ),
            media_type="text/event-stream"
        )

    except HTTPException:
        raise
    except AttributeError as e:
        logger.error(f"Attribute error in chat_stream for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Bot '{bot_name}' does not support chat_stream feature"
        )
    except Exception as e:
        logger.error(f"An unhandled error occurred in chat_stream for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.post(
    "/{bot_name}/chat/user/stream",
    dependencies=[Depends(validate_auth)],
    response_model=ChatResponse,
    tags=['Chat']
)
async def chat_user_stream(
    chat_request: ChatRequest,
    email: str = Body(..., embed=True),
    bot_name: str = Path(...),
):
    try:
        bot_manager: BaseManager = get_bot_manager(bot_name)

        return StreamingResponse(
            bot_manager.chat_user_stream(
                chat_request=chat_request,
                email=email,
            ),
            media_type="text/event-stream"
        )

    except HTTPException:
        raise
    except AttributeError as e:
        logger.error(f"Attribute error in chat_user_stream for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Bot '{bot_name}' does not support chat_user_stream feature"
        )
    except Exception as e:
        logger.error(f"An unhandled error occurred in chat_user_stream for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# File API Endpoints
@app.post(
    "/{bot_name}/files",
    dependencies=[Depends(validate_auth)],
    tags=['Files']
)
async def get_files_metadata(
    bot_name: str = Path(...),
    document_type: DocumentType = Body(None),
    q: str = Body(None),
    limit: int = Body(10, ge=1, le=1000),
    page_index: int = Body(1),
    file_ext: list[str] = Body([], description=".xlsx, .pdf, ..."),
    sort_field: str = Body(None),
    sort_order: int = Body(None, description="Sort order (Asc = 1, Desc = -1)"),
):
    bot_manager: BaseManager = get_bot_manager(bot_name)
    try:
        response = await bot_manager.get_files_metadata(
            document_type=document_type,
            q=q,
            limit=limit,
            page_index=page_index,
            file_ext=file_ext,
            sort_field=sort_field,
            sort_order=sort_order
        )
        return response

    except AttributeError as e:
        logger.error(f"Attribute error in get_file_metadata for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Bot '{bot_name}' does not support get_file_metadata feature"
        )
    except Exception as e:
        logger.error(f"An unhandled error occurred in get_file_metadata for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.delete(
    "/{bot_name}/files",
    dependencies=[Depends(validate_auth)],
    # response_model=FileResponse,
    tags=['Files']
)
async def delete_file(
    bot_name: str = Path(...),
    file_ids: list[UUID] = Body(..., embed=True),
):
    bot_manager: BaseManager = get_bot_manager(bot_name)
    try:
        response = await bot_manager.delete_file(
            file_ids=file_ids
        )
        return response
        # return FileResponse(**response)
    except HTTPException:
        raise
    except AttributeError as e:
        logger.error(f"Attribute error in delete_file for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Bot '{bot_name}' does not support delete_file feature"
        )
    except Exception as e:
        logger.error(f"An unhandled error occurred in delete_file for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.get(
    "/{bot_name}/files/{file_id}",
    dependencies=[Depends(validate_auth)],
    # response_model=FileResponse,
    tags=['Files']
)
async def get_file(
    bot_name: str = Path(...),
    file_id: UUID = Path(...),
):
    bot_manager: BaseManager = get_bot_manager(bot_name)

    try:
        result = await bot_manager.get_file(file_id=file_id)
        return result

    except HTTPException:
        raise
    except AttributeError as e:
        logger.error(f"Attribute error in get_file for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Bot '{bot_name}' does not support get_file feature"
        )
    except Exception as e:
        logger.error(f"Unhandled error in get_file for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.post(
    "/{bot_name}/files/excel",
    dependencies=[Depends(validate_auth)],
    # response_model=FileResponse,
    tags=['Files']
)
async def upload_excel(
    bot_name: str = Path(...),
    email: EmailStr = Form(...),
    file: UploadFile = File(...),
    use_pandas: bool = Form(False),
    document_type: DocumentType = Form(DocumentType.CHATBOT)
):
    if not file.filename.endswith((".xlsx", ".xls", ".xlsm")):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Please upload an Excel file."
        )

    bot_manager: BaseManager = get_bot_manager(bot_name)
    try:
        response = await bot_manager.upload_excel(
            email=email,
            file=file,
            use_pandas=use_pandas,
            document_type=document_type
        )
        return response
        # return FileResponse(**response)
    except AttributeError as e:
        logger.error(f"Attribute error in upload_excel for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Bot '{bot_name}' does not support upload_excel feature"
        )
    except Exception as e:
        logger.error(f"An unhandled error occurred in upload_excel for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.post(
    "/{bot_name}/files/pdf/ocr-to-md",
    dependencies=[Depends(validate_auth)],
    tags=['Files']
)
async def ocr_pdf_to_md(
    bot_name: str = Path(...),
    email: EmailStr = Form(...),
    file: UploadFile = File(...),
    document_type: DocumentType = Form(DocumentType.CHATBOT)
):
    if not file.filename.endswith((".pdf")):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Please upload an PDF file."
        )

    bot_manager: BaseManager = get_bot_manager(bot_name)
    try:
        response = await bot_manager.ocr_pdf_to_md(
            email=email,
            file=file,
            document_type=document_type
        )
        return response

    except AttributeError as e:
        logger.error(f"Attribute error in upload_pdf_to_md for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Bot '{bot_name}' does not support upload_pdf_to_md feature"
        )
    except Exception as e:
        logger.error(f"An unhandled error occurred in upload_pdf_to_md for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# Session API Endpoints
@app.get(
    "/{bot_name}/sessions",
    dependencies=[Depends(validate_auth)],
    response_model=SessionResponse,
    tags=['Sessions']
)
async def get_session(
    session_id: str = Query(...),
    bot_name: str = Path(...),
):
    bot_manager: BaseManager = get_bot_manager(bot_name)

    try:
        history = await bot_manager.get_session(
            session_id=session_id,
        )
        if history:
            return SessionResponse(
                status=200,
                data={
                    "user_id": history.user_id,
                    "history": history.history,
                    "title": history.session_title
                }
            )
        return SessionResponse(
            status=200,
            data={
                "user_id": None,
                "history": [],
                "title": None
            }
        )
    except AttributeError as e:
        logger.error(f"Attribute error in get_session for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Bot '{bot_name}' does not support get_session feature"
        )
    except Exception as e:
        logger.error(f"An error occurred in get_session for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.post(
    "/{bot_name}/sessions/rating",
    dependencies=[Depends(validate_auth)],
    response_model=SessionRatingResponse,
    tags=['Sessions']
)
async def add_rating(
    chat_id: str,
    bot_name: str = Path(...),
    rating_type: str = None,
    rating_text: str = None,
):
    bot_manager: BaseManager = get_bot_manager(bot_name)

    try:
        await bot_manager.add_rating(
            chat_id=chat_id,
            rating_type=rating_type,
            rating_text=rating_text
        )
        return SessionRatingResponse(
            status=200,
            data={
                "rating_type": rating_type,
                "rating_text": rating_text
            }
        )
    except AttributeError as e:
        logger.error(f"Attribute error in add_rating for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Bot '{bot_name}' does not support add_rating feature"
        )
    except Exception as e:
        logger.error(f"An error occurred in add_rating for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.post(
    "/{bot_name}/sessions/count-tokens",
    dependencies=[Depends(validate_auth)],
    response_model=BaseResponse,
    tags=['Sessions']
)
async def count_tokens(
    session_id: str = Body(..., embed=True),
    message: str = Body(..., embed=True),
    bot_name: str = Path(...),
):
    bot_manager: BaseManager = get_bot_manager(bot_name)

    try:
        response = await bot_manager.count_tokens(
            session_id=session_id,
            message=message
        )
        return BaseResponse(
            status=200,
            data=response
        )
    except AttributeError as e:
        logger.error(f"Attribute error in count_tokens for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Bot '{bot_name}' does not support count_tokens feature"
        )
    except Exception as e:
        logger.error(f"An error occurred in count_tokens for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.post(
    "/{bot_name}/sessions/count-video-tokens",
    dependencies=[Depends(validate_auth)],
    response_model=BaseResponse,
    tags=['Sessions']
)
async def count_video_tokens(
    video_url: str = Body(..., embed=True),
    start_offset: str = Body(None, embed=True),
    end_offset: str = Body(None, embed=True),
    fps: int = Body(1, embed=True),
    bot_name: str = Path(...),
):
    try:
        from core.mcp.vid_ytb import count_video_tokens

        total_tokens = await count_video_tokens(
            video_url,
            start_offset,
            end_offset,
            fps,
        )

        return BaseResponse(
            status=200,
            data={
                "totalTokens": total_tokens
            }
        )
    except AttributeError as e:
        logger.error(f"Attribute error in count_video_tokens for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Bot '{bot_name}' does not support count_video_tokens feature"
        )
    except Exception as e:
        logger.error(f"An error occurred in count_video_tokens for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# Log API Endpoints
@app.post(
    "/{bot_name}/logs",
    dependencies=[Depends(validate_auth)],
    tags=['Logs'],
    response_model=LogResponse
)
async def get_logs(
    bot_name: str = Path(...),
    limit: int = Body(10, ge=1, le=1000),
    page_index: int = Body(1),
    rating_type: list[str] = Body([]),
    st: str = Body("", description="Start time filter"),
    et: str = Body("", description="End time filter"),
    so: int = Body(None, description="Sort order (Asc = 1, Desc = -1)"),
):
    bot_manager: BaseManager = get_bot_manager(bot_name)

    try:
        logs, page_info = await bot_manager.get_logs(
            page_index=page_index,
            rating_type=rating_type,
            limit=limit,
            st=st,
            et=et,
            so=so
        )
        return LogResponse(
            status=200,
            data={
                'history': logs,
                'pages': {
                    **page_info,
                    'page_index': page_index
                }
            }
        )

    except AttributeError as e:
        logger.error(f"Attribute error in get_logs for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Bot '{bot_name}' does not support get_logs feature"
        )
    except Exception as e:
        logger.error(f"An error occurred in get_logs for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.get(
    "/{bot_name}/logs/file",
    dependencies=[Depends(validate_auth)],
    tags=['Logs'],
)
async def get_logs_file(
    bot_name: str = Path(...),
):
    bot_manager: BaseManager = get_bot_manager(bot_name)

    try:
        file, ts = await bot_manager.get_logs_file()

        filename = f"{bot_name}_logs_{ts}.xlsx"
        headers = {"Content-Disposition": f'attachment; filename=\"{filename}\"'}
        return StreamingResponse(
            file,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=headers
        )

    except AttributeError as e:
        logger.error(f"Attribute error in get_logs_file for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Bot '{bot_name}' does not support get_logs_file feature"
        )
    except Exception as e:
        logger.error(f"An error occurred in get_logs_file for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.get(
    "/{bot_name}/logs/sys-resp-cnt",
    dependencies=[Depends(validate_auth)],
    response_model=BaseResponse,
    tags=['Logs']
)
async def get_user_sys_resp_cnt(
    user_id: str = Query(...),
    bot_name: str = Path(...),
):
    bot_manager: BaseManager = get_bot_manager(bot_name)

    try:
        cnt = await bot_manager.get_user_sys_resp_cnt(
            user_id=user_id,
        )
        return BaseResponse(
            status=200,
            data={
                'sys_resp_cnt': cnt
            }
        )

    except AttributeError as e:
        logger.error(f"Attribute error in get_user_sys_resp_cnt for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Bot '{bot_name}' does not support get_user_sys_resp_cnt feature"
        )
    except Exception as e:
        logger.error(f"An error occurred in get_user_sys_resp_cnt for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# User Info API Endpoints
@app.post(
    "/{bot_name}/users/upserts",
    dependencies=[Depends(validate_auth)],
    tags=['User Info']
)
async def upsert_users(
    bot_name: str = Path(...),
    users: List[UserInfo] = Body(..., embed=True)
):
    bot_manager: BaseManager = get_bot_manager(bot_name)
    try:
        response = await bot_manager.upsert_users(
            users=users
        )
        return response
    except HTTPException:
        raise
    except AttributeError as e:
        logger.error(f"Attribute error in upsert_users for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Bot '{bot_name}' does not support upsert_users feature"
        )
    except Exception as e:
        logger.error(f"An unhandled error occurred in upsert_users for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# @app.post(
#     "/{bot_name}/users",
#     dependencies=[Depends(validate_auth)],
#     tags=['User Info']
# )
# async def create_users(
#     bot_name: str = Path(...),
#     users: List[UserInfo] = Body(..., embed=True)
# ):
#     bot_manager: BaseManager = get_bot_manager(bot_name)
#     try:
#         response = await bot_manager.create_users(
#             users=users
#         )
#         return response
#     except HTTPException:
#         raise
#     except AttributeError as e:
#         logger.error(f"Attribute error in create_users for bot '{bot_name}': {e}", exc_info=True)
#         raise HTTPException(
#             status_code=status.HTTP_501_NOT_IMPLEMENTED,
#             detail=f"Bot '{bot_name}' does not support create_users feature"
#         )
#     except Exception as e:
#         logger.error(f"An unhandled error occurred in create_users for bot '{bot_name}': {e}", exc_info=True)
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Internal server error"
#         )

# @app.put(
#     "/{bot_name}/users",
#     dependencies=[Depends(validate_auth)],
#     tags=['User Info']
# )
# async def update_users(
#     bot_name: str = Path(...),
#     users: List[UserInfo] = Body(..., embed=True)
# ):
#     bot_manager: BaseManager = get_bot_manager(bot_name)
#     try:
#         response = await bot_manager.update_users(
#             users=users
#         )
#         return response
#     except HTTPException:
#         raise
#     except AttributeError as e:
#         logger.error(f"Attribute error in update_users for bot '{bot_name}': {e}", exc_info=True)
#         raise HTTPException(
#             status_code=status.HTTP_501_NOT_IMPLEMENTED,
#             detail=f"Bot '{bot_name}' does not support update_users feature"
#         )
#     except Exception as e:
#         logger.error(f"An unhandled error occurred in update_users for bot '{bot_name}': {e}", exc_info=True)
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Internal server error"
#         )

@app.delete(
    "/{bot_name}/users",
    dependencies=[Depends(validate_auth)],
    tags=['User Info']
)
async def delete_users(
    bot_name: str = Path(...),
    ids: List[UUID] = Body(..., embed=True)
):
    bot_manager: BaseManager = get_bot_manager(bot_name)
    try:
        response = await bot_manager.delete_users(
            ids=ids
        )
        return response
    except HTTPException:
        raise
    except AttributeError as e:
        logger.error(f"Attribute error in delete_users for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Bot '{bot_name}' does not support delete_users feature"
        )
    except Exception as e:
        logger.error(f"An unhandled error occurred in delete_users for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.post(
    "/{bot_name}/users/unique-values/{column_name}",
    dependencies=[Depends(validate_auth)],
    tags=['User Info']
)
async def get_distinct_user_values(
    bot_name: str = Path(...),
    column_name: str = Path(...),
    filters: Optional[List[Dict[str, Any]]] = Body(None,
    description="Dictionary of multiple field-value pairs to filter by (optional). Supported operators: eq, ne, like, in, gt, gte, lt, lte",
    embed=True)
):
    bot_manager: BaseManager = get_bot_manager(bot_name)
    try:
        response = await bot_manager.get_distinct_user_values(
            column_name=column_name,
            filters=filters
        )
        return response
    except HTTPException:
        raise
    except AttributeError as e:
        logger.error(f"Attribute error in get_users for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Bot '{bot_name}' does not support get_users feature"
        )
    except Exception as e:
        logger.error(f"An unhandled error occurred in get_users for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.post(
    "/{bot_name}/users/search",
    dependencies=[Depends(validate_auth)],
    tags=['User Info']
)
async def search_users(
    bot_name: str = Path(...),
    limit: int = Body(10, ge=1, le=1000),
    page_index: int = Body(1),
    sort_field: str = Body(None),
    sort_order: Literal[1, -1] = Body(-1, description="Sort order (Asc = 1, Desc = -1)"),
    filters: Optional[List[Dict[str, Any]]] = Body(None,
    description="Dictionary of multiple field-value pairs to filter by (optional). Supported operators: eq, ne, like, in, gt, gte, lt, lte")
):
    bot_manager: BaseManager = get_bot_manager(bot_name)
    try:
        response = await bot_manager.search_users(
            limit=limit,
            page_index=page_index,
            sort_field=sort_field,
            sort_order=sort_order,
            filters=filters
        )
        return response
    except HTTPException:
        raise
    except AttributeError as e:
        logger.error(f"Attribute error in get_users for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Bot '{bot_name}' does not support get_users feature"
        )
    except Exception as e:
        logger.error(f"An unhandled error occurred in get_users for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.get(
    "/{bot_name}/user",
    dependencies=[Depends(validate_auth)],
    tags=['User Info']
)
async def get_user(
    bot_name: str = Path(...),
    email: EmailStr = Query(...),
):
    bot_manager: BaseManager = get_bot_manager(bot_name)
    try:
        response = await bot_manager.get_user(email=email)
        return response
    except HTTPException:
        raise
    except AttributeError as e:
        logger.error(f"Attribute error in get_user for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Bot '{bot_name}' does not support get_user feature"
        )
    except Exception as e:
        logger.error(f"An unhandled error occurred in get_user for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.get(
    "/{bot_name}/user/aggregated",
    dependencies=[Depends(validate_auth)],
    tags=['User Info']
)
async def get_aggregated_user(
    bot_name: str = Path(...),
    email: EmailStr = Query(...),
):
    bot_manager: BaseManager = get_bot_manager(bot_name)
    try:
        response = await bot_manager.get_aggregated_user(email=email)
        return response
    except HTTPException:
        raise
    except AttributeError as e:
        logger.error(f"Attribute error in get_user for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Bot '{bot_name}' does not support get_user feature"
        )
    except Exception as e:
        logger.error(f"An unhandled error occurred in get_user for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# Agent API Endpoints
@app.post(
    "/{bot_name}/agents/eval",
    dependencies=[Depends(validate_auth)],
    response_model=AgentResponse,
    tags=['Agents']
)
async def agent_evaluation(
    agent_request: AgentRequest,
    user_context: UserContext = None,
    bot_name: str = Path(...),
):
    try:
        bot_manager: BaseManager = get_bot_manager(bot_name)

        response = await bot_manager.agent_evaluation(
            agent_request=agent_request,
            user_context=user_context,
        )

        return AgentResponse(
            status=200,
            data={
                "response": response
            }
        )

    except HTTPException:
        raise
    except AttributeError as e:
        logger.error(f"Attribute error in agent_evaluation for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Bot '{bot_name}' does not support agent_evaluation feature"
        )
    except Exception as e:
        logger.error(f"An unhandled error occurred in chat for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
