from pydantic import BaseModel
from .base import BaseResponse
from typing import Union, Dict, Any

class AgentRequest(BaseModel):
    query_text: str
    agent_name: str
    response_text: str | None = None

class AgentResult(BaseModel):
    response: Union[str, Dict[str, Any], list[Any]]

class AgentResponse(BaseResponse):
    data: AgentResult | None = None
