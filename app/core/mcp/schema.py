from enum import Enum

from pydantic import BaseModel, Field, HttpUrl
from typing import Type

class ToolName(str, Enum):
    VIDEO_ANALYZE   = 'video_analyze'
    COMMENT_ANALYZE = 'comment_analyze'

class ToolDefinition(BaseModel):
    name: str
    description: str
    args_schema: Type[BaseModel]

    def to_json_schema(self) -> dict:
        schema = self.args_schema.model_json_schema()
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": schema.get("properties", {}),
                "required": schema.get("required", [])
            }
        }

class CommentAnalyze(BaseModel):
    """
    Mô hình dữ liệu cho các tham số đầu vào của công cụ phân tích bình luận.
    """
    video_url: HttpUrl = Field(
        ...,
        description="Đường link URL đầy đủ của video YouTube cần phân tích."
    )
class VideoAnalyze(BaseModel):
    """
    Mô hình dữ liệu cho các tham số đầu vào của công cụ phân tích video.
    """
    video_url: HttpUrl = Field(
        ...,
        description="Đường link URL đầy đủ của video YouTube cần phân tích."
    )
