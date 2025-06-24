import logging
logger = logging.getLogger(__name__)

import timeit

from fastapi import APIRouter, Depends, HTTPException, Path, status, UploadFile, File, Query, Body
from fastapi.responses import StreamingResponse
from typing import Literal

from api.security.api_credentials import validate_auth
from api.schema import (
    ChatRequest, ChatResponse, UserContext,
    FileResponse,
    SessionResponse, SessionRatingResponse,
    AgentRequest, AgentResponse, AgentResult,
    LogResponse, LogResult
)
from api.config import get_bot_manager
from api.routers.bots.base import BaseManager

app = APIRouter(
    prefix="/bots",
)

logger = logging.getLogger(__name__)

# Chat API Endpoints
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
    "/{bot_name}/chat/user",
    dependencies=[Depends(validate_auth)],
    response_model=ChatResponse,
    tags=['Chat']
)
async def chat_user(
    chat_request: ChatRequest,
    user_context: UserContext,
    bot_name: str = Path(...),

):
    try:
        bot_manager: BaseManager = get_bot_manager(bot_name)

        st = timeit.default_timer()
        response = await bot_manager.chat_user(
            chat_request=chat_request,
            user_context=user_context,
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
        logger.error(f"Attribute error in chat_user for bot '{bot_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Bot '{bot_name}' does not support chat_user feature"
        )
    except Exception as e:
        logger.error(f"An unhandled error occurred in chat for bot '{bot_name}': {e}", exc_info=True)
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
    user_context: UserContext,
    bot_name: str = Path(...),
):
    try:
        bot_manager: BaseManager = get_bot_manager(bot_name)

        return StreamingResponse(
            bot_manager.chat_user_stream(
                chat_request=chat_request,
                user_context=user_context,
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
@app.get(
    "/{bot_name}/files",
    dependencies=[Depends(validate_auth)],
    # response_model=FileResponse,
    tags=['Files']
)
async def get_files_metadata(
    bot_name: str = Path(...),
):
    bot_manager: BaseManager = get_bot_manager(bot_name)
    try:
        response = await bot_manager.get_files_metadata()
        return response
        # return FileResponse(**response)
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
    response_model=FileResponse,
    tags=['Files']
)
async def delete_file(
    bot_name: str = Path(...),
    file_name: str = Body(..., embed=True),
):
    bot_manager: BaseManager = get_bot_manager(bot_name)
    try:
        response = await bot_manager.delete_file(
            file_name=file_name
        )
        return FileResponse(**response)
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

@app.post(
    "/{bot_name}/files/excel",
    dependencies=[Depends(validate_auth)],
    response_model=FileResponse,
    tags=['Files']
)
async def upload_excel(
    bot_name: str = Path(...),
    file: UploadFile = File(...),
    use_type: bool = Literal[True, False],
    use_pandas: bool = Literal[False, True]
):
    if not file.filename.endswith((".xlsx", ".xls", ".xlsm")):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Please upload an Excel file."
        )

    bot_manager: BaseManager = get_bot_manager(bot_name)
    try:
        response = await bot_manager.upload_excel(
            file=file,
            use_type=use_type,
            use_pandas=use_pandas
        )
        return FileResponse(**response)
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

# Log API Endpoints
@app.get(
    "/{bot_name}/logs",
    dependencies=[Depends(validate_auth)],
    tags=['Logs'],
    response_model=LogResponse
)
async def get_logs(
    bot_name: str = Path(...),
    limit: int = Query(10, ge=1, le=1000),
    page_index: int = Query(1),
    rating_type: list[str] = Query([]),
    st: str = Query(None, description="Start time filter"),
    et: str = Query(None, description="End time filter"),
    so: int = Query(None, description="Sort order (Asc = 1, Desc = -1)"),
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
