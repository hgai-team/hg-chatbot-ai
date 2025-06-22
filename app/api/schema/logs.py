from pydantic import BaseModel
from .base import BaseResponse
from typing import List, Dict, Any

class PageInfo(BaseModel):
    page_number: int
    page_index: int
    total_items: int

class LogResult(BaseModel):
    history: List[Dict[str, Any]]
    pages: PageInfo

class LogResponse(BaseResponse):
    data: LogResult | None = None
