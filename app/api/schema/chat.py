from typing import Optional

from pydantic import BaseModel, Field
from .base import BaseResponse

from core.mcp.schema import ToolName
class UserContext(BaseModel):
    role: str
    departments: list[str] = []
    teams: list[str] = []
    projects: list[str] = []
    networks: list[str] = []
class ChatRequest(BaseModel):
    query_text: str = Field(...)
    session_id: str = Field(...)
    user_id:    str = Field(...)

    start_time: Optional[str] = Field(
        None,
        description="Thời điểm bắt đầu (ví dụ '30s', '300s'). Mặc định từ đầu."
    )
    end_time: Optional[str] = Field(
        None,
        description="Thời điểm kết thúc (ví dụ '600s'). Mặc định tới cuối."
    )
    fps: Optional[int] = Field(
        1,
        description="Số khung hình trên giây. Mặc định 1."
    )
    selected_tool: Optional[ToolName] = Field(
        None,
        description="Tên tool để xử lý (ví dụ 'video_analyze')."
    )

class ChatResult(BaseModel):
    response: str
    time_taken: float

class ChatResponse(BaseResponse):
    data: ChatResult | None = None
