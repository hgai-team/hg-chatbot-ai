from typing import Optional, Any, List, Dict

from uuid import uuid4, UUID
from datetime import datetime

from sqlmodel import (
    func,
    select, update, delete, asc, desc
)

from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import JSONB

from core.storages.client import PostgresEngineManager as PEM
from core.storages.tracestores import TraceSpan


async def get_all_traces(
    limit: int,
    page_index: int,
    sort_field: str,
    sort_order: int,
    filters: Optional[List[Dict[str, Any]]] = None
):
    """
    Advanced version with support for multiple filter operators

    Args:
        filters: List of filter dictionaries with format:
                [{"field": "status", "operator": "eq", "value": "OK"},
                 {"field": "name", "operator": "like", "value": "%test%"}]

    Supported operators: eq, ne, like, in, gt, gte, lt, lte
    """
    async with PEM.get_session() as session:
        query = select(TraceSpan)

        # Apply advanced filters
        if filters:
            for filter_config in filters:
                field = filter_config.get("field")
                operator = filter_config.get("operator", "eq")
                value = filter_config.get("value")

                if not hasattr(TraceSpan, field):
                    continue

                field_attr = getattr(TraceSpan, field)

                if operator == "eq":
                    query = query.where(field_attr == value)
                elif operator == "ne":
                    query = query.where(field_attr != value)
                elif operator == "like":
                    query = query.where(field_attr.like(value))
                elif operator == "in":
                    query = query.where(field_attr.in_(value))
                elif operator == "gt":
                    query = query.where(field_attr > value)
                elif operator == "gte":
                    query = query.where(field_attr >= value)
                elif operator == "lt":
                    query = query.where(field_attr < value)
                elif operator == "lte":
                    query = query.where(field_attr <= value)
                elif operator == "contains" and field == "metadata_":
                    query = query.where(
                        cast(field_attr, JSONB).op('@>')(cast(value, JSONB))
                    )

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_count_result = await session.exec(count_query)
        total_count = total_count_result.one()

        if total_count == 0:
            return {
                "items": [],
                "total_items": 0,
                "total_pages": 0,
                "page_index": page_index,
            }

        total_pages = (total_count + limit - 1) // limit if total_count > 0 else 0

        if page_index > total_pages and total_pages >= 0:
            raise ValueError(f"page_index ({page_index}) cannot be greater than to total pages ({total_pages})")

        # Apply sorting
        if sort_field:
            if hasattr(TraceSpan, sort_field) and sort_field not in ['metadata_']:
                field_attr = getattr(TraceSpan, sort_field)
                if sort_order == 1:
                    query = query.order_by(asc(field_attr))
                elif sort_order == -1:
                    query = query.order_by(desc(field_attr))

        # Apply pagination
        offset = (page_index - 1) * limit
        query = query.offset(offset).limit(limit)

        result = await session.exec(query)
        traces = result.all()

        return {
            "items": traces,
            "total_items": total_count,
            "total_pages": total_pages,
            "page_index": page_index
        }

async def get_all_traces_by_date_range(
    start_date: datetime,
    end_date: datetime,
    limit: int,
    page_index: int,
    sort_field: str,
    sort_order: int,
    filters: Optional[List[Dict[str, Any]]] = None
):
    """Get model usage statistics within a date range"""
    filter_ = [
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
        filters.extend(filter_)
    else:
        filters = filter_

    return await get_all_traces(
        limit=limit,
        page_index=page_index,
        sort_field=sort_field,
        sort_order=sort_order,
        filters=filters
    )

async def get_model_usage_statistics(
    filters: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Calculate usage statistics for each model including:
    - Number of calls
    - Total input tokens
    - Total output tokens
    - Total cache tokens
    - Daily token usage breakdown
    - Daily request count
    - Daily cost calculation
    - Per-user request count

    Returns a dictionary with model names as keys and usage stats as values.
    """
    async with PEM.get_session() as session:
        # Base query to get all traces
        query = select(TraceSpan)

        # Apply filters if provided
        if filters:
            for filter_config in filters:
                field = filter_config.get("field")
                operator = filter_config.get("operator", "eq")
                value = filter_config.get("value")

                if not hasattr(TraceSpan, field):
                    continue

                field_attr = getattr(TraceSpan, field)

                if operator == "eq":
                    query = query.where(field_attr == value)
                elif operator == "ne":
                    query = query.where(field_attr != value)
                elif operator == "like":
                    query = query.where(field_attr.like(value))
                elif operator == "in":
                    query = query.where(field_attr.in_(value))
                elif operator == "gt":
                    query = query.where(field_attr > value)
                elif operator == "gte":
                    query = query.where(field_attr >= value)
                elif operator == "lt":
                    query = query.where(field_attr < value)
                elif operator == "lte":
                    query = query.where(field_attr <= value)
                elif operator == "contains" and field == "metadata_":
                    query = query.where(
                        cast(field_attr, JSONB).op('@>')(cast(value, JSONB))
                    )

        result = await session.exec(query)
        traces = result.all()

        # Initialize statistics dictionary
        model_stats = {}
        daily_stats = {}  # date -> {input_tokens, output_tokens, cache_tokens, request_count}
        daily_model_costs = {}  # date -> {model -> {input_cost, output_cost, cache_cost}}
        user_request_counts = {}  # user_id -> request_count

        # Define pricing per model (cost per 1M tokens)
        model_pricing = {
            # # OpenAI models
            # "gpt-4": {"input": 30.0, "output": 60.0, "cache": 15.0},
            # "gpt-4-turbo": {"input": 10.0, "output": 30.0, "cache": 5.0},
            # "gpt-3.5-turbo": {"input": 0.5, "output": 1.5, "cache": 0.25},
            # # Anthropic models
            # "claude-3-opus": {"input": 15.0, "output": 75.0, "cache": 7.5},
            # "claude-3-sonnet": {"input": 3.0, "output": 15.0, "cache": 1.5},
            # "claude-3-haiku": {"input": 0.25, "output": 1.25, "cache": 0.125},

            # Google models
            "models/gemini-2.5-flash-preview-05-20": {"input": 0.30, "output": 2.50, "cache": 0.075},
            "models/gemini-2.5-flash-lite-preview-06-17": {"input": 0.10, "output": 0.40, "cache": 0.025},
            "gemini-2.0-flash": {"input": 0.10, "output": 0.40, "cache": 0.025},

            # xAI models
            "grok-3-mini": {"input": 0.30, "output": 0.50, "cache": 0.075},

            # Default pricing for unknown models
            "default": {"input": 5.0, "output": 15.0, "cache": 2.5}
        }

        for trace in traces:
            # Skip if no metadata
            if not trace.metadata_:
                continue

            # Extract model name and user_id
            model_name = trace.metadata_.get("model_name")
            user_id = trace.metadata_.get("user_id")

            if not model_name:
                continue

            # Get date from start_time
            date_key = trace.start_time.date().isoformat()

            # Initialize daily stats if not exists
            if date_key not in daily_stats:
                daily_stats[date_key] = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cache_tokens": 0,
                    "request_count": 0
                }

            if date_key not in daily_model_costs:
                daily_model_costs[date_key] = {}

            # Initialize model stats if not exists
            if model_name not in model_stats:
                model_stats[model_name] = {
                    "model_name": model_name,
                    "call_count": 0,
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "total_cache_tokens": 0,
                    "total_tokens": 0,
                    "provider": _extract_provider(model_name)
                }

            # Initialize model cost tracking for this date
            if model_name not in daily_model_costs[date_key]:
                daily_model_costs[date_key][model_name] = {
                    "input_cost": 0.0,
                    "output_cost": 0.0,
                    "cache_cost": 0.0,
                    "total_cost": 0.0
                }

            # Increment call count
            model_stats[model_name]["call_count"] += 1
            daily_stats[date_key]["request_count"] += 1

            # Track user request count
            if user_id:
                user_request_counts[user_id] = user_request_counts.get(user_id, 0) + 1

            # Extract token usage from different response formats
            output = trace.metadata_.get("output", {})

            input_tokens = 0
            output_tokens = 0
            cache_tokens = 0

            # Handle OpenAI format (grok)
            if "usage" in output:
                usage = output["usage"]

                # Input tokens
                input_tokens = usage.get("prompt_tokens", 0) or 0
                model_stats[model_name]["total_input_tokens"] += input_tokens

                # Output tokens
                output_tokens = usage.get("completion_tokens", 0) or 0
                model_stats[model_name]["total_output_tokens"] += output_tokens

                # Cache tokens (from prompt_tokens_details)
                prompt_details = usage.get("prompt_tokens_details", {}) or {}
                cache_tokens = prompt_details.get("cached_tokens", 0) or 0
                model_stats[model_name]["total_cache_tokens"] += cache_tokens

                # Total tokens
                total_tokens = usage.get("total_tokens", 0) or 0
                model_stats[model_name]["total_tokens"] += total_tokens

            # Handle Gemini format
            elif "raw" in output and "usage_metadata" in output["raw"]:
                usage_metadata = output["raw"]["usage_metadata"] or {}

                # Input tokens
                input_tokens = usage_metadata.get("prompt_token_count", 0) or 0
                model_stats[model_name]["total_input_tokens"] += input_tokens

                # Output tokens
                output_tokens = usage_metadata.get("candidates_token_count", 0) or 0
                model_stats[model_name]["total_output_tokens"] += output_tokens

                # Cache tokens
                cache_tokens = usage_metadata.get("cached_content_token_count", 0) or 0
                model_stats[model_name]["total_cache_tokens"] += cache_tokens

                # Total tokens
                total_tokens = usage_metadata.get("total_token_count", 0) or 0
                model_stats[model_name]["total_tokens"] += total_tokens

            # Update daily token stats
            daily_stats[date_key]["input_tokens"] += input_tokens
            daily_stats[date_key]["output_tokens"] += output_tokens
            daily_stats[date_key]["cache_tokens"] += cache_tokens

            # Calculate costs
            pricing = next((v for k, v in model_pricing.items() if k in model_name.lower()), model_pricing["default"])

            input_cost = (input_tokens / 1_000_000) * pricing["input"]
            output_cost = (output_tokens / 1_000_000) * pricing["output"]
            cache_cost = (cache_tokens / 1_000_000) * pricing["cache"]

            daily_model_costs[date_key][model_name]["input_cost"] += input_cost
            daily_model_costs[date_key][model_name]["output_cost"] += output_cost
            daily_model_costs[date_key][model_name]["cache_cost"] += cache_cost
            daily_model_costs[date_key][model_name]["total_cost"] += input_cost + output_cost + cache_cost

        # Convert to list and sort by call count
        stats_list = list(model_stats.values())
        stats_list.sort(key=lambda x: x["call_count"], reverse=True)

        # Format daily stats
        daily_token_usage = []
        for date, stats in sorted(daily_stats.items()):
            daily_token_usage.append({
                "date": date,
                "input_tokens": stats["input_tokens"],
                "output_tokens": stats["output_tokens"],
                "cache_tokens": stats["cache_tokens"],
                "total_tokens": stats["input_tokens"] + stats["output_tokens"] + stats["cache_tokens"]
            })

        # Format daily request counts
        daily_request_counts = []
        for date, stats in sorted(daily_stats.items()):
            daily_request_counts.append({
                "date": date,
                "request_count": stats["request_count"]
            })

        # Format daily costs
        daily_costs = []
        for date, models in sorted(daily_model_costs.items()):
            total_daily_cost = sum(m["total_cost"] for m in models.values())
            model_breakdown = [
                {
                    "model": model,
                    "input_cost": round(costs["input_cost"], 4),
                    "output_cost": round(costs["output_cost"], 4),
                    "cache_cost": round(costs["cache_cost"], 4),
                    "total_cost": round(costs["total_cost"], 4)
                }
                for model, costs in models.items()
            ]
            daily_costs.append({
                "date": date,
                "total_cost": round(total_daily_cost, 4),
                "model_breakdown": model_breakdown
            })

        # Format user request counts
        user_stats = [
            {"user_id": user_id, "request_count": count}
            for user_id, count in sorted(user_request_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        return {
            "models": stats_list,
            "summary": {
                "total_models": len(stats_list),
                "total_calls": sum(m["call_count"] for m in stats_list),
                "total_input_tokens": sum(m["total_input_tokens"] for m in stats_list),
                "total_output_tokens": sum(m["total_output_tokens"] for m in stats_list),
                "total_cache_tokens": sum(m["total_cache_tokens"] for m in stats_list),
                "total_tokens": sum(m["total_tokens"] for m in stats_list)
            },
            "daily_token_usage": daily_token_usage,
            "daily_request_counts": daily_request_counts,
            "daily_costs": daily_costs,
            "user_request_counts": user_stats
        }


def _extract_provider(model_name: str) -> str:
    """Extract provider from model name"""
    if "grok" in model_name.lower():
        return "xAI"
    elif "gemini" in model_name.lower() or "models/" in model_name:
        return "Google"
    elif "gpt" in model_name.lower():
        return "OpenAI"
    elif "claude" in model_name.lower():
        return "Anthropic"
    else:
        return "Unknown"

# Get usage by date range
async def get_model_usage_statistics_by_date_range(
    start_date: datetime,
    end_date: datetime,
    filters: Optional[List[Dict[str, Any]]] = None
):
    """Get model usage statistics within a date range"""
    filter_ = [
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
        filters.extend(filter_)
    else:
        filters = filter_

    return await get_model_usage_statistics(filters)

# Example usage with filters
async def get_model_usage_for_user(
    user_id: UUID,
    filters: Optional[List[Dict[str, Any]]] = None
):
    """Get model usage statistics for a specific user"""
    _filter = [
        {
            "field": "metadata_",
            "operator": "contains",
            "value": {"user_id": str(user_id)}
        }
    ]
    if isinstance(filters, list):
        filters.extend(_filter)
    else:
        filters = _filter

    return await get_model_usage_statistics(filters)

async def get_model_usage_for_user_by_date_range(
    start_date: datetime,
    end_date: datetime,
    user_id: UUID,
    filters: Optional[List[Dict[str, Any]]] = None
):
    """Get model usage statistics for a specific user"""
    _filter = [
        {
            "field": "metadata_",
            "operator": "contains",
            "value": {"user_id": str(user_id)}
        },
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
    if isinstance(filters, list):
        filters.extend(_filter)
    else:
        filters = _filter

    return await get_model_usage_statistics(filters)

