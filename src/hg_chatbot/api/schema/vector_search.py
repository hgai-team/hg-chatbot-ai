from typing import List
from pydantic import BaseModel

class SearchRequest(BaseModel):
    query_text: str
    top_k: int = 20

class SearchResponse(BaseModel):
    results: List[dict]
    status: int
