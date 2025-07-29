from typing import Optional, Any, List, Dict

from uuid import uuid4, UUID
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
                
                if not hasattr(TraceSpan, field) or field in ['metadata_', 'id']:
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
            if hasattr(TraceSpan, sort_field) and sort_field not in ['metadata_', 'id']:
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
        
async def get_model_usage_statistics(
    filters: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Calculate usage statistics for each model including:
    - Number of calls
    - Total input tokens
    - Total output tokens  
    - Total cache tokens
    
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
        
        for trace in traces:
            # Skip if no metadata
            if not trace.metadata_:
                continue
                
            # Extract model name
            model_name = trace.metadata_.get("model_name")
            if not model_name:
                continue
            
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
            
            # Increment call count
            model_stats[model_name]["call_count"] += 1
            
            # Extract token usage from different response formats
            output = trace.metadata_.get("output", {})
            
            # Handle OpenAI format (grok)
            if "usage" in output:
                usage = output["usage"]
                
                # Input tokens
                prompt_tokens = usage.get("prompt_tokens", 0) or 0
                model_stats[model_name]["total_input_tokens"] += prompt_tokens
                
                # Output tokens
                completion_tokens = usage.get("completion_tokens", 0) or 0
                model_stats[model_name]["total_output_tokens"] += completion_tokens
                
                # Cache tokens (from prompt_tokens_details)
                prompt_details = usage.get("prompt_tokens_details", {}) or {}
                cached_tokens = prompt_details.get("cached_tokens", 0) or 0
                model_stats[model_name]["total_cache_tokens"] += cached_tokens
                
                # Total tokens
                total_tokens = usage.get("total_tokens", 0) or 0
                model_stats[model_name]["total_tokens"] += total_tokens
            
            # Handle Gemini format
            elif "raw" in output and "usage_metadata" in output["raw"]:
                usage_metadata = output["raw"]["usage_metadata"] or {}
                
                # Input tokens
                prompt_token_count = usage_metadata.get("prompt_token_count", 0) or 0
                model_stats[model_name]["total_input_tokens"] += prompt_token_count
                
                # Output tokens
                candidates_token_count = usage_metadata.get("candidates_token_count", 0) or 0
                model_stats[model_name]["total_output_tokens"] += candidates_token_count
                
                # Cache tokens
                cached_content_token_count = usage_metadata.get("cached_content_token_count", 0) or 0
                model_stats[model_name]["total_cache_tokens"] += cached_content_token_count
                
                # Total tokens
                total_token_count = usage_metadata.get("total_token_count", 0) or 0
                model_stats[model_name]["total_tokens"] += total_token_count
        
        # Convert to list and sort by call count
        stats_list = list(model_stats.values())
        stats_list.sort(key=lambda x: x["call_count"], reverse=True)
        
        return {
            "models": stats_list,
            "summary": {
                "total_models": len(stats_list),
                "total_calls": sum(m["call_count"] for m in stats_list),
                "total_input_tokens": sum(m["total_input_tokens"] for m in stats_list),
                "total_output_tokens": sum(m["total_output_tokens"] for m in stats_list),
                "total_cache_tokens": sum(m["total_cache_tokens"] for m in stats_list),
                "total_tokens": sum(m["total_tokens"] for m in stats_list)
            }
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


# Get usage by date range
# async def get_model_usage_by_date_range(start_date: datetime, end_date: datetime):
#     """Get model usage statistics within a date range"""
#     filters = [
#         {
#             "field": "start_time",
#             "operator": "gte",
#             "value": start_date
#         },
#         {
#             "field": "start_time",
#             "operator": "lte",
#             "value": end_date
#         }
#     ]
#     return await get_model_usage_statistics(filters)

