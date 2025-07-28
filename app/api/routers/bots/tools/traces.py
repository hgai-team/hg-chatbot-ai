from typing import Optional, Any, List, Dict

from uuid import uuid4
from sqlmodel import (
    func,
    select, update, delete, asc, desc
)

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
        
        total_pages = (total_count + limit - 1) // limit if total_count > 0 else 0
        
        if page_index >= total_pages and total_pages > 0:
            raise ValueError(f"page_index ({page_index}) cannot be greater than or equal to total pages ({total_pages})")
        
        # Apply sorting
        if hasattr(TraceSpan, sort_field) and sort_field not in ['metadata_', 'id']:
            field_attr = getattr(TraceSpan, sort_field)
            if sort_order == 1:
                query = query.order_by(asc(field_attr))
            elif sort_order == -1:
                query = query.order_by(desc(field_attr))
        
        # Apply pagination
        offset = page_index * limit
        query = query.offset(offset).limit(limit)
        
        result = await session.exec(query)
        traces = result.all()
        
        return {
            "items": traces,
            "total_items": total_count,
            "total_pages": total_pages,
            "page_index": page_index
        }

