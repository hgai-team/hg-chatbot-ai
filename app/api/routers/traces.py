import logging
logger = logging.getLogger(__name__)

import os
import io
import requests
import timeit

from datetime import datetime, timedelta, timezone
from uuid import UUID
from pydantic import EmailStr

from typing import Optional, Any, List, Dict, Literal

from fastapi import (
    APIRouter, HTTPException, status,
    Depends, Path, File, Query, Body, Form
)

from api.security.api_credentials import validate_auth
from api.routers.bots.tools.traces import (
    get_all_traces,
    get_all_traces_by_date_range,
    get_model_usage_statistics,
    get_model_usage_statistics_by_date_range,
    get_model_usage_for_user,
    get_model_usage_for_user_by_date_range
)

app = APIRouter(
    prefix="/bots",
)

@app.post(
    "/traces",
    dependencies=[Depends(validate_auth)],
    tags=['Traces']
)
async def fetch_all_traces(
    limit: int = Body(10, ge=1, le=1000),
    page_index: int = Body(1),
    sort_field: str = Body(None),
    sort_order: Literal[-1, 1] = Body(-1, description="Sort order (Asc = 1, Desc = -1)"),
    filters: Optional[List[Dict[str, Any]]] = Body(None, description="Dictionary of multiple field-value pairs to filter by (optional). Supported operators: eq, ne, like, in, gt, gte, lt, lte")
):
    try:
        resp = await get_all_traces(
            limit=limit,
            page_index=page_index,
            sort_field=sort_field,
            sort_order=sort_order,
            filters=filters
        )
        return resp

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"An unhandled error occurred in fetch_all_traces: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.post(
    "/traces/date-range",
    dependencies=[Depends(validate_auth)],
    tags=['Traces']
)
async def fetch_all_traces_by_date_range(
    start_date: datetime = Body(...),
    end_date: datetime = Body(...),
    limit: int = Body(10, ge=1, le=1000),
    page_index: int = Body(1),
    sort_field: str = Body(None),
    sort_order: Literal[-1, 1] = Body(-1, description="Sort order (Asc = 1, Desc = -1)"),
    filters: Optional[List[Dict[str, Any]]] = Body(None, description="Dictionary of multiple field-value pairs to filter by (optional). Supported operators: eq, ne, like, in, gt, gte, lt, lte")
):
    try:
        resp = await get_all_traces_by_date_range(
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            page_index=page_index,
            sort_field=sort_field,
            sort_order=sort_order,
            filters=filters
        )
        return resp

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"An unhandled error occurred in fetch_all_traces_by_date_range: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.post(
    "/traces/statistics",
    dependencies=[Depends(validate_auth)],
    tags=['Traces']
)
async def fetch_traces_statistics(
    filters: Optional[List[Dict[str, Any]]] = Body(
        None,
        description="Dictionary of multiple field-value pairs to filter by (optional). Supported operators: eq, ne, like, in, gt, gte, lt, lte",
        embed=True
    )
):
    try:
        resp = await get_model_usage_statistics(
            filters=filters
        )
        return resp

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"An unhandled error occurred in fetch_traces_statistics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.post(
    "/traces/statistics/date-range",
    dependencies=[Depends(validate_auth)],
    tags=['Traces']
)
async def fetch_traces_statistics_by_date_range(
    start_date: datetime = Body(...),
    end_date: datetime = Body(...),
    filters: Optional[List[Dict[str, Any]]] = Body(
        None,
        description="Dictionary of multiple field-value pairs to filter by (optional). Supported operators: eq, ne, like, in, gt, gte, lt, lte",
        embed=True
    )
):
    try:
        resp = await get_model_usage_statistics_by_date_range(
            start_date=start_date,
            end_date=end_date,
            filters=filters
        )
        return resp

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"An unhandled error occurred in fetch_traces_statistics_by_date_range: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.post(
    "/traces/statistics/user",
    dependencies=[Depends(validate_auth)],
    tags=['Traces']
)
async def fetch_traces_statistics_for_user(
    user_id: UUID = Body(...),
    filters: Optional[List[Dict[str, Any]]] = Body(
        None,
        description="Dictionary of multiple field-value pairs to filter by (optional). Supported operators: eq, ne, like, in, gt, gte, lt, lte",
        embed=True
    )
):
    try:
        resp = await get_model_usage_for_user(
            user_id=user_id,
            filters=filters
        )
        return resp

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"An unhandled error occurred in fetch_traces_statistics_for_user: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.post(
    "/traces/statistics/user/date-range",
    dependencies=[Depends(validate_auth)],
    tags=['Traces']
)
async def fetch_traces_statistics_for_user_by_date_range(
    start_date: datetime = Body(...),
    end_date: datetime = Body(...),
    user_id: UUID = Body(...),
    filters: Optional[List[Dict[str, Any]]] = Body(
        None,
        description="Dictionary of multiple field-value pairs to filter by (optional). Supported operators: eq, ne, like, in, gt, gte, lt, lte",
        embed=True
    )
):
    try:
        resp = await get_model_usage_for_user_by_date_range(
            start_date=start_date,
            end_date=end_date,
            user_id=user_id,
            filters=filters
        )
        return resp

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"An unhandled error occurred in fetch_traces_statistics_for_user: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
