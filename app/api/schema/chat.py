from pydantic import BaseModel
from .base import BaseResponse

class UserContext(BaseModel):
    role: str
    departments: list[str] = []
    teams: list[str] = []
    projects: list[str] = []
    networks: list[str] = []

class ChatRequest(BaseModel):
    query_text: str
    session_id: str
    user_id: str

class ChatResult(BaseModel):
    response: str
    time_taken: float

class ChatResponse(BaseResponse):
    data: ChatResult | None = None
