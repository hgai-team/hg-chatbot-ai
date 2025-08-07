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
    get_model_usage_statistics
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
    start_date: Optional[datetime] = Body(None, description="Start date for filtering (optional)"),
    end_date: Optional[datetime] = Body(None, description="End date for filtering (optional)"),
    filters: Optional[List[Dict[str, Any]]] = Body(None, description="Dictionary of multiple field-value pairs to filter by (optional). Supported operators: eq, ne, like, in, gt, gte, lt, lte")
):
    """
    Fetch all traces with optional date range and custom filters.

    If start_date and end_date are provided, traces will be filtered to that date range.
    Additional filters can be applied through the filters parameter.
    """
    try:
        # Add date range filters if provided
        if start_date and end_date:
            date_filters = [
                {
                    "field": "start_time",
                    "operator": "gte",
                    "value": start_date
                },
                {
                    "field": "start_time",
                    "operator": "lte",
                    "value": end_date
                }
            ]

            if filters:
                filters.extend(date_filters)
            else:
                filters = date_filters
        elif start_date or end_date:
            # If only one date is provided, return error
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Both start_date and end_date must be provided together"
            )

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
    "/traces/statistics",
    dependencies=[Depends(validate_auth)],
    tags=['Traces']
)
async def fetch_traces_statistics(
    start_date: Optional[datetime] = Body(None, description="Start date for filtering (optional)"),
    end_date: Optional[datetime] = Body(None, description="End date for filtering (optional)"),
    filters: Optional[List[Dict[str, Any]]] = Body(
        None,
        description="Dictionary of multiple field-value pairs to filter by (optional). Supported operators: eq, ne, like, in, gt, gte, lt, lte"
    )
):
    """
    Fetch model usage statistics with optional date range and custom filters.

    If start_date and end_date are provided, statistics will be filtered to that date range.
    Additional filters can be applied through the filters parameter.
    """
    try:
        # If date range is provided, add to filters
        if start_date and end_date:
            date_filters = [
                {
                    "field": "start_time",
                    "operator": "gte",
                    "value": start_date
                },
                {
                    "field": "start_time",
                    "operator": "lte",
                    "value": end_date
                }
            ]

            if filters:
                filters.extend(date_filters)
            else:
                filters = date_filters
        elif start_date or end_date:
            # If only one date is provided, return error
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Both start_date and end_date must be provided together"
            )

        resp = await get_model_usage_statistics(filters=filters)
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
    "/traces/statistics/user",
    dependencies=[Depends(validate_auth)],
    tags=['Traces']
)
async def fetch_traces_statistics_for_user(
    user_id: UUID = Body(..., description="User ID to filter statistics"),
    start_date: Optional[datetime] = Body(None, description="Start date for filtering (optional)"),
    end_date: Optional[datetime] = Body(None, description="End date for filtering (optional)"),
    filters: Optional[List[Dict[str, Any]]] = Body(
        None,
        description="Dictionary of multiple field-value pairs to filter by (optional). Supported operators: eq, ne, like, in, gt, gte, lt, lte"
    )
):
    """
    Fetch model usage statistics for a specific user with optional date range and custom filters.

    If start_date and end_date are provided, statistics will be filtered to that date range.
    Additional filters can be applied through the filters parameter.
    """
    try:
        # Build filters list
        _filters = [
            {
                "field": "metadata_",
                "operator": "contains",
                "value": {"user_id": str(user_id)}
            }
        ]

        # Add date range filters if provided
        if start_date and end_date:
            _filters.extend([
                {
                    "field": "start_time",
                    "operator": "gte",
                    "value": start_date
                },
                {
                    "field": "start_time",
                    "operator": "lte",
                    "value": end_date
                }
            ])
        elif start_date or end_date:
            # If only one date is provided, return error
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Both start_date and end_date must be provided together"
            )

        # Add any additional filters
        if filters:
            _filters.extend(filters)

        resp = await get_model_usage_statistics(filters=_filters)
        return resp

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"An unhandled error occurred in fetch_traces_statistics_for_user: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
