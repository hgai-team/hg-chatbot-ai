from pydantic import BaseModel
from typing import Dict, Any
from enum import Enum
class UserContext(BaseModel):
    role: str
    departments: list[str] = []
    teams: list[str] = []
    projects: list[str] = []
    networks: list[str] = []

class BotNames(str, Enum):
    VAHACHA = "VaHaCha"

class ChatRequest(BaseModel):
    query_text: str

    bot_name: BotNames

    session_id: str
    user_id: str
    user_context: UserContext

class ChatResponse(BaseModel):
    results: str
    status: int
    time_taken: float
