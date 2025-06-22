from pydantic import BaseModel
from .base import BaseResponse
from typing import List, Dict, Any, Optional


class SessionResult(BaseModel):
    user_id: Optional[str] = None
    history: Optional[List[Dict[str, Any]]] = []
    title: Optional[str] = None

class SessionResponse(BaseResponse):
    data: SessionResult | None = None

class SessionRatingResult(BaseModel):
    rating_type: str
    rating_text: str

class SessionRatingResponse(BaseResponse):
    data: SessionRatingResult | None = None
